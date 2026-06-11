"""`/비틱` 아이템 단위 집계 단위테스트.

픽스처는 레이아웃 참고 스크린샷 수치 재현: 12→19(강화 19번·파괴 0번·★19도전 1성공 4실패),
17→17(4실패, 끝≤시작 → 전액 손해). 잠재는 (이름, 레벨) 그룹·횟수 내림차순·섹션 추출 검증.
"""

from __future__ import annotations

import pytest

from maple_mate.bitik.service import (
    group_potential,
    group_starforce,
)
from maple_mate.history import potential_cost
from maple_mate.history.expected_cost import actual_meso, expected_meso
from maple_mate.history.potential_service import (
    CubeRecord,
    ResetRecord,
    parse_cube_records,
)
from maple_mate.history.service import StarforceAttempt, parse_attempts

# ── 스타포스 픽스처 ──────────────────────────────────────────────────────────


def _attempt(
    item: str,
    before: int,
    after: int,
    result: str,
    when: str,
    *,
    superior: bool = False,
) -> StarforceAttempt:
    return StarforceAttempt(
        target_item=item,
        before_star=before,
        after_star=after,
        result=result,
        date_create=when,
        superior=superior,
    )


def _ring_12_to_19() -> list[StarforceAttempt]:
    """스크린샷 1 재현: 12→19, 강화 19번/파괴 0번, ★19도전 1성공 4실패."""
    item = "여명의 가디언 엔젤 링"
    seq: list[tuple[int, int, str]] = [
        # (before, after, result) — 12~17 구간: 유지 실패 8회 + 성공 6회.
        (12, 12, "실패(유지)"),
        (12, 12, "실패(유지)"),
        (12, 13, "성공"),
        (13, 13, "실패(유지)"),
        (13, 13, "실패(유지)"),
        (13, 14, "성공"),
        (14, 14, "실패(유지)"),
        (14, 14, "실패(유지)"),
        (14, 15, "성공"),
        (15, 15, "실패(유지)"),
        (15, 16, "성공"),
        (16, 16, "실패(유지)"),
        (16, 17, "성공"),
        (17, 18, "성공"),
        # ★19 도전(before=18): 4실패 1성공.
        (18, 18, "실패(유지)"),
        (18, 18, "실패(유지)"),
        (18, 18, "실패(유지)"),
        (18, 18, "실패(유지)"),
        (18, 19, "성공"),
    ]
    return [
        _attempt(item, b, a, r, f"2026-06-01T10:{i:02d}:00+09:00")
        for i, (b, a, r) in enumerate(seq)
    ]


def test_group_starforce_reproduces_screenshot_fixture() -> None:
    bitiks, excluded = group_starforce(_ring_12_to_19(), lambda item: 160)
    assert excluded.count == 0
    assert len(bitiks) == 1
    b = bitiks[0]
    assert b.item == "여명의 가디언 엔젤 링"
    assert b.level == 160
    assert (b.start_star, b.end_star) == (12, 19)
    assert (b.attempt_count, b.destroy_count) == (19, 0)
    assert (b.challenge_star, b.challenge_success, b.challenge_fail) == (19, 1, 4)
    assert b.actual_meso == actual_meso(160, [a.before_star for a in _ring_12_to_19()])
    assert b.expected_meso == round(expected_meso(160, 12, 19))
    assert b.net_meso == b.expected_meso - b.actual_meso


def test_group_starforce_no_progress_is_full_loss() -> None:
    """스크린샷 2 재현: 17→17(4실패) — 끝≤시작 → 기댓값 0 → 전액 손해."""
    attempts = [
        _attempt("거대한 공포", 17, 17, "실패(유지)", f"2026-06-01T10:0{i}:00+09:00")
        for i in range(4)
    ]
    bitiks, _ = group_starforce(attempts, lambda item: 200)
    b = bitiks[0]
    assert (b.start_star, b.end_star) == (17, 17)
    assert b.expected_meso == 0
    assert b.net_meso == -b.actual_meso
    assert (b.challenge_star, b.challenge_success, b.challenge_fail) == (18, 0, 4)


