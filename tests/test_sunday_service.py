"""썬데이 service 순수/선별 로직 단위테스트 (넥슨 mock, DB 불요 — 작업지시서 Q8·#7).

DB 함수(dedup 마커·채널 토글)는 pg_insert 통합 영역이라 제외(기존 registration 테스트와 동일 방침).
여기서는 매칭·주차·기간 포맷·이벤트 선별만 검증한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from maple_mate.nexon.client import KST
from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from maple_mate.notification.service import (
    current_week_id,
    extract_content_image,
    format_period,
    match_sunday,
    select_sunday_events,
)

# ── match_sunday: 공백 무시 부분일치(미실측 양성 매칭 완화의 핵심) ──────────────


def test_match_sunday_accepts_spaced_and_unspaced():
    assert match_sunday("썬데이 메이플 이벤트") is True
    assert match_sunday("썬데이메이플") is True
    assert match_sunday("썬 데이 메이플") is True  # 공백 변형 흡수
    assert match_sunday("[썬데이 메이플] 특별 보상") is True  # 부분일치


def test_match_sunday_rejects_other_titles_and_empty():
    assert match_sunday("메이플 용사 진") is False
    assert match_sunday("리버스 차원의 탑") is False
    assert match_sunday("") is False
    assert match_sunday(None) is False


# ── current_week_id: ISO 연-주차, KST, 연말경계 ──────────────────────────────


def test_current_week_id_year_boundary_uses_iso_year():
    # 2021-01-01(금)은 ISO 기준 2020년 53주차.
    assert current_week_id(datetime(2021, 1, 1)) == "2020-W53"
    # naive(KST 간주)와 tz-aware(KST) 결과 동일.
    assert current_week_id(datetime(2021, 1, 1, tzinfo=KST)) == "2020-W53"


def test_current_week_id_converts_utc_to_kst_before_week():
    # 2021-01-03 16:00 UTC = KST 2021-01-04 01:00(월) → ISO 2021년 1주차.
    utc_sunday_night = datetime(2021, 1, 3, 16, 0, tzinfo=timezone.utc)
    assert current_week_id(utc_sunday_night) == "2021-W01"


def test_current_week_id_zero_pads_week():
    assert current_week_id(datetime(2026, 1, 5)) == "2026-W02"  # 2026-01-05(월) = 2주차


# ── format_period: +09:00/Z, 초·밀리초 혼재, None 가드 ──────────────────────


def test_format_period_real_api_offset_form():
    # C3 실샘플 형식(초 없음, +09:00).
    assert (
        format_period("2026-05-14T10:00+09:00", "2026-07-01T23:59+09:00")
        == "2026-05-14 10:00 ~ 2026-07-01 23:59"
    )


def test_format_period_z_millisecond_form_converted_to_kst():
    # 문서 예시 형식(밀리초 + Z). UTC → KST(+9h) 변환 확인.
    assert (
        format_period("2024-01-14T00:00:00.000Z", "2024-01-21T23:59:59.000Z")
        == "2024-01-14 09:00 ~ 2024-01-22 08:59"
    )


def test_format_period_none_and_unparseable_guards():
    assert format_period(None, None) == "기간 미정"
    assert format_period("garbage", "garbage") == "기간 미정"
    assert format_period(None, "2026-05-14T10:00+09:00") == "~ 2026-05-14 10:00"
    assert format_period("2026-05-14T10:00+09:00", None) == "2026-05-14 10:00 ~"


# ── extract_content_image: 상세 본문 HTML → 첫 절대 이미지 URL ───────────────

_REAL_CONTENTS = """<body>
<div class="gen_container" style="max-width: 876px;">
  <img src="https://lwi.nexon.com/maplestory/2026/0514_board/260607_SUNDAY_ABC.png" style="width: 100%;">
  <a href="https://maplestory.nexon.com/Guide/x" target="_blank"></a>
