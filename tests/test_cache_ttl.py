"""history_cache TTL 판정 순수함수 단위테스트 (handoff §6, design §5②).

과거 일자=불변(항상 fresh), 오늘(KST)=5분 TTL.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from maple_mate.history.cache import KST, is_cache_fresh

# KST 기준 고정 '현재': 2026-06-04 14:30
NOW = datetime(2026, 6, 4, 14, 30, tzinfo=KST)
TODAY = NOW.date()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def test_past_date_always_fresh():
    fetched_long_ago = NOW - timedelta(days=30)
    assert is_cache_fresh(YESTERDAY, fetched_long_ago, NOW) is True


def test_today_within_ttl_is_fresh():
    fetched = NOW - timedelta(minutes=1)
    assert is_cache_fresh(TODAY, fetched, NOW) is True


def test_today_past_ttl_is_stale():
    fetched = NOW - timedelta(minutes=10)
    assert is_cache_fresh(TODAY, fetched, NOW) is False


def test_today_exactly_at_ttl_boundary_is_stale():
    fetched = NOW - timedelta(minutes=5)
    assert is_cache_fresh(TODAY, fetched, NOW) is False


def test_future_date_not_fresh():
    assert is_cache_fresh(TOMORROW, NOW, NOW) is False


def test_today_judgment_uses_kst_not_utc():
    # UTC 로는 아직 6/3 23:30 이지만 KST 로는 6/4 08:30 → '오늘'은 6/4.
    from datetime import timezone

    now_utc = datetime(2026, 6, 3, 23, 30, tzinfo=timezone.utc)  # = 6/4 08:30 KST
    fetched = now_utc - timedelta(minutes=1)
    assert is_cache_fresh(datetime(2026, 6, 4).date(), fetched, now_utc) is True
