"""`/경험치`·`/경험치알림` 명령 계층 단위테스트 (Discord/DB mock).

푸터 라벨, 명령 분기(2명 미만/데이터 없음 → 안내, 그래프 발송), 토글 권한 가드·upsert 호출을
검증한다. 실제 발송·select 시각은 라이브 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from maple_mate.leaderboard import broadcast, commands
from maple_mate.leaderboard.broadcast import (
    LeaderboardPayload,
    _build_embed,
    _footer_text,
)
from maple_mate.leaderboard.service import LeaderRow
from maple_mate.registration.realm import Realm

# ── 푸터 라벨 ────────────────────────────────────────────────────────────────


def test_footer_label_says_today_current():
    text = _footer_text(date(2026, 6, 13))
    assert "기준: 오늘(06/13) 현재" in text  # 표시 레벨이 라이브(오늘 현재)
    assert "NEXON Open API" in text


# ── 임베드 순위판(위치) 텍스트 (ADR-0011) ────────────────────────────────────


def _row(rank, nick, level, exp_rate, world_rank):
    return LeaderRow(
        discord_user_id=rank,
        rank=rank,
        nickname=nick,
        level=level,
        exp_rate=exp_rate,
        delta=None,
        world_rank=world_rank,
    )


def test_embed_ranking_lists_medal_and_level_only():
    # 메달 · 닉 · 레벨(exp%)만 — 전체 서버순위·그래프 안내문구는 미표기(ADR-0011 피드백).
    rows = [
        _row(1, "손바", 287, 79.0, 12345),
        _row(2, "라딘라면", 287, 41.0, 45678),
    ]
    desc = _build_embed(rows, date(2026, 6, 22)).description or ""
    assert "🥇 **손바** — Lv.287 (79%)" in desc
    assert "🥈 **라딘라면** — Lv.287 (41%)" in desc
    assert "전체 #" not in desc  # 전체 서버 등수 제외
    assert "성장 레이스" not in desc and "그래프" not in desc  # 안내 문구 제외


def test_embed_ranking_caps_at_top_ten():
    # 순위판은 Top10까지만(그래프도 같은 10명). 11위 이하는 임베드에 안 나온다.
    rows = [_row(i, f"유저{i:02d}", 300 - i, 50.0, None) for i in range(1, 13)]
    desc = _build_embed(rows, date(2026, 6, 22)).description or ""
    for i in range(1, 11):
        assert f"유저{i:02d}" in desc
    assert "유저11" not in desc and "유저12" not in desc


def test_embed_ranking_graceful_without_exp_rate():
    # exp% 보강 실패(None) → 'Lv.287'(괄호 % 생략, ADR-0005 그레이스풀).
    desc = (
        _build_embed(
            [_row(1, "네벨루크", 281, None, None)], date(2026, 6, 22)
        ).description
        or ""
    )
    assert "🥇 **네벨루크** — Lv.281" in desc
    assert "(%" not in desc


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


async def _noop_ensure(deps, guild_id, realm=None):
    pass


async def test_leaderboard_command_sends_public_payload(monkeypatch):
    payload = LeaderboardPayload(
        graph_png=b"\x89PNG",
        embed="embed",
        ref_date=date(2026, 6, 13),
    )

    async def fake_build(bot, deps, guild_id, realm=Realm.MAIN):
        return payload

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_payload", fake_build)
    interaction = _FakeInteraction()
    await commands.handle_leaderboard(deps=object(), interaction=interaction)
    [call] = interaction.followup.sent
    assert call["embed"] == "embed"
    assert len(call["files"]) == 1  # to_files() → 그래프 1장
    assert "ephemeral" not in call  # 공개 발송


async def test_leaderboard_command_no_data_below_two_registrants(monkeypatch):
    """등록자 < 2명이면 '2명 이상 등록' 안내."""

    async def fake_build(bot, deps, guild_id, realm=Realm.MAIN):
        return None

    async def fake_get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_payload", fake_build)
    monkeypatch.setattr(commands, "get_targets", fake_get_targets)
    interaction = _FakeInteraction()
    deps = SimpleNamespace(session_factory=object())
    await commands.handle_leaderboard(deps=deps, interaction=interaction)
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True
    assert "2명 이상" in (call["embed"].description or "")


async def test_leaderboard_command_no_data_data_not_ready(monkeypatch):
    """등록자 ≥ 2명인데 payload None이면 '데이터 미준비' 안내."""

    async def fake_build(bot, deps, guild_id, realm=Realm.MAIN):
        return None

    async def fake_get_targets(sf, guild_id, realm=None):
        return [
            SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1"),
            SimpleNamespace(discord_user_id=20, nickname="라딘라면", ocid="o2"),
        ]

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_payload", fake_build)
    monkeypatch.setattr(commands, "get_targets", fake_get_targets)
    interaction = _FakeInteraction()
    deps = SimpleNamespace(session_factory=object())
    await commands.handle_leaderboard(deps=deps, interaction=interaction)
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True
    assert "잠시 후" in (call["embed"].description or "")


async def test_leaderboard_command_dm_guard(monkeypatch):
    called = {"build": False}

    async def fake_build(bot, deps, guild_id, realm=Realm.MAIN):
        called["build"] = True
        return None

    monkeypatch.setattr(commands, "build_payload", fake_build)
    interaction = _FakeInteraction(guild_id=None)  # DM
    await commands.handle_leaderboard(deps=object(), interaction=interaction)
    assert called["build"] is False  # 길드 밖이면 build_payload 호출 안 함
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True


async def test_leaderboard_command_bootstrap_fetches_when_no_snapshot(monkeypatch):
    """온디맨드 부트스트랩: ensure_guild_data(빈 날 백필) 호출 후 build_payload."""
    bootstrap_called: list[int] = []

    async def fake_ensure(deps, guild_id, realm=None):
        bootstrap_called.append(guild_id)

    payload = LeaderboardPayload(
        graph_png=b"\x89PNG",
        embed="embed",
        ref_date=date(2026, 6, 13),
    )

    async def fake_build(bot, deps, guild_id, realm=Realm.MAIN):
        return payload

    monkeypatch.setattr(commands, "ensure_guild_data", fake_ensure)
    monkeypatch.setattr(commands, "build_payload", fake_build)
    interaction = _FakeInteraction(guild_id=42)
    await commands.handle_leaderboard(deps=object(), interaction=interaction)
    assert bootstrap_called == [42]  # ensure_guild_data 호출됨
    [call] = interaction.followup.sent
    assert call["embed"] == "embed"  # 이후 정상 발송


# ── /경험치알림 스펙 배선 (대상 분기 본체는 test_notification_toggle 에서 검증) ──


def test_exp_alert_spec_wires_exp_kind_and_channel_setter():
    # 경험치 알림 스펙이 exp 구독 kind·채널 토글 함수에 묶여 있는지(통일 패턴, ADR-0017).
    assert commands._EXP_SPEC.kind == commands.channel_service.KIND_EXP
    assert commands._EXP_SPEC.set_channel is commands.channel_service.set_exp_alert
    assert commands._EXP_SPEC.title == "경험치 알림"


# ── build_payload: 2명 미만 → None ───────────────────────────────────────────


async def test_build_payload_returns_none_below_min_ranked(monkeypatch):
    async def fake_get_targets(sf, guild_id, realm=None):
        return [
            SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1"),
        ]

    async def fake_snapshots_on(sf, guild_id, snap_date, realm=None):
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


async def test_build_payload_caps_embed_and_graph_to_top_ten(monkeypatch):
    # 등재 12명 → 임베드 순위판 10줄·그래프 라인 10개, 둘 다 동일한 상위 10명(레벨 내림차순).
    n = 12
    targets = [
        SimpleNamespace(discord_user_id=i, nickname=f"유저{i:02d}", ocid=f"o{i}")
        for i in range(1, n + 1)
    ]

    async def fake_get_targets(sf, guild_id, realm=None):
        return targets

    async def fake_snapshots_on(sf, guild_id, snap_date, realm=None):
        # 레벨 내림차순이 되도록 character_level 을 i 로 부여(유저01 이 최고 레벨).
        return [
            SimpleNamespace(
                discord_user_id=t.discord_user_id,
                snapshot_date=snap_date,
                character_level=300 - i,
                total_exp=1,
                world_rank=i,
                exp_rate=50.0,
            )
            for i, t in enumerate(targets, start=1)
        ]

    async def fake_live_levels(deps, tgts):
        return {}  # 라이브 실패 → D-1 스냅샷 폴백(결정적 레벨 순서)

    async def fake_history_progress(sf, guild_id, nicknames, today, *, realm=None):
        return {nick: [(date(2026, 6, 13), 290.0)] for nick in nicknames.values()}

    captured: dict[str, object] = {}

    def fake_render(series, ref_date):
        captured["series"] = series
        return SimpleNamespace(getvalue=lambda: b"PNG")

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    monkeypatch.setattr(broadcast.service, "snapshots_on", fake_snapshots_on)
    monkeypatch.setattr(broadcast.service, "live_levels", fake_live_levels)
    monkeypatch.setattr(broadcast.service, "history_progress", fake_history_progress)
    monkeypatch.setattr(
        broadcast.leaderboard_image, "render_progress_graph", fake_render
    )

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    payload = await broadcast.build_payload(object(), deps, 1)
    assert payload is not None

    # 그래프 = 상위 10명만(임베드와 동일 멤버) + 임베드와 동일 순위 순서(렌더러는 재정렬 안 함).
    assert len(captured["series"]) == broadcast._TOP_N == 10
    assert list(captured["series"]) == [f"유저{i:02d}" for i in range(1, 11)]

    # 임베드 순위판도 10줄, 11·12위 제외.
    desc = payload.embed.description or ""
    for i in range(1, 11):
        assert f"유저{i:02d}" in desc
    assert "유저11" not in desc and "유저12" not in desc
