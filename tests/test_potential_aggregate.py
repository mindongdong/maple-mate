"""잠재 파싱·집계 단위테스트 (순수). 캐릭터 필터·총 큐브·등업 버킷·메소·단일 보조 분포."""

from __future__ import annotations

from maple_mate.history.potential_service import (
    CubeRecord,
    ResetRecord,
    aggregate_potential,
    parse_cube_records,
    parse_reset_records,
)

WHEN = "2026-05-31T17:00:00+09:00"


def _cube(
    *,
    cube_type: str = "수상한 큐브",
    result: str = "실패",
    before: tuple[str, ...] = ("레전드리", "유니크", "유니크"),
    pot_grade: str = "레전드리",
    add_grade: str = "유니크",
    level: int = 200,
    part: str = "모자",
) -> CubeRecord:
    return CubeRecord(
        cube_type=cube_type,
        item_level=level,
        item_part=part,
        target_item="아케인셰이드 모자",
        result=result,
        pot_grade=pot_grade,
        add_grade=add_grade,
        before_pot=before,
        after_pot=before,
        before_add=(),
        after_add=(),
        date_create=WHEN,
    )


def _reset(
    *,
    potential_type: str = "잠재능력",
    result: str = "실패",
    before: tuple[str, ...] = ("유니크",),
    pot_grade: str = "레전드리",
    add_grade: str = "유니크",
    level: int = 200,
    part: str = "모자",
) -> ResetRecord:
    return ResetRecord(
        potential_type=potential_type,
        item_level=level,
        item_part=part,
        target_item="아케인셰이드 모자",
        result=result,
        pot_grade=pot_grade,
        add_grade=add_grade,
        before_pot=before,
        after_pot=before,
        before_add=(),
        after_add=(),
        date_create=WHEN,
    )


# ── 파싱: 캐릭터 필터 + 등급 추출 ──────────────────────────────────────────


def _raw(name: str, result: str = "실패", grades=("레전드리", "유니크")) -> dict:
    return {
        "character_name": name,
        "cube_type": "수상한 큐브",
        "potential_type": "잠재능력",
        "item_upgrade_result": result,
        "item_level": 200,
        "item_equipment_part": "모자",
        "target_item": "아케인셰이드 모자",
        "potential_option_grade": "레전드리",
        "additional_potential_option_grade": "유니크",
        "before_potential_option": [{"value": "x", "grade": g} for g in grades],
        "after_potential_option": [],
        "before_additional_potential_option": [],
        "after_additional_potential_option": [],
        "date_create": WHEN,
    }


def test_parse_cube_filters_by_character_name() -> None:
    records = [_raw("손바"), _raw("부캐")]
    parsed = parse_cube_records(records, "손바")
    assert len(parsed) == 1
    assert parsed[0].before_pot == ("레전드리", "유니크")


def test_parse_reset_filters_and_extracts_grades() -> None:
    parsed = parse_reset_records([_raw("손바", grades=("유니크", "레어"))], "손바")
    assert len(parsed) == 1
    assert parsed[0].before_pot == ("유니크", "레어")
    assert parsed[0].potential_type == "잠재능력"


# ── 집계: 총 큐브/재설정 ───────────────────────────────────────────────────


def test_counts_cube_and_reset() -> None:
    summary = aggregate_potential([_cube(), _cube()], [_reset()])
    assert summary.cube_count == 2
    assert summary.reset_count == 1
    # 잠재 재설정 = 큐브 + 메소 전체(둘 다 재설정 행위).
    assert summary.total_resets == 3


# ── 집계: 등업 버킷(성공·from-등급·레전드리 제외·0건 제외) ────────────────────


def test_tierup_success_bucketed_by_from_grade() -> None:
    # before 최고=에픽 → 에픽에서 등업.
    summary = aggregate_potential([_cube(result="성공", before=("에픽", "레어"))], [])
    assert summary.tierups == (("에픽", 1),)
    assert summary.tierup_total == 1


def test_tierup_only_counts_success() -> None:
    summary = aggregate_potential([_cube(result="실패", before=("에픽",))], [])
    assert summary.tierups == ()
    assert summary.tierup_total == 0


def test_tierup_excludes_legendary_from() -> None:
    # 레전드리(종착)는 from 이 될 수 없음 → 성공이어도 등업에서 제외(엔드게임 동급 재롤).
    summary = aggregate_potential(
        [_cube(result="성공", before=("레전드리", "유니크"))], []
    )
    assert summary.tierups == ()


