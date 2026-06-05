"""run_sunday_job 오케스트레이션 단위테스트 — 가지치기 순서 + 발송→마킹 (작업지시서 Q3·Q4·#3).

모든 I/O(DB·넥슨·디스코드)를 페이크로 막고 제어흐름만 검증한다. 실 스케줄러/디스코드
통합은 일회성 스크립트로 확인(작업지시서 Q8)하므로 여기선 다루지 않는다.
"""
from __future__ import annotations

import pytest

from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from maple_mate.notification import scheduler


class _Nexon:
    pass


def _deps():
    # session_factory/nexon 은 페이크 서비스가 가로채므로 더미면 충분.
    return type("Deps", (), {"session_factory": object(), "nexon": _Nexon()})()


@pytest.fixture
def patched(monkeypatch):
    """service/broadcast/error_log 를 페이크로 교체하고 호출 순서를 기록한다."""
    calls: list[str] = []
    state = {
        "already_sent": False,
        "channels": [(1, 100)],
        "events": ["evt"],  # 비어있지 않으면 발송 대상
        "raise": None,
    }

    async def already_sent_this_week(sf, week_id):
        calls.append("already_sent")
        return state["already_sent"]

    async def enabled_sunday_channels(sf):
        calls.append("channels")
        return state["channels"]

    async def select_sunday_events(nexon):
        calls.append("fetch")
        if state["raise"] is not None:
            raise state["raise"]
        return state["events"]

    async def mark_week_sent(sf, week_id):
        calls.append("mark")

    async def broadcast_sunday(bot, channels, events):
        calls.append("broadcast")
        return len(channels)

    async def record(sf, **kwargs):
        calls.append(f"error_log:{kwargs.get('error_type')}")

    monkeypatch.setattr(scheduler.service, "already_sent_this_week", already_sent_this_week)
    monkeypatch.setattr(scheduler.service, "enabled_sunday_channels", enabled_sunday_channels)
    monkeypatch.setattr(scheduler.service, "select_sunday_events", select_sunday_events)
    monkeypatch.setattr(scheduler.service, "mark_week_sent", mark_week_sent)
    monkeypatch.setattr(scheduler, "broadcast_sunday", broadcast_sunday)
    monkeypatch.setattr(scheduler.error_log, "record", record)
    return calls, state


async def test_happy_path_broadcasts_then_marks(patched):
    calls, _ = patched
    await scheduler.run_sunday_job(bot=object(), deps=_deps())
    # 순서: 주차→채널→페치→발송→마킹.
    assert calls == ["already_sent", "channels", "fetch", "broadcast", "mark"]


async def test_already_sent_skips_everything(patched):
    calls, state = patched
    state["already_sent"] = True
    await scheduler.run_sunday_job(bot=object(), deps=_deps())
    assert calls == ["already_sent"]  # 넥슨 호출/발송/마킹 없음


async def test_no_channels_skips_nexon_call(patched):
    calls, state = patched
    state["channels"] = []
    await scheduler.run_sunday_job(bot=object(), deps=_deps())
    assert calls == ["already_sent", "channels"]  # 넥슨 호출 안 함(Q3②)


async def test_zero_match_does_not_mark(patched):
    calls, state = patched
    state["events"] = []
    await scheduler.run_sunday_job(bot=object(), deps=_deps())
    assert calls == ["already_sent", "channels", "fetch"]  # 발송·마킹 없음(0매칭=마킹 안 함)


async def test_nexon_failure_records_error_and_does_not_mark(patched):
    calls, state = patched
    state["raise"] = NexonAPIError("OPENAPI00001", "boom", error_class=ErrorClass.NEXON_API)
    await scheduler.run_sunday_job(bot=object(), deps=_deps())
    assert calls == ["already_sent", "channels", "fetch", "error_log:nexon_api"]
    assert "broadcast" not in calls and "mark" not in calls
