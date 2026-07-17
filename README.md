# Video Feed Scoring Pipeline — Setup & Run Guide

This is your entire ML deliverable for the MVP: a script that reads
`videos` + `interactions` and writes `user_feed_cache`. No API server,
no deployment framework — just a script your teammate's endpoint reads from.

## 0. Before you start

Get from your teammate (or create yourself if you're setting up Supabase):
- A Supabase project URL and **service role key** (Project Settings → API —
  service key, NOT the anon/public key, since this script needs write access
  bypassing row-level security)

## 1. Local environment setup

```bash
cd video_feed_ml
python3 -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt --break-system-packages
```

## 2. Create the tables

Open the Supabase dashboard → SQL Editor → paste the contents of
`schema.sql` → run it. This creates `videos`, `interactions`, and
`user_feed_cache`. Confirm this matches what your teammate expects — this
schema IS the contract, so any disagreement gets resolved here, not in code.

## 3. Set your environment variables

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-role-key"
```

(Put these in a `.env` file + use `python-dotenv` if you'd rather not
export them manually every session — optional polish, not required for MVP.)

## 4. Run the unit tests first — always

```bash
python tests/test_features.py
```

All 8 should pass. If you change any weighting or formula in `features.py`,
rerun this before trusting the pipeline against real data.

## 5. Seed dummy data and do a dry run

Before your teammate's upload/interaction endpoints exist, validate the
whole pipeline against fake data:

```bash
python seed_dummy_data.py
python score_feed.py
```

Check the Supabase dashboard → Table Editor → `user_feed_cache`. You should
see ~20 rows for the one test user, ranked by score, with the fitness
videos ranked highest (since the seed script gives that user fitness likes).

## 6. Validate against REAL data once your teammate's endpoints are live

1. Have them confirm a few real rows exist in `videos` and `interactions`
2. Check field values match what `features.py` expects:
   - `created_at` is a real timestamp, not null
   - `event_type` values are exactly `view`/`like`/`share`/`skip`/`replay`
     (typos here silently break `category_match` and `engagement_rate`)
3. Run `python score_feed.py` manually and inspect `user_feed_cache` again

## 7. Automate it — GitHub Actions (simplest path, no server needed)

Already set up in `.github/workflows/score_feed.yml`, running every 15 min.

To activate:
1. Push this repo to GitHub
2. Repo Settings → Secrets and variables → Actions → add `SUPABASE_URL`
   and `SUPABASE_SERVICE_KEY` as secrets
3. Check the "Actions" tab — you can trigger it manually
   (`workflow_dispatch`) to test before waiting for the schedule

This is the easiest "production" path for someone who hasn't deployed
anything before — GitHub runs it for you, no server to manage.

## 8. What to tune once real data flows in

- `TOP_N_PER_USER` in `score_feed.py` — how many videos to precompute
- The `weights` dict in `features.compute_score()` — try shifting
  recency vs. engagement vs. category weight and see how rankings change
- `half_life_hours` in `recency_score()` — how fast old videos fade

## 9. The v2 upgrade path (once you have 1–2 weeks of real interaction logs)

This is where the two-tower notebook comes back in. The architecture in
`C3_W2_RecSysNN_Assignment.ipynb` — a user tower + item tower producing
embeddings whose dot product predicts engagement — becomes your
`compute_score` replacement:

- Replace the explicit 0.5–5 star rating label with a weighted implicit
  engagement label (the same formula as `engagement_rate()` above, applied
  per user-video pair as a training target instead of an inference-time score)
- Item tower input: swap one-hot genre for your multimodal video embedding
- Train exactly like the notebook's custom loop (`tf.GradientTape`,
  `optimizer.apply_gradients`), just on your logged interactions table
  instead of the MovieLens CSVs
- At serving time: precompute video embeddings once, recompute user
  embeddings on the same schedule as `score_feed.py` runs now, and replace
  `compute_score()`'s heuristic with a dot product + FAISS lookup

Don't start this until `interactions` has real volume — training on sparse
logs will just overfit and produce worse rankings than the heuristic above.
