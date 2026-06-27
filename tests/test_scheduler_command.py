"""`/스케줄러`·`/스케줄러알림` 핸들러 단위테스트 — 결과 분기 + 구독 가드 (작업지시서 #5).

가짜 Interaction 으로 핸들러를 직접 호출하고, build_homework·service DB 함수는 monkeypatch
(test_guide·test_leaderboard_commands 패턴). 실제 발송은 라이브 1회 확인.
"""

from __future__ import annotations

from types import SimpleNamespace

from maple_mate.registration.realm import Realm
from maple_mate.scheduler import commands
from maple_mate.scheduler.service import BossItem, ContentItem, Homework


class _Response:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, **kwargs) -> None:
        self._done = True

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


def _interaction(guild_id: int | None = 1, user_id: int = 10):
    return SimpleNamespace(
        guild_id=guild_id,
        channel_id=100,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        followup=_Followup(),
    )


def _deps():
    return SimpleNamespace(
        session_factory=object(), nexon=SimpleNamespace(), cipher=SimpleNamespace()
    )


def _homework(empty: bool = False) -> Homework:
    if empty:
        return Homework("신규", "스카니아", 200, [], [], [], 0, 0)
    return Homework(
        "내캐릭",
        "스카니아",
        285,
        [ContentItem("무릉도장", 1, 1)],
        [],
        [BossItem("검은마법사", "하드", True)],
        8,
        14,
    )


# ── /스케줄러 온디맨드 분기 ──────────────────────────────────────────────────


async def test_scheduler_guild_only(monkeypatch):
    interaction = _interaction(guild_id=None)
    await commands.handle_scheduler(_deps(), interaction, Realm.MAIN)
    [sent] = interaction.followup.sent
    assert "서버" in sent["embed"].description


async def test_scheduler_shows_error_when_build_fails(monkeypatch):
    async def build_homework(deps, g, u, realm):
        return None, "개인 키 미등록이라 스케줄러를 볼 수 없어요."

    monkeypatch.setattr(commands, "build_homework", build_homework)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction, Realm.MAIN)
    [sent] = interaction.followup.sent
    assert "개인 키 미등록" in sent["embed"].description
    assert sent["ephemeral"] is True


async def test_scheduler_empty_homework_message(monkeypatch):
    async def build_homework(deps, g, u, realm):
        return _homework(empty=True), None

    monkeypatch.setattr(commands, "build_homework", build_homework)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction, Realm.MAIN)
    [sent] = interaction.followup.sent
    assert "등록된 숙제" in sent["embed"].description  # 빈 안내(체크리스트 아님)


async def test_scheduler_renders_checklist_embed(monkeypatch):
    async def build_homework(deps, g, u, realm):
        return _homework(), None

    monkeypatch.setattr(commands, "build_homework", build_homework)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction, Realm.MAIN)
    [sent] = interaction.followup.sent
    assert sent["embed"].title == "🗓 내캐릭 의 스케줄러 숙제"
    assert sent["ephemeral"] is True  # 온디맨드는 ephemeral(결정 1)


# ── /스케줄러알림 켜기: fail fast 가드 + 시각 저장 ───────────────────────────


async def test_reminder_on_rejects_without_key_or_rep(monkeypatch):
    set_calls: list = []

    async def resolve_self(sf, g, u, realm):
        return None, None, "개인 키 미등록이라 알림을 켤 수 없어요."

    async def set_subscription(sf, **kwargs):
        set_calls.append(kwargs)

    monkeypatch.setattr(commands.service, "resolve_self", resolve_self)
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    await commands.handle_reminder_on(_deps(), interaction, 21, Realm.MAIN)
    [sent] = interaction.response.sent
    assert "개인 키 미등록" in sent["embed"].description
    assert set_calls == []  # 가드 실패 → 구독 안 함(fail fast)


async def test_reminder_on_stores_hour_and_realm(monkeypatch):
    set_calls: list = []

    async def resolve_self(sf, g, u, realm):
        return "enc", "ocid1", None

    async def set_subscription(sf, **kwargs):
        set_calls.append(kwargs)

    monkeypatch.setattr(commands.service, "resolve_self", resolve_self)
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    await commands.handle_reminder_on(_deps(), interaction, 9, Realm.CHALLENGERS)
    [kwargs] = set_calls
    assert kwargs["hour"] == 9 and kwargs["realm"] is Realm.CHALLENGERS
    [sent] = interaction.response.sent
    assert "09:00" in sent["embed"].description


async def test_reminder_on_rejects_invalid_hour(monkeypatch):
    set_calls: list = []

    async def resolve_self(sf, g, u, realm):  # 도달하면 안 됨
        set_calls.append("resolve")
        return "enc", "ocid1", None

    async def set_subscription(sf, **kwargs):
        set_calls.append("set")

    monkeypatch.setattr(commands.service, "resolve_self", resolve_self)
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    await commands.handle_reminder_on(_deps(), interaction, 25, Realm.MAIN)
    [sent] = interaction.response.sent
    assert "0" in sent["embed"].description and "23" in sent["embed"].description
    assert set_calls == []  # 범위 밖 → 해석·구독 모두 안 함


# ── /스케줄러알림 끄기 ───────────────────────────────────────────────────────


async def test_reminder_off_existing(monkeypatch):
    async def clear_subscription(sf, **kwargs):
        return True

    monkeypatch.setattr(commands.service, "clear_subscription", clear_subscription)
    interaction = _interaction()
    await commands.handle_reminder_off(_deps(), interaction, Realm.MAIN)
    [sent] = interaction.response.sent
    assert "껐어요" in sent["embed"].description


async def test_reminder_off_when_not_subscribed(monkeypatch):
    async def clear_subscription(sf, **kwargs):
        return False

    monkeypatch.setattr(commands.service, "clear_subscription", clear_subscription)
    interaction = _interaction()
    await commands.handle_reminder_off(_deps(), interaction, Realm.MAIN)
    [sent] = interaction.response.sent
    assert "없어요" in sent["embed"].description
