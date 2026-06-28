"""스타포스 기대값·운빨 엔진 (순수). 메소 컬럼(기대/실제)과 운빨 백분위 산출.

- expected_meso: 마르코프 흡수 기대비용(시작★→최종★). 파괴→12성 되돌림을 고정점으로 풀이.
- actual_meso: 이력 시도들의 시도당 정가 비용 합산(파괴 추가비 0). /비틱 등 정가 경로 전용.
- actual_paid_meso: 실지불(할인 반영) 합산 — /스타포스 운빨·손익의 분자(ADR-0016).
- net_meso: 총 사용 − 기댓값 (기댓값 대비 손익, CONTEXT.md).
- meso_luck_percentile: 실제 총 메소가 가능한 결과 분포에서 상위 몇 %인지(ADR-0002).
  손익과 같은 메소 기반 → 정렬 일치, 파괴 손해 반영. 몬테카를로(레벨 무관 시도분포 캐시).

이벤트 보정(ADR-0016): 기대값·분포·비용을 강화 당시 이벤트(파괴확률 감소·비용 할인)로 중립화한다 —
성수별 마스크(destroy_stars·discount_stars)를 주입받아 조정 확률 `(p',m',d')`·조정 비용 `cost'`를 쓴다.
마스크가 빈 frozenset 이면 정가·무이벤트와 **동일**(회귀 가드).

검증: expected_meso(level, 0, N) 가 기댓값 이미지 "누적기댓값" 재현(test_expected_cost.py).
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from functools import lru_cache
from typing import NamedTuple

from .starforce_data import (
    DESTROY_STAR,
    MAX_STAR,
    STARFORCE_PROB,
    apply_destroy_reduction,
    cost,
    discounted_cost,
)


class ClimbItem(NamedTuple):
    """운빨 분포 산출 단위 1개 — 레벨 매칭 아이템의 climb + 실지불 + 성수별 이벤트 마스크.

    destroy_stars/discount_stars 가 빈 frozenset 이면 정가·무이벤트(현행과 동일). 4-튜플
    ``(level, start, end, actual)`` 도 ``ClimbItem(*t)`` 로 받아 빈 마스크로 정규화한다(회귀 가드).
    """

    level: int
    start_star: int
    end_star: int
    actual_meso: float
    destroy_stars: frozenset[int] = frozenset()
    discount_stars: frozenset[int] = frozenset()


def _prob_row(star: int, destroy_stars: frozenset[int]) -> tuple[float, float, float]:
    """성수의 1행 전이확률 — destroy_stars 에 들면 파괴감소 적용, 아니면 정가표."""
    row = STARFORCE_PROB[star]
    return apply_destroy_reduction(row) if star in destroy_stars else row


def _item_cost(level: int, star: int, discount_stars: frozenset[int]) -> float:
    """성수의 1회 시도 비용 — discount_stars 에 들면 30% 할인, 아니면 정가(float)."""
    return (
        discounted_cost(level, star)
        if star in discount_stars
        else float(cost(level, star))
    )


DEFAULT_SIMS = (
    5000  # (시작★,최종★)별 몬테카를로 표본 수. 분포는 레벨 무관이라 1회만 계산·캐시.
)
_DECORR_STRIDE = (
    7919  # 같은 (시작★,최종★) 아이템 간 페어링 탈상관용 소수 오프셋(아래 참조).
)
_SIM_GUARD = 5000  # 단일 시뮬 최대 시도(파괴 지옥 꼬리에서 무한루프 방지)


def expected_meso(
    level: int,
    start_star: int,
    end_star: int,
    destroy_stars: frozenset[int] = frozenset(),
    discount_stars: frozenset[int] = frozenset(),
) -> float:
    """start_star → end_star 도달까지의 기대 소모 메소. 마스크 빈 경우 = 정가·무이벤트(현행).

    상태=성수. 전이: 성공→s+1 / 유지→s / 파괴→DESTROY_STAR(12). 비용=조정비용 매 시도.
    흡수 상태 C[end]=0, C[s]=(cost+p·C[s+1]+d·C[12])/(1−m). 파괴가 12로 되돌리므로
    C[12]=X 를 미지수로 두고 C[s]=a[s]+b[s]·X 하향 전개 → C[12]=X 고정점으로 X 해 → 역대입.

    이벤트 보정(ADR-0016): destroy_stars 성수는 `(p,m',d')` 조정(파괴↓), discount_stars 성수는
    비용 30% 할인. 둘 다 그 성수의 a/b 계수에만 들어가 기대값을 강화 당시 조건으로 맞춘다.
    """
    if end_star <= start_star:
        return 0.0
    if not 0 <= start_star or end_star > MAX_STAR:
        raise ValueError(f"성수 범위 오류: start={start_star}, end={end_star}")

    # C[s] = a[s] + b[s]·X (X = C[DESTROY_STAR]). a[end]=b[end]=0 (흡수).
    a = [0.0] * (end_star + 1)
    b = [0.0] * (end_star + 1)
    for s in range(end_star - 1, -1, -1):
        p, m, d = _prob_row(s, destroy_stars)
        denom = 1.0 - m
        a[s] = (_item_cost(level, s, discount_stars) + p * a[s + 1]) / denom
        b[s] = (p * b[s + 1] + d) / denom

    has_destroy = any(
        _prob_row(s, destroy_stars)[2] > 0 for s in range(start_star, end_star)
    )
    if has_destroy and DESTROY_STAR <= end_star:
        x = a[DESTROY_STAR] / (1.0 - b[DESTROY_STAR])
    else:
        x = 0.0  # 파괴 구간 미포함 → b[s] 전부 0, X 무관(곱해서 사라짐)
    return a[start_star] + b[start_star] * x


def actual_meso(level: int, before_stars: Iterable[int]) -> int:
    """이력 시도들의 실제 소모(분자, 정가). 각 행 cost(level, before_star) 합. 파괴 추가비 0.

    재등반 시도는 이력에 별도 행으로 이미 존재(before_star 가 낮아짐) → 자동 반영.
    /비틱(정가 경로) 전용. /스타포스 는 actual_paid_meso(할인 반영)를 쓴다(ADR-0016).
    """
    return sum(cost(level, s) for s in before_stars)


def actual_paid_meso(level: int, attempts: Iterable[tuple[int, bool]]) -> float:
    """이력 시도들의 실지불 합(분자, 할인 반영). attempts = [(before_star, 할인적용여부), ...].

    각 시도의 **실제** 할인 플래그로 정확 계산(ADR-0016 §3-3): 할인 시 정가×0.7, 아니면 정가.
    float 유지(표시에서 정수화). 무이벤트(전부 False)면 actual_meso 와 동일.
    """
    return sum(
        discounted_cost(level, s) if discounted else float(cost(level, s))
        for s, discounted in attempts
    )


def net_meso(actual: float, expected: float) -> int:
    """기댓값 대비 손익 = 실제 − 기대 (반올림 정수). 음수면 기댓값보다 덜 씀(운 좋음)."""
    return round(actual - expected)


@lru_cache(maxsize=4096)
def _climb_attempt_samples(
    start: int, end: int, destroy_stars: frozenset[int], n_sims: int
) -> tuple[tuple[int, ...], ...]:
    """start★→end★ climb 을 n_sims 회 시뮬 → 각 표본의 '성수별 시도횟수' 벡터.

    레벨 무관(확률표만 결정) → (start,end,파괴마스크)별 1회 계산 후 캐시. 결정적 시드라 재현 가능.
    전이: 성공→s+1 / 유지→s / 파괴→DESTROY_STAR. destroy_stars 성수는 파괴감소 확률 사용.
    가드 초과(극단 파괴 꼬리)는 절단. 할인은 비용에만 영향이라 이 단계 키에 불포함.
    """
    rng = random.Random(start * 100 + end)
    probs = [_prob_row(s, destroy_stars) for s in range(MAX_STAR)]
    samples: list[tuple[int, ...]] = []
    for _ in range(n_sims):
        counts = [0] * MAX_STAR
        star = start
        guard = 0
        while star < end and guard < _SIM_GUARD:
            guard += 1
            counts[star] += 1
            p, m, _d = probs[star]
            r = rng.random()
            if r < p:
                star += 1
            elif r < p + m:
                pass  # 유지
            else:
                star = DESTROY_STAR  # 파괴 → 12성 하락
        samples.append(tuple(counts))
    return tuple(samples)


@lru_cache(maxsize=4096)
def _item_meso_samples(
    level: int,
    start: int,
    end: int,
    destroy_stars: frozenset[int],
    discount_stars: frozenset[int],
    n_sims: int,
) -> tuple[float, ...]:
    """(level,start,end,마스크) climb 의 총 메소 표본 분포. 시도횟수 벡터 × 조정 비용 합산."""
    costs = [_item_cost(level, s, discount_stars) for s in range(MAX_STAR)]
    return tuple(
        sum(n * costs[s] for s, n in enumerate(vec))
        for vec in _climb_attempt_samples(start, end, destroy_stars, n_sims)
    )


def meso_luck_percentile(
    items: Sequence[ClimbItem | tuple], n_sims: int = DEFAULT_SIMS
) -> float | None:
    """실제 총 메소가 가능한 결과 분포에서 차지하는 행운 백분위 (0~100, 높을수록 운 좋음).

    items = [ClimbItem(level, 시작★, 최종★, 실지불, destroy_stars, discount_stars), ...]
    (레벨 매칭된 아이템; 4-튜플도 빈 마스크로 정규화). 각 아이템의 시작★→최종★ climb 분포를
    **강화 당시 이벤트 조건**(마스크)으로 시뮬해 '총 메소' 분포를 만들고, 실지불 총합이 그보다 비싼
    표본의 비율(mid-p)을 L 로 반환한다(ADR-0002·0016). 싸게 끝냈으면 L 큼=운 좋음, 비싸게
    썼으면(파괴 출혈 등) L 작음=운 나쁨. 정렬·표시는 손익(메소)과 일관된다.

    무진행(시작★≥최종★)이면 그 아이템 시뮬 비용=0(실제는 그대로 가산) → 헛돈이 불운으로
    반영. 매칭 아이템이 없으면 None.

    탈상관: 시뮬 분포는 (시작★,최종★,마스크)별로 캐시 공유한다(성능). 같은 구간 아이템(예: 방어구
    세트를 함께 강화)은 동일 표본열을 보므로, 그대로 인덱스 페어링하면 합 분포가 완전 상관 →
    분산이 √m배가 아닌 m배로 부풀어 운빨이 50%로 압축된다. 아이템마다 다른 오프셋으로 표본열을
    회전(_DECORR_STRIDE)해, 같은 k에서 서로 다른 독립 표본이 더해지도록 한다(합 분포 복원).
    """
    if not items:
        return None
    climbs = [ClimbItem(*it) for it in items]  # 4-튜플(무이벤트)도 빈 마스크로 정규화
    totals = [0.0] * n_sims
    actual_total = 0.0
    any_climb = False
    for idx, it in enumerate(climbs):
        actual_total += it.actual_meso
        if it.end_star > it.start_star:
            any_climb = True
            samples = _item_meso_samples(
                it.level,
                it.start_star,
                it.end_star,
                it.destroy_stars,
                it.discount_stars,
                n_sims,
            )
            offset = (idx * _DECORR_STRIDE) % n_sims  # 아이템별 고유 회전 → 독립 페어링
            for k in range(n_sims):
                totals[k] += samples[(k + offset) % n_sims]
    if not any_climb:  # 모든 아이템 무진행 → 헛돈만 썼으면 최하위, 아니면 중립
        return 0.0 if actual_total > 0 else 50.0

    greater = sum(1 for t in totals if t > actual_total)
    equal = sum(1 for t in totals if t == actual_total)
    return 100.0 * (greater + 0.5 * equal) / n_sims
