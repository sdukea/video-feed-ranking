"""
OWNERSHIP: ML-owned. Backend should not need to edit this file — if the
integration requires a change here, flag it to the ML side rather than
patching it directly, so both people stay in sync on what's running.

score_feed.py — the production scoring pipeline.

Run manually for now:   python score_feed.py
Later, on a schedule:   cron / GitHub Actions / Supabase pg_cron (see README)

This is the ENTIRE ML deliverable for the MVP. It reads two tables your
backend teammate owns (videos, interactions) and writes one table they
read from (user_feed_cache). It has zero knowledge of the API, the app,
or how videos get uploaded — that separation is the whole point.
"""

import os
from collections import defaultdict
from features import compute_score

# supabase-py client — install with: pip install supabase --break-system-packages
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")  # service key, not anon key
TOP_N_PER_USER = 50  # how many videos to precompute per user


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables. "
            "Get these from your teammate / the Supabase project settings."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all_videos(client: Client) -> list[dict]:
    """Pulls the full video catalog. Fine at MVP scale (hundreds-thousands
    of videos); if this ever gets slow, that's a 'add pagination' problem,
    not a 'rewrite the pipeline' problem."""
    response = client.table("videos").select("*").execute()
    return response.data


def fetch_active_user_ids(client: Client) -> list[str]:
    """Users who've interacted at all in the last 30 days, plus anyone with
    zero interactions gets picked up by the cold-start path in the app
    itself (backend's fallback), so we don't need to compute for them here."""
    response = client.table("interactions").select("user_id").execute()
    return list({row["user_id"] for row in response.data})


def build_user_category_profile(client: Client, user_id: str) -> dict:
    """
    Looks at this user's last 50 'like' or 'replay' events (the strongest
    positive signals) and counts categories to build a taste profile.
    Returns {} for a user with no such history — features.py's
    category_match() already handles that as a cold-start case.
    """
    interactions = (
        client.table("interactions")
        .select("video_id, event_type")
        .eq("user_id", user_id)
        .in_("event_type", ["like", "replay"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    ).data

    if not interactions:
        return {}

    video_ids = [i["video_id"] for i in interactions]
    videos = (
        client.table("videos")
        .select("id, category")
        .in_("id", video_ids)
        .execute()
    ).data
    category_by_id = {v["id"]: v["category"] for v in videos}

    counts = defaultdict(int)
    for i in interactions:
        cat = category_by_id.get(i["video_id"])
        if cat:
            counts[cat] += 1
    return dict(counts)


def score_videos_for_user(videos: list[dict], user_category_counts: dict) -> list[tuple]:
    """Returns [(video_id, score), ...] sorted descending by score."""
    scored = []
    for v in videos:
        s = compute_score(v, user_category_counts)
        scored.append((v["id"], s))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def write_feed_cache(client: Client, user_id: str, ranked: list[tuple]) -> None:
    """
    Overwrites this user's cached feed. Delete-then-insert is simplest and
    fine at MVP scale — an upsert-based diff is a later optimization, not
    a day-1 concern.
    """
    client.table("user_feed_cache").delete().eq("user_id", user_id).execute()

    rows = [
        {"user_id": user_id, "video_id": vid, "rank": rank, "score": float(score)}
        for rank, (vid, score) in enumerate(ranked[:TOP_N_PER_USER], start=1)
    ]
    if rows:
        client.table("user_feed_cache").insert(rows).execute()


def run():
    client = get_client()

    print("Fetching video catalog...")
    videos = fetch_all_videos(client)
    print(f"  {len(videos)} videos found")

    print("Fetching active users...")
    user_ids = fetch_active_user_ids(client)
    print(f"  {len(user_ids)} active users found")

    for user_id in user_ids:
        profile = build_user_category_profile(client, user_id)
        ranked = score_videos_for_user(videos, profile)
        write_feed_cache(client, user_id, ranked)
        print(f"  scored feed for user {user_id[:8]}... ({len(ranked)} videos)")

    print("Done.")


if __name__ == "__main__":
    run()
