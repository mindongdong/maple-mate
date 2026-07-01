"""정기 알림 토글 공통 본체 단위테스트 — 대상(채널/개인) 분기 + 권한 제거 (ADR-0017).

handle_toggle 은 경험치·공지·썬데이가 공유한다. 가짜 AlertSpec·Interaction 으로 호출하고
channel set / DM subscribe 분기, 끄기 전부, 멱등 미구독, 권한 없는 유저 통과, 길드 가드를 검증한다.
"""

from __future__ import annotations

from types import SimpleNamespace

from discord import app_commands

from maple_mate.notification import toggle
from maple_mate.notification.target import targets_for
from maple_mate.notification.toggle import AlertSpec, handle_toggle


def _channel() -> app_commands.Choice[str]:
    return app_commands.Choice(name="채널", value="channel")


def _personal() -> app_commands.Choice[str]:
    return app_commands.Choice(name="개인", value="personal")


class _Response:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)


def _interaction(guild_id: int | None = 1, channel_id: int | None = 100, user_id=10):
    # guild_permissions 를 일부러 두지 않아 '권한 없는 유저'를 모사 — handle_toggle 이 안 봄.
    return SimpleNamespace(
        guild_id=guild_id,
        channel_id=channel_id,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
    )


def _deps():
    return SimpleNamespace(session_factory=object())


def _spec(set_channel) -> AlertSpec:
    return AlertSpec(
        kind="exp",
        title="테스트 알림",
        set_channel=set_channel,
        channel_on="채널 켜짐",
        channel_off="채널 꺼짐",
        personal_on="개인 켜짐",
        personal_off="개인 꺼짐",
    )


def _patch_dm(monkeypatch, *, existed=True):
    sub: list = []
    unsub: list = []

    async def subscribe_dm(sf, guild_id, user_id, kind):
        sub.append((guild_id, user_id, kind))

    async def unsubscribe_dm(sf, guild_id, user_id, kind):
        unsub.append((guild_id, user_id, kind))
        return existed

    monkeypatch.setattr(toggle.service, "subscribe_dm", subscribe_dm)
    monkeypatch.setattr(toggle.service, "unsubscribe_dm", unsubscribe_dm)
    return sub, unsub


# ── targets_for: 기본값 비대칭(결정 4) ───────────────────────────────────────


def test_targets_for_defaults_asymmetric():
    assert targets_for(None, enabling=True) == (True, False)  # 켜기 기본=채널만
    assert targets_for(None, enabling=False) == (True, True)  # 끄기 기본=둘 다
    assert targets_for(_channel(), enabling=True) == (True, False)
    assert targets_for(_personal(), enabling=True) == (False, True)
    assert targets_for(_personal(), enabling=False) == (False, True)


# ── handle_toggle: 대상 분기 ─────────────────────────────────────────────────


async def test_on_default_channel_only(monkeypatch):
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    sub, _unsub = _patch_dm(monkeypatch)
    interaction = _interaction()
    await handle_toggle(
        _deps(), interaction, _spec(set_channel), enabled=True, target=None
    )
    assert set_calls == [{"guild_id": 1, "channel_id": 100, "enabled": True}]
    assert sub == []  # 개인 구독 안 함(켜기 기본=채널만)
    [sent] = interaction.response.sent
    assert "채널 켜짐" in sent["embed"].description
    assert "켜짐" in sent["embed"].title


async def test_on_personal_target_subscribes(monkeypatch):
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    sub, _unsub = _patch_dm(monkeypatch)
    interaction = _interaction()
    await handle_toggle(
        _deps(), interaction, _spec(set_channel), enabled=True, target=_personal()
    )
    assert set_calls == []  # 채널 토글 안 함
    assert sub == [(1, 10, "exp")]  # 본인 DM 구독
    [sent] = interaction.response.sent
    assert "개인 켜짐" in sent["embed"].description


async def test_off_default_clears_both(monkeypatch):
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    sub, unsub = _patch_dm(monkeypatch, existed=True)
    interaction = _interaction()
    await handle_toggle(
        _deps(), interaction, _spec(set_channel), enabled=False, target=None
    )
    assert set_calls == [{"guild_id": 1, "channel_id": 100, "enabled": False}]
    assert unsub == [(1, 10, "exp")]
    [sent] = interaction.response.sent
    desc = sent["embed"].description
    assert "채널 꺼짐" in desc and "개인 꺼짐" in desc
    assert "꺼짐" in sent["embed"].title


async def test_off_personal_idempotent_when_not_subscribed(monkeypatch):
    async def set_channel(sf, **kwargs):
        raise AssertionError("채널 토글 호출 금지")

    _sub, unsub = _patch_dm(monkeypatch, existed=False)
    interaction = _interaction()
    await handle_toggle(
        _deps(), interaction, _spec(set_channel), enabled=False, target=_personal()
    )
    assert unsub == [(1, 10, "exp")]
    [sent] = interaction.response.sent
    assert "켜져 있지 않았어요" in sent["embed"].description  # 멱등 안내


async def test_no_permission_user_passes(monkeypatch):
    # interaction.user 에 guild_permissions 가 없어도 토글된다(권한 제거, 결정 3).
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    _patch_dm(monkeypatch)
    interaction = _interaction()
    await handle_toggle(
        _deps(), interaction, _spec(set_channel), enabled=True, target=_channel()
    )
    assert len(set_calls) == 1
    [sent] = interaction.response.sent
    assert "권한" not in (sent["embed"].title or "")


async def test_guild_only_guard(monkeypatch):
    set_calls: list = []

    async def set_channel(sf, **kwargs):
        set_calls.append(kwargs)

    sub, unsub = _patch_dm(monkeypatch)
    interaction = _interaction(guild_id=None)
    await handle_toggle(
        _deps(), interaction, _spec(set_channel), enabled=True, target=None
    )
    assert set_calls == [] and sub == [] and unsub == []
    [sent] = interaction.response.sent
    assert "서버" in sent["embed"].description
