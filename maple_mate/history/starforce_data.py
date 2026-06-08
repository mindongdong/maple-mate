"""스타포스 확률표·비용공식·도달가능스타 (정가 기준, 순수 데이터 모듈).

출처: docs/starforce-expected-value-data.md §1~3 (메수라이브 자료 추출).
검증: cost()·확률표가 기댓값/{레벨}_기댓값.png 와 일치(test_starforce_data.py).
별캐치 상시 반영·성수 하락 없음(실패=유지)·할인/파괴방지 미적용 = 분모(기대)와 동일 조건.
"""
from __future__ import annotations

import math

# 0~29성 각 행 = 현재 성수에서 1회 시도 결과 (성공, 유지, 파괴). 별캐치 반영값.
STARFORCE_PROB: tuple[tuple[float, float, float], ...] = (
    (0.95, 0.05, 0.0),
    (0.90, 0.10, 0.0),
    (0.85, 0.15, 0.0),
    (0.85, 0.15, 0.0),
    (0.80, 0.20, 0.0),
    (0.75, 0.25, 0.0),
    (0.70, 0.30, 0.0),
    (0.65, 0.35, 0.0),
    (0.60, 0.40, 0.0),
    (0.55, 0.45, 0.0),
    (0.50, 0.50, 0.0),
    (0.45, 0.55, 0.0),
    (0.40, 0.60, 0.0),
    (0.35, 0.65, 0.0),
    (0.30, 0.70, 0.0),
    (0.30, 0.679, 0.021),
    (0.30, 0.679, 0.021),
    (0.15, 0.782, 0.068),
    (0.15, 0.782, 0.068),
    (0.15, 0.765, 0.085),
    (0.30, 0.595, 0.105),
    (0.15, 0.7225, 0.1275),
    (0.15, 0.68, 0.17),
    (0.10, 0.72, 0.18),
    (0.10, 0.72, 0.18),
    (0.10, 0.72, 0.18),
    (0.07, 0.744, 0.186),
    (0.05, 0.76, 0.19),
    (0.03, 0.776, 0.194),
    (0.01, 0.792, 0.198),
)

MAX_STAR = len(STARFORCE_PROB)  # 30 (시도 가능한 성수는 0~29 → 도달 최대 30)

# 파괴 시 하락할 성수 (plain 모델: 12성 하락 + 스페어/복구비 0).
DESTROY_STAR = 12

# 10~29성 강화비용 공식의 divisor[star]. 명시되지 않은 22~29성은 200.
_DIVISOR: dict[int, int] = {
    10: 571, 11: 314, 12: 214, 13: 157, 14: 107,
    15: 200, 16: 200, 17: 150, 18: 70, 19: 45,
    20: 200, 21: 125,
}
_DEFAULT_DIVISOR = 200


def _round100(value: float) -> int:
    """100메소 단위 반올림(round-half-up). 메수라이브 시뮬레이터의 Math.round 와 일치."""
    return int(math.floor(value / 100 + 0.5)) * 100


def cost(level: int, star: int) -> int:
    """현재 성수 star(0~29)에서 1회 시도 비용(메소, 정가). data §2 공식.

    0~9성과 10성+ 공식이 다르다. 검증: 기댓값 이미지 "강화비용" 컬럼 재현.
    """
    if not 0 <= star < MAX_STAR:
        raise ValueError(f"star 는 0~{MAX_STAR - 1} 범위여야 합니다: {star}")
    base = level**3 * (star + 1)
    if star < 10:
        return _round100(1000 + base / 36)
    divisor = _DIVISOR.get(star, _DEFAULT_DIVISOR)
    return 1000 + _round100(level**3 * (star + 1) ** 2.7 / divisor)


def reachable_star(level: int) -> int:
    """레벨별 도달 가능한 최대 성수. data §3. 입력 검증·기대값 상한에 사용."""
    if level < 95:
        return 5
    if level <= 107:
        return 10
    if level <= 127:
        return 15
    if level <= 137:
        return 20
    return 30
