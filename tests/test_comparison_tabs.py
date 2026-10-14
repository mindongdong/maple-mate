"""비교 결과 탭 전환 View(ADR-0022) 단위테스트.

컴포넌트 상태 동기화, 실행자 전용, 교체 흐름(즉시 비활성 → 빌드 → 결과·재활성), 스펙 탭 5명 절단,
연타 락, 예외 복구, 타임아웃 정리, 핸들러 배선(가드 실패엔 View 없음)을 검증한다.
"""

from __future__ import annotations

import asyncio
import random
from types import SimpleNamespace

import discord

from maple_mate.bot import comparison
from maple_mate.bot.comparison import ComparisonMessage
from maple_mate.bot.comparison_tabs import (
    NOT_AUTHOR,
    SPEC_TRUNCATED_NOTE,
    ComparisonTabsView,
)
from maple_mate.character import commands as char_commands
from maple_mate.registration.realm import Realm
from maple_mate.registration.service import Target, TargetOutcome
from maple_mate.union import commands as union_commands

SLOTS = ("모자", "무기", "장갑")


def _target(uid: int) -> Target:
    return Target(guild_id=1, discord_user_id=uid, nickname=f"닉{uid}", ocid=f"o{uid}")


class _Recorder:
    def __init__(self, result=None, error: Exception | None = None, gate=None):
        self.calls: list[tuple] = []
        self.result = result or ComparisonMessage(discord.Embed(title="결과"))
        self.error = error
        self.gate = gate

    async def __call__(self, targets, missing, notes, slot):
        self.calls.append((targets, missing, notes, slot))
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return self.result


def _view(builders=None, *, targets=None, current="spec", slot=None, notes=()):
    rec = _Recorder()
    builders = builders or {"spec": rec, "item": rec, "union": rec}
    view = ComparisonTabsView(
        author_id=1,
        targets=targets if targets is not None else [_target(1), _target(2)],
        missing=[TargetOutcome(target=_target(9), error="미등록")],
        notes=list(notes),
        current=current,
        slot=slot,
        slots=SLOTS,
        builders=builders,
    )
    return view, rec


class _Response:
    def __init__(self, view_states: list | None = None) -> None:
        self.edits: list[dict] = []
        self.sent: list[tuple] = []
        self.deferred = False
        self._view_states = view_states

    async def edit_message(self, **kwargs) -> None:
        view = kwargs["view"]
        self.edits.append(
            {
                "spec": view.spec_button.disabled,
                "union": view.union_button.disabled,
                "select": view.slot_select.disabled,
            }
        )

    async def defer(self, **kwargs) -> None:
        self.deferred = True

    async def send_message(self, *args, **kwargs) -> None:
        self.sent.append((args, kwargs))


def _click(user_id: int = 1) -> SimpleNamespace:
    edits: list[dict] = []

    async def edit_original_response(**kwargs):
        edits.append(kwargs)

    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        edit_original_response=edit_original_response,
        original_edits=edits,
    )


# ── 컴포넌트 상태 ────────────────────────────────────────────────────────────


async def test_sync_marks_current_tab():
    view, _ = _view(current="spec")
    assert view.spec_button.disabled and not view.union_button.disabled
    assert view.spec_button.style is discord.ButtonStyle.primary
    assert view.union_button.style is discord.ButtonStyle.secondary
    assert not any(o.default for o in view.slot_select.options)


async def test_sync_item_tab_selects_slot():
    view, _ = _view(current="item", slot="무기")
    assert not view.spec_button.disabled and not view.union_button.disabled
    assert [o.value for o in view.slot_select.options if o.default] == ["무기"]


# ── 실행자 전용 ──────────────────────────────────────────────────────────────


async def test_other_user_is_rejected_ephemerally():
    view, rec = _view()
    click = _click(user_id=2)
    assert await view.interaction_check(click) is False
    [(args, kwargs)] = click.response.sent
    assert args == (NOT_AUTHOR,) and kwargs["ephemeral"] is True
    assert rec.calls == []


# ── 교체 흐름 ────────────────────────────────────────────────────────────────


