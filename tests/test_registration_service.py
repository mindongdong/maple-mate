"""registration.service 전달-무관 로직 단위테스트 (Nexon mock, DB 불요 — handoff §6).

DB upsert 는 통합 영역이라 여기서 제외(순수/모킹 가능한 부분만). resolve_ocid·키검증·암호화 검증.
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration import service
from maple_mate.registration.realm import Realm
from maple_mate.security.crypto import KeyCipher


class FakeNexon:
    def __init__(self, *, ocids=None, valid_keys=None, raise_on_verify=None):
        self._ocids = ocids or {}
        self._valid_keys = valid_keys or {}
        self._raise_on_verify = raise_on_verify

    async def get_ocid(self, name):
        if name in self._ocids:
            return self._ocids[name]
        raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)

    async def verify_personal_key(self, key):
        if self._raise_on_verify is not None:
            raise self._raise_on_verify
        return self._valid_keys.get(key, False)


CIPHER = KeyCipher(Fernet.generate_key())


# ── 등록 시 레벨·월드 스냅샷 (realm 자동 판별, ADR-0009) ─────────────────────


async def test_fetch_level_and_world_extracts_both():
    nexon = FakeNexon()

    async def basic(ocid):
        return {"character_level": 260, "world_name": "챌린저스3"}

    nexon.character_basic = basic  # type: ignore[attr-defined]
    level, world = await service._fetch_level_and_world(nexon, "o1")
    assert level == 260 and world == "챌린저스3"


async def test_fetch_level_and_world_main_realm():
    nexon = FakeNexon()

    async def basic(ocid):
        return {"character_level": 287, "world_name": "스카니아"}

    nexon.character_basic = basic  # type: ignore[attr-defined]
    level, world = await service._fetch_level_and_world(nexon, "o1")
    assert level == 287 and world == "스카니아"


async def test_fetch_level_and_world_api_error_returns_none_none():
    nexon = FakeNexon()

    async def boom(ocid):
        raise NexonAPIError("OPENAPI00001", "internal", http_status=500)

    nexon.character_basic = boom  # type: ignore[attr-defined]
    level, world = await service._fetch_level_and_world(nexon, "o1")
    assert level is None and world is None


async def test_resolve_ocid_success():
    nexon = FakeNexon(ocids={"손가락": "ocid_son"})
    ocid, err = await service.resolve_ocid(nexon, "손가락")
    assert ocid == "ocid_son" and err is None


async def test_resolve_ocid_missing_nickname_returns_message():
    nexon = FakeNexon(ocids={})
    ocid, err = await service.resolve_ocid(nexon, "없는닉")
    assert ocid is None and "찾을 수 없" in err


async def test_resolve_ocid_api_error_returns_retry_message():
    nexon = FakeNexon(raise_on_verify=None)

    async def boom(_name):
        raise NexonAPIError("OPENAPI00001", "internal", http_status=500)

    nexon.get_ocid = boom  # type: ignore[assignment]
    ocid, err = await service.resolve_ocid(nexon, "x")
    assert ocid is None and "잠시 후" in err


async def test_verify_and_encrypt_valid_key_roundtrips():
    nexon = FakeNexon(valid_keys={"goodkey": True})
    enc, err = await service.verify_and_encrypt_key(nexon, CIPHER, "goodkey")
    assert err is None and enc is not None
    assert CIPHER.decrypt(enc) == "goodkey"


async def test_verify_and_encrypt_invalid_key_rejected():
    nexon = FakeNexon(valid_keys={"goodkey": True})  # badkey → False
    enc, err = await service.verify_and_encrypt_key(nexon, CIPHER, "badkey")
    assert enc is None and "무효" in err


async def test_verify_and_encrypt_api_error_returns_message():
    nexon = FakeNexon(
        raise_on_verify=NexonAPIError("OPENAPI00001", "internal", http_status=500)
    )
    enc, err = await service.verify_and_encrypt_key(nexon, CIPHER, "k")
    assert enc is None and "잠시 후" in err


# ── 솔로 비교(/내캐릭터) 캐릭터 타깃 해석 (ADR-0018) ─────────────────────────


def _char(ocid, nickname, level, world=None):
    from types import SimpleNamespace

    return SimpleNamespace(ocid=ocid, maple_nickname=nickname, level=level, world=world)


def test_my_character_targets_empty_when_no_characters():
    assert service._my_character_targets([], 1, 10) == []


def test_my_character_targets_sorted_by_level_then_nickname():
    chars = [
        _char("o1", "나중닉", 250),
        _char("o2", "최고레벨", 287),
        _char("o3", "가나다", 250),  # 동률 → 닉 오름차순
        _char("o4", "레벨미상", None),  # NULL 레벨은 맨 뒤
    ]
    targets = service._my_character_targets(chars, 1, 10)
    assert [t.ocid for t in targets] == ["o2", "o3", "o1", "o4"]


def test_my_character_targets_preserves_ocid_order_and_dedupes():
    chars = [_char("o1", "일", 200), _char("o2", "이", 280), _char("o3", "삼", 250)]
    targets = service._my_character_targets(
        chars, 1, 10, ocids=["o3", "o1", "o3", "남의ocid"]
    )
    # 입력 순서 보존 + 중복 제거 + 본인 것 아닌 ocid 무시(레벨 정렬 아님).
    assert [t.ocid for t in targets] == ["o3", "o1"]


def test_my_character_targets_mixes_realms_and_keeps_fields():
    # realm 필터 없음(결정 7) — 챌린저스 캐릭터도 포함, world 신호 보존.
    chars = [
        _char("o1", "본캐", 287, "스카니아"),
        _char("o2", "챌캐", 260, "챌린저스3"),
    ]
    targets = service._my_character_targets(chars, 7, 42)
    assert [t.ocid for t in targets] == ["o1", "o2"]
    top = targets[0]
    assert (top.guild_id, top.discord_user_id) == (7, 42)
    assert top.nickname == "본캐" and top.world == "스카니아"
    assert targets[1].world == "챌린저스3"


# ── 경험치 수집 캐릭터 타깃 해석 (ADR-0018 결정 5 — 등록 전 캐릭터) ────────────


def _guild_char(uid, ocid, nickname, level, world=None, guild_id=1):
    from types import SimpleNamespace

    return SimpleNamespace(
        guild_id=guild_id,
        discord_user_id=uid,
        ocid=ocid,
        maple_nickname=nickname,
        level=level,
        world=world,
    )


def test_guild_character_targets_empty():
    assert service._guild_character_targets([]) == []


def test_guild_character_targets_returns_every_character_per_user():
    # 유저당 대표 1명(get_targets)이 아니라 등록 캐릭터 전부 — 캐릭터당 Target 1개.
    chars = [
        _guild_char(20, "oB1", "친구본캐", 260),
        _guild_char(10, "oA2", "부캐", 250),
        _guild_char(10, "oA1", "본캐", 287),
    ]
    targets = service._guild_character_targets(chars)
    # 정렬 = (유저, ocid) 오름차순 — 수집(넥슨 콜) 순서 결정성.
    assert [(t.discord_user_id, t.ocid) for t in targets] == [
        (10, "oA1"),
        (10, "oA2"),
        (20, "oB1"),
    ]
    assert targets[0].nickname == "본캐" and targets[0].world is None


def test_guild_character_targets_realm_filter():
    chars = [
        _guild_char(10, "oM", "본캐", 287, "스카니아"),
        _guild_char(10, "oC", "챌캐", 260, "챌린저스3"),
        _guild_char(20, "oL", "레거시", 200, None),  # NULL world = 본서버
    ]
    main = service._guild_character_targets(chars, Realm.MAIN)
    chal = service._guild_character_targets(chars, Realm.CHALLENGERS)
    assert [t.ocid for t in main] == ["oM", "oL"]
    assert [t.ocid for t in chal] == ["oC"]
    none = service._guild_character_targets(chars, None)  # 미지정 = 전 캐릭터
    assert [t.ocid for t in none] == ["oC", "oM", "oL"]  # (유저, ocid) 정렬