def test_group_starforce_start_is_chronological_not_input_order() -> None:
    attempts = [
        _attempt("itemA", 15, 16, "성공", "2026-06-02T10:00:00+09:00"),
        _attempt("itemA", 12, 13, "성공", "2026-06-01T10:00:00+09:00"),  # 가장 이른
    ]
    bitiks, _ = group_starforce(attempts, lambda item: 200)
    assert (bitiks[0].start_star, bitiks[0].end_star) == (12, 16)


def test_group_starforce_destroy_counted_and_end_is_last_after() -> None:
    attempts = [
        _attempt("itemA", 17, 18, "성공", "2026-06-01T10:00:00+09:00"),
        _attempt("itemA", 18, 12, "파괴", "2026-06-01T11:00:00+09:00"),
    ]
    bitiks, _ = group_starforce(attempts, lambda item: 200)
    b = bitiks[0]
    assert b.destroy_count == 1
    assert b.end_star == 12  # 끝 = 마지막 시도의 after (최고치 아님)
    assert b.expected_meso == 0  # 끝≤시작 → 기댓값 0(전액 손해)


def test_group_starforce_excludes_unknown_level_and_superior() -> None:
    attempts = [
        _attempt("매칭됨", 0, 1, "성공", "2026-06-01T10:00:00+09:00"),
        _attempt("정체불명", 0, 1, "성공", "2026-06-01T10:01:00+09:00"),
        _attempt(
            "타일런트 부츠", 3, 4, "성공", "2026-06-01T10:02:00+09:00", superior=True
        ),
    ]
    bitiks, excluded = group_starforce(
        attempts, lambda item: 200 if item == "매칭됨" else None
    )
    assert [b.item for b in bitiks] == ["매칭됨"]
    assert excluded.unmatched == ("정체불명",)
    assert excluded.superior == ("타일런트 부츠",)
    assert excluded.count == 2


def test_group_starforce_superior_not_reported_as_unmatched() -> None:
    """슈페리얼은 레벨 매칭 성공이어도 제외 — error_log 제보 대상(unmatched)엔 빠진다."""
    attempts = [
        _attempt(
            "타일런트 부츠", 3, 4, "성공", "2026-06-01T10:00:00+09:00", superior=True
        ),
    ]
    bitiks, excluded = group_starforce(attempts, lambda item: 150)
    assert bitiks == []
    assert excluded.unmatched == ()
    assert excluded.superior == ("타일런트 부츠",)


def test_group_starforce_sorted_by_net_desc() -> None:
    # 이득(저비용 등반) vs 손해(무진행 헛돈) — net 내림차순.
    lucky = [_attempt("운좋음", 12, 13, "성공", "2026-06-01T10:00:00+09:00")]
    unlucky = [
        _attempt("운나쁨", 17, 17, "실패(유지)", f"2026-06-01T11:0{i}:00+09:00")
        for i in range(5)
    ]
    bitiks, _ = group_starforce(unlucky + lucky, lambda item: 200)
    assert [b.item for b in bitiks] == ["운좋음", "운나쁨"]
    assert bitiks[0].net_meso > bitiks[1].net_meso


def test_parse_attempts_extracts_superior_flag() -> None:
    """superior_item_flag 는 서술형 한글 문자열(실측) — '미해당' 포함이면 일반 장비."""
    records = [
        {
            "character_name": "손바",
            "target_item": "타일런트 부츠",
            "before_starforce_count": 3,
            "after_starforce_count": 4,
            "item_upgrade_result": "성공",
            "date_create": "2026-06-01T10:00:00+09:00",
            "superior_item_flag": "슈페리얼 장비 해당",
        },
        {
            "character_name": "손바",
            "target_item": "여명의 가디언 엔젤 링",
            "before_starforce_count": 12,
            "after_starforce_count": 13,
            "item_upgrade_result": "성공",
            "date_create": "2026-06-01T10:01:00+09:00",
            "superior_item_flag": "슈페리얼 장비 미해당",
        },
    ]
    attempts = parse_attempts(records, "손바")
    assert [a.superior for a in attempts] == [True, False]


def test_parse_attempts_superior_unknown_format_falls_back_to_regular() -> None:
    """미상 포맷(빈값·"0" 등 서술형 아님) → 일반 장비 폴백(전 아이템 과잉 제외 방지)."""
    base = {
        "character_name": "손바",
        "target_item": "여명의 가디언 엔젤 링",
        "before_starforce_count": 12,
        "after_starforce_count": 13,
        "item_upgrade_result": "성공",
        "date_create": "2026-06-01T10:00:00+09:00",
    }
    records = [
        {**base, "superior_item_flag": "0"},
        {**base, "superior_item_flag": ""},
        {**base},  # 필드 자체 부재
    ]
    assert [a.superior for a in parse_attempts(records, "손바")] == [False] * 3