async def test_switch_disables_then_replaces_with_same_targets():
    file = discord.File(__file__, filename="x.png")
    union = _Recorder(result=ComparisonMessage(discord.Embed(title="유니온"), file))
    view, rec = _view({"spec": _Recorder(), "item": _Recorder(), "union": union})
    click = _click()

    await view.switch(click, "union", None)

    # 1) 즉시 응답 = 전체 비활성
    assert click.response.edits == [{"spec": True, "union": True, "select": True}]
    # 2) 같은 대상·사전 실패 그대로 전달(재해석 없음)
    [(targets, missing, notes, slot)] = union.calls
    assert [t.ocid for t in targets] == ["o1", "o2"]
    assert [o.target.ocid for o in missing] == ["o9"]
    # 3) 결과 교체 + 재활성(현재 탭만 비활성)
    [edit] = click.original_edits
    assert edit["embed"].title == "유니온" and edit["attachments"] == [file]
    assert view.current == "union" and view.union_button.disabled
    assert not view.spec_button.disabled and not view.busy


async def test_switch_to_embed_only_result_clears_attachments():
    view, rec = _view(current="union")
    click = _click()
    await view.switch(click, "item", "모자")
    [(_, _, _, slot)] = rec.calls
    assert slot == "모자"
    assert click.original_edits[0]["attachments"] == []  # 단일 상세 등 첨부 없음 → 제거
    assert view.current == "item" and view.slot == "모자"


async def test_spec_tab_truncates_to_five_with_note():
    targets = [_target(uid) for uid in range(1, 11)]  # 무인자 아이템 10명
    view, rec = _view(targets=targets, current="item", slot="무기", notes=["팬아웃"])
    await view.switch(_click(), "spec", None)
    [(spec_targets, _, notes, _)] = rec.calls
    assert [t.discord_user_id for t in spec_targets] == [
        1,
        2,
        3,
        4,
        5,
    ]  # 본인(맨 앞) 보존
    assert notes == ["팬아웃", SPEC_TRUNCATED_NOTE]


async def test_non_spec_tab_keeps_all_targets():
    targets = [_target(uid) for uid in range(1, 11)]
    view, rec = _view(targets=targets, current="item", slot="무기")
    await view.switch(_click(), "union", None)
    assert len(rec.calls[0][0]) == 10


async def test_concurrent_click_is_ignored_while_busy():
    gate = asyncio.Event()
    slow = _Recorder(gate=gate)
    view, _ = _view({"spec": slow, "item": slow, "union": slow}, current="spec")
    first = asyncio.create_task(view.switch(_click(), "union", None))
    await asyncio.sleep(0)
    second = _click()
    await view.switch(second, "item", "모자")
    assert second.response.deferred and len(slow.calls) == 1
    gate.set()
    await first
    assert len(slow.calls) == 1 and not view.busy


async def test_builder_error_reenables_components():
    broken = _Recorder(error=RuntimeError("boom"))
    view, _ = _view({"spec": broken, "item": broken, "union": broken})
    click = _click()
    await view.switch(click, "union", None)
    assert view.current == "spec"  # 실패 시 탭 유지
    assert not view.union_button.disabled and not view.slot_select.disabled
    assert click.original_edits == [{"view": view}] and not view.busy


# ── 타임아웃 ─────────────────────────────────────────────────────────────────


async def test_timeout_removes_components():
    view, _ = _view()
    edits: list[dict] = []

    async def edit(**kwargs):
        edits.append(kwargs)

    view.message = SimpleNamespace(edit=edit)
    await view.on_timeout()
    assert edits == [{"view": None}]


async def test_timeout_swallows_http_error_and_missing_message():
    view, _ = _view()
    await view.on_timeout()  # message None → no-op

    async def gone(**kwargs):
        raise discord.HTTPException(SimpleNamespace(status=404, reason="x"), "gone")

    view.message = SimpleNamespace(edit=gone)
    await view.on_timeout()


# ── 핸들러 배선 ──────────────────────────────────────────────────────────────


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(id=123)


