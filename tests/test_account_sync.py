"""키 기반 계정 동기화(ADR-0025) 단위테스트.

클라이언트(`character/list` 평탄화), 순수 대조(plan_sync), 서비스(조회 실패 분기·일괄 등록 상한 재확인·갱신),
동기화 View(5개씩 페이지·페이지 넘어 선택 유지·남은 자리 상한·가져오기·정리·나가기), 진입점(허브 버튼·/키등록)을
검증한다. DB·디스코드·넥슨은 모두 가짜.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord
import httpx
from cryptography.fernet import Fernet

from maple_mate.nexon.client import NexonClient
from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration import commands as reg_commands
from maple_mate.registration import service
from maple_mate.registration.service import AccountCharacter, CharacterInfo
from maple_mate.security.crypto import KeyCipher


def _acc(ocid, nick, level, world="크로아", job="히어로") -> AccountCharacter:
    return AccountCharacter(ocid=ocid, nickname=nick, world=world, job=job, level=level)


def _info(ocid, nick, level, world="크로아", rep=False) -> CharacterInfo:
    return CharacterInfo(
        ocid=ocid, nickname=nick, level=level, is_representative=rep, world=world
    )


# ── 클라이언트 ───────────────────────────────────────────────────────────────


async def test_character_list_flattens_accounts_with_personal_key():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers["x-nxopen-api-key"]
        return httpx.Response(
            200,
            json={
                "account_list": [
                    {"account_id": "a1", "character_list": [{"ocid": "o1"}]},
                    {"account_id": "a2", "character_list": [{"ocid": "o2"}]},
                ]
            },
        )

    client = NexonClient(
        "app_key",
        throttle=0,
        personal_throttle=0,
        transport=httpx.MockTransport(handler),
    )
    assert await client.character_list("personal") == [{"ocid": "o1"}, {"ocid": "o2"}]
    assert seen == {"path": "/maplestory/v1/character/list", "key": "personal"}
    await client.aclose()


# ── 순수 변환·대조 ───────────────────────────────────────────────────────────


def test_to_account_characters_parses_and_skips_invalid():
    rows = service.to_account_characters(
        [
            {
                "ocid": "o1",
                "character_name": "본캐",
                "world_name": "크로아",
                "character_class": "히어로",
                "character_level": "285",
            },
            {"ocid": "", "character_name": "빈ocid"},
            {"ocid": "o3", "character_name": "레벨이상", "character_level": "?"},
        ]
    )
    assert rows == [
        _acc("o1", "본캐", 285),
        AccountCharacter(
            ocid="o3", nickname="레벨이상", world=None, job=None, level=None
        ),
    ]


def test_plan_sync_buckets():
    registered = [
        _info("o1", "옛닉", 280),  # 계정에 있음 + 닉·레벨 바뀜 → 갱신
        _info("o2", "그대로", 270),  # 계정에 있음 + 변화 없음
        _info("oX", "남의캐", 260),  # 계정에 없음 → 정리 제안
    ]
    account = [
        _acc("o1", "새닉", 281),
        _acc("o2", "그대로", 270),
        _acc("o4", "부캐", 200),
        _acc("o5", "본계정고렙", 290),
        _acc("o6", "챌캐", 250, world="챌린저스3"),  # 챌린저스 제외
    ]
    plan = service.plan_sync(registered, account)
    assert [a.ocid for a in plan.updates] == ["o1"]
    assert [a.ocid for a in plan.candidates] == ["o5", "o4"]  # 레벨 내림차순
    assert [m.ocid for m in plan.missing] == ["oX"]


# ── 서비스 ───────────────────────────────────────────────────────────────────


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, *, reg=None, chars=()):
        self.reg = reg
        self.chars = list(chars)
        self.statements: list = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, key):
        return self.reg

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Rows(self.chars) if stmt.is_select else SimpleNamespace(rowcount=1)

    async def commit(self):
        self.committed = True


_CIPHER = KeyCipher(Fernet.generate_key())


class _Nexon:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.keys = rows or [], error, []

    async def character_list(self, api_key):
        self.keys.append(api_key)
        if self.error:
            raise self.error
        return self.rows


async def _fetch(session, nexon):
    return await service.fetch_account_characters(
        nexon=nexon,
        cipher=_CIPHER,
        session_factory=lambda: session,
        guild_id=1,
        discord_user_id=10,
    )


async def test_fetch_account_characters_paths():
    reg = SimpleNamespace(api_key_encrypted=_CIPHER.encrypt("my-key"))
    nexon = _Nexon(
        rows=[{"ocid": "o1", "character_name": "본캐", "character_level": 285}]
    )
    chars, error = await _fetch(_Session(reg=reg), nexon)
    assert error is None and [c.ocid for c in chars] == ["o1"]
    assert nexon.keys == ["my-key"]  # 복호화한 개인 키로 1콜

    assert (await _fetch(_Session(reg=None), _Nexon()))[1].startswith(
        "개인 키가 없어요"
    )
    invalid = _Nexon(error=NexonAPIError("OPENAPI00005", "x", http_status=400))
    assert "무효" in (await _fetch(_Session(reg=reg), invalid))[1]
    limited = _Nexon(error=NexonAPIError("OPENAPI00007", "x", http_status=429))
    assert "잠시 후" in (await _fetch(_Session(reg=reg), limited))[1]


def _char_row(ocid):
    return SimpleNamespace(ocid=ocid, guild_id=1, discord_user_id=10)


async def test_import_rechecks_cap_and_skips_existing():
    existing = [_char_row(f"e{i}") for i in range(8)]  # 8/10 등록
    session = _Session(chars=existing)
    picks = [
        _acc("e0", "이미", 280),
        _acc("n1", "새1", 270),
        _acc("n2", "새2", 260),
        _acc("n3", "새3", 250),
    ]
    added, skipped = await service.import_characters(lambda: session, 1, 10, picks)
    assert added == ["새1", "새2"] and skipped == 1  # 남은 2자리만, 기등록은 제외
    insert_chars = session.statements[-1]
    values = insert_chars.compile().params
    assert {v for k, v in values.items() if k.startswith("ocid")} == {"n1", "n2"}
    assert session.committed


async def test_import_with_no_room_writes_nothing():
    session = _Session(chars=[_char_row(f"e{i}") for i in range(10)])
    assert await service.import_characters(
        lambda: session, 1, 10, [_acc("n1", "새", 1)]
    ) == ([], 1)
    assert len(session.statements) == 1 and not session.committed


async def test_apply_account_updates_issues_scoped_updates():
    session = _Session()
    await service.apply_account_updates(
        lambda: session, 1, 10, [_acc("o1", "새닉", 281)]
    )
    [stmt] = session.statements
    params = stmt.compile().params
    assert (
        stmt.is_update and params["maple_nickname"] == "새닉" and params["level"] == 281
    )
    assert params["guild_id_1"] == 1 and params["discord_user_id_1"] == 10
    await service.apply_account_updates(
        lambda: _Session(), 1, 10, []
    )  # 빈 목록은 no-op


# ── 동기화 View ──────────────────────────────────────────────────────────────


class _Response:
    def __init__(self) -> None:
        self.edits: list[dict] = []
        self.deferred = False

    async def edit_message(self, **kwargs) -> None:
        self.edits.append(kwargs)

    async def defer(self, **kwargs) -> None:
        self.deferred = True


def _click(values=None):
    original: list[dict] = []

    async def edit_original_response(**kwargs):
        original.append(kwargs)

    return SimpleNamespace(
        data={"values": values} if values is not None else {},
        response=_Response(),
        edit_original_response=edit_original_response,
        original_edits=original,
        user=SimpleNamespace(id=10),
    )


def _sync_view(monkeypatch, *, account, registered, back=None, reload_to=None):
    async def fake_get_characters(sf, scope, uid):
        return reload_to if reload_to is not None else registered

    monkeypatch.setattr(reg_commands.service, "get_characters", fake_get_characters)
    deps = SimpleNamespace(session_factory=object(), nexon=object(), cipher=object())
    return reg_commands.AccountSyncView(
        deps,
        scope=1,
        user_id=10,
        account=account,
        registered=registered,
        updated=0,
        back=back,
    )


def _labels(view):
    return [
        (i.label, i.disabled) for i in view.children if isinstance(i, discord.ui.Button)
    ]


def _select(view):
    [s] = [i for i in view.children if isinstance(i, discord.ui.Select)]
    return s


_TWELVE = [_acc(f"c{i:02d}", f"캐{i:02d}", 290 - i) for i in range(12)]


async def test_pages_of_five_by_level(monkeypatch):
    view = _sync_view(monkeypatch, account=_TWELVE, registered=[])
    assert view.pages == 3
    assert [o.value for o in _select(view).options] == [
        "c00",
        "c01",
        "c02",
        "c03",
        "c04",
    ]
    assert ("◀ 이전", True) in _labels(view) and ("1 / 3", True) in _labels(view)
    await view._next(_click())
    await view._next(_click())
    assert [o.value for o in _select(view).options] == ["c10", "c11"]
    assert ("다음 ▶", True) in _labels(view)


async def test_selection_persists_across_pages(monkeypatch):
    view = _sync_view(monkeypatch, account=_TWELVE, registered=[])
    await view._picked_import(_click(["c00", "c01"]))
    await view._next(_click())
    await view._picked_import(_click(["c05"]))
    await view._prev(_click())
    assert list(view.picked) == ["c00", "c01", "c05"]
    assert {o.value for o in _select(view).options if o.default} == {"c00", "c01"}
    await view._picked_import(_click(["c01"]))  # 1페이지에서 c00 해제
    assert list(view.picked) == ["c05", "c01"]
    assert ("✅ 2개 가져오기", False) in _labels(view)


async def test_room_caps_selection(monkeypatch):
    registered = [_info(f"r{i}", f"등록{i}", 200) for i in range(8)]  # 남은 자리 2
    view = _sync_view(monkeypatch, account=_TWELVE, registered=registered)
    assert view.room == 2 and _select(view).max_values == 2
    await view._picked_import(
        _click(["c00", "c01", "c02"])
    )  # 넘치면 앞에서부터 자리만큼
    assert list(view.picked) == ["c00", "c01"]
    await view._next(_click())
    assert _select(view).disabled  # 다른 페이지는 더 고를 자리가 없음


async def test_import_calls_service_and_refreshes(monkeypatch):
    calls: list = []

    async def fake_import(sf, scope, uid, picks):
        calls.append([p.ocid for p in picks])
        return [p.nickname for p in picks], 0

    monkeypatch.setattr(reg_commands.service, "import_characters", fake_import)
    view = _sync_view(
        monkeypatch,
        account=_TWELVE,
        registered=[],
        reload_to=[_info("c00", "캐00", 290)],
    )
    await view._picked_import(_click(["c00"]))
    done = _click()
    await view._confirm_import(done)
    assert calls == [["c00"]]
    assert "캐00** 가져왔어요" in done.original_edits[-1]["embed"].description
    assert "c00" not in [
        c.ocid for c in view.plan.candidates
    ]  # 가져온 건 후보에서 빠짐
    assert view.picked == {}


async def test_cleanup_flow_deletes_selected_missing(monkeypatch):
    calls: list = []

    async def fake_delete(sf, scope, uid, ocids):
        calls.append(list(ocids))
        return ["남의캐"], False

    monkeypatch.setattr(reg_commands.service, "delete_characters", fake_delete)
    view = _sync_view(
        monkeypatch,
        account=[_acc("o1", "본캐", 280)],
        registered=[_info("o1", "본캐", 280), _info("oX", "남의캐", 260)],
        reload_to=[_info("o1", "본캐", 280)],
    )
    assert ("🧹 계정에 없는 캐릭터 정리 (1)", False) in _labels(view)
    await view._open_cleanup(_click())
    await view._picked_cleanup(_click(["oX"]))
    assert calls == []  # 확인 전엔 삭제 안 함
    done = _click()
    await view._confirm_cleanup(done)
    assert calls == [["oX"]]
    assert "남의캐** 정리했어요" in done.original_edits[-1]["embed"].description
    assert view.plan.missing == []


async def test_leave_goes_back_or_closes(monkeypatch):
    went_back: list = []

    async def back(interaction):
        went_back.append(interaction)

    view = _sync_view(monkeypatch, account=_TWELVE, registered=[], back=back)
    assert ("← 목록으로", False) in _labels(view)
    click = _click()
    await view._leave(click)
    assert went_back == [click] and view.is_finished()

    closed = _sync_view(monkeypatch, account=_TWELVE, registered=[])
    assert ("닫기", False) in _labels(closed)
    click = _click()
    await closed._leave(click)
    assert click.response.edits == [{"view": None}]


async def test_no_candidates_message(monkeypatch):
    view = _sync_view(
        monkeypatch,
        account=[_acc("o1", "본캐", 280)],
        registered=[_info("o1", "본캐", 280)],
    )
    assert not [i for i in view.children if isinstance(i, discord.ui.Select)]
    assert "가져올 새 캐릭터가 없어요" in view._embed(None).description


# ── 빌더·진입점 ──────────────────────────────────────────────────────────────


async def test_build_failure_returns_embed_without_view(monkeypatch):
    async def fail(**kwargs):
        return None, "API 키가 무효예요."

    monkeypatch.setattr(reg_commands.service, "fetch_account_characters", fail)
    deps = SimpleNamespace(session_factory=object(), nexon=object(), cipher=object())
    embed, view = await reg_commands.build_account_sync(deps, 1, 10, header="머리말")
    assert view is None
    assert embed.description.startswith("머리말") and "무효" in embed.description


async def test_build_applies_updates_then_builds_view(monkeypatch):
    applied: list = []

    async def ok(**kwargs):
        return [_acc("o1", "새닉", 281), _acc("o2", "부캐", 200)], None

    state = {"registered": [_info("o1", "옛닉", 280)]}

    async def get_characters(sf, scope, uid):
        return state["registered"]

    async def apply(sf, scope, uid, updates):
        applied.append([u.ocid for u in updates])
        state["registered"] = [_info("o1", "새닉", 281)]

    monkeypatch.setattr(reg_commands.service, "fetch_account_characters", ok)
    monkeypatch.setattr(reg_commands.service, "get_characters", get_characters)
    monkeypatch.setattr(reg_commands.service, "apply_account_updates", apply)
    deps = SimpleNamespace(session_factory=object(), nexon=object(), cipher=object())
    embed, view = await reg_commands.build_account_sync(deps, 1, 10)
    assert applied == [["o1"]] and view.updated == 1
    assert [c.ocid for c in view.plan.candidates] == ["o2"]
    assert "닉·레벨 갱신 1개" in embed.description


async def test_hub_sync_button_swaps_view_or_keeps_hub(monkeypatch):
    async def get_characters(sf, scope, uid):
        return [_info("o1", "본캐", 280, rep=True)]

    async def has_key(sf, scope, uid):
        return True

    monkeypatch.setattr(reg_commands.service, "get_characters", get_characters)
    monkeypatch.setattr(reg_commands.service, "has_personal_key", has_key)
    deps = SimpleNamespace(session_factory=object(), nexon=object(), cipher=object())
    hub = reg_commands.CharacterManageView(
        deps,
        scope=1,
        user_id=10,
        characters=await get_characters(0, 0, 0),
        has_key=True,
    )
    sentinel_view = SimpleNamespace(_last_interaction=None)

    async def build_ok(*a, **k):
        return discord.Embed(title="동기화"), sentinel_view

    monkeypatch.setattr(reg_commands, "build_account_sync", build_ok)
    click = _click()
    await hub._open_sync(click)
    assert click.response.deferred
    assert click.original_edits[-1]["view"] is sentinel_view and hub.is_finished()

    hub2 = reg_commands.CharacterManageView(
        deps,
        scope=1,
        user_id=10,
        characters=await get_characters(0, 0, 0),
        has_key=True,
    )

    async def build_fail(*a, **k):
        return discord.Embed(title="실패"), None

    monkeypatch.setattr(reg_commands, "build_account_sync", build_fail)
    click = _click()
    await hub2._open_sync(click)
    assert click.original_edits[-1]["view"] is hub2 and not hub2.is_finished()


class _DeferResponse:
    def __init__(self):
        self._done = False

    def is_done(self):
        return self._done

    async def defer(self, **kwargs):
        self._done = True


class _Followup:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(id=1)


async def test_key_register_opens_sync_or_falls_back(monkeypatch):
    async def register_key(**kwargs):
        return service.KeyRegisterResult(ok=True)

    monkeypatch.setattr(reg_commands.service, "register_key", register_key)
    deps = SimpleNamespace(session_factory=object(), nexon=object(), cipher=object())

    view = SimpleNamespace(message=None)

    async def build_ok(d, scope, uid, **kwargs):
        assert "키를 등록했어요" in kwargs["header"]
        return discord.Embed(title="동기화"), view

    monkeypatch.setattr(reg_commands, "build_account_sync", build_ok)
    interaction = SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=10),
        response=_DeferResponse(),
        followup=_Followup(),
    )
    await reg_commands.handle_key_register(deps, interaction, " key ")
    [sent] = interaction.followup.sent
    assert sent["view"] is view and sent["ephemeral"] and view.message.id == 1

    async def build_fail(d, scope, uid, **kwargs):
        return discord.Embed(title="실패"), None

    monkeypatch.setattr(reg_commands, "build_account_sync", build_fail)
    interaction = SimpleNamespace(
        guild_id=1,
        user=SimpleNamespace(id=10),
        response=_DeferResponse(),
        followup=_Followup(),
    )
    await reg_commands.handle_key_register(deps, interaction, "key")
    [sent] = interaction.followup.sent
    assert "view" not in sent and sent["embed"].title == "실패"  # 키 등록은 성공 유지
