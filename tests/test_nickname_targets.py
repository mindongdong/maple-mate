"""닉네임 직접 지정·게스트 대상(ADR-0021) + `/스펙` 무인자(ADR-0008 개정) 단위테스트.

DB(find_guild_characters_by_nicknames)·넥슨은 mock. 순수 파싱/매칭, 혼합 해석 순서·중복 제거,
게스트 실패 문구·error_log, 핸들러의 상한 사전거부(defer 전 ephemeral)와 무인자 K=5 를 검증한다.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

from maple_mate.bot import comparison
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
    outcome = await service.resolve_guest_target(_Nexon({"외부닉": "ox"}), 1, "외부닉")
    assert outcome.ok
    assert outcome.target == _guest("외부닉", "ox")


async def test_resolve_guest_target_not_found():
    outcome = await service.resolve_guest_target(_Nexon(), 1, "없는닉")
    assert outcome.error == GUEST_NOT_FOUND
    assert outcome.target.nickname == "없는닉"


async def test_resolve_guest_target_api_error_is_retry_message():
    outcome = await service.resolve_guest_target(
        _Nexon(error_code="OPENAPI00007"), 1, "닉"
    )
    assert "잠시 후" in outcome.error


# ── resolve_mixed_targets ────────────────────────────────────────────────────


def _patch_resolution(monkeypatch, *, members_result, matched, nexon):
    calls: dict = {"resolve": []}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
        calls["resolve"].append(list(members))
        return members_result

    async def fake_find(session_factory, guild_id, nicknames):
        return {k: v for k, v in matched.items() if k in {n.lower() for n in nicknames}}

    async def fake_guest(nx, guild_id, nickname):
        return await service.resolve_guest_target(nexon, guild_id, nickname)

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
        object(), nexon, 1, [member], ["외부", "없는닉", "중복대표"]
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


async def test_too_many_rejected_before_defer_without_lookup(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("상한 초과는 조회 전에 거부돼야 한다")

    monkeypatch.setattr(comparison, "resolve_mixed_targets", boom)
    members = [SimpleNamespace(id=i) for i in range(3)]
    for handler in (
        lambda i: char_commands.handle_spec(
            object(), i, members, nicknames=["a", "b", "c"]
        ),
        lambda i: char_commands.handle_item(
            object(), i, "무기", members, nicknames=["a", "b", "c"]
        ),
        lambda i: union_commands.handle_union(
            object(), i, members, nicknames=["a", "b", "c"]
        ),
    ):
        interaction = _interaction()
        await handler(interaction)
        assert not interaction.response.deferred
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
    async def fake_mixed(sf, nexon, guild_id, members, nicknames, realm=None):
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
