# Backend Handoff — Video Feed Integration

This doc covers only what you need on your end. The rest of this repo
(scoring logic, feature engineering) is mine to iterate on — you shouldn't
need to open those files, just the interface below.

## What this repo gives you

A script that runs on a schedule and writes a ranked list of video IDs
per user into a table called `user_feed_cache`. That's the entire
interface between us.

## What you need to do

### 1. Run the schema

Run `schema.sql` against our shared Supabase project (SQL Editor → paste
→ run). It creates three tables:

- `videos` — **you own writes here** (from your upload endpoint)
- `interactions` — **you own writes here** (from your logging endpoint)
- `user_feed_cache` — **I own writes here**, you only ever read from it

If any column name or type doesn't fit how you're building your
endpoints, tell me before you build against it — this schema is the one
place we need to agree before either of us goes further.

### 2. Your feed endpoint

```sql
SELECT v.*
FROM user_feed_cache f
JOIN videos v ON v.id = f.video_id
WHERE f.user_id = :user_id
ORDER BY f.rank
LIMIT :limit OFFSET :cursor;
```

That's the whole query. No ML logic runs in your request path — you're
just reading a precomputed table.

### 3. Cold-start fallback (this one's on you, not me)

If a user has zero rows in `user_feed_cache` — either they're brand new,
or my scoring script hasn't run yet — your endpoint needs to fall back to:

```sql
SELECT * FROM videos ORDER BY created_at DESC LIMIT :limit;
```

Please build this fallback path first and test your endpoint against it
directly — don't wait on my pipeline being populated to start your own
testing.

### 4. Your interaction-logging endpoint — exact field contract

Whatever endpoint you build for logging likes/skips/watch-time needs to
write rows matching this exactly, since my scoring logic reads these
fields by name:

| field | type | notes |
|---|---|---|
| `user_id` | uuid | |
| `video_id` | uuid | must reference an existing `videos.id` |
| `event_type` | text | exactly one of: `view`, `like`, `share`, `skip`, `replay` — no other strings, this is checked at the DB level |
| `watch_duration_ms` | integer, nullable | required for `view`/`replay`, can be null for `like`/`share`/`skip` |
| `video_duration_ms` | integer, nullable | |

If `event_type` values don't match exactly (e.g. `"Like"` vs `"like"`,
or a typo), my scoring logic silently treats that row as unrecognized —
worth a quick sanity check on your side once the endpoint is live.

### 5. What you don't need to do

- No need to install Python, run `score_feed.py`, or understand
  `features.py` — that's my pipeline, running independently on a schedule
- No need to compute anything about "ranking" — you're a pure reader of
  `user_feed_cache`

## Once your endpoints are live

Ping me — I'll pull a sample of real rows from `videos` and `interactions`
to confirm the fields match what's above before I point my scoring
pipeline at production data instead of the seeded test data I've been
using.
