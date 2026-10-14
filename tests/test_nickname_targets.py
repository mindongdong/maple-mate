"""닉네임 직접 지정·게스트 대상(ADR-0021) + `/스펙` 무인자(ADR-0008 개정) 단위테스트.

DB(find_guild_characters_by_nicknames)·넥슨은 mock. 순수 파싱/매칭, 혼합 해석 순서·중복 제거,
게스트 실패 문구·error_log, 핸들러의 상한 사전거부(defer 전 ephemeral)와 무인자 K=5 를 검증한다.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from types import SimpleNamespace

import discord
import pytest

from maple_mate.bot import comparison
from maple_mate.bot.core import MapleMateBot, on_app_command_error
from maple_mate.character import commands as char_commands
from maple_mate.error_log.models import ErrorLog
from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration import service
from maple_mate.registration.service import (
    GUEST_NOT_FOUND,
    GUEST_USER_ID,
    Target,
    TargetOutcome,
)
from maple_mate.union import commands as union_commands


def _target(uid: int, ocid: str, nickname: str | None = None) -> Target:
    return Target(
        guild_id=1, discord_user_id=uid, nickname=nickname or f"닉{uid}", ocid=ocid
    )


def _guest(nickname: str, ocid: str) -> Target:
    return Target(
        guild_id=1, discord_user_id=GUEST_USER_ID, nickname=nickname, ocid=ocid
    )


# ── parse_nicknames / too_many_targets (순수) ───────────────────────────────


def test_parse_nicknames_trims_dedupes_case_insensitive():
    assert comparison.parse_nicknames(" 아델 , ,Hero, hero ,아델") == ["아델", "Hero"]


def test_parse_nicknames_empty():
    assert comparison.parse_nicknames(None) == []
    assert comparison.parse_nicknames(" , ") == []


def test_too_many_targets_counts_members_and_nicknames():
    assert not comparison.too_many_targets([1, 2, 3], ["a", "b"])
    assert comparison.too_many_targets([1, 2, 3], ["a", "b", "c"])


# ── _match_nicknames (순수) ──────────────────────────────────────────────────


def _char(uid: int, ocid: str, nickname: str, level: int | None = None):
    return SimpleNamespace(
        guild_id=1,
        discord_user_id=uid,
        ocid=ocid,
        maple_nickname=nickname,
        world=None,
        level=level,
    )


def test_match_nicknames_case_insensitive_and_non_representative():
    chars = [_char(10, "o-main", "본캐", 280), _char(10, "o-sub", "Bucae", 220)]
    matched = service._match_nicknames(chars, ["bucae"])
    assert matched["bucae"].ocid == "o-sub"  # 대표 아닌 캐릭도 그대로
    assert matched["bucae"].discord_user_id == 10  # 소유자 태그용 uid


def test_match_nicknames_duplicate_picks_lowest_user_then_ocid():
    chars = [_char(30, "o3", "같은닉"), _char(20, "o2", "같은닉")]
    assert service._match_nicknames(chars, ["같은닉"])["같은닉"].ocid == "o2"


# ── resolve_guest_target ─────────────────────────────────────────────────────


class _Nexon:
    def __init__(self, ocids=None, error_code="OPENAPI00004"):
        self.ocids = ocids or {}
        self.error_code = error_code
        self.calls: list[str] = []

    async def get_ocid(self, name):
        self.calls.append(name)
        if name in self.ocids:
            return self.ocids[name]
        raise NexonAPIError(self.error_code, "x", http_status=400)


async def test_resolve_guest_target_success():
    outcome = await service.resolve_guest_target(
        _Nexon({"외부닉": "ox"}), _factory()[0], 1, "외부닉"
    )
    assert outcome.ok
    assert outcome.target == _guest("외부닉", "ox")


async def test_resolve_guest_target_not_found():
    outcome = await service.resolve_guest_target(_Nexon(), _factory()[0], 1, "없는닉")
    assert outcome.error == GUEST_NOT_FOUND
    assert outcome.target.nickname == "없는닉"


async def test_resolve_guest_target_api_error_logs_and_retry_message():
    factory, added = _factory()
    outcome = await service.resolve_guest_target(
        _Nexon(error_code="OPENAPI00007"), factory, 1, "닉", command="스펙"
    )
    assert "잠시 후" in outcome.error
    [log] = [a for a in added if isinstance(a, ErrorLog)]  # 운영 요약 집계 대상
    assert log.discord_user_id is None and log.command == "스펙"


async def test_resolve_guest_target_not_found_is_not_logged():
    factory, added = _factory()
    await service.resolve_guest_target(_Nexon(), factory, 1, "없는닉")
    assert added == []  # 오타 닉은 운영 대응 대상 아님


def test_find_guild_characters_query_scopes_guild_and_lowercases():
    captured: dict = {}

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            captured["stmt"] = stmt
            return _Result()

    import asyncio

    asyncio.run(
        service.find_guild_characters_by_nicknames(
            lambda: _Session(), 7, ["Hero", "아델"]
        )
    )
    stmt = captured["stmt"]
    sql = str(stmt.compile())
    assert "character.guild_id =" in sql
    assert "lower(character.maple_nickname) IN" in sql
    assert list(stmt.compile().params.values()) == [7, ["hero", "아델"]]


# ── resolve_mixed_targets ────────────────────────────────────────────────────


def _patch_resolution(monkeypatch, *, members_result, matched, nexon):
    calls: dict = {"resolve": []}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
        calls["resolve"].append(list(members))
        return members_result

    async def fake_find(session_factory, guild_id, nicknames):
        return {k: v for k, v in matched.items() if k in {n.lower() for n in nicknames}}

    async def fake_guest(nx, session_factory, guild_id, nickname, *, command=None):
        calls.setdefault("command", command)
        return await service.resolve_guest_target(
            nexon, _factory()[0], guild_id, nickname
        )

    monkeypatch.setattr(comparison, "resolve_targets", fake_resolve)
    monkeypatch.setattr(comparison, "find_guild_characters_by_nicknames", fake_find)
    monkeypatch.setattr(comparison, "resolve_guest_target", fake_guest)
    return calls


async def test_mixed_without_nicknames_delegates_to_resolve_targets(monkeypatch):
    nexon = _Nexon()
    calls = _patch_resolution(
        monkeypatch, members_result=([_target(1, "o1")], []), matched={}, nexon=nexon
    )
    targets, missing = await comparison.resolve_mixed_targets(
        object(), nexon, 1, [], []
    )
    assert calls["resolve"] == [[]]  # 무인자 = 기존 경로 그대로(전원)
    assert [t.ocid for t in targets] == ["o1"] and missing == []


async def test_mixed_registered_match_uses_no_nexon_call(monkeypatch):
    nexon = _Nexon()
    calls = _patch_resolution(
        monkeypatch,
        members_result=([], []),
        matched={"친구부캐": _target(20, "o20sub", "친구부캐")},
        nexon=nexon,
    )
    targets, missing = await comparison.resolve_mixed_targets(
        object(), nexon, 1, [], ["친구부캐"]
    )
    assert calls["resolve"] == []  # 유저 슬롯 없으면 전원 해석 금지
    assert nexon.calls == []
    assert [(t.discord_user_id, t.ocid) for t in targets] == [(20, "o20sub")]
    assert missing == []


async def test_mixed_member_plus_friend_sub_character(monkeypatch):
    # 수용 기준: 유저1:@A + 닉네임:B의부캐 → A 대표 + B 부캐(B 태그), /id 호출 0.
    nexon = _Nexon()
    member_a = SimpleNamespace(id=10, display_name="A")
    _patch_resolution(
        monkeypatch,
        members_result=([_target(10, "oA")], []),
        matched={"b부캐": _target(20, "oBsub", "B부캐")},
        nexon=nexon,
    )
    targets, missing = await comparison.resolve_mixed_targets(
        object(), nexon, 1, [member_a], ["B부캐"]
    )
    assert [(t.discord_user_id, t.ocid) for t in targets] == [(10, "oA"), (20, "oBsub")]
    assert missing == [] and nexon.calls == []


async def test_mixed_order_dedupe_and_failures(monkeypatch):
    nexon = _Nexon({"외부": "ox", "중복대표": "o1"})
    member = SimpleNamespace(id=1, display_name="유저1")
    member_missing = TargetOutcome(target=_target(2, ""), error="미등록")
    _patch_resolution(
        monkeypatch,
        members_result=([_target(1, "o1")], [member_missing]),
        matched={},
        nexon=nexon,
    )
    targets, missing = await comparison.resolve_mixed_targets(
        object(), nexon, 1, [member], ["외부", "없는닉", "중복대표"], command="유니온"
    )
    # 유저(입력순) → 닉(입력순), 유저 대표와 같은 ocid 는 1회만.
    assert [(t.discord_user_id, t.ocid) for t in targets] == [
        (1, "o1"),
        (GUEST_USER_ID, "ox"),
    ]
    assert [o.target.nickname for o in missing] == ["닉2", "없는닉"]
    assert missing[1].error == GUEST_NOT_FOUND


# ── _fetch_one 게스트 분기 ───────────────────────────────────────────────────


def _factory():
    added: list[object] = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *a, **k):
            raise AssertionError("게스트는 DB 갱신 대상이 아니다")

        async def commit(self):
            return None

        def add(self, obj):
            added.append(obj)

    return (lambda: _Session()), added


async def test_guest_stale_ocid_skips_refresh_with_guest_message():
    factory, _ = _factory()
    nexon = _Nexon()

    async def fetch(ocid):
        raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)

    [outcome] = await service.fetch_each(
        targets=[_guest("외부", "ox")],
        nexon=nexon,
        session_factory=factory,
        command="스펙",
        fetch=fetch,
    )
    assert outcome.error == GUEST_NOT_FOUND
    assert nexon.calls == []  # 닉 재조회(refresh_ocid) 안 함


async def test_guest_hard_failure_logs_without_user_id():
    factory, added = _factory()

    async def fetch(ocid):
        raise NexonAPIError("OPENAPI00007", "rate", http_status=429)

    await service.fetch_each(
        targets=[_guest("외부", "ox")],
        nexon=_Nexon(),
        session_factory=factory,
        command="스펙",
        fetch=fetch,
    )
    [log] = [a for a in added if isinstance(a, ErrorLog)]
    assert log.discord_user_id is None


# ── 핸들러: 상한 사전거부 / `/스펙` 무인자 K=5 ──────────────────────────────


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


def _interaction(user_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        followup=_Followup(),
    )


class _Namespace:
    def __init__(self, **values) -> None:
        self._values = values

    def __iter__(self):
        return iter(self._values.items())

    def __getattr__(self, name):  # discord Namespace 처럼 없는 키는 None
        return self.__dict__.get("_values", {}).get(name)


def _member_obj() -> discord.Member:
    return object.__new__(discord.Member)  # isinstance 판정용(초기화 불필요)


def _check_interaction(namespace: _Namespace, user_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=user_id),
        namespace=namespace,
        created_at=datetime.now(timezone.utc),
    )


async def test_target_limit_check_counts_members_and_nicknames():
    [predicate] = _limit_predicates()
    ok = _Namespace(유저1=_member_obj(), 유저2=_member_obj(), 닉네임="a, b, c")
    assert await predicate(_check_interaction(ok)) is True
    over = _Namespace(대상1=_member_obj(), 부위="무기", 닉네임="a,b,c,d,e")
    with pytest.raises(comparison.TooManyTargets):
        await predicate(_check_interaction(over))


def _limit_predicates():
    check = comparison.target_limit_check()

    async def callback(interaction):  # pragma: no cover - 체크만 꺼낸다
        return None

    return check(callback).__discord_app_commands_checks__


def _tree_command(name: str):
    bot = MapleMateBot(deps=object(), dev_guild_id=None)
    bot._register_commands()
    return next(c for c in bot.tree.get_commands() if c.name == name)


async def test_rejection_runs_before_cooldown_and_keeps_token():
    # 리뷰 지적: 상한 거부가 10초 쿨다운을 소모하면 입력을 고쳐 재실행할 때 쿨다운에 걸린다.
    for name, slot in (("스펙", "유저1"), ("아이템", "대상1"), ("유니온", "대상1")):
        command = _tree_command(name)
        over = _Namespace(**{slot: _member_obj(), "닉네임": "a,b,c,d,e"})
        with pytest.raises(comparison.TooManyTargets):
            for predicate in command.checks:
                await predicate(_check_interaction(over))
        fixed = _Namespace(**{slot: _member_obj(), "닉네임": "a"})
        for predicate in command.checks:  # 같은 유저 즉시 재실행 — 쿨다운 미소모
            assert await predicate(_check_interaction(fixed)) is True


async def test_error_handler_answers_too_many_ephemerally():
    interaction = _interaction()
    await on_app_command_error(
        interaction, comparison.TooManyTargets(comparison.TOO_MANY_TARGETS)
    )
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert sent["embed"].description == comparison.TOO_MANY_TARGETS


def _spec_info():
    return SimpleNamespace(date="2026-10-11", combat_power="100")


async def test_spec_unspecified_selects_five_with_self(monkeypatch):
    registrants = [_target(uid, f"o{uid}") for uid in range(1, 8)]  # 7명, 본인 uid=1
    captured: dict = {}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
        assert members == []
        return list(registrants), []

    async def fake_fetch(deps, targets, *, command="스펙"):
        captured["targets"] = list(targets)
        return [TargetOutcome(target=t, data=_spec_info()) for t in targets]

    async def fake_build(deps, successes, outcomes, *, title, footer, label=None):
        captured["footer"] = footer
        return SimpleNamespace(), SimpleNamespace()

    monkeypatch.setattr(comparison, "resolve_targets", fake_resolve)
    monkeypatch.setattr(comparison, "random", random.Random(0))
    monkeypatch.setattr(char_commands, "fetch_spec_outcomes", fake_fetch)
    monkeypatch.setattr(char_commands, "build_spec_comparison", fake_build)

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await char_commands.handle_spec(deps, _interaction(user_id=1), [])

    uids = [t.discord_user_id for t in captured["targets"]]
    assert len(uids) == 5 and uids[0] == 1  # 본인 맨 앞 포함
    assert "등록자 7명 중 본인 포함 랜덤 5명" in captured["footer"]


async def test_spec_guest_single_detail_has_no_mention(monkeypatch):
    async def fake_mixed(
        sf, nexon, guild_id, members, nicknames, realm=None, *, command=None
    ):
        assert nicknames == ["외부닉"]
        return [_guest("외부닉", "ox")], []

    async def fake_fetch(deps, targets, *, command="스펙"):
        info = SimpleNamespace(
            date="2026-10-11",
            combat_power="100",
            level=280,
            job="히어로",
            ability_grade=None,
            abilities=(),
            symbols=SimpleNamespace(counts=()),
            hexa_cores=(),
            hexa_stats=(),
        )
        return [TargetOutcome(target=t, data=info) for t in targets]

    monkeypatch.setattr(comparison, "resolve_mixed_targets", fake_mixed)
    monkeypatch.setattr(char_commands, "fetch_spec_outcomes", fake_fetch)

    interaction = _interaction()
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await char_commands.handle_spec(deps, interaction, [], nicknames=["외부닉"])

    [sent] = interaction.followup.sent
    assert sent["embed"].title == "외부닉 스펙"
    assert not sent["embed"].description  # 게스트 = 태그 없음
    assert "랜덤" not in sent["embed"].footer.text  # 지정 실행엔 팬아웃 안내 없음


def _union_info():
    return SimpleNamespace(
        date="2026-10-11",
        union_level=9000,
        union_grade="그랜드 마스터 유니온",
        artifact_level=60,
        champion_grades=[],
    )


def _patch_union_nicknames(monkeypatch, targets, missing):
    async def fake_mixed(
        sf, nexon, guild_id, members, nicknames, realm=None, *, command=None
    ):
        assert command == "유니온"
        return list(targets), list(missing)

    async def fake_fetch_each(*, targets, nexon, session_factory, command, fetch):
        return [TargetOutcome(target=t, data=_union_info()) for t in targets]

    def no_random(*a, **k):
        raise AssertionError("닉네임 지정 실행은 랜덤 선정을 하지 않는다")

    monkeypatch.setattr(comparison, "resolve_mixed_targets", fake_mixed)
    monkeypatch.setattr(union_commands.reg, "fetch_each", fake_fetch_each)
    monkeypatch.setattr(comparison, "select_with_self", no_random)


async def test_union_guest_single_card_has_no_blank_first_line(monkeypatch):
    _patch_union_nicknames(monkeypatch, [_guest("외부닉", "ox")], [])
    interaction = _interaction()
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await union_commands.handle_union(deps, interaction, [], nicknames=["외부닉"])
    [sent] = interaction.followup.sent
    [field] = sent["embed"].fields
    assert field.value.startswith("유니온 Lv.")
    assert "랜덤" not in sent["embed"].footer.text


async def test_union_missing_nickname_is_partial_success(monkeypatch):
    missing = TargetOutcome(target=_guest("없는닉", ""), error=GUEST_NOT_FOUND)
    _patch_union_nicknames(
        monkeypatch, [_guest("외부1", "o1"), _guest("외부2", "o2")], [missing]
    )
    interaction = _interaction()
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await union_commands.handle_union(
        deps, interaction, [], nicknames=["외부1", "외부2", "없는닉"]
    )
    [sent] = interaction.followup.sent
    assert sent["file"] is not None  # 성공 2명 = 비교표
    [failure] = [f for f in sent["embed"].fields if "조회 실패" in f.name]
    assert "없는닉" in failure.value and GUEST_NOT_FOUND in failure.value


async def test_item_nicknames_only_skips_random(monkeypatch):
    captured: dict = {}

    async def fake_mixed(
        sf, nexon, guild_id, members, nicknames, realm=None, *, command=None
    ):
        assert command == "아이템"
        return [_guest("외부", "ox"), _target(1, "o1")], []

    async def fake_fetch(deps, targets, slot, *, command="아이템"):
        captured["targets"] = list(targets)
        return [
            TargetOutcome(target=t, data=SimpleNamespace(date="2026-10-11"))
            for t in targets
        ]

    async def fake_cards(deps, successes, outcomes, slot, *, title, footer, label=None):
        captured["order"] = [o.target.ocid for o in successes]
        captured["footer"] = footer
        return SimpleNamespace(), SimpleNamespace()

    def no_random(*a, **k):
        raise AssertionError("닉네임 지정 실행은 랜덤 선정을 하지 않는다")

    monkeypatch.setattr(comparison, "resolve_mixed_targets", fake_mixed)
    monkeypatch.setattr(comparison, "select_with_self", no_random)
    monkeypatch.setattr(char_commands, "fetch_item_outcomes", fake_fetch)
    monkeypatch.setattr(char_commands, "build_item_cards", fake_cards)

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await char_commands.handle_item(
        deps, _interaction(user_id=1), "무기", [], nicknames=["외부", "내닉"]
    )
    assert captured["order"] == ["o1", "ox"]  # 본인 먼저 + 나머지 입력순
    assert "랜덤" not in captured["footer"] and "전원" not in captured["footer"]
