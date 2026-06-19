"""이력류 realm 필터 비대칭 단위테스트 (순수, 결정 6·ADR-0009).

/스타포스 = 레코드 world_name 정밀 필터. /잠재 = 등록 닉맵 필터(cube/potential 엔 world_name
부재). 미상(world_name 빈값·미등록 닉)은 둘 다 본서버로 흡수 — 챌린저스 모드는 명시 신호만.
"""

from __future__ import annotations

from maple_mate.history.potential_service import (
    CubeRecord,
    ResetRecord,
    records_in_realm,
)
from maple_mate.history.service import StarforceAttempt, attempts_in_realm
from maple_mate.registration.realm import Realm


def _sf(world: str, name: str = "캐릭") -> StarforceAttempt:
    return StarforceAttempt(
        target_item="무기",
        before_star=17,
        after_star=18,
        result="성공",
        date_create="2026-06-19T00:00:00+09:00",
        character_name=name,
        world_name=world,
    )


def test_attempts_in_realm_starforce_world_name() -> None:
    attempts = [_sf("스카니아"), _sf("챌린저스3"), _sf("")]  # 본서버·챌린저스·미상
    main = attempts_in_realm(attempts, Realm.MAIN)
    chal = attempts_in_realm(attempts, Realm.CHALLENGERS)
    # 본서버 = 스카니아 + 미상(빈값) 2건, 챌린저스 = 챌린저스3 1건(누수 0).
    assert [a.world_name for a in main] == ["스카니아", ""]
    assert [a.world_name for a in chal] == ["챌린저스3"]


def _cube(name: str) -> CubeRecord:
    return CubeRecord(
        cube_type="수상한 큐브",
        item_level=200,
        item_part="모자",
        target_item="모자",
        result="성공",
        pot_grade="유니크",
        add_grade="레어",
        before_pot=(),
        after_pot=(),
        before_add=(),
        after_add=(),
        date_create="2026-06-19T00:00:00+09:00",
        character_name=name,
    )


def _reset(name: str) -> ResetRecord:
    return ResetRecord(
        potential_type="잠재능력",
        item_level=200,
        item_part="모자",
        target_item="모자",
        result="성공",
        pot_grade="유니크",
        add_grade="레어",
        before_pot=(),
        after_pot=(),
        before_add=(),
        after_add=(),
        date_create="2026-06-19T00:00:00+09:00",
        character_name=name,
    )


def test_records_in_realm_potential_nickmap() -> None:
    realm_by_nick = {"본캐": Realm.MAIN, "챌캐": Realm.CHALLENGERS}
    cubes = [_cube("본캐"), _cube("챌캐"), _cube("미등록닉")]
    resets = [_reset("본캐"), _reset("챌캐")]
    # 챌린저스 모드 = 등록된 챌린저스 닉만(미등록닉은 본서버 폴백 → 챌린저스에서 누락).
    assert [
        c.character_name
        for c in records_in_realm(cubes, realm_by_nick, Realm.CHALLENGERS)
    ] == ["챌캐"]
    # 본서버 모드 = 챌린저스 닉 배제, 미상 닉은 본서버 흡수.
    assert [
        c.character_name for c in records_in_realm(cubes, realm_by_nick, Realm.MAIN)
    ] == ["본캐", "미등록닉"]
    assert [
        r.character_name
        for r in records_in_realm(resets, realm_by_nick, Realm.CHALLENGERS)
    ] == ["챌캐"]


def test_records_in_realm_unknown_nick_defaults_main() -> None:
    # 닉맵이 비면 전부 본서버(레거시·미등록) → 챌린저스 모드는 빈 결과.
    cubes = [_cube("a"), _cube("b")]
    assert records_in_realm(cubes, {}, Realm.CHALLENGERS) == []
    assert len(records_in_realm(cubes, {}, Realm.MAIN)) == 2
