"""기간 분해 단위테스트 — 프리셋·커스텀·30일 클램프·미래 컷 (순수)."""

from __future__ import annotations

from datetime import date, timedelta

from maple_mate.history.service import MAX_PERIOD_DAYS, resolve_period

# 2026-06-07 = 일요일(weekday()=6).
TODAY = date(2026, 6, 7)


def test_today() -> None:
    assert resolve_period("오늘", None, None, TODAY) == [TODAY]


def test_yesterday() -> None:
    assert resolve_period("어제", None, None, TODAY) == [date(2026, 6, 6)]


def test_recent_7_days() -> None:
    days = resolve_period("최근7일", None, None, TODAY)
    assert len(days) == 7
    assert days[0] == date(2026, 6, 1)
    assert days[-1] == TODAY


def test_recent_30_days() -> None:
    days = resolve_period("최근30일", None, None, TODAY)
    assert len(days) == 30
    assert days[-1] == TODAY


def test_recent_90_days() -> None:
    days = resolve_period("최근90일", None, None, TODAY)
    assert len(days) == 90
    assert days[0] == TODAY - timedelta(days=89)
    assert days[-1] == TODAY


def test_recent_1_year() -> None:
    days = resolve_period("최근1년", None, None, TODAY)
    assert len(days) == 365
    assert days[0] == TODAY - timedelta(days=364)
    assert days[-1] == TODAY


def test_this_week_starts_monday() -> None:
    days = resolve_period("이번주", None, None, TODAY)
    assert days[0] == date(2026, 6, 1)  # 월요일
    assert days[-1] == TODAY


def test_this_month_starts_first() -> None:
    days = resolve_period("이번달", None, None, TODAY)
    assert days[0] == date(2026, 6, 1)
    assert days[-1] == TODAY


def test_unknown_preset_defaults_to_recent_7() -> None:
    assert len(resolve_period("이상한값", None, None, TODAY)) == 7


def test_custom_range_inclusive() -> None:
    days = resolve_period("최근7일", date(2026, 6, 3), date(2026, 6, 5), TODAY)
    assert days == [date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5)]


def test_custom_reversed_range_is_swapped() -> None:
    days = resolve_period("오늘", date(2026, 6, 5), date(2026, 6, 3), TODAY)
    assert days == [date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5)]


def test_only_start_extends_to_today() -> None:
    days = resolve_period("오늘", date(2026, 6, 5), None, TODAY)
    assert days[0] == date(2026, 6, 5)
    assert days[-1] == TODAY


def test_future_end_is_clamped_to_today() -> None:
    days = resolve_period("오늘", None, date(2026, 12, 25), TODAY)
    assert days[-1] == TODAY


def test_one_year_clamp_keeps_most_recent() -> None:
    # 1년(365일)을 초과하는 커스텀 범위는 최근 365일로 클램프.
    days = resolve_period("최근7일", date(2024, 1, 1), date(2026, 6, 7), TODAY)
    assert len(days) == MAX_PERIOD_DAYS  # 365
    assert days[-1] == TODAY
    assert days[0] == TODAY - timedelta(days=MAX_PERIOD_DAYS - 1)