class _DeferResponse:
    def __init__(self) -> None:
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, **kwargs) -> None:
        self._done = True


def _command_interaction(user_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=user_id),
        response=_DeferResponse(),
        followup=_Followup(),
    )


def _union_info():
    return SimpleNamespace(
        date="2026-10-11",
        union_level=9000,
        union_grade="그랜드 마스터 유니온",
        artifact_level=60,
        champion_grades=[],
    )


async def test_union_result_carries_tabs_view(monkeypatch):
    async def fake_mixed(sf, nexon, guild_id, members, nicknames, realm=None, **kw):
        return [_target(1)], []

    async def fake_fetch_each(*, targets, nexon, session_factory, command, fetch):
        return [TargetOutcome(target=t, data=_union_info()) for t in targets]

    monkeypatch.setattr(comparison, "resolve_mixed_targets", fake_mixed)
    monkeypatch.setattr(union_commands.reg, "fetch_each", fake_fetch_each)

    interaction = _command_interaction()
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await union_commands.handle_union(deps, interaction, [union_commands_member()])

    [sent] = interaction.followup.sent
    view = sent["view"]
    assert isinstance(view, ComparisonTabsView)
    assert view.current == "union" and sent["wait"] is True
    assert view.message.id == 123  # 타임아웃 정리용 핸들 보관
    assert "file" not in sent  # 단일 카드 = 첨부 없음


def union_commands_member():
    return SimpleNamespace(id=1, display_name="유저1")


async def test_guard_failure_has_no_view(monkeypatch):
    async def fake_mixed(sf, nexon, guild_id, members, nicknames, realm=None, **kw):
        return [], []  # 등록자 0명

    monkeypatch.setattr(comparison, "resolve_mixed_targets", fake_mixed)
    interaction = _command_interaction()
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await char_commands.handle_item(deps, interaction, "무기", [])
    [sent] = interaction.followup.sent
    assert "view" not in sent


async def test_tab_builders_route_to_domain_builders(monkeypatch):
    seen: dict = {}

    async def fake_spec(deps, targets, missing, *, notes=(), realm=None):
        seen["spec"] = (targets, notes, realm)
        return "spec"

    async def fake_item(deps, targets, missing, slot, *, notes=(), self_id, realm=None):
        seen["item"] = (slot, self_id, realm)
        return "item"

    async def fake_union(deps, targets, missing, *, notes=()):
        seen["union"] = notes
        return "union"

    monkeypatch.setattr(char_commands, "build_spec_message", fake_spec)
    monkeypatch.setattr(char_commands, "build_item_message", fake_item)
    monkeypatch.setattr(union_commands, "build_union_message", fake_union)

    builders = char_commands.make_tab_builders(object(), 7, Realm.CHALLENGERS)
    assert await builders["spec"]([_target(1)], [], ["n"], None) == "spec"
    assert await builders["item"]([], [], [], "장갑") == "item"
    assert await builders["union"]([], [], ["u"], None) == "union"
    assert seen == {
        "spec": ([_target(1)], ["n"], Realm.CHALLENGERS),  # realm 전달
        "item": ("장갑", 7, Realm.CHALLENGERS),
        "union": ["u"],
    }


# ── 리뷰 반영: 본인 우선 절단 · 실패 시 탭 복원 · 마지막 클릭 토큰 ─────────


async def test_spec_tab_keeps_author_when_not_first():
    # 등록자 ≤10 무인자는 선정 없이 DB 순서 — 본인(uid 1)이 맨 뒤여도 스펙 탭에 들어가야 한다.
    targets = [_target(uid) for uid in (2, 3, 4, 5, 6, 7, 8, 1)]
    view, rec = _view(targets=targets, current="item", slot="무기")
    await view.switch(_click(), "spec", None)
    [(spec_targets, _, _, _)] = rec.calls
    assert [t.discord_user_id for t in spec_targets] == [1, 2, 3, 4, 5]


