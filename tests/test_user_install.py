"""유저 설치(DM 워크스페이스) 단위테스트 — resolve_scope 분기 + 데코레이터 배선 + DM 스코프 전달 (ADR-0019).

resolve_scope 4분기(길드/봇DM/유저설치-타서버/양통합)와, 봇 트리 전 명령의 allowed_installs·
allowed_contexts 분류(개방/미개방 — G0 게이트로 알림 3종은 미개방 유지, §7), 개방 핸들러가
DM 에서 guild_id 자리에 센티널 0 을 전달하는 배선을 검증한다. DB·넥슨은 monkeypatch.
가짜 Interaction 은 test_mychar_commands 의 _Response/_Followup 패턴 + 통합 판별 스텁.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from maple_mate.bot.core import MapleMateBot
from maple_mate.bot.scope import DM_WORKSPACE_ID, resolve_scope
from maple_mate.notification import toggle
from maple_mate.notification.target import TARGET_CHANNEL
from maple_mate.notification.toggle import AlertSpec, handle_toggle
from maple_mate.registration import commands as reg_commands
from maple_mate.registration import service as reg_service
from maple_mate.scheduler import commands as sched_commands
from maple_mate.scheduler import service as sched_service

# ── 가짜 상호작용 (test_mychar_commands 패턴 + 통합 판별 스텁) ────────────────


class _Response:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.deferred = False
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)
        self._done = True

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred = True
        self._done = True


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


def _interaction(
    guild_id: int | None = 1,
    user_id: int = 10,
    *,
    user_install: bool = False,
    guild_install: bool | None = None,
) -> SimpleNamespace:
    """guild_install 미지정 시 길드 컨텍스트면 길드 설치로 간주(실디스코드 기본 상황)."""
    if guild_install is None:
        guild_install = guild_id is not None
    return SimpleNamespace(
        guild_id=guild_id,
        channel_id=99,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        followup=_Followup(),
        is_user_integration=lambda: user_install,
        is_guild_integration=lambda: guild_install,
    )


def _deps() -> SimpleNamespace:
    return SimpleNamespace(session_factory=object(), nexon=object(), cipher=object())


# ── resolve_scope 4분기 (§3-1) ───────────────────────────────────────────────


def test_scope_guild_install_in_guild_returns_guild_id():
    scope = resolve_scope(_interaction(guild_id=123))
    assert scope == 123


def test_scope_user_install_bot_dm_returns_workspace():
    scope = resolve_scope(_interaction(guild_id=None, user_install=True))
    assert scope == DM_WORKSPACE_ID


def test_scope_user_install_in_foreign_guild_rejected():
    # 봇 미초대 서버에서 유저 설치로 호출 — guild_id 는 있지만 길드 통합이 아님(결정 4).
    scope = resolve_scope(
        _interaction(guild_id=456, user_install=True, guild_install=False)
    )
    assert scope is None


def test_scope_both_integrations_in_guild_returns_guild_id():
    # 봇 초대 서버 + 유저 설치 동시 — 길드 통합이 우선(길드 경로 회귀 0).
    scope = resolve_scope(
        _interaction(guild_id=789, user_install=True, guild_install=True)
    )
    assert scope == 789


def test_scope_guild_only_bot_dm_still_rejected():
    # 서버 공유 유저의 봇 DM(유저 설치 아님) — 기존 거부 동작 유지(결정 1: 별개 데이터 혼란 방지).
    assert resolve_scope(_interaction(guild_id=None, user_install=False)) is None


def test_scope_fake_without_integration_methods_treated_as_guild_install():
    # 판별 메서드 없는 가짜(기존 테스트 SimpleNamespace) — 길드 설치로 간주(레거시 경로 보존).
    legacy = SimpleNamespace(guild_id=1)
    assert resolve_scope(legacy) == 1
    legacy_dm = SimpleNamespace(guild_id=None)
    assert resolve_scope(legacy_dm) is None


# ── 데코레이터 배선 분류 (§3-2 — 기본값 드리프트 방지) ───────────────────────

# G0 통과 시 GATED → OPEN 으로 플립(allowed_installs users=False→True 한 줄씩, §7).
OPEN_COMMANDS = {
    "가이드",
    "캐릭터등록",
    "키등록",
    "대표지정",
    "캐릭터목록",
    "내캐릭터",
    "스케줄러",
}
GATED_COMMANDS = {"스케줄러알림", "공지알림", "썬데이알림"}
CLOSED_COMMANDS = {
    "스펙",
    "아이템",
    "유니온",
    "스타포스",
    "잠재",
    "경험치",
    "경험치알림",
}


@pytest.fixture(scope="module")
def bot() -> MapleMateBot:
    bot = MapleMateBot(deps=object(), dev_guild_id=None)
    bot._register_commands()
    return bot


def test_all_tree_commands_classified(bot):
    names = {cmd.name for cmd in bot.tree.get_commands()}
    assert names == OPEN_COMMANDS | GATED_COMMANDS | CLOSED_COMMANDS


def test_open_commands_allow_user_install_and_bot_dm(bot):
    for name in OPEN_COMMANDS:
        cmd = bot.tree.get_command(name)
        assert cmd.allowed_installs.user is True, name
        assert cmd.allowed_installs.guild is True, name
        assert cmd.allowed_contexts.dm_channel is True, name
        assert cmd.allowed_contexts.private_channel is False, name  # 그룹 DM 차단


def test_gated_alerts_hidden_from_user_install_but_dm_ready(bot):
    # G0 미판정(§7): 유저 설치 목록에서 숨기되, DM 컨텍스트는 열어 둬 플립 한 줄만 남긴다.
    for name in GATED_COMMANDS:
        cmd = bot.tree.get_command(name)
        assert cmd.allowed_installs.user is False, name
        assert cmd.allowed_installs.guild is True, name
        assert cmd.allowed_contexts.dm_channel is True, name
        assert cmd.allowed_contexts.private_channel is False, name


def test_closed_commands_guild_only(bot):
    for name in CLOSED_COMMANDS:
        cmd = bot.tree.get_command(name)
        assert cmd.allowed_installs.user is False, name
        assert cmd.allowed_installs.guild is True, name
        assert cmd.allowed_contexts.dm_channel is False, name
        assert cmd.allowed_contexts.private_channel is False, name


# ── 개방 핸들러의 DM 스코프 전달 (guild_id 자리에 센티널 0) ──────────────────


async def test_register_in_dm_uses_workspace_scope(monkeypatch):
    captured: dict = {}

    async def fake_register(
        *, nexon, session_factory, guild_id, discord_user_id, nickname
    ):
        captured.update(guild_id=guild_id, discord_user_id=discord_user_id)
        return SimpleNamespace(ok=True, nickname=nickname, level=280, character_count=1)

    async def fake_has_key(session_factory, guild_id, discord_user_id):
        captured["key_guild_id"] = guild_id
        return True

    monkeypatch.setattr(reg_service, "register_character", fake_register)
    monkeypatch.setattr(reg_service, "has_personal_key", fake_has_key)
    interaction = _interaction(guild_id=None, user_install=True)

    await reg_commands.handle_character_register(_deps(), interaction, "닉네임")

    assert captured["guild_id"] == DM_WORKSPACE_ID
    assert captured["key_guild_id"] == DM_WORKSPACE_ID
    [sent] = interaction.followup.sent
    assert "등록 완료" in sent["embed"].title


async def test_register_in_foreign_guild_rejected(monkeypatch):
    called = {"register": False}

    async def fake_register(**kwargs):
        called["register"] = True

    monkeypatch.setattr(reg_service, "register_character", fake_register)
    interaction = _interaction(guild_id=456, user_install=True, guild_install=False)

    await reg_commands.handle_character_register(_deps(), interaction, "닉")

    assert called["register"] is False
    [sent] = interaction.followup.sent
    assert sent["ephemeral"] is True
    assert "서버 채널 또는 봇 DM" in sent["embed"].description


async def test_scheduler_in_dm_uses_workspace_scope(monkeypatch):
    captured: dict = {}

    async def fake_build(deps, guild_id, user_id):
        captured.update(guild_id=guild_id, user_id=user_id)
        return [], "개인 키 미등록이라 스케줄러를 볼 수 없어요."

    monkeypatch.setattr(sched_commands, "build_homeworks", fake_build)
    interaction = _interaction(guild_id=None, user_install=True)

    await sched_commands.handle_scheduler(_deps(), interaction)

    assert captured["guild_id"] == DM_WORKSPACE_ID


async def test_reminder_on_in_dm_subscribes_workspace_scope(monkeypatch):
    captured: dict = {}

    async def fake_resolve(session_factory, guild_id, user_id):
        captured["resolve_guild_id"] = guild_id
        return "key", [("o1", "닉")], None

    async def fake_get(session_factory, guild_id, user_id):
        return None

    async def fake_set(session_factory, *, guild_id, discord_user_id, hour, excluded):
        captured.update(guild_id=guild_id, hour=hour)

    monkeypatch.setattr(sched_service, "resolve_self_characters", fake_resolve)
    monkeypatch.setattr(sched_service, "get_subscription", fake_get)
    monkeypatch.setattr(sched_service, "set_subscription", fake_set)
    interaction = _interaction(guild_id=None, user_install=True)

    await sched_commands.handle_reminder_on(_deps(), interaction, 21)

    assert captured["resolve_guild_id"] == DM_WORKSPACE_ID
    assert captured["guild_id"] == DM_WORKSPACE_ID
    assert captured["hour"] == 21


# ── 알림 토글의 DM 배선 (§3-2 — 채널 대상 거부, 기본값은 개인으로) ───────────


def _alert_spec(set_channel) -> AlertSpec:
    return AlertSpec(
        kind="notice",
        title="공지 알림",
        set_channel=set_channel,
        channel_on="채널 켬",
        channel_off="채널 끔",
        personal_on="개인 켬",
        personal_off="개인 끔",
    )


def _channel_choice() -> SimpleNamespace:
    return SimpleNamespace(value=TARGET_CHANNEL)


def _patch_dm_subs(monkeypatch) -> dict:
    captured: dict = {"sub": [], "unsub": []}

    async def fake_sub(session_factory, guild_id, user_id, kind):
        captured["sub"].append(guild_id)

    async def fake_unsub(session_factory, guild_id, user_id, kind):
        captured["unsub"].append(guild_id)
        return True

    monkeypatch.setattr(toggle.service, "subscribe_dm", fake_sub)
    monkeypatch.setattr(toggle.service, "unsubscribe_dm", fake_unsub)
    return captured


async def test_toggle_dm_explicit_channel_target_rejected(monkeypatch):
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    subs = _patch_dm_subs(monkeypatch)
    interaction = _interaction(guild_id=None, user_install=True)

    await handle_toggle(
        _deps(),
        interaction,
        _alert_spec(set_channel),
        enabled=True,
        target=_channel_choice(),
    )

    assert set_calls == [] and subs["sub"] == []
    [sent] = interaction.response.sent
    assert "개인 알림만" in sent["embed"].description


async def test_toggle_dm_default_on_routes_to_personal(monkeypatch):
    # DM 엔 공용 채널이 없다 — 대상 미지정 켜기는 개인 구독으로 라우팅(guild 0 채널행 생성 금지).
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    subs = _patch_dm_subs(monkeypatch)
    interaction = _interaction(guild_id=None, user_install=True)

    await handle_toggle(
        _deps(), interaction, _alert_spec(set_channel), enabled=True, target=None
    )

    assert set_calls == []
    assert subs["sub"] == [DM_WORKSPACE_ID]
    [sent] = interaction.response.sent
    assert "개인 켬" in sent["embed"].description


async def test_toggle_dm_default_off_clears_personal_only(monkeypatch):
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    subs = _patch_dm_subs(monkeypatch)
    interaction = _interaction(guild_id=None, user_install=True)

    await handle_toggle(
        _deps(), interaction, _alert_spec(set_channel), enabled=False, target=None
    )

    assert set_calls == []
    assert subs["unsub"] == [DM_WORKSPACE_ID]


async def test_toggle_guild_path_unchanged(monkeypatch):
    # 길드 경로 회귀 0 — 채널 토글이 기존처럼 guild_id 로 저장된다.
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    _patch_dm_subs(monkeypatch)
    interaction = _interaction(guild_id=42)

    await handle_toggle(
        _deps(), interaction, _alert_spec(set_channel), enabled=True, target=None
    )

    assert [c["guild_id"] for c in set_calls] == [42]
