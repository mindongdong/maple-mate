"""run_notice_job 오케스트레이션 단위테스트 — 카테고리별 폴링·baseline·발송→마킹·에러격리.

모든 I/O(DB·넥슨·디스코드)를 페이크로 막고 제어흐름만 검증한다(test_sunday_job 과 동일 방침).
순수 로직(parse_notices·select_new·latest_id)은 그대로 통과시켜 실제 신규 판정을 함께 검증한다.
"""

from __future__ import annotations

import pytest

from maple_mate.bot.embeds import DATA_SOURCE
from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from maple_mate.notification import scheduler
from maple_mate.notification.notice_service import NoticeItem


def _raw(*ids: int) -> list[dict]:
    """notice_id 만 채운 최소 raw 공지(파싱은 실제 parse_notices 가 처리)."""
    return [
        {"notice_id": i, "title": f"t{i}", "url": f"u{i}", "date": None} for i in ids
    ]


class _Nexon:
    def __init__(self, calls, notice_raw, update_raw, notice_err=None, update_err=None):
        self._calls = calls
        self._notice_raw = notice_raw
        self._update_raw = update_raw
        self._notice_err = notice_err
        self._update_err = update_err

    async def notice(self):
        self._calls.append("fetch:notice")
        if self._notice_err is not None:
            raise self._notice_err
        return self._notice_raw

    async def notice_update(self):
        self._calls.append("fetch:update")
        if self._update_err is not None:
            raise self._update_err
        return self._update_raw


def _deps(nexon):
    return type("Deps", (), {"session_factory": object(), "nexon": nexon})()


@pytest.fixture
def patched(monkeypatch):
    """notice_service DB 함수·broadcast·error_log 를 페이크로 교체하고 호출을 기록한다."""
    calls: list = []
    state = {"channels": [(1, 100)], "last_ids": {}}

    async def enabled_notice_channels(sf):
        calls.append("channels")
        return state["channels"]

    async def get_last_notice_id(sf, category):
        return state["last_ids"].get(category)

    async def set_last_notice_id(sf, category, notice_id):
        calls.append(("mark", category, notice_id))

    async def broadcast_notices(bot, channels, items):
        calls.append(("broadcast", tuple(i.notice_id for i in items)))
        return len(channels)

    async def record(sf, **kwargs):
        calls.append(("error_log", kwargs.get("error_type")))

    monkeypatch.setattr(
        scheduler.notice_service, "enabled_notice_channels", enabled_notice_channels
    )
    monkeypatch.setattr(
        scheduler.notice_service, "get_last_notice_id", get_last_notice_id
    )
    monkeypatch.setattr(
        scheduler.notice_service, "set_last_notice_id", set_last_notice_id
    )
    monkeypatch.setattr(scheduler, "broadcast_notices", broadcast_notices)
    monkeypatch.setattr(scheduler.error_log, "record", record)
    return calls, state


async def test_new_items_broadcast_then_mark_per_category(patched):
    calls, state = patched
    state["last_ids"] = {"notice": 100, "notice-update": 200}
    nexon = _Nexon(calls, notice_raw=_raw(102, 101, 99), update_raw=_raw(201, 200))
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == [
        "channels",
        "fetch:notice",
        ("broadcast", (101, 102)),  # 100 초과만, 오름차순
        ("mark", "notice", 102),
        "fetch:update",
        ("broadcast", (201,)),
        ("mark", "notice-update", 201),
    ]


async def test_baseline_marks_without_broadcast(patched):
    calls, state = patched  # last_ids 비어 있음 → 두 카테고리 모두 baseline
    nexon = _Nexon(calls, notice_raw=_raw(11, 10), update_raw=_raw(20))
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == [
        "channels",
        "fetch:notice",
        ("mark", "notice", 11),  # 발송 없이 최대 id 만 마킹
        "fetch:update",
        ("mark", "notice-update", 20),
    ]
    assert not any(c[0] == "broadcast" for c in calls if isinstance(c, tuple))


async def test_caught_up_does_not_rebroadcast_or_remark(patched):
    # 신규 없음(marker == last_id): 발송도 없고, 마커도 전진 안 하므로 재마킹도 없음(불필요 DB write 회피).
    calls, state = patched
    state["last_ids"] = {"notice": 11, "notice-update": 20}
    nexon = _Nexon(calls, notice_raw=_raw(11, 10), update_raw=_raw(20))
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == ["channels", "fetch:notice", "fetch:update"]


async def test_marker_never_moves_backward_on_short_page(patched):
    # 일시적으로 짧은 페이지(max id < last_id): 발송 없음 + 마커 후퇴 금지(중복 재발송 방지).
    calls, state = patched
    state["last_ids"] = {"notice": 200, "notice-update": 300}
    nexon = _Nexon(calls, notice_raw=_raw(195, 194), update_raw=_raw(299))
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == [
        "channels",
        "fetch:notice",
        "fetch:update",
    ]  # broadcast·mark 둘 다 없음


async def test_no_channels_skips_nexon(patched):
    calls, state = patched
    state["channels"] = []
    nexon = _Nexon(calls, notice_raw=_raw(1), update_raw=_raw(2))
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == ["channels"]  # 넥슨 호출 안 함


async def test_fetch_error_isolated_to_category(patched):
    calls, state = patched  # baseline
    err = NexonAPIError("OPENAPI00001", "boom", error_class=ErrorClass.NEXON_API)
    nexon = _Nexon(calls, notice_raw=_raw(1), update_raw=_raw(20), notice_err=err)
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == [
        "channels",
        "fetch:notice",
        ("error_log", "nexon_api"),  # 공지 실패 → 마킹 안 함
        "fetch:update",
        ("mark", "notice-update", 20),  # 업데이트는 정상 진행
    ]


async def test_empty_category_does_not_mark(patched):
    calls, state = patched
    state["last_ids"] = {"notice-update": 20}
    nexon = _Nexon(calls, notice_raw=[], update_raw=_raw(21, 20))
    await scheduler.run_notice_job(bot=object(), deps=_deps(nexon))
    assert calls == [
        "channels",
        "fetch:notice",  # 빈 목록 → 마킹·발송 없음
        "fetch:update",
        ("broadcast", (21,)),
        ("mark", "notice-update", 21),
    ]


# ── build_notice_embeds: 제목 + 링크 + 등록일 (scheduler 렌더 헬퍼) ───────────


def test_build_embeds_maps_title_url_date():
    [embed] = scheduler.build_notice_embeds(
        [
            NoticeItem(
                notice_id=1,
                title="정기 점검",
                url="https://x/1",
                date_text="2026-01-15 10:00",
            )
        ]
    )
    assert embed.title == "정기 점검"
    assert embed.url == "https://x/1"
    assert embed.description == "2026-01-15 10:00"
    assert embed.footer.text == DATA_SOURCE  # 넥슨 출처표시(제6조④)


def test_build_embeds_url_none_when_empty():
    [embed] = scheduler.build_notice_embeds(
        [NoticeItem(notice_id=1, title="t", url="", date_text="d")]
    )
    assert embed.url is None
