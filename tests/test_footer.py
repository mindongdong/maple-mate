"""푸터 포맷 순수함수 단위테스트 (handoff §6, design §7).

지난 날짜 = 'YYYY-MM-DD' / 오늘(KST) = 'HH:MM 기준'.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from maple_mate.bot.embeds import DATA_SOURCE, KST, append_source, format_footer

NOW = datetime(2026, 6, 4, 14, 30, tzinfo=KST)


def test_past_date_shows_iso_date():
    assert format_footer(date(2026, 6, 1), NOW) == "2026-06-01"


def test_today_date_shows_hhmm():
    assert format_footer(date(2026, 6, 4), NOW) == "14:30 기준"


def test_today_datetime_uses_its_own_time():
    ref = datetime(2026, 6, 4, 9, 5, tzinfo=KST)
    assert format_footer(ref, NOW) == "09:05 기준"


def test_past_datetime_shows_its_date():
    ref = datetime(2026, 6, 2, 23, 0, tzinfo=KST)
    assert format_footer(ref, NOW) == "2026-06-02"


def test_datetime_converted_to_kst_before_compare():
    # UTC 06-04 02:00 = KST 06-04 11:00 → 오늘, HH:MM 은 KST 기준 11:00.
    ref = datetime(2026, 6, 4, 2, 0, tzinfo=timezone.utc)
    assert format_footer(ref, NOW) == "11:00 기준"


# ── 출처표시(넥슨 약관 제6조④) ────────────────────────────────────────


def test_append_source_with_existing_footer():
    assert append_source("2026-06-08") == f"2026-06-08 · {DATA_SOURCE}"


def test_append_source_without_footer():
    assert append_source(None) == DATA_SOURCE
    assert append_source("") == DATA_SOURCE
