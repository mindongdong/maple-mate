"""`/캐릭터목록` 관리 허브(ADR-0023) 단위테스트.

서비스(삭제·대표 자동 복귀·키 삭제)는 가짜 세션으로 발행 SQL·반환값을, View 는 상태 전환·확인 단계·
서비스 호출 인자·결과 문구를, 핸들러는 View 부착 조건을 검증한다(DB·디스코드 없이).
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from maple_mate.registration import commands as reg_commands
from maple_mate.registration import service
from maple_mate.registration.service import CharacterInfo


def _info(ocid: str, nick: str, level: int, rep: bool = False) -> CharacterInfo:
    return CharacterInfo(ocid=ocid, nickname=nick, level=level, is_representative=rep)


def _char_row(ocid: str, nick: str):
    return SimpleNamespace(
        guild_id=1, discord_user_id=10, ocid=ocid, maple_nickname=nick, level=200
    )


# ── 서비스: 가짜 세션 ────────────────────────────────────────────────────────


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, *, chars=(), reg=None, rowcount=0):
        self.chars = list(chars)
        self.reg = reg
        self.rowcount = rowcount
        self.statements: list = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        if stmt.is_select:
            return _Rows(self.chars)
        return SimpleNamespace(rowcount=self.rowcount)

    async def get(self, model, key):
        return self.reg

    async def commit(self):
        self.committed = True


def _sql(stmt) -> str:
    return str(stmt.compile())


async def test_delete_characters_only_own_and_resets_rep_pointer():
    session = _Session(chars=[_char_row("o1", "본캐"), _char_row("o2", "부캐")])
    removed = await service.delete_characters(lambda: session, 1, 10, ["o2", "남의것"])

    assert removed == ["부캐"]
    _, delete_stmt, update_stmt = session.statements
    assert delete_stmt.is_delete and "character.ocid IN" in _sql(delete_stmt)
    assert list(delete_stmt.compile().params.values())[-1] == ["o2"]  # 본인 것만
    # 지운 캐릭터가 대표였으면 포인터를 NULL(자동)로
    assert update_stmt.is_update and "representative_ocid IN" in _sql(update_stmt)
    assert session.committed


async def test_delete_characters_nothing_matching_is_noop():
    session = _Session(chars=[_char_row("o1", "본캐")])
    assert await service.delete_characters(lambda: session, 1, 10, ["x"]) == []
    assert len(session.statements) == 1 and not session.committed  # 조회만
    assert await service.delete_characters(lambda: _Session(), 1, 10, []) == []


async def test_reset_representative_sets_null():
    session = _Session()
    await service.reset_representative(lambda: session, 1, 10)
    [stmt] = session.statements
    assert stmt.is_update and stmt.compile().params["representative_ocid"] is None


async def test_remove_key_clears_key_and_scheduler_subscription():
    session = _Session(reg=SimpleNamespace(api_key_encrypted="enc"), rowcount=1)
    had_key, unsubscribed = await service.remove_personal_key(lambda: session, 1, 10)
    assert (had_key, unsubscribed) == (True, True)
    update_stmt, delete_stmt = session.statements
    assert update_stmt.compile().params["api_key_encrypted"] is None
    assert "scheduler_subscription" in _sql(delete_stmt)


async def test_remove_key_without_key_still_clears_stale_subscription():
    session = _Session(reg=SimpleNamespace(api_key_encrypted=None), rowcount=0)
    assert await service.remove_personal_key(lambda: session, 1, 10) == (False, False)
    [delete_stmt] = session.statements  # 키 UPDATE 없음
    assert delete_stmt.is_delete


# ── 임베드(순수) ─────────────────────────────────────────────────────────────


def test_list_embed_note_and_empty_state():
    embed = reg_commands.character_list_embed([], True, "🔑 결과")
    assert embed.description.startswith("🔑 결과")
    assert "등록된 캐릭터가 없어요" in embed.description
    assert "개인 키: 등록됨" in embed.description
    assert embed.title == "캐릭터 목록 (0/10)"


# ── View ─────────────────────────────────────────────────────────────────────


class _Response:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit_message(self, **kwargs) -> None:
        self.edits.append(kwargs)


def _click() -> SimpleNamespace:
    original: list[dict] = []

    async def edit_original_response(**kwargs):
        original.append(kwargs)

    return SimpleNamespace(
        response=_Response(),
        edit_original_response=edit_original_response,
        original_edits=original,
    )


def _labels(view) -> list[tuple[str, bool]]:
    return [
        (item.label, item.disabled)
        for item in view.children
        if isinstance(item, discord.ui.Button)
    ]


def _view(monkeypatch, characters, has_key=True, reload_to=None):
    async def fake_get_characters(sf, scope, uid):
        return reload_to if reload_to is not None else characters

    async def fake_has_key(sf, scope, uid):
        return has_key

    monkeypatch.setattr(reg_commands.service, "get_characters", fake_get_characters)
    monkeypatch.setattr(reg_commands.service, "has_personal_key", fake_has_key)
    deps = SimpleNamespace(session_factory=object())
    return reg_commands.CharacterManageView(
        deps, scope=1, user_id=10, characters=characters, has_key=has_key
    )


async def test_hub_buttons_reflect_state(monkeypatch):
    view = _view(monkeypatch, [], has_key=False)
    assert _labels(view) == [
        ("🗑️ 캐릭터 삭제", True),
        ("👑 대표 변경", True),
        ("🔑 키 삭제", True),
    ]
    view = _view(monkeypatch, [_info("o1", "본캐", 280, True)], has_key=True)
    assert all(not disabled for _, disabled in _labels(view))


async def test_delete_flow_select_confirm_and_result(monkeypatch):
    chars = [_info("o1", "본캐", 280, rep=True), _info("o2", "부캐", 250)]
    view = _view(monkeypatch, chars, reload_to=[_info("o2", "부캐", 250, True)])
    calls: list = []

    async def fake_delete(sf, scope, uid, ocids):
        calls.append((scope, uid, list(ocids)))
        return ["본캐"]

    monkeypatch.setattr(reg_commands.service, "delete_characters", fake_delete)

    click = _click()
    await view._open_delete(click)
    assert view.mode == "delete_select" and view.select.max_values == 2

    view.select._values = ["o1"]
    await view._picked_delete(_click())
    assert view.mode == "delete_confirm" and calls == []  # 확인 전엔 삭제 안 함
    assert _labels(view) == [("1개 삭제", False), ("취소", False)]

    done = _click()
    await view._confirm_delete(done)
    assert calls == [(1, 10, ["o1"])]
    assert view.mode == "hub"
    description = done.response.edits[-1]["embed"].description
    assert "본캐** 삭제했어요" in description
    assert "자동 선택" in description  # 대표를 지웠으니 자동 복귀 안내
    assert [c.ocid for c in view.characters] == ["o2"]  # 재조회 반영


async def test_cancel_returns_to_hub_without_deleting(monkeypatch):
    view = _view(monkeypatch, [_info("o1", "본캐", 280, True)])
    await view._open_delete(_click())
    view.select._values = ["o1"]
    await view._picked_delete(_click())
    await view._cancel(_click())
    assert view.mode == "hub" and view._pending == []


async def test_rep_auto_and_manual(monkeypatch):
    chars = [_info("o1", "본캐", 280, True), _info("o2", "부캐", 250)]
    view = _view(monkeypatch, chars)
    seen: list = []

    async def fake_reset(sf, scope, uid):
        seen.append("reset")

    async def fake_set(sf, scope, uid, ocid):
        seen.append(ocid)
        return "부캐"

    monkeypatch.setattr(reg_commands.service, "reset_representative", fake_reset)
    monkeypatch.setattr(reg_commands.service, "set_representative", fake_set)

    await view._open_rep(_click())
    assert view.select.options[0].value == reg_commands._AUTO_REP
    view.select._values = [reg_commands._AUTO_REP]
    click = _click()
    await view._picked_rep(click)
    assert "자동(최고 레벨)" in click.response.edits[-1]["embed"].description

    await view._open_rep(_click())
    view.select._values = ["o2"]
    click = _click()
    await view._picked_rep(click)
    assert seen == ["reset", "o2"]
    assert "**부캐** 으로 지정" in click.response.edits[-1]["embed"].description


async def test_key_delete_confirms_then_reports_unsubscribe(monkeypatch):
    view = _view(monkeypatch, [_info("o1", "본캐", 280, True)], has_key=True)
    calls: list = []

    async def fake_remove(sf, scope, uid):
        calls.append((scope, uid))
        return True, True

    monkeypatch.setattr(reg_commands.service, "remove_personal_key", fake_remove)

    await view._open_key(_click())
    assert view.mode == "key_confirm" and calls == []
    assert _labels(view) == [("키 삭제", False), ("취소", False)]

    done = _click()
    await view._confirm_key(done)
    assert calls == [(1, 10)]
    description = done.response.edits[-1]["embed"].description
    assert "개인 키를 삭제했어요" in description and "구독도 해제" in description


async def test_timeout_uses_last_click_token(monkeypatch):
    view = _view(monkeypatch, [_info("o1", "본캐", 280, True)])
    click = _click()
    await view._open_rep(click)
    await view.on_timeout()
    assert click.original_edits == [{"view": None}]


# ── 핸들러: View 부착 조건 ───────────────────────────────────────────────────


class _DeferResponse:
    def __init__(self) -> None:
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, **kwargs) -> None:
        self._done = True


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(id=1)


def _command_interaction():
    return SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=10),
        response=_DeferResponse(),
        followup=_Followup(),
    )


async def test_list_without_anything_has_no_view(monkeypatch):
    _view(monkeypatch, [], has_key=False)  # 서비스 패치 재사용
    interaction = _command_interaction()
    await reg_commands.handle_character_list(
        SimpleNamespace(session_factory=object()), interaction
    )
    [sent] = interaction.followup.sent
    assert "view" not in sent and sent["ephemeral"] is True


async def test_list_with_key_only_offers_key_delete(monkeypatch):
    _view(monkeypatch, [], has_key=True)
    interaction = _command_interaction()
    await reg_commands.handle_character_list(
        SimpleNamespace(session_factory=object()), interaction
    )
    [sent] = interaction.followup.sent
    view = sent["view"]
    assert sent["ephemeral"] is True and sent["wait"] is True
    assert _labels(view)[2] == ("🔑 키 삭제", False)
    assert _labels(view)[0] == ("🗑️ 캐릭터 삭제", True)
