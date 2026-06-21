"""/캐릭터목록·자동완성 realm 라벨 순수 렌더 테스트 (ADR-0009).

챌린저스 캐릭터만 realm 을 괄호에 표기하고 본서버는 무표기(시각적 회귀 0, 결정 9)다.
"""

from __future__ import annotations

from maple_mate.registration.commands import _char_label


def test_main_realm_label_unchanged() -> None:
    # 본서버는 world 를 붙이지 않는다(기존 출력 그대로).
    assert _char_label("손가락", 287, "스카니아") == "손가락 (Lv.287)"
    assert _char_label("손가락", 287, None) == "손가락 (Lv.287)"


def test_challengers_label_shows_realm() -> None:
    assert (
        _char_label("힘찬하악질", 260, "챌린저스3") == "힘찬하악질 (Lv.260, 챌린저스3)"
    )


def test_label_without_level() -> None:
    assert _char_label("닉", None, None) == "닉"
    assert _char_label("닉", None, "챌린저스3") == "닉 (챌린저스3)"
