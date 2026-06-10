"""레벨 3단 매칭 + 장착 레벨 파싱 단위테스트."""

from __future__ import annotations

from maple_mate.history.equipment_level import (
    EQUIPMENT_LEVEL_SEED,
    fetch_equipped_levels,
    match_level,
)


def test_match_level_prefers_equipped() -> None:
    # (A) 현재 장착이 시드보다 우선(가장 정확). 세트명 비포함 단품으로 검증.
    equipped = {"거대한 공포": 150}
    seed = {"거대한 공포": 999}
    assert match_level("거대한 공포", equipped, seed) == 150


def test_match_level_falls_back_to_seed() -> None:
    # (B) 장착에 없으면 시드.
    assert match_level("제네시스 라피스", {}, {"제네시스 라피스": 200}) == 200


def test_match_level_set_name_substring() -> None:
    # 아이템명에 세트명이 포함되면 장착/시드 없이도 고정 레벨로 매칭(부위·직업 무관).
    assert match_level("에테르넬 나이트아머", {}) == 250
    assert match_level("아케인셰이드 나이트헬름", {}) == 200
    assert match_level("앱솔랩스 나이트헬름", {}) == 160
    assert match_level("파프니르 페어리완드", {}) == 150
    assert match_level("하이네스 워리어헬름", {}) == 150
    assert match_level("트릭스터 워리어팬츠", {}) == 150
    assert match_level("이글아이 워리어아머", {}) == 150
    assert match_level("마이스터링", {}) == 140


def test_match_level_set_overrides_equipped_and_seed() -> None:
    # 세트명 매칭은 무조건 최우선 — 장착/시드에 다른 값이 있어도 세트 레벨로 고정.
    assert (
        match_level(
            "에테르넬 나이트아머",
            {"에테르넬 나이트아머": 999},
            {"에테르넬 나이트아머": 1},
        )
        == 250
    )


def test_match_level_boss_accessory_seed() -> None:
    # 보스 장신구 세트 — 부위별 제각각 레벨(사용자 제공·API 교차검증). 정확 일치 시드.
    assert match_level("근원의 속삭임", {}) == 250  # 광휘
    assert match_level("몽환의 벨트", {}) == 200  # 칠흑
    assert match_level("데이브레이크 펜던트", {}) == 140
    assert match_level("혼테일의 목걸이", {}) == 120
    assert match_level("실버블라썸 링", {}) == 110
    assert match_level("아쿠아틱 레터 눈장식", {}) == 100


def test_match_level_returns_none_when_unmatched() -> None:
    # (C) 둘 다 실패 → None.
    assert match_level("듣보 장비", {}, {}) is None


def test_match_level_uses_default_seed() -> None:
    name, level = next(iter(EQUIPMENT_LEVEL_SEED.items()))
    assert match_level(name, {}) == level


class _FakeNexon:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def character_item_equipment(self, ocid: str) -> dict:
        return self._payload


async def test_fetch_equipped_levels_parses_names_and_levels() -> None:
    payload = {
        "item_equipment": [
            {
                "item_name": "하이네스 워리어헬름",
                "item_base_option": {"base_equipment_level": 150},
            },
            {
                "item_name": "아케인셰이드 나이트슈즈",
                "item_base_option": {"base_equipment_level": 200},
            },
        ]
    }
    levels = await fetch_equipped_levels(_FakeNexon(payload), "ocid")
    assert levels == {"하이네스 워리어헬름": 150, "아케인셰이드 나이트슈즈": 200}


async def test_fetch_equipped_levels_skips_missing_level() -> None:
    payload = {
        "item_equipment": [
            {"item_name": "정상", "item_base_option": {"base_equipment_level": 200}},
            {"item_name": "레벨없음", "item_base_option": {}},
            {"item_name": "옵션없음"},
        ]
    }
    levels = await fetch_equipped_levels(_FakeNexon(payload), "ocid")
    assert levels == {"정상": 200}


async def test_fetch_equipped_levels_empty_when_no_items() -> None:
    assert await fetch_equipped_levels(_FakeNexon({}), "ocid") == {}


# ── 자동 학습 병합 (명령부가 {**learned, **equipped} 로 합쳐 match_level 에 넘김) ──


def test_learned_level_matches_when_not_currently_equipped() -> None:
    learned = {"에테르넬 나이트아머": 250, "교체된 구장비": 200}
    equipped = {"현재 장비": 160}
    known = {**learned, **equipped}
    assert match_level("교체된 구장비", known) == 200  # 학습으로 매칭(현재 미장착)
    assert match_level("현재 장비", known) == 160  # 현재 장착
    assert match_level("처음 보는 장비", known) is None


def test_currently_equipped_overrides_learned() -> None:
    # 같은 이름이면 현재 장착(A)이 학습(B)보다 우선.
    assert match_level("X", {**{"X": 100}, **{"X": 200}}) == 200