def test_tierup_orders_and_drops_zero_buckets() -> None:
    cubes = [
        _cube(result="성공", before=("레어",)),
        _cube(result="성공", before=("유니크",)),
        _cube(result="성공", before=("유니크",)),
    ]
    summary = aggregate_potential(cubes, [])
    # 등급 오름차순(레어→유니크), 에픽(0건)은 생략.
    assert summary.tierups == (("레어", 1), ("유니크", 2))
    assert summary.tierup_total == 3


def test_tierup_combines_cube_and_reset() -> None:
    summary = aggregate_potential(
        [_cube(result="성공", before=("에픽",))],
        [_reset(result="성공", before=("에픽",))],
    )
    assert summary.tierups == (("에픽", 2),)


def test_from_grade_uses_highest_before_grade_regardless_of_order() -> None:
    # before 배열이 섞여 있어도 최고 등급이 from.
    summary = aggregate_potential(
        [_cube(result="성공", before=("레어", "유니크", "에픽"))], []
    )
    assert summary.tierups == (("유니크", 1),)


# ── 집계: 메소(G2 단가표) ──────────────────────────────────────────────────


def test_meso_none_when_no_cost_model() -> None:
    summary = aggregate_potential([_cube()], [_reset()])
    assert summary.total_meso is None
    assert summary.appraisal_meso is None
    assert summary.reset_meso is None


class _FakeCost:
    """집계 로직 격리용 가짜 단가(큐브 100/재설정 1000 고정)."""

    def appraisal_cost(self, item_level: int) -> int:
        return 100

    def reset_cost(self, item_level: int, grade: str, potential_type: str) -> int:
        return 1000


def test_meso_sums_cube_appraisal_and_reset_cost() -> None:
    # 총 메소 = 큐브 감정비 합 + 재설정비 합(큐브도 0이 아니라 감정비를 낸다).
    summary = aggregate_potential(
        [_cube(), _cube()], [_reset(), _reset(), _reset()], cost=_FakeCost()
    )
    assert summary.appraisal_meso == 200  # 큐브 2 × 100
    assert summary.reset_meso == 3000  # 재설정 3 × 1000
    assert summary.total_meso == 3200


def test_meso_with_real_cost_table() -> None:
    from maple_mate.history import potential_cost

    # 200제 큐브 1회(감정비 80만) + 200제 유니크 잠재 재설정 1회(38.25M).
    summary = aggregate_potential(
        [_cube(level=200)],
        [_reset(level=200, before=("유니크",), potential_type="잠재능력")],
        cost=potential_cost,
    )
    assert summary.appraisal_meso == 800_000
    assert summary.reset_meso == 38_250_000
    assert summary.total_meso == 39_050_000


def test_meso_additional_reset_uses_additional_table() -> None:
    from maple_mate.history import potential_cost

    # 에디 재설정은 에디 단가표 + 에디 등급(before_add 비면 add_grade 폴백).
    summary = aggregate_potential(
        [],
        [_reset(level=200, potential_type="에디셔널 잠재능력", add_grade="유니크")],
        cost=potential_cost,
    )
    assert summary.reset_meso == 74_800_000  # 에디 200제 유니크


# ── 집계: 단일 대상 보조 분포 ──────────────────────────────────────────────


def test_by_cube_type_descending() -> None:
    cubes = [
        _cube(cube_type="장인의 큐브"),
        _cube(cube_type="수상한 큐브"),
        _cube(cube_type="수상한 큐브"),
    ]
    summary = aggregate_potential(cubes, [])
    assert summary.by_cube_type == (("수상한 큐브", 2), ("장인의 큐브", 1))


def test_by_grade_counts_pot_and_add() -> None:
    cubes = [
        _cube(pot_grade="레전드리", add_grade="유니크"),
        _cube(pot_grade="유니크", add_grade="유니크"),
    ]
    summary = aggregate_potential(cubes, [])
    # 등급 내림차순. 레전드리: 잠재1·에디0, 유니크: 잠재1·에디2.
    assert summary.by_grade == (("레전드리", 1, 0), ("유니크", 1, 2))


def test_empty_inputs_produce_zero_summary() -> None:
    summary = aggregate_potential([], [])
    assert summary.cube_count == 0
    assert summary.reset_count == 0
    assert summary.tierups == ()
    assert summary.by_cube_type == ()
    assert summary.by_grade == ()
