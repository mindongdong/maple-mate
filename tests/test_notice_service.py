"""공지알림 service 순수 로직 단위테스트 (넥슨/DB mock 불요 — 순수 함수만).

신규 판정은 notice_id 최대값 기준, 발송은 오래된→최신 순, baseline(last_id None)은 미발송.
DB 함수(notice_state 마커·채널 토글)는 pg_insert 통합 영역이라 제외(썬데이 테스트와 동일 방침).
"""

from __future__ import annotations

from maple_mate.notification.notice_service import (
    NoticeItem,
    _format_date,
    latest_id,
    parse_notices,
    select_new,
)

# ── _format_date: +09:00/Z, 초·밀리초 혼재, None/garbage 가드 ────────────────


def test_format_date_offset_form():
    # 실 API 형식(+09:00) — 그대로 KST 표기.
    assert _format_date("2026-01-15T10:00:00+09:00") == "2026-01-15 10:00"


def test_format_date_z_form_converted_to_kst():
    # UTC(Z) → KST(+9h) 변환.
    assert _format_date("2024-01-15T10:00:00.000Z") == "2024-01-15 19:00"


def test_format_date_none_and_garbage_fall_back():
    assert _format_date(None) == "날짜 미상"
    assert _format_date("") == "날짜 미상"
    assert _format_date("not-a-date") == "날짜 미상"


# ── parse_notices: notice_id 정렬(오름차순)·비정수 제외·필드 매핑 ────────────


def test_parse_sorts_ascending_reversing_newest_first_input():
    # 넥슨은 최신순(내림차순) → 발송용 오름차순으로 뒤집힌다.
    raw = [
        {
            "notice_id": 30,
            "title": "C",
            "url": "u3",
            "date": "2026-01-03T00:00:00+09:00",
        },
        {
            "notice_id": 10,
            "title": "A",
            "url": "u1",
            "date": "2026-01-01T00:00:00+09:00",
        },
        {
            "notice_id": 20,
            "title": "B",
            "url": "u2",
            "date": "2026-01-02T00:00:00+09:00",
        },
    ]
    items = parse_notices(raw)
    assert [i.notice_id for i in items] == [10, 20, 30]
    assert items[0] == NoticeItem(
        notice_id=10, title="A", url="u1", date_text="2026-01-01 00:00"
    )


def test_parse_skips_items_without_int_notice_id():
    raw = [
        {"notice_id": 5, "title": "ok"},
        {"notice_id": None, "title": "missing id"},
        {"title": "no id key"},
        {"notice_id": "12", "title": "string id"},  # 비정수 제외
    ]
    items = parse_notices(raw)
    assert [i.notice_id for i in items] == [5]


def test_parse_none_guards_title_and_url():
    items = parse_notices([{"notice_id": 1}])
    assert items[0].title == "" and items[0].url == ""


def test_parse_empty_input():
    assert parse_notices([]) == []


# ── select_new: last_id 초과만, 다건 전부, baseline 미발송 ───────────────────


def _items(*ids: int) -> list[NoticeItem]:
    return [NoticeItem(notice_id=i, title=f"t{i}", url="", date_text="") for i in ids]


def test_select_new_returns_items_above_last_id_in_order():
    items = _items(10, 11, 12, 13)
    assert [i.notice_id for i in select_new(items, last_id=11)] == [12, 13]


def test_select_new_baseline_sends_nothing():
    # 최초 가동: last_id None → 신규 없음(과거 공지 미발송, design §3.6).
    assert select_new(_items(10, 11, 12), last_id=None) == []


def test_select_new_none_above_when_caught_up():
    assert select_new(_items(10, 11), last_id=11) == []


def test_select_new_all_above_when_last_id_below_min():
    assert [i.notice_id for i in select_new(_items(10, 11), last_id=9)] == [10, 11]


# ── latest_id: 마킹용 최대값 ─────────────────────────────────────────────────


def test_latest_id_returns_max_after_ascending_sort():
    assert latest_id(_items(10, 20, 30)) == 30


def test_latest_id_none_for_empty():
    assert latest_id([]) is None
