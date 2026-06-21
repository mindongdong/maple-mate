"""realm 판정 순수 술어 단위테스트 (DB 불요, ADR-0009).

realm 신호 = world_name 접두 `챌린저스`. NULL/빈값 = 본서버(레거시). `챌린저스N` 전부 한 realm.
"""

from __future__ import annotations

import pytest

from maple_mate.registration.realm import (
    Realm,
    in_realm,
    is_challengers,
    realm_of,
    realm_prefix,
    realm_title,
)


@pytest.mark.parametrize(
    "world,expected",
    [
        ("챌린저스", True),
        ("챌린저스1", True),
        ("챌린저스2", True),
        ("챌린저스3", True),
        ("스카니아", False),
        ("루나", False),
        ("", False),
        (None, False),
        ("크로아챌린저스", False),  # 접두만 인정(중간 등장은 본서버)
    ],
)
def test_is_challengers(world, expected) -> None:
    assert is_challengers(world) is expected


def test_realm_of_maps_world_to_realm() -> None:
    assert realm_of("챌린저스3") is Realm.CHALLENGERS
    assert realm_of("스카니아") is Realm.MAIN
    assert realm_of(None) is Realm.MAIN  # 레거시 NULL = 본서버


def test_in_realm_predicate() -> None:
    # 본서버 모드는 챌린저스를 배제, 챌린저스 모드는 챌린저스만(핵심 불변식).
    assert in_realm("스카니아", Realm.MAIN) is True
    assert in_realm("스카니아", Realm.CHALLENGERS) is False
    assert in_realm("챌린저스3", Realm.CHALLENGERS) is True
    assert in_realm("챌린저스3", Realm.MAIN) is False
    assert in_realm(None, Realm.MAIN) is True  # NULL = 본서버


def test_realm_value_matches_mode_choices() -> None:
    # 모드 파라미터 choices 와 enum 값이 일치해야 무상태 파라미터가 곧 realm 으로 해석된다.
    assert Realm.MAIN.value == "본서버"
    assert Realm.CHALLENGERS.value == "챌린저스"


def test_realm_prefix_and_title_label_challengers_only() -> None:
    # 챌린저스만 🏆 프리픽스, 본서버는 무라벨(시각적 회귀 0, 결정 9).
    assert realm_prefix(Realm.MAIN) == ""
    assert realm_prefix(Realm.CHALLENGERS) == "🏆 챌린저스 "
    assert realm_title("스펙 비교", Realm.MAIN) == "스펙 비교"
    assert realm_title("스펙 비교", Realm.CHALLENGERS) == "🏆 챌린저스 스펙 비교"
