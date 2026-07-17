"""
OWNERSHIP: ML-owned.

Feature engineering for the v1 heuristic scorer.

Design note: these are pure functions — no database calls, no side effects.
That's what makes them testable in isolation (see tests/test_features.py)
before they ever touch a real database. This is the habit that replaces
"run the notebook cell and eyeball the output": write a function, write
an assert for it, THEN wire it into the pipeline.
"""

import math
from datetime import datetime, timezone


def recency_score(created_at: datetime, half_life_hours: float = 24.0) -> float:
    """
    Exponential decay: a video's recency score halves every `half_life_hours`.
    A video uploaded right now scores 1.0; one uploaded 24h ago (default)
    scores 0.5; one uploaded 48h ago scores 0.25, etc.

    This mirrors the same idea as the notebooks' Ymean normalization step —
    centering/scaling a raw signal before it enters a bigger formula.
    """
    now = datetime.now(timezone.utc)
    hours_elapsed = (now - created_at).total_seconds() / 3600.0
    decay_constant = math.log(2) / half_life_hours
    return math.exp(-decay_constant * hours_elapsed)


def engagement_rate(view_count: int, like_count: int, share_count: int,
                     skip_count: int) -> float:
    """
    Weighted engagement per impression. Shares count for more than likes
    (stronger intent signal), skips subtract.

    Returns a value roughly in [-1, 1+]. Guards against division by zero
    for brand-new videos with no views yet.
    """
    total_impressions = view_count + skip_count
    if total_impressions == 0:
        return 0.0  # neutral score for a video nobody has seen yet

    weighted_positive = (like_count * 2.0) + (share_count * 3.0)
    weighted_negative = skip_count * 1.0
    return (weighted_positive - weighted_negative) / total_impressions


def category_match(user_category_counts: dict, video_category: str) -> float:
    """
    user_category_counts: e.g. {'comedy': 5, 'fitness': 2} built from the
    user's recent liked/watched videos.

    Returns 0.0 for a user with no history (cold start) — this is the
    explicit branch that keeps cold-start users from getting a broken score.
    """
    if not user_category_counts or video_category is None:
        return 0.0

    total = sum(user_category_counts.values())
    if total == 0:
        return 0.0

    return user_category_counts.get(video_category, 0) / total


def compute_score(video: dict, user_category_counts: dict,
                   weights: dict = None) -> float:
    """
    video: dict with keys created_at (datetime), view_count, like_count,
           share_count, skip_count, category

    weights: override default weighting, e.g. for A/B testing different
             formulas. Defaults tuned to weight personalization moderately
             once a user has history, while recency/engagement always apply.
    """
    if weights is None:
        weights = {"recency": 0.4, "engagement": 0.4, "category": 0.2}

    r = recency_score(video["created_at"])
    e = engagement_rate(video["view_count"], video["like_count"],
                         video["share_count"], video["skip_count"])
    c = category_match(user_category_counts, video.get("category"))

    return (weights["recency"] * r) + (weights["engagement"] * e) + (weights["category"] * c)