# ── 잠재 픽스처 ──────────────────────────────────────────────────────────────


def _cube(
    item: str = "제네시스 스태프",
    *,
    cube_type: str = "레드 큐브",
    level: int = 200,
    when: str = "2026-06-01T10:00:00+09:00",
    before_pot: tuple[str, ...] = ("유니크", "유니크", "에픽"),
    after_pot: tuple[str, ...] = ("유니크", "유니크", "에픽"),
    after_pot_values: tuple[str, ...] = (),
    before_add: tuple[str, ...] = (),
    after_add: tuple[str, ...] = (),
    after_add_values: tuple[str, ...] = (),
) -> CubeRecord:
    return CubeRecord(
        cube_type=cube_type,
        item_level=level,
        item_part="무기",
        target_item=item,
        result="실패",
        pot_grade=after_pot[0] if after_pot else "",
        add_grade=after_add[0] if after_add else "",
        before_pot=before_pot,
        after_pot=after_pot,
        before_add=before_add,
        after_add=after_add,
        date_create=when,
        after_pot_values=after_pot_values,
        after_add_values=after_add_values,
    )


def _reset(
    item: str = "제네시스 스태프",
    *,
    potential_type: str = "잠재능력",
    level: int = 200,
    when: str = "2026-06-01T12:00:00+09:00",
    before_pot: tuple[str, ...] = ("유니크",),
    after_pot: tuple[str, ...] = ("유니크",),
    after_pot_values: tuple[str, ...] = (),
    before_add: tuple[str, ...] = (),
    after_add: tuple[str, ...] = (),
    after_add_values: tuple[str, ...] = (),
) -> ResetRecord:
    return ResetRecord(
        potential_type=potential_type,
        item_level=level,
        item_part="무기",
        target_item=item,
        result="실패",
        pot_grade=after_pot[0] if after_pot else "",
        add_grade=after_add[0] if after_add else "",
        before_pot=before_pot,
        after_pot=after_pot,
        before_add=before_add,
        after_add=after_add,
        date_create=when,
        after_pot_values=after_pot_values,
        after_add_values=after_add_values,
    )


def test_group_potential_groups_by_item_and_level_sorted_by_resets() -> None:
    cubes = [
        _cube("제네시스 스태프", when=f"2026-06-01T10:0{i}:00+09:00") for i in range(3)
    ] + [_cube("제네시스 라피스", when="2026-06-01T11:00:00+09:00")]
    resets = [
        _reset("제네시스 라피스", when=f"2026-06-01T12:0{i}:00+09:00") for i in range(3)
    ]
    bitiks = group_potential(cubes, resets, cost=potential_cost)
    # 라피스 = 큐브1 + 재설정3 = 4회 > 스태프 3회.
    assert [(b.item, b.reset_count) for b in bitiks] == [
        ("제네시스 라피스", 4),
        ("제네시스 스태프", 3),
    ]
    assert bitiks[0].meso_reset_count == 3
    assert bitiks[0].cube_counts == (("레드 큐브", 1),)


def test_group_potential_cube_counts_descending() -> None:
    cubes = [
        _cube(cube_type="블랙 큐브", when="2026-06-01T10:00:00+09:00"),
        _cube(cube_type="레드 큐브", when="2026-06-01T10:01:00+09:00"),
        _cube(cube_type="레드 큐브", when="2026-06-01T10:02:00+09:00"),
    ]
    bitiks = group_potential(cubes, [], cost=potential_cost)
    assert bitiks[0].cube_counts == (("레드 큐브", 2), ("블랙 큐브", 1))


def test_group_potential_meso_breakdown() -> None:
    cubes = [_cube(when=f"2026-06-01T10:0{i}:00+09:00") for i in range(2)]
    resets = [
        _reset(before_pot=("유니크",), when="2026-06-01T12:00:00+09:00"),
        _reset(
            potential_type="에디셔널 잠재능력",
            before_add=("에픽",),
            after_add=("에픽",),
            when="2026-06-01T12:01:00+09:00",
        ),
    ]
    bitiks = group_potential(cubes, resets, cost=potential_cost)
    b = bitiks[0]
    assert b.appraisal_meso == 2 * potential_cost.appraisal_cost(200)
    assert b.reset_meso == potential_cost.reset_cost(
        200, "유니크", "잠재능력"
    ) + potential_cost.reset_cost(200, "에픽", "에디셔널 잠재능력")