</div>
</body>"""


def test_extract_content_image_from_real_html():
    assert (
        extract_content_image(_REAL_CONTENTS)
        == "https://lwi.nexon.com/maplestory/2026/0514_board/260607_SUNDAY_ABC.png"
    )


def test_extract_content_image_returns_first_absolute_skipping_relative():
    html = '<img src="/relative/banner.png"><img src="https://cdn/x/big.png">'
    assert extract_content_image(html) == "https://cdn/x/big.png"


def test_extract_content_image_none_when_no_image():
    assert extract_content_image("<p>본문 텍스트만</p>") is None
    assert extract_content_image(None) is None
    assert extract_content_image("") is None


def test_extract_content_image_handles_single_quotes():
    assert (
        extract_content_image("<img src='https://cdn/x/a.jpg'>")
        == "https://cdn/x/a.jpg"
    )


# ── select_sunday_events: 페치 + 필터 + 구성 ────────────────────────────────


class _FakeNexon:
    def __init__(
        self,
        events: list[dict],
        details: dict[int, dict] | None = None,
        detail_error: Exception | None = None,
    ):
        self._events = events
        self._details = details or {}
        self._detail_error = detail_error

    async def notice_event(self) -> list[dict]:
        return self._events

    async def notice_event_detail(self, notice_id: int) -> dict:
        if self._detail_error is not None:
            raise self._detail_error
        return self._details.get(notice_id, {})


async def test_select_filters_to_sunday_and_builds_event():
    nexon = _FakeNexon(
        [
            {
                "title": "썬데이 메이플 이벤트",
                "url": "https://x/1",
                "thumbnail_url": "https://x/thumb.jpg",
                "date_event_start": "2026-05-14T10:00+09:00",
                "date_event_end": "2026-05-17T23:59+09:00",
            },
            {"title": "메이플 용사 진", "url": "https://x/2"},  # 비매칭 제외
        ]
    )
    events = await select_sunday_events(nexon)
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "썬데이 메이플 이벤트"
    assert ev.url == "https://x/1"
    assert ev.thumbnail_url == "https://x/thumb.jpg"
    assert ev.period_text == "2026-05-14 10:00 ~ 2026-05-17 23:59"


async def test_select_passes_through_missing_thumbnail_and_multi_match():
    nexon = _FakeNexon(
        [
            {"title": "썬데이 메이플 1", "url": "https://x/1"},  # thumbnail 없음
            {
                "title": "[썬데이 메이플] 2",
                "url": "https://x/2",
                "thumbnail_url": "https://x/t.jpg",
            },
        ]
    )
    events = await select_sunday_events(nexon)
    assert len(events) == 2
    assert events[0].thumbnail_url is None
    assert events[0].period_text == "기간 미정"  # 기간 키 없음 → 우아한 폴백
    assert events[1].thumbnail_url == "https://x/t.jpg"


async def test_select_returns_empty_when_no_match():
    nexon = _FakeNexon([{"title": "리버스 차원의 탑"}, {"title": "VIP 사우나"}])
    assert await select_sunday_events(nexon) == []


async def test_select_fills_detail_banner_from_contents():
    nexon = _FakeNexon(
        events=[{"title": "썬데이 메이플", "url": "https://x/1", "notice_id": 1329}],
        details={1329: {"contents": '<img src="https://lwi/banner.png">'}},
    )
    [event] = await select_sunday_events(nexon)
    assert event.detail_image_url == "https://lwi/banner.png"


async def test_select_banner_none_when_detail_fetch_fails():
    # 상세 페치 실패는 비치명 — 이벤트는 발송하되 배너만 생략(목록 페치 실패와 구분).
    nexon = _FakeNexon(
        events=[{"title": "썬데이 메이플", "url": "https://x/1", "notice_id": 1329}],
        detail_error=NexonAPIError(
            "OPENAPI00001", "boom", error_class=ErrorClass.NEXON_API
        ),
    )
    [event] = await select_sunday_events(nexon)
    assert event.detail_image_url is None
    assert event.title == "썬데이 메이플"  # 이벤트 자체는 살아 있음


async def test_select_skips_detail_call_when_no_notice_id():
    # notice_id 없으면 상세 호출 자체를 하지 않음(배너 None).
    nexon = _FakeNexon(events=[{"title": "썬데이 메이플", "url": "https://x/1"}])
    [event] = await select_sunday_events(nexon)
    assert event.detail_image_url is None
