"""
Run with: python tests/test_features.py
No pytest required — plain asserts, so there's zero setup friction.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone, timedelta
from features import recency_score, engagement_rate, category_match, compute_score


def test_recency_score_fresh_video_scores_near_one():
    now = datetime.now(timezone.utc)
    score = recency_score(now, half_life_hours=24)
    assert 0.99 <= score <= 1.0, f"expected ~1.0, got {score}"


def test_recency_score_halves_at_half_life():
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    score = recency_score(yesterday, half_life_hours=24)
    assert 0.49 <= score <= 0.51, f"expected ~0.5, got {score}"


def test_engagement_rate_no_views_is_neutral():
    score = engagement_rate(view_count=0, like_count=0, share_count=0, skip_count=0)
    assert score == 0.0


def test_engagement_rate_all_likes_is_positive():
    score = engagement_rate(view_count=100, like_count=50, share_count=0, skip_count=0)
    assert score > 0, f"expected positive score, got {score}"


def test_engagement_rate_all_skips_is_negative():
    score = engagement_rate(view_count=0, like_count=0, share_count=0, skip_count=100)
    assert score < 0, f"expected negative score, got {score}"


def test_category_match_cold_start_returns_zero():
    score = category_match(user_category_counts={}, video_category="comedy")
    assert score == 0.0


def test_category_match_returns_fraction():
    counts = {"comedy": 3, "fitness": 1}
    score = category_match(counts, "comedy")
    assert score == 0.75, f"expected 0.75, got {score}"


def test_compute_score_cold_start_user_still_gets_a_score():
    video = {
        "created_at": datetime.now(timezone.utc),
        "view_count": 10, "like_count": 2, "share_count": 0, "skip_count": 1,
        "category": "comedy"
    }
    score = compute_score(video, user_category_counts={})
    assert isinstance(score, float)
    # cold start user should still get a sensible score driven by recency+engagement
    assert score > 0


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