def test_group_potential_sections_start_and_end() -> None:
    """Q7: 시작 = 첫 레코드 before 등급만, 끝 = 마지막 레코드 after 등급+옵션 풀표시."""
    cubes = [
        _cube(
            when="2026-06-01T10:00:00+09:00",
            before_pot=("유니크", "에픽", "에픽"),
            after_pot=("유니크", "유니크", "에픽"),
            after_pot_values=("보공 +30%", "공격력 +9%", "공격력 +6%"),
        ),
        _cube(
            when="2026-06-01T11:00:00+09:00",
            before_pot=("유니크", "유니크", "에픽"),
            after_pot=("레전드리", "유니크", "유니크"),
            after_pot_values=("보공 +40%", "공격력 +12%", "공격력 +9%"),
        ),
    ]
    bitiks = group_potential(cubes, [], cost=potential_cost)
    assert len(bitiks[0].sections) == 1
    section = bitiks[0].sections[0]
    assert section.kind == "잠재능력"
    assert section.start_grade == "유니크"
    assert section.end_grade == "레전드리"
    assert section.end_options == ("보공 +40%", "공격력 +12%", "공격력 +9%")


def test_group_potential_additional_section_split() -> None:
    """잠재·에디는 기간 내 기록 있는 종류만 섹션 분리 — 에디 큐브/재설정은 에디 섹션."""
    cubes = [
        _cube(when="2026-06-01T10:00:00+09:00"),  # 잠재
        _cube(
            cube_type="에디셔널 큐브",
            when="2026-06-01T10:30:00+09:00",
            before_add=("레어",),
            after_add=("에픽",),
            after_add_values=("STR +6%",),
        ),
    ]
    resets = [
        _reset(
            potential_type="에디셔널 잠재능력",
            when="2026-06-01T12:00:00+09:00",
            before_add=("에픽",),
            after_add=("유니크",),
            after_add_values=("STR +9%", "DEX +6%", "MaxHP +6%"),
        ),
    ]
    bitiks = group_potential(cubes, resets, cost=potential_cost)
    kinds = [s.kind for s in bitiks[0].sections]
    assert kinds == ["잠재능력", "에디셔널 잠재능력"]
    add = bitiks[0].sections[1]
    assert add.start_grade == "레어"  # 첫 에디 레코드(에디 큐브)의 before
    assert add.end_grade == "유니크"  # 마지막 에디 레코드(메소 재설정)의 after
    assert add.end_options == ("STR +9%", "DEX +6%", "MaxHP +6%")


def test_group_potential_empty_input() -> None:
    assert group_potential([], [], cost=potential_cost) == []


def test_parse_cube_records_extracts_after_option_values() -> None:
    records = [
        {
            "character_name": "손바",
            "cube_type": "레드 큐브",
            "item_level": 200,
            "item_equipment_part": "무기",
            "target_item": "제네시스 스태프",
            "item_upgrade_result": "실패",
            "potential_option_grade": "유니크",
            "additional_potential_option_grade": "",
            "before_potential_option": [{"value": "공격력 +9%", "grade": "유니크"}],
            "after_potential_option": [
                {"value": "보공 +30%", "grade": "유니크"},
                {"value": "공격력 +9%", "grade": "에픽"},
            ],
            "before_additional_potential_option": [],
            "after_additional_potential_option": [],
            "date_create": "2026-06-01T10:00:00+09:00",
        }
    ]
    parsed = parse_cube_records(records, "손바")
    assert parsed[0].after_pot_values == ("보공 +30%", "공격력 +9%")
    assert parsed[0].after_add_values == ()


def test_expected_meso_sanity_for_fixture_levels() -> None:
    """픽스처 레벨(160·200)의 기대값이 양수인지 — 위 테스트들의 손익 부호 전제."""
    assert expected_meso(160, 12, 19) > 0
    assert expected_meso(200, 17, 17) == pytest.approx(0.0)
