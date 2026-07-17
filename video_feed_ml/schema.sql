-- ============================================================
-- Video Feed Recommendation Schema
-- Owner: shared contract between ML (scoring) and Backend (serving)
-- ============================================================

-- Backend owns creating/migrating this — ML just reads it.
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id UUID NOT NULL,
    playback_url TEXT NOT NULL,           -- CDN url from Mux/Cloudinary
    category TEXT,                         -- e.g. 'comedy', 'fitness', 'dance'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    view_count INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    share_count INTEGER NOT NULL DEFAULT 0,
    skip_count INTEGER NOT NULL DEFAULT 0
);

-- Backend owns writing to this (from the interaction-logging endpoint).
-- ML reads this to build user taste profiles and update video counters.
CREATE TABLE IF NOT EXISTS interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    video_id UUID NOT NULL REFERENCES videos(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('view','like','share','skip','replay')),
    watch_duration_ms INTEGER,             -- null for like/share/skip events
    video_duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_video ON interactions(video_id);

-- ML owns writing to this. Backend ONLY reads it — this is the whole
-- interface between your ranking logic and their feed endpoint.
CREATE TABLE IF NOT EXISTS user_feed_cache (
    user_id UUID NOT NULL,
    video_id UUID NOT NULL REFERENCES videos(id),
    rank INTEGER NOT NULL,                 -- 1 = show first
    score REAL NOT NULL,                   -- raw score, useful for debugging
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, video_id)
);

CREATE INDEX IF NOT EXISTS idx_feed_cache_user_rank ON user_feed_cache(user_id, rank);

-- Backend's feed endpoint is just:
--   SELECT v.* FROM user_feed_cache f
--   JOIN videos v ON v.id = f.video_id
--   WHERE f.user_id = :user_id
--   ORDER BY f.rank
--   LIMIT :limit OFFSET :cursor;
--
-- If no rows exist for a user (cold start / your script hasn't run yet),
-- backend's fallback (THEIR code, not yours):
--   SELECT * FROM videos ORDER BY created_at DESC LIMIT :limit;
