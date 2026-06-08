"""잠재 메소 비용표 (G2 해소). 큐브 감정비 + 메소 잠재/에디 재설정 단가.

넥슨 API에 메소 소모량 필드가 없어(실측, docs/api/history.md) `item_level`·등급 기준 단가표로
역산한다(potential-handoff.md G2). 출처: 나무위키 메이플스토리 잠재능력 — 감정비 공식 + 재설정 단가표.

메소 출처 두 종:
  - 큐브 사용(`history/cube`) → **감정비**(레벨 기준). 큐브 아이템 자체 값(현금/이벤트)은 스코프 밖.
  - 메소 직접 재설정(`history/potential`) → **재설정 단가**(레벨 구간 × 등급, 잠재/에디 별표).
"""
from __future__ import annotations

# ── 큐브 감정비 ─────────────────────────────────────────────────────────────
# 감정비 = floor(계수 × L² / 100) × 100. 계수 = 0.5(31~70) / 2.5(71~120) / 20(121~).
# ⚠️ 120제 이하는 통찰력(Insight) 트레잇으로 무료가 될 수 있어 기본 무료 가정(charge_under_121=False).
#    121제 이상은 통찰력 무관 항상 부과 → 엔드게임(200제 등) 메소는 정확.


def appraisal_cost(item_level: int, *, charge_under_121: bool = False) -> int:
    """큐브 1회 사용 감정비(메소). 30제 이하·(기본)120제 이하는 0.

    charge_under_121=True 면 통찰력 무료를 무시하고 31~120제도 공식대로 부과한다.
    """
    if item_level <= 30:
        return 0
    if item_level <= 120:
        if not charge_under_121:
            return 0  # 통찰력 무료 가정
        raw = (item_level * item_level) // 2 if item_level <= 70 else (5 * item_level * item_level) // 2
    else:
        raw = 20 * item_level * item_level
    return (raw // 100) * 100  # 100메소 단위 내림


# ── 메소 재설정 단가 ────────────────────────────────────────────────────────
# (레벨 구간 하한) → {등급: 메소}. 등급 = 재설정 시점(=before) 등급.
_POTENTIAL_RESET: dict[int, dict[str, int]] = {
    250: {"레어": 5_000_000, "에픽": 20_000_000, "유니크": 42_500_000, "레전드리": 50_000_000},
    200: {"레어": 4_500_000, "에픽": 18_000_000, "유니크": 38_250_000, "레전드리": 45_000_000},
    160: {"레어": 4_250_000, "에픽": 17_000_000, "유니크": 36_125_000, "레전드리": 42_500_000},
    1: {"레어": 4_000_000, "에픽": 16_000_000, "유니크": 34_000_000, "레전드리": 40_000_000},
}
_ADDITIONAL_RESET: dict[int, dict[str, int]] = {
    250: {"레어": 12_250_000, "에픽": 34_300_000, "유니크": 83_300_000, "레전드리": 98_000_000},
    200: {"레어": 11_000_000, "에픽": 30_800_000, "유니크": 74_800_000, "레전드리": 88_000_000},
    160: {"레어": 10_375_000, "에픽": 29_050_000, "유니크": 70_550_000, "레전드리": 83_000_000},
    1: {"레어": 9_750_000, "에픽": 27_300_000, "유니크": 66_300_000, "레전드리": 78_000_000},
}
_BRACKET_MINS = (250, 200, 160, 1)  # 내림차순


def _bracket(item_level: int) -> int:
    for m in _BRACKET_MINS:
        if item_level >= m:
            return m
    return 1


def reset_cost(item_level: int, grade: str, potential_type: str) -> int:
    """메소 잠재/에디 재설정 1회 비용. 등급 미상(레어/에픽/유니크/레전드리 외)이면 0.

    potential_type 에 '에디' 포함 시 에디셔널 단가표, 아니면 일반 잠재 단가표.
    """
    table = _ADDITIONAL_RESET if "에디" in potential_type else _POTENTIAL_RESET
    return table[_bracket(item_level)].get(grade, 0)
