"""잠재 메소 단가표 단위테스트 (나무위키 알려진 값 픽스처 대조)."""
from __future__ import annotations

from maple_mate.history import potential_cost as pc


# ── 큐브 감정비: floor(계수×L²/100)×100, 121+ 항상 부과 ─────────────────────


def test_appraisal_121plus_matches_wiki() -> None:
    # 121제 이상은 통찰력 무관 항상 부과(20×L²).
    assert pc.appraisal_cost(130) == 338_000
    assert pc.appraisal_cost(150) == 450_000
    assert pc.appraisal_cost(160) == 512_000
    assert pc.appraisal_cost(200) == 800_000


def test_appraisal_floor_to_100() -> None:
    # 2.5×90²=20,250 → 100단위 내림 20,200 (≤120 이라 charge 옵션으로 강제).
    assert pc.appraisal_cost(90, charge_under_121=True) == 20_200
    assert pc.appraisal_cost(110, charge_under_121=True) == 30_200
    assert pc.appraisal_cost(80, charge_under_121=True) == 16_000
    assert pc.appraisal_cost(100, charge_under_121=True) == 25_000
    assert pc.appraisal_cost(120, charge_under_121=True) == 36_000


def test_appraisal_free_under_121_by_default() -> None:
    # 통찰력 무료 가정: 30 이하·120 이하는 기본 0.
    assert pc.appraisal_cost(30) == 0
    assert pc.appraisal_cost(70) == 0
    assert pc.appraisal_cost(120) == 0


def test_appraisal_121_boundary_always_charged() -> None:
    # 121제는 무료 불가 → charge 옵션과 무관하게 부과.
    assert pc.appraisal_cost(121) == 292_800  # floor(20×121²/100)×100 = floor(292820/100)×100
    assert pc.appraisal_cost(121, charge_under_121=False) == 292_800


# ── 메소 재설정 단가: (레벨 구간, 등급) 룩업 ───────────────────────────────


def test_reset_cost_potential_table() -> None:
    assert pc.reset_cost(200, "유니크", "잠재능력") == 38_250_000
    assert pc.reset_cost(250, "레전드리", "잠재능력") == 50_000_000
    assert pc.reset_cost(150, "레어", "잠재능력") == 4_000_000  # 1~159 구간


def test_reset_cost_additional_table_is_higher() -> None:
    assert pc.reset_cost(200, "유니크", "에디셔널 잠재능력") == 74_800_000
    assert pc.reset_cost(160, "레전드리", "에디셔널 잠재능력") == 83_000_000
    # 같은 레벨·등급이라도 에디가 일반보다 비싸다.
    assert pc.reset_cost(200, "레전드리", "에디셔널 잠재능력") > pc.reset_cost(200, "레전드리", "잠재능력")


def test_reset_cost_bracket_boundaries() -> None:
    assert pc.reset_cost(159, "레어", "잠재능력") == 4_000_000
    assert pc.reset_cost(160, "레어", "잠재능력") == 4_250_000
    assert pc.reset_cost(199, "레어", "잠재능력") == 4_250_000
    assert pc.reset_cost(200, "레어", "잠재능력") == 4_500_000
    assert pc.reset_cost(249, "레어", "잠재능력") == 4_500_000
    assert pc.reset_cost(250, "레어", "잠재능력") == 5_000_000


def test_reset_cost_unknown_grade_is_zero() -> None:
    assert pc.reset_cost(200, "", "잠재능력") == 0
    assert pc.reset_cost(200, "노멀", "잠재능력") == 0
