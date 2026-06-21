"""`모드` 파라미터 파서 단위테스트 (ADR-0009).

미지정(None)은 본서버(무상태 기본). choice value 가 Realm value 와 일치한다.
"""

from __future__ import annotations

from discord import app_commands

from maple_mate.bot.modes import MODE_CHOICES, parse_mode
from maple_mate.registration.realm import Realm


def test_none_defaults_to_main() -> None:
    assert parse_mode(None) is Realm.MAIN


def test_main_choice() -> None:
    choice = app_commands.Choice(name="본서버", value="본서버")
    assert parse_mode(choice) is Realm.MAIN


def test_challengers_choice() -> None:
    choice = app_commands.Choice(name="챌린저스", value="챌린저스")
    assert parse_mode(choice) is Realm.CHALLENGERS


def test_unknown_value_defaults_to_main() -> None:
    choice = app_commands.Choice(name="x", value="알수없음")
    assert parse_mode(choice) is Realm.MAIN


def test_choices_match_realm_values() -> None:
    # 첫 choice = 본서버(기본), value 가 Realm value 와 일치.
    assert [c.value for c in MODE_CHOICES] == [
        Realm.MAIN.value,
        Realm.CHALLENGERS.value,
    ]
