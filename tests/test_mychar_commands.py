"""`/내캐릭터` 명령 단위테스트 — 트리 등록·솔로 타깃 해석·라벨·상한 절단 (ADR-0018).

DB·넥슨은 monkeypatch(가짜 타깃·outcome 주입)로 막고, 전달 계층의 분기만 검증한다:
0캐릭/DM = ephemeral 에러(defer 전 판정), 1캐릭 = 상세 임베드(graceful), 2캐릭+ = 비교표
(공유 빌드 함수 위임 + 소유자 한 줄 설명), 6캐릭+ = 레벨 상위 5 절단 + 안내 푸터.
기존 `/스펙`·`/아이템` 경로는 무수정(회귀 0) — 그쪽 테스트가 별도로 지킨다.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from maple_mate.bot.core import MapleMateBot
from maple_mate.bot.embeds import make_embed
from maple_mate.character import commands as character
from maple_mate.leaderboard import broadcast as leaderboard_broadcast
from maple_mate.mychar import commands as mychar
from maple_mate.mychar.commands import (
    MAX_COMPARE,
    char_label,
    handle_my_exp,
    handle_my_item,
    handle_my_spec,
)
from maple_mate.registration import service as reg
from maple_mate.registration.service import Target, TargetOutcome

# ── 트리 등록 ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def bot() -> MapleMateBot:
    bot = MapleMateBot(deps=object(), dev_guild_id=None)
    bot._register_commands()
    return bot


def test_group_registered_with_subcommands(bot):
    group = bot.tree.get_command("내캐릭터")
    assert group is not None
    names = {cmd.name for cmd in group.commands}
    assert names == {"스펙", "아이템", "경험치"}


def test_exp_subcommand_has_no_parameters(bot):
    # 경험치는 무인자 = 등록 전체(상한 10, 결정 4) — 캐릭터 파라미터 없음.
    group = bot.tree.get_command("내캐릭터")
    exp = group.get_command("경험치")
    assert exp.parameters == []


def test_subcommand_params_renamed_korean(bot):
    group = bot.tree.get_command("내캐릭터")
    spec = group.get_command("스펙")
    item = group.get_command("아이템")
    assert [p.display_name for p in spec.parameters] == [
        f"캐릭터{i}" for i in range(1, 6)
    ]
    assert item.parameters[0].display_name == "부위"
    assert item.parameters[0].required is True
    assert len(item.parameters[0].choices) > 0  # 기존 /아이템 part choices 재사용


# ── 라벨 (§3-2: 챌린저스만 월드 병기) ───────────────────────────────────────


def _target(ocid: str, nickname: str, world: str | None = None) -> Target:
    return Target(
        guild_id=1, discord_user_id=10, nickname=nickname, ocid=ocid, world=world
    )


def test_char_label_main_realm_plain():
    assert char_label(_target("o1", "본캐닉", "스카니아")) == "본캐닉"
    assert char_label(_target("o1", "레거시", None)) == "레거시"


def test_char_label_challengers_appends_world():
    assert char_label(_target("o2", "챌캐닉", "챌린저스3")) == "챌캐닉 (챌린저스3)"


def test_char_label_truncates_wide_nickname():
    label = char_label(_target("o1", "가나다라마바사아자차카타파하", None))
    assert label.endswith("…")


# ── 가짜 상호작용 ────────────────────────────────────────────────────────────


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


def _interaction(guild_id: int | None = 1, user_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        guild_id=guild_id,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        followup=_Followup(),
    )


def _deps() -> SimpleNamespace:
    return SimpleNamespace(session_factory=object(), nexon=object())


def _patch_targets(monkeypatch, targets: list[Target]) -> dict:
    captured: dict = {}

    async def fake(session_factory, guild_id, discord_user_id, ocids=None):
        captured["ocids"] = ocids
        if ocids is None:
            return list(targets)
        by_ocid = {t.ocid: t for t in targets}
        return [by_ocid[o] for o in ocids if o in by_ocid]

    monkeypatch.setattr(reg, "get_my_character_targets", fake)
    return captured


def _spec_data(date: str | None = "2026-07-01T00:00:00+09:00") -> SimpleNamespace:
    """single_detail_embed 가 실제 렌더 가능한 최소 SpecInfo 형태."""
    return SimpleNamespace(
        date=date,
        level=287,
        job="아크메이지(불,독)",
        combat_power="9000000000",
        ability_grade="레전드리",
        abilities=("STR +12",),
        symbols=SimpleNamespace(counts=(("아케인", 6),)),
        hexa_cores=(("코어", 30, "마스터리"),),
        hexa_stats=("마력 Lv.10",),
    )


def _patch_spec_fetch(monkeypatch) -> dict:
    captured: dict = {}

    async def fake(deps, targets, *, command="스펙"):
        captured["targets"] = targets
        captured["command"] = command
        return [TargetOutcome(target=t, data=_spec_data()) for t in targets]

    monkeypatch.setattr(character, "fetch_spec_outcomes", fake)
    return captured


def _patch_spec_build(monkeypatch) -> dict:
    captured: dict = {}

    async def fake(deps, successes, outcomes, *, title, footer, label):
        captured.update(
            successes=successes,
            outcomes=outcomes,
            title=title,
            footer=footer,
            label=label,
        )
        return make_embed(title, footer=footer), None

    monkeypatch.setattr(character, "build_spec_comparison", fake)
    return captured


# ── /내캐릭터 스펙 분기 ──────────────────────────────────────────────────────


async def test_dm_rejected_ephemeral_before_defer(monkeypatch):
    interaction = _interaction(guild_id=None)
    await handle_my_spec(_deps(), interaction, [])
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert interaction.response.deferred is False


async def test_no_characters_ephemeral_error(monkeypatch):
    _patch_targets(monkeypatch, [])
    interaction = _interaction()
    await handle_my_spec(_deps(), interaction, [])
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert "캐릭터등록" in sent["embed"].description
    assert interaction.response.deferred is False
    assert interaction.followup.sent == []


async def test_spec_unspecified_compares_all_characters(monkeypatch):
    targets = [_target(f"o{i}", f"닉{i}") for i in range(3)]
    _patch_targets(monkeypatch, targets)
    fetch = _patch_spec_fetch(monkeypatch)
    build = _patch_spec_build(monkeypatch)
    interaction = _interaction()

    await handle_my_spec(_deps(), interaction, [])

    assert interaction.response.deferred is True
    assert fetch["targets"] == targets  # 무인자 = 등록 전체(≤5)
    assert fetch["command"] == "내캐릭터 스펙"
    assert build["title"] == "내 캐릭터 스펙 비교"
    assert build["label"] is char_label  # 챌린저스 월드 병기 라벨 주입
    [sent] = interaction.followup.sent
    # 범례 대신 소유자 1명 태그(전부 본인 캐릭).
    assert sent["embed"].description == "👤 <@10>"


async def test_spec_over_limit_truncates_top5_with_note(monkeypatch):
    targets = [_target(f"o{i}", f"닉{i}") for i in range(7)]
    _patch_targets(monkeypatch, targets)
    fetch = _patch_spec_fetch(monkeypatch)
    build = _patch_spec_build(monkeypatch)
    interaction = _interaction()

    await handle_my_spec(_deps(), interaction, [])

    assert fetch["targets"] == targets[:MAX_COMPARE]  # 헬퍼 정렬(레벨순) 상위 5
    assert "7개 중" in build["footer"] and "캐릭터 파라미터" in build["footer"]


async def test_spec_specified_ocids_passed_through(monkeypatch):
    targets = [_target("o1", "일"), _target("o2", "이"), _target("o3", "삼")]
    resolver = _patch_targets(monkeypatch, targets)
    fetch = _patch_spec_fetch(monkeypatch)
    _patch_spec_build(monkeypatch)
    interaction = _interaction()

    await handle_my_spec(_deps(), interaction, ["o3", "o1"])

    assert resolver["ocids"] == ["o3", "o1"]  # 지정 순서 그대로 헬퍼에 위임
    assert [t.ocid for t in fetch["targets"]] == ["o3", "o1"]


async def test_spec_single_character_detail_embed(monkeypatch):
    _patch_targets(monkeypatch, [_target("o1", "외길닉")])
    _patch_spec_fetch(monkeypatch)
    interaction = _interaction()

    await handle_my_spec(_deps(), interaction, [])

    [sent] = interaction.followup.sent
    assert "file" not in sent  # 표 PNG 아님 — 기존 단일 상세 임베드 경로
    assert sent["embed"].title == "외길닉 스펙"


async def test_spec_all_failed_sends_error_embed(monkeypatch):
    targets = [_target("o1", "일"), _target("o2", "이")]
    _patch_targets(monkeypatch, targets)

    async def failing(deps, tgts, *, command="스펙"):
        return [TargetOutcome(target=t, error="조회 실패") for t in tgts]

    monkeypatch.setattr(character, "fetch_spec_outcomes", failing)
    interaction = _interaction()

    await handle_my_spec(_deps(), interaction, [])

    [sent] = interaction.followup.sent
    assert sent["embed"].title == "내 캐릭터 스펙"
    assert "조회 실패" in sent["embed"].description


# ── /내캐릭터 아이템 분기 ────────────────────────────────────────────────────


async def test_item_delegates_to_shared_builder(monkeypatch):
    targets = [_target("o1", "본캐"), _target("o2", "챌캐", "챌린저스3")]
    _patch_targets(monkeypatch, targets)
    fetch_captured: dict = {}
    build_captured: dict = {}

    async def fake_fetch(deps, tgts, slot, *, command="아이템"):
        fetch_captured.update(targets=tgts, slot=slot, command=command)
        return [TargetOutcome(target=t, data=SimpleNamespace(date=None)) for t in tgts]

    async def fake_build(deps, successes, outcomes, slot, *, title, footer, label):
        build_captured.update(title=title, footer=footer, label=label)
        return make_embed(title, footer=footer), None

    monkeypatch.setattr(character, "fetch_item_outcomes", fake_fetch)
    monkeypatch.setattr(character, "build_item_cards", fake_build)
    interaction = _interaction()

    await handle_my_item(_deps(), interaction, "무기", [])

    assert fetch_captured["slot"] == "무기"
    assert fetch_captured["command"] == "내캐릭터 아이템"
    assert build_captured["title"] == "내 캐릭터 아이템 — 무기"
    assert build_captured["label"] is char_label
    [sent] = interaction.followup.sent
    assert sent["embed"].description == "👤 <@10>"


# ── /내캐릭터 경험치 분기 (PR2 — 스키마 확장, ADR-0018 결정 4·5) ─────────────


def _payload_stub():
    embed = make_embed("📈 내 캐릭터 경험치")
    embed.description = "🥇 **본캐** — Lv.287 (79%)"
    return SimpleNamespace(embed=embed, to_files=lambda: ["graph.png"])


def _patch_exp_backfill(monkeypatch) -> dict:
    captured: dict = {}

    async def fake(deps, guild_id, targets, days=8):
        captured["guild_id"] = guild_id
        captured["targets"] = targets
        return None

    monkeypatch.setattr(mychar.exp_service, "backfill", fake)
    return captured


def _patch_exp_payload(monkeypatch, payload) -> dict:
    captured: dict = {}

    async def fake(deps, guild_id, targets, *, labels, title, min_ranked, realm=None):
        captured.update(
            targets=targets,
            labels=labels,
            title=title,
            min_ranked=min_ranked,
            realm=realm,
        )
        return payload

    monkeypatch.setattr(leaderboard_broadcast, "build_targets_payload", fake)
    return captured


async def test_exp_dm_rejected_ephemeral_before_defer():
    interaction = _interaction(guild_id=None)
    await handle_my_exp(_deps(), interaction)
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert interaction.response.deferred is False


async def test_exp_no_characters_ephemeral_error(monkeypatch):
    _patch_targets(monkeypatch, [])
    interaction = _interaction()
    await handle_my_exp(_deps(), interaction)
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert "캐릭터등록" in sent["embed"].description
    assert interaction.followup.sent == []


async def test_exp_backfills_all_characters_without_truncation(monkeypatch):
    # 무인자 = 등록 전체(최대 10) — _resolve_my_targets 의 상위 5 절단을 쓰지 않는다(결정 4).
    targets = [_target(f"o{i}", f"닉{i}") for i in range(10)]
    _patch_targets(monkeypatch, targets)
    backfill = _patch_exp_backfill(monkeypatch)
    build = _patch_exp_payload(monkeypatch, _payload_stub())
    interaction = _interaction()

    await handle_my_exp(_deps(), interaction)

    assert interaction.response.deferred is True
    assert backfill["targets"] == targets  # 10캐릭 전부 멱등 백필(절단 없음)
    assert build["targets"] == targets  # Top10 파이프라인에도 전부 전달


async def test_exp_sends_public_payload_with_owner_line(monkeypatch):
    targets = [_target("o1", "본캐"), _target("o2", "챌캐", "챌린저스3")]
    _patch_targets(monkeypatch, targets)
    _patch_exp_backfill(monkeypatch)
    build = _patch_exp_payload(monkeypatch, _payload_stub())
    interaction = _interaction()

    await handle_my_exp(_deps(), interaction)

    # 라벨 = ocid → char_label(챌린저스 월드 병기), realm 혼합(None), 1캐릭 게이트.
    assert build["labels"] == {"o1": "본캐", "o2": "챌캐 (챌린저스3)"}
    assert build["title"] == "📈 내 캐릭터 경험치"
    assert build["min_ranked"] == 1
    assert build["realm"] is None
    [sent] = interaction.followup.sent
    assert "ephemeral" not in sent  # 공개 발송
    assert sent["files"] == ["graph.png"]
    # 소유자 한 줄 태그가 순위판 위에 붙는다(스펙·아이템과 동일 패턴).
    assert sent["embed"].description.startswith("👤 <@10>\n\n🥇")


async def test_exp_not_ready_sends_ephemeral_notice(monkeypatch):
    _patch_targets(monkeypatch, [_target("o1", "본캐")])
    _patch_exp_backfill(monkeypatch)
    _patch_exp_payload(monkeypatch, None)  # 등재 0캐릭 → payload None
    interaction = _interaction()

    await handle_my_exp(_deps(), interaction)

    [sent] = interaction.followup.sent
    assert sent["ephemeral"] is True
    assert "잠시 후" in sent["embed"].description
