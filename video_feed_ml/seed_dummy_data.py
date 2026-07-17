"""
seed_dummy_data.py — populates your Supabase project with fake videos,
a fake user, and fake interactions, so you can run score_feed.py and see
real output BEFORE your teammate's upload/interaction endpoints exist.

Run once: python seed_dummy_data.py
Then:     python score_feed.py
Then check the user_feed_cache table in the Supabase dashboard.
"""

import os
import random
import uuid
from datetime import datetime, timezone, timedelta
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

CATEGORIES = ["comedy", "fitness", "dance", "cooking", "tech"]


def seed():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 20 fake videos across categories, uploaded at varying recency
    video_rows = []
    video_ids = []
    for i in range(20):
        vid = str(uuid.uuid4())
        video_ids.append(vid)
        hours_ago = random.randint(0, 96)
        video_rows.append({
            "id": vid,
            "uploader_id": str(uuid.uuid4()),
            "playback_url": f"https://example.com/video_{i}.m3u8",
            "category": random.choice(CATEGORIES),
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(),
            "view_count": random.randint(0, 500),
            "like_count": random.randint(0, 100),
            "share_count": random.randint(0, 20),
            "skip_count": random.randint(0, 50),
        })
    client.table("videos").insert(video_rows).execute()
    print(f"Seeded {len(video_rows)} videos")

    # one fake user with a fitness-heavy taste profile
    test_user_id = str(uuid.uuid4())
    fitness_videos = [v["id"] for v in video_rows if v["category"] == "fitness"]
    interaction_rows = []
    for vid in fitness_videos[:3]:
        interaction_rows.append({
            "user_id": test_user_id,
            "video_id": vid,
            "event_type": "like",
            "watch_duration_ms": 15000,
            "video_duration_ms": 20000,
        })
    if interaction_rows:
        client.table("interactions").insert(interaction_rows).execute()
    print(f"Seeded {len(interaction_rows)} interactions for test user {test_user_id}")
    print(f"\nTest user ID (for manual checking): {test_user_id}")


if __name__ == "__main__":
    seed()
