"""manual_broadcast_sunday 오케스트레이션 단위테스트 — 마킹 게이트(sent>0)·0채널·전채널실패.

핸드오프 #2(override·dedup 체크 안 함)·#3(0채널 미마킹)·#7(sent>0 게이트). 모든 I/O
(DB·디스코드)를 페이크로 막고 제어흐름만 검증(test_sunday_job 과 동일 방침).
"""

from __future__ import annotations

import pytest

from maple_mate.notification import scheduler
from maple_mate.notification.service import SundayEvent

_EVENT = SundayEvent(
    title="썬데이 메이플", url="", thumbnail_url=None, period_text="기간 미정"
)


def _deps():
    # session_factory 는 페이크 서비스가 가로채므로 더미면 충분.
    return type("Deps", (), {"session_factory": object()})()


@pytest.fixture
def patched(monkeypatch):
    """enabled_sunday_channels·broadcast_sunday·mark_week_sent 를 페이크로 교체하고 호출 기록."""
    calls: list[str] = []
    state = {"channels": [(1, 100)], "sent": 1}

    async def enabled_sunday_channels(sf):
        calls.append("channels")
        return state["channels"]

    async def broadcast_sunday(bot, channels, events):
        calls.append("broadcast")
        return state["sent"]

    async def mark_week_sent(sf, week_id):
        calls.append("mark")

    monkeypatch.setattr(
        scheduler.service, "enabled_sunday_channels", enabled_sunday_channels
    )
    monkeypatch.setattr(scheduler, "broadcast_sunday", broadcast_sunday)
    monkeypatch.setattr(scheduler.service, "mark_week_sent", mark_week_sent)
    return calls, state


async def test_sent_positive_marks_week(patched):
    calls, state = patched
    state["channels"] = [(1, 100), (1, 200)]
    state["sent"] = 2
    result = await scheduler.manual_broadcast_sunday(object(), _deps(), _EVENT)
    assert result == (2, 2)
    assert calls == ["channels", "broadcast", "mark"]  # sent>0 → 마킹(#7)


async def test_no_channels_returns_zero_and_skips_mark(patched):
    calls, state = patched
    state["channels"] = []
    result = await scheduler.manual_broadcast_sunday(object(), _deps(), _EVENT)
    assert result == (0, 0)
    assert calls == ["channels"]  # 발송·마킹 없음(#3)


async def test_all_channels_fail_does_not_mark(patched):
    calls, state = patched
    state["channels"] = [(1, 100)]
    state["sent"] = 0  # 전 채널 발송 실패
    result = await scheduler.manual_broadcast_sunday(object(), _deps(), _EVENT)
    assert result == (0, 1)
    assert calls == ["channels", "broadcast"]  # sent=0 → 마킹 안 함(#7)
