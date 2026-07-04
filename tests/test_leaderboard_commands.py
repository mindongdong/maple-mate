"""`/경험치`·`/경험치알림` 명령 계층 단위테스트 (Discord/DB mock).

푸터 라벨, 명령 분기(미등록/데이터 없음 → 안내, 그래프 발송), 토글 권한 가드·upsert 호출을
검증한다. 실제 발송·select 시각은 라이브 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

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


def _row(rank, nick, level, exp_rate):
    return LeaderRow(
        ocid=f"o{rank}",
        rank=rank,
        nickname=nick,
        level=level,
        exp_rate=exp_rate,
    )


def test_embed_ranking_lists_medal_and_level_only():
    # 메달 · 닉 · 레벨(exp%)만 — 전체 서버순위·그래프 안내문구는 미표기(ADR-0011 피드백).
    rows = [
        _row(1, "손바", 287, 79.0),
        _row(2, "라딘라면", 287, 41.0),
    ]
    desc = _build_embed(rows, date(2026, 6, 22)).description or ""
    assert "🥇 **손바** — Lv.287 (79%)" in desc
    assert "🥈 **라딘라면** — Lv.287 (41%)" in desc
    assert "전체 #" not in desc  # 전체 서버 등수 제외
    assert "성장 레이스" not in desc and "그래프" not in desc  # 안내 문구 제외


def test_embed_ranking_caps_at_top_ten():
    # 순위판은 Top10까지만(그래프도 같은 10명). 11위 이하는 임베드에 안 나온다.
    rows = [_row(i, f"유저{i:02d}", 300 - i, 50.0) for i in range(1, 13)]
    desc = _build_embed(rows, date(2026, 6, 22)).description or ""
    for i in range(1, 11):
        assert f"유저{i:02d}" in desc
    assert "유저11" not in desc and "유저12" not in desc


def test_embed_ranking_graceful_without_exp_rate():
    # exp% 보강 실패(None) → 'Lv.287'(괄호 % 생략, ADR-0005 그레이스풀).
    desc = (
        _build_embed([_row(1, "네벨루크", 281, None)], date(2026, 6, 22)).description
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


async def test_leaderboard_command_no_targets_prompts_registration(monkeypatch):
    """등록자 0명이면 '캐릭터 등록' 안내."""

    async def fake_build(bot, deps, guild_id, realm=Realm.MAIN):
        return None

    async def fake_get_targets(sf, guild_id, realm=None):
        return []

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_payload", fake_build)
    monkeypatch.setattr(commands, "get_targets", fake_get_targets)
    interaction = _FakeInteraction()
    deps = SimpleNamespace(session_factory=object())
    await commands.handle_leaderboard(deps=deps, interaction=interaction)
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True
    assert "캐릭터를 등록" in (call["embed"].description or "")


async def test_leaderboard_command_no_data_data_not_ready(monkeypatch):
    """등록자가 있는데 payload None(스냅샷 0건)이면 '데이터 미준비' 안내 — 1명이어도 표시가
    원칙이라(게이트 1명) 이 분기는 넥슨 미준비뿐이다."""

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


# ── /경험치 대상 지정 (build_specified_payload 분기) ─────────────────────────


def _member(uid: int) -> SimpleNamespace:
    return SimpleNamespace(id=uid, display_name=f"유저{uid}")


async def test_leaderboard_specified_sends_targets_payload(monkeypatch):
    """대상 지정: build_specified_payload(지정 유저 id) 로 그 유저들만 공개 발송."""
    payload = LeaderboardPayload(
        graph_png=b"\x89PNG", embed="targets-embed", ref_date=date(2026, 6, 13)
    )
    captured: dict = {}

    async def fake_specified(deps, guild_id, user_ids, realm=Realm.MAIN):
        captured["user_ids"] = list(user_ids)
        return payload

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_specified_payload", fake_specified)
    interaction = _FakeInteraction()
    await commands.handle_leaderboard(
        deps=object(), interaction=interaction, members=[_member(7), _member(8)]
    )
    assert captured["user_ids"] == [7, 8]  # 지정 유저 id 만 전달
    [call] = interaction.followup.sent
    assert call["embed"] == "targets-embed"
    assert "ephemeral" not in call  # 공개 발송


async def test_leaderboard_specified_all_missing_prompts(monkeypatch):
    """지정 유저가 전원 미등록/데이터 없음(payload None) → 안내(ephemeral)."""

    async def fake_specified(deps, guild_id, user_ids, realm=Realm.MAIN):
        return None

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_specified_payload", fake_specified)
    interaction = _FakeInteraction()
    await commands.handle_leaderboard(
        deps=object(), interaction=interaction, members=[_member(7)]
    )
    [call] = interaction.followup.sent
    assert call["ephemeral"] is True
    assert "미등록" in (call["embed"].description or "")


async def test_leaderboard_specified_does_not_use_server_build(monkeypatch):
    """대상 지정 시 서버 리더보드 build_payload 는 호출하지 않는다(무인자 전용)."""
    called = {"server": False}

    async def fake_server(bot, deps, guild_id, realm=Realm.MAIN):
        called["server"] = True
        return None

    async def fake_specified(deps, guild_id, user_ids, realm=Realm.MAIN):
        return LeaderboardPayload(
            graph_png=b"\x89PNG", embed="e", ref_date=date(2026, 6, 13)
        )

    monkeypatch.setattr(commands, "ensure_guild_data", _noop_ensure)
    monkeypatch.setattr(commands, "build_payload", fake_server)
    monkeypatch.setattr(commands, "build_specified_payload", fake_specified)
    interaction = _FakeInteraction()
    await commands.handle_leaderboard(
        deps=object(), interaction=interaction, members=[_member(7)]
    )
    assert called["server"] is False


# ── /경험치알림 스펙 배선 (대상 분기 본체는 test_notification_toggle 에서 검증) ──


def test_exp_alert_spec_wires_exp_kind_and_channel_setter():
    # 경험치 알림 스펙이 exp 구독 kind·채널 토글 함수에 묶여 있는지(통일 패턴, ADR-0017).
    assert commands._EXP_SPEC.kind == commands.channel_service.KIND_EXP
    assert commands._EXP_SPEC.set_channel is commands.channel_service.set_exp_alert
    assert commands._EXP_SPEC.title == "경험치 알림"


# ── build_payload: 스냅샷 0건 → None · 1명 표시 · 기준일 폴백 ─────────────────


async def test_build_payload_returns_none_when_no_snapshots(monkeypatch):
    # 스냅샷이 아예 없으면(신규 길드 + 넥슨 미준비) 표시 불가 → None.
    async def fake_get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def fake_latest(sf, guild_id, ocids, on_or_before, realm=None):
        return None  # 스냅샷 0건

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    monkeypatch.setattr(broadcast.service, "latest_snapshot_date", fake_latest)
    deps = SimpleNamespace(session_factory=object())
    result = await broadcast.build_payload(object(), deps, 1)
    assert result is None


def test_min_ranked_is_one():
    # Q10 개정(2026-07-04): 1명이어도 1라인 그래프 표시 — 어떤 경우에도 조회 가능.
    assert broadcast.MIN_RANKED == 1


def _single_target_payload_patches(monkeypatch, *, latest: date):
    """1명 등록 + 기준일 latest 스냅샷 → payload 생성 경로의 공통 페이크 배선."""
    targets = [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def fake_get_targets(sf, guild_id, realm=None):
        return targets

    async def fake_latest(sf, guild_id, ocids, on_or_before, realm=None):
        return latest

    async def fake_snapshots_on(sf, guild_id, snap_date, realm=None):
        assert snap_date == latest  # 게이트·순위판이 폴백 기준일을 읽는다
        return [
            SimpleNamespace(
                discord_user_id=10,
                ocid="o1",
                snapshot_date=snap_date,
                character_level=287,
                exp_rate=50.0,
            )
        ]

    async def fake_live_levels(deps, tgts):
        return {}

    captured: dict = {}

    async def fake_history_progress(sf, guild_id, labels, today, *, realm=None):
        captured["history_ref"] = today
        return {label: [(latest, 287.5)] for label in labels.values()}

    def fake_render(series, ref_date):
        captured["render_ref"] = ref_date
        return SimpleNamespace(getvalue=lambda: b"PNG")

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    monkeypatch.setattr(broadcast.service, "latest_snapshot_date", fake_latest)
    monkeypatch.setattr(broadcast.service, "snapshots_on", fake_snapshots_on)
    monkeypatch.setattr(broadcast.service, "live_levels", fake_live_levels)
    monkeypatch.setattr(broadcast.service, "history_progress", fake_history_progress)
    monkeypatch.setattr(
        broadcast.leaderboard_image, "render_progress_graph", fake_render
    )
    return captured


async def test_build_payload_single_registrant_renders(monkeypatch):
    # 등록 1명 = 1라인 그래프(게이트 1명) — payload 가 생성된다.
    from datetime import datetime, timedelta

    d1 = (datetime.now(broadcast.KST) - timedelta(days=1)).date()
    _single_target_payload_patches(monkeypatch, latest=d1)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    payload = await broadcast.build_payload(object(), deps, 1)
    assert payload is not None
    assert "손바" in (payload.embed.description or "")


async def test_build_payload_falls_back_to_latest_snapshot_date(monkeypatch):
    # 자정~넥슨 전일 데이터 생성 사이(D-1 미준비): 기준일이 가장 최근 스냅샷 일자(D-2)로
    # 내려가 그래프·순위판이 그대로 뜬다(특정 시각 가정 없음).
    from datetime import datetime, timedelta

    d2 = (datetime.now(broadcast.KST) - timedelta(days=2)).date()
    captured = _single_target_payload_patches(monkeypatch, latest=d2)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    payload = await broadcast.build_payload(object(), deps, 1)
    assert payload is not None
    assert payload.ref_date == d2  # 기준일 = 폴백된 최근 스냅샷 일자
    assert captured["history_ref"] == d2  # 7일 이력 창도 같은 기준일로 끝난다


async def test_build_payload_caps_embed_and_graph_to_top_ten(monkeypatch):
    # 등재 12명 → 임베드 순위판 10줄·그래프 라인 10개, 둘 다 동일한 상위 10명(레벨 내림차순).
    n = 12
    targets = [
        SimpleNamespace(discord_user_id=i, nickname=f"유저{i:02d}", ocid=f"o{i}")
        for i in range(1, n + 1)
    ]

    async def fake_get_targets(sf, guild_id, realm=None):
        return targets

    async def fake_latest(sf, guild_id, ocids, on_or_before, realm=None):
        return on_or_before  # D-1 스냅샷 존재(폴백 없음)

    async def fake_snapshots_on(sf, guild_id, snap_date, realm=None):
        # 레벨 내림차순이 되도록 character_level 을 i 로 부여(유저01 이 최고 레벨).
        return [
            SimpleNamespace(
                discord_user_id=t.discord_user_id,
                ocid=t.ocid,
                snapshot_date=snap_date,
                character_level=300 - i,
                exp_rate=50.0,
            )
            for i, t in enumerate(targets, start=1)
        ]

    async def fake_live_levels(deps, tgts):
        return {}  # 라이브 실패 → D-1 스냅샷 폴백(결정적 레벨 순서)

    async def fake_history_progress(sf, guild_id, labels, today, *, realm=None):
        return {label: [(date(2026, 6, 13), 290.0)] for label in labels.values()}

    captured: dict[str, object] = {}

    def fake_render(series, ref_date):
        captured["series"] = series
        return SimpleNamespace(getvalue=lambda: b"PNG")

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    monkeypatch.setattr(broadcast.service, "latest_snapshot_date", fake_latest)
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


# ── build_specified_payload: 지정 유저만 표시 + 빠진 인원 안내 ─────────────────


def _patch_specified(monkeypatch, targets, snap_users):
    """대상 지정 payload 경로 페이크. targets = get_targets 반환, snap_users = 스냅샷 있는 유저 id."""

    async def fake_get_targets(sf, guild_id, user_ids=None, realm=None):
        ids = set(user_ids or [])
        return [t for t in targets if t.discord_user_id in ids]

    async def fake_latest(sf, guild_id, ocids, on_or_before, realm=None):
        return on_or_before

    async def fake_snapshots_on(sf, guild_id, snap_date, realm=None):
        return [
            SimpleNamespace(
                discord_user_id=t.discord_user_id,
                ocid=t.ocid,
                snapshot_date=snap_date,
                character_level=270 + t.discord_user_id,
                exp_rate=50.0,
            )
            for t in targets
            if t.discord_user_id in snap_users
        ]

    async def fake_live_levels(deps, tgts):
        return {}

    async def fake_history_progress(sf, guild_id, labels, today, *, realm=None):
        return {label: [(today, 275.0)] for label in labels.values()}

    def fake_render(series, ref_date):
        return SimpleNamespace(getvalue=lambda: b"PNG")

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    monkeypatch.setattr(broadcast.service, "latest_snapshot_date", fake_latest)
    monkeypatch.setattr(broadcast.service, "snapshots_on", fake_snapshots_on)
    monkeypatch.setattr(broadcast.service, "live_levels", fake_live_levels)
    monkeypatch.setattr(broadcast.service, "history_progress", fake_history_progress)
    monkeypatch.setattr(
        broadcast.leaderboard_image, "render_progress_graph", fake_render
    )


async def test_build_specified_payload_shows_only_targets_with_note(monkeypatch):
    # 지정 3명 중 1명은 미등록(target 없음), 1명은 데이터 없음 → 표시 1명 + '2명 미등록/데이터 없음'.
    targets = [
        SimpleNamespace(discord_user_id=1, nickname="손바", ocid="o1"),
        SimpleNamespace(discord_user_id=2, nickname="라딘", ocid="o2"),
    ]
    _patch_specified(monkeypatch, targets, snap_users={1})  # uid2 는 스냅샷 없음
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    payload = await broadcast.build_specified_payload(deps, 1, [1, 2, 999])
    assert payload is not None
    desc = payload.embed.description or ""
    assert "손바" in desc and "라딘" not in desc  # 데이터 있는 1명만
    assert "2명은 미등록/데이터 없음" in desc  # uid2(데이터 없음) + uid999(미등록)


async def test_build_specified_payload_none_when_no_registered(monkeypatch):
    # 지정 유저가 전원 미등록(get_targets 빈 목록) → None(호출자가 안내).
    async def fake_get_targets(sf, guild_id, user_ids=None, realm=None):
        return []

    monkeypatch.setattr(broadcast, "get_targets", fake_get_targets)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    assert await broadcast.build_specified_payload(deps, 1, [7, 8]) is None


async def test_build_specified_payload_no_note_when_all_shown(monkeypatch):
    # 지정 2명 전원 표시되면 안내 줄 없음.
    targets = [
        SimpleNamespace(discord_user_id=1, nickname="손바", ocid="o1"),
        SimpleNamespace(discord_user_id=2, nickname="라딘", ocid="o2"),
    ]
    _patch_specified(monkeypatch, targets, snap_users={1, 2})
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    payload = await broadcast.build_specified_payload(deps, 1, [1, 2])
    assert payload is not None
    assert "미등록/데이터 없음" not in (payload.embed.description or "")
