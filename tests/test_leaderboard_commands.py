"""`/경험치`·`/경험치알림` 명령 계층 단위테스트 (Discord/DB mock).

순수 렌더 헬퍼(레벨·Δ·전체순위 라벨), 명령 분기(2명 미만/데이터 없음 → 안내, 발송), 토글
권한 가드·upsert 호출을 검증한다. 실제 발송·select 시각은 라이브 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from maple_mate.bot.leaderboard_image import (
    _delta_text,
    _level_text,
    _world_rank_text,
)
from maple_mate.leaderboard import broadcast, commands
from maple_mate.leaderboard.broadcast import LeaderboardPayload, _footer_text

_DELTA = 935_107_160_853  # 스파이크 실측 어제 획득


# ── 순수 라벨 헬퍼 ───────────────────────────────────────────────────────────


def test_level_text_without_rate():
    assert _level_text(287, None) == "Lv.287"


def test_level_text_with_rate():
    assert _level_text(287, 45.2) == "Lv.287 (45.2%)"


def test_delta_text_positive_uses_eok():
    assert _delta_text(_DELTA) == "+9351억 716만"


def test_delta_text_none_and_zero_are_dash():
    assert _delta_text(None) == "—"
    assert _delta_text(0) == "—"


def test_world_rank_text_formats_with_commas():
    assert _world_rank_text(129978) == "#129,978"
    assert _world_rank_text(None) == "—"


def test_footer_label_says_yesterday_kst():
    text = _footer_text(date(2026, 6, 13))
    assert "기준: 어제(06/13) KST" in text
    assert "NEXON Open API" in text


# ── /경험치 명령 분기 (defer → build_payload) ────────────────────────────────


class _FakeResponse:
    def __init__(self) -> None:
        self.done = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.done = True


class _FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


class _FakeInteraction:
    def __init__(self, *, guild_id: int | None = 1) -> None:
        self.guild_id = guild_id
        self.client = object()
        self.response = _FakeResponse()
        self.followup = _FakeFollowup()


async def test_leaderboard_command_sends_public_payload(monkeypatch):
    payload = LeaderboardPayload(
        table_png=b"\x89PNG",
        graph_png=b"\x89PNG",
        embed="embed",
        ref_date=date(2026, 6, 13),
    )

    async def fake_build(bot, deps, guild_id):
        return payload

    monkeypatch.setattr(commands, "build_payload", fake_build)
    interaction = _FakeInteraction()
    await commands.handle_leaderboard(deps=object(), interaction=interaction)
    [call] = interaction.followup.sent
    assert call["embed"] == "embed"
    assert len(call["files"]) == 2  # to_files() → 표 + 그래프
    assert "ephemeral" not in call  # 공개 발송


async def test_leaderboard_command_no_data_branch(monkeypatch):
    async def fake_build(bot, deps, guild_id):
        return None  # 2명 미만 / 데이터 없음

    monkeypatch.setattr(commands, "build_payload", fake_build)
    interaction = _FakeInteraction()
    await commands.handle_leaderboard(deps=object(), interaction=interaction)
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True
    assert "아직" in (call["embed"].description or "")


async def test_leaderboard_command_dm_guard(monkeypatch):
    called = {"build": False}

    async def fake_build(bot, deps, guild_id):
        called["build"] = True
        return None

    monkeypatch.setattr(commands, "build_payload", fake_build)
    interaction = _FakeInteraction(guild_id=None)  # DM
    await commands.handle_leaderboard(deps=object(), interaction=interaction)
    assert called["build"] is False  # 길드 밖이면 build_payload 호출 안 함
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True


# ── /경험치알림 토글 (권한 가드 + upsert 호출) ──────────────────────────────


class _ToggleResponse:
    def __init__(self) -> None:
        self.message: dict | None = None

    async def send_message(self, **kwargs) -> None:
        self.message = kwargs


class _ToggleInteraction:
    def __init__(self, *, guild_id, channel_id, manage_guild: bool) -> None:
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.user = SimpleNamespace(
            guild_permissions=SimpleNamespace(manage_guild=manage_guild)
        )
        self.response = _ToggleResponse()


async def test_exp_alert_requires_manage_guild(monkeypatch):
    calls: list = []

    async def fake_set(sf, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(commands.channel_service, "set_exp_alert", fake_set)
    interaction = _ToggleInteraction(guild_id=1, channel_id=2, manage_guild=False)
    await commands.handle_exp_alert(
        deps=SimpleNamespace(session_factory=object()),
        interaction=interaction,
        enabled=True,
    )
    assert calls == []  # 권한 없으면 토글 안 함
    assert "권한" in (interaction.response.message["embed"].title or "")


async def test_exp_alert_toggles_on(monkeypatch):
    calls: list = []

    async def fake_set(sf, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(commands.channel_service, "set_exp_alert", fake_set)
    interaction = _ToggleInteraction(guild_id=1, channel_id=2, manage_guild=True)
    await commands.handle_exp_alert(
        deps=SimpleNamespace(session_factory=object()),
        interaction=interaction,
        enabled=True,
    )
    assert calls == [{"guild_id": 1, "channel_id": 2, "enabled": True}]
    assert "켜짐" in (interaction.response.message["embed"].title or "")


async def test_exp_alert_dm_guard(monkeypatch):
    calls: list = []

    async def fake_set(sf, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(commands.channel_service, "set_exp_alert", fake_set)
    interaction = _ToggleInteraction(guild_id=None, channel_id=None, manage_guild=True)
    await commands.handle_exp_alert(
        deps=SimpleNamespace(session_factory=object()),
        interaction=interaction,
        enabled=True,
    )
    assert calls == []


# ── build_payload: 2명 미만 → None ───────────────────────────────────────────


async def test_build_payload_returns_none_below_min_ranked(monkeypatch):
    async def fake_get_targets(sf, guild_id):
        return [
            SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1"),
        ]

    async def fake_snapshots_on(sf, guild_id, snap_date):
        return [
            SimpleNamespace(
                discord_user_id=10,
                snapshot_date=snap_date,
                character_level=287,
                total_exp=1,
                world_rank=1,
                exp_rate=None,
            )
        ]

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    monkeypatch.setattr(broadcast.service, "snapshots_on", fake_snapshots_on)
    deps = SimpleNamespace(session_factory=object())
    result = await broadcast.build_payload(object(), deps, 1)
    assert result is None  # 등재 1명 < MIN_RANKED(2)


@pytest.mark.parametrize("count", [0, 1])
async def test_min_ranked_is_two(count):
    assert broadcast.MIN_RANKED == 2
