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


# ── 자동완성 공용 헬퍼 (/대표지정·/내캐릭터 공유) ────────────────────────────


def _info(ocid, nickname, level=260, *, rep=False, world=None):
    from maple_mate.registration.service import CharacterInfo

    return CharacterInfo(
        ocid=ocid, nickname=nickname, level=level, is_representative=rep, world=world
    )


def test_character_choices_labels_and_values() -> None:
    from maple_mate.registration.commands import character_choices

    choices = character_choices(
        [
            _info("o1", "대표닉", 287, rep=True),
            _info("o2", "챌캐", 260, world="챌린저스3"),
        ],
        "",
    )
    assert [(c.name, c.value) for c in choices] == [
        ("대표닉 (Lv.287) 👑", "o1"),
        ("챌캐 (Lv.260, 챌린저스3)", "o2"),
    ]


def test_character_choices_filters_by_substring_case_insensitive() -> None:
    from maple_mate.registration.commands import character_choices

    infos = [_info("o1", "MapleHero"), _info("o2", "다른닉")]
    assert [c.value for c in character_choices(infos, "maple")] == ["o1"]
    assert [c.value for c in character_choices(infos, "없는닉")] == []


def test_character_choices_caps_at_discord_limit() -> None:
    from maple_mate.registration.commands import character_choices

    infos = [_info(f"o{i}", f"닉{i}") for i in range(30)]
    assert len(character_choices(infos, "")) == 25