async def test_failed_final_edit_restores_previous_tab():
    view, _ = _view(current="spec")
    click = _click()
    attempts: list[dict] = []

    async def edit_original_response(**kwargs):
        attempts.append(kwargs)
        if "embed" in kwargs:  # 결과 교체(첨부 413 등) 실패
            raise discord.HTTPException(SimpleNamespace(status=413, reason="x"), "big")

    click.edit_original_response = edit_original_response
    await view.switch(click, "union", None)
    assert view.current == "spec"  # 화면은 이전 탭 그대로
    assert not view.union_button.disabled  # 원하던 탭을 다시 누를 수 있다
    assert attempts[-1] == {"view": view} and not view.busy


async def test_timeout_uses_last_click_token():
    view, _ = _view()
    message_edits: list[dict] = []

    async def message_edit(**kwargs):
        message_edits.append(kwargs)

    view.message = SimpleNamespace(edit=message_edit)
    click = _click()
    await view.switch(click, "union", None)
    await view.on_timeout()
    assert click.original_edits[-1] == {"view": None}  # 클릭 토큰으로 정리
    assert message_edits == []  # 원 명령 토큰(만료 가능)은 쓰지 않음


# ── 빌더: 전원 실패 = 첨부 없는 실패 임베드 ──────────────────────────────────


async def test_union_builder_all_failed_has_no_file(monkeypatch):
    async def fake_fetch_each(*, targets, nexon, session_factory, command, fetch):
        return [TargetOutcome(target=t, error="조회 실패") for t in targets]

    monkeypatch.setattr(union_commands.reg, "fetch_each", fake_fetch_each)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    message = await union_commands.build_union_message(deps, [_target(1)], [])
    assert message.file is None and message.embed.title == "유니온 비교"


async def test_spec_builder_all_failed_has_no_file(monkeypatch):
    async def fake_fetch(deps, targets, *, command="스펙"):
        return [TargetOutcome(target=t, error="조회 실패") for t in targets]

    monkeypatch.setattr(char_commands, "fetch_spec_outcomes", fake_fetch)
    message = await char_commands.build_spec_message(object(), [_target(1)], [])
    assert message.file is None and message.embed.title == "스펙 비교"


# ── 핸들러 배선: /스펙 · /아이템 ─────────────────────────────────────────────


async def test_spec_handler_attaches_view_with_selected_targets(monkeypatch):
    registrants = [_target(uid) for uid in range(1, 8)]  # 7명 → 무인자 5명 선정
    captured: dict = {}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
        return list(registrants), []

    async def fake_build(deps, targets, missing, *, notes=(), realm=None):
        captured["targets"] = list(targets)
        return ComparisonMessage(discord.Embed(title="스펙"))

    monkeypatch.setattr(comparison, "resolve_targets", fake_resolve)
    monkeypatch.setattr(comparison, "random", random.Random(0))
    monkeypatch.setattr(char_commands, "build_spec_message", fake_build)

    interaction = _command_interaction(user_id=1)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await char_commands.handle_spec(deps, interaction, [])

    [sent] = interaction.followup.sent
    view = sent["view"]
    assert view.current == "spec"
    assert view._targets == captured["targets"] and len(view._targets) == 5
    assert "랜덤 5명" in view._notes[0]  # 탭 전환에도 같은 안내 재사용


async def test_item_handler_attaches_view_with_slot(monkeypatch):
    async def fake_mixed(sf, nexon, guild_id, members, nicknames, realm=None, **kw):
        return [_target(1), _target(2)], []

    async def fake_build(
        deps, targets, missing, slot, *, notes=(), self_id, realm=None
    ):
        return ComparisonMessage(discord.Embed(title=slot), discord.File(__file__))

    monkeypatch.setattr(comparison, "resolve_mixed_targets", fake_mixed)
    monkeypatch.setattr(char_commands, "build_item_message", fake_build)

    interaction = _command_interaction(user_id=1)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    await char_commands.handle_item(deps, interaction, "무기", [object()])

    [sent] = interaction.followup.sent
    view = sent["view"]
    assert (view.current, view.slot) == ("item", "무기")
    assert [o.value for o in view.slot_select.options if o.default] == ["무기"]
    assert "file" in sent
