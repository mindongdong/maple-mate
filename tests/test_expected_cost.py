"""기대값 엔진 단위테스트 — 마르코프 누적기댓값 vs 이미지 + 운지수/손익메소.

expected_meso(level, 0, N) 는 기댓값 이미지 "누적기댓값"(정가 plain)을 재현해야 한다.
이미지는 정수 메소로 절사 표기 → 엔진 float 와 ±1 차이(허용오차 2)로 검증. 파괴 구간(16성+)
포함 — 파괴→12성 되돌림 고정점 풀이가 맞아야 통과한다.
"""

from __future__ import annotations

import pytest

from maple_mate.history.expected_cost import (
    ClimbItem,
    actual_meso,
    actual_paid_meso,
    expected_meso,
    meso_luck_percentile,
    net_meso,
)

# 기댓값/200레벨_기댓값.png "누적기댓값" (reach N → 메소). 16~20성 = 파괴 구간.
_CUM_200 = {
    1: 234_947,
    2: 729_836,
    5: 3_952_431,
    10: 18_069_010,
    15: 732_061_370,
    16: 1_015_240_995,
    17: 1_360_520_194,
    18: 2_811_073_257,
    20: 13_539_425_831,
}
# 기댓값/250레벨_기댓값.png "누적기댓값".
_CUM_250 = {
    1: 457_894,
    5: 7_714_142,
    10: 35_278_280,
    12: 161_432_369,
    14: 700_722_369,
    15: 1_429_782_702,
}


@pytest.mark.parametrize("n,expected", _CUM_200.items())
def test_expected_meso_level_200_matches_cumulative_image(
    n: int, expected: int
) -> None:
    assert expected_meso(200, 0, n) == pytest.approx(expected, abs=2)


@pytest.mark.parametrize("n,expected", _CUM_250.items())
def test_expected_meso_level_250_matches_cumulative_image(
    n: int, expected: int
) -> None:
    assert expected_meso(250, 0, n) == pytest.approx(expected, abs=2)


def test_expected_meso_zero_when_end_not_above_start() -> None:
    assert expected_meso(200, 5, 5) == 0.0
    assert expected_meso(200, 7, 3) == 0.0


def test_expected_meso_destruction_region_costs_more_than_no_destruction() -> None:
    # 16성(파괴 구간 진입)은 15성보다 비싸야 한다(파괴 후 재등반 기대비용 반영).
    assert expected_meso(200, 0, 16) > expected_meso(200, 0, 15)


def test_expected_meso_interval_uses_absorbing_start() -> None:
    # 구간 시작이 0 이 아니어도 흡수 비용으로 계산된다(파괴는 12로 되돌림).
    v = expected_meso(200, 15, 18)
    assert v > 0


def test_actual_meso_sums_per_attempt_cost() -> None:
    # cost(200,0)+cost(200,1) = 223_200 + 445_400.
    assert actual_meso(200, [0, 1]) == 223_200 + 445_400
    assert actual_meso(200, []) == 0


def test_net_meso_rounds_difference() -> None:
    assert net_meso(100, 250.4) == -150  # round(100 - 250.4)
    assert net_meso(1000, 600.0) == 400


# ── meso_luck_percentile: 메소 행운 백분위 (ADR-0002) ──────────────────────────


def test_meso_luck_none_when_no_items() -> None:
    assert meso_luck_percentile([]) is None


def test_meso_luck_mc_mean_approximates_markov_expected() -> None:
    # 시뮬 평균이 마르코프 기대값과 ±5% 이내(엔진 일관성). 0→18(파괴 구간 포함). 무이벤트 마스크.
    from maple_mate.history.expected_cost import _item_meso_samples

    samples = _item_meso_samples(200, 0, 18, frozenset(), frozenset(), 2000)
    mc_mean = sum(samples) / len(samples)
    assert mc_mean == pytest.approx(expected_meso(200, 0, 18), rel=0.05)


def test_meso_luck_high_when_cheap() -> None:
    # 기댓값의 40%만 쓰면 매우 운 좋음 → 상위권(L 큼).
    exp = expected_meso(200, 0, 18)
    score = meso_luck_percentile([(200, 0, 18, int(exp * 0.4))])
    assert score is not None and score > 80


def test_meso_luck_low_when_expensive() -> None:
    # 기댓값의 2배를 쓰면 매우 운 나쁨 → 하위권(L 작음).
    exp = expected_meso(200, 0, 18)
    score = meso_luck_percentile([(200, 0, 18, int(exp * 2))])
    assert score is not None and score < 20


def test_meso_luck_monotonic_cheaper_is_luckier() -> None:
    exp = expected_meso(200, 0, 18)
    cheap = meso_luck_percentile([(200, 0, 18, int(exp * 0.6))])
    pricey = meso_luck_percentile([(200, 0, 18, int(exp * 1.4))])
    assert cheap is not None and pricey is not None and cheap > pricey


def test_meso_luck_same_bucket_items_are_decorrelated() -> None:
    # 같은 (시작★,최종★) 장비 여러 개를 똑같은 비율로 싸게 끝냈으면, 독립 합산상 1개보다
    # 훨씬 더 운 좋아야 한다(중심극한: 평균에서 √m·σ 만큼 더 벗어남). 시드 상관 버그가
    # 있으면 완전 상관이라 1개와 동일한 백분위로 압축돼 이 검증이 실패한다.
    exp = expected_meso(200, 0, 18)
    cheap = int(exp * 0.6)
    one = meso_luck_percentile([(200, 0, 18, cheap)])
    five = meso_luck_percentile([(200, 0, 18, cheap)] * 5)
    assert one is not None and five is not None
    assert five > one + 5  # 압축이 풀려 유의하게 더 높은 행운 백분위


def test_meso_luck_null_climb_with_spend_is_worst() -> None:
    # 시작★=최종★(별 못 올림)인데 메소를 썼으면 최하위(0.0).
    assert meso_luck_percentile([(200, 17, 17, 5_000_000)]) == 0.0


def test_meso_luck_null_climb_no_spend_is_neutral() -> None:
    assert meso_luck_percentile([(200, 17, 17, 0)]) == 50.0


# ── 이벤트 보정 (ADR-0016) ─────────────────────────────────────────────────


def test_no_event_masks_match_legacy_values() -> None:
    # 빈 마스크 = 정가·무이벤트 회귀: 기대값/분포 모두 현행 값과 동일.
    assert expected_meso(200, 15, 18, frozenset(), frozenset()) == expected_meso(
        200, 15, 18
    )
    assert meso_luck_percentile(
        [ClimbItem(200, 0, 18, 5_000_000_000)]
    ) == meso_luck_percentile([(200, 0, 18, 5_000_000_000)])


def test_destroy_reduction_lowers_expected_in_destroy_region() -> None:
    # 파괴감소(d↓ → 재등반↓)는 파괴 구간 기대값을 낮춘다.
    destroy = frozenset(range(15, 22))
    assert expected_meso(200, 15, 21, destroy, frozenset()) < expected_meso(200, 15, 21)


def test_destroy_reduction_below_destroy_floor_has_no_effect() -> None:
    # 파괴 없는 성수(d=0)는 파괴감소 마스크가 무영향(11→13 구간).
    destroy = frozenset({11, 12})
    assert expected_meso(200, 11, 13, destroy, frozenset()) == expected_meso(
        200, 11, 13
    )


def test_event_adjustment_pulls_inflated_luck_toward_median() -> None:
    # 핵심: 파괴감소 이벤트 중 강화한 실지불을 *무이벤트* 분포로 재면 과대평가(운 좋아 보임).
    # 같은 actual 을 *이벤트 조건* 분포로 재면 백분위가 낮아진다(50%쪽 회귀). 분포가 더 싸지므로
    # 고정 actual 대비 '더 비싼 표본 비율'이 줄어 L 가 작아진다(수학적으로 naive ≥ adjusted).
    destroy = frozenset(range(15, 22))
    actual = int(expected_meso(200, 15, 21, destroy, frozenset()))
    naive = meso_luck_percentile([ClimbItem(200, 15, 21, actual)])
    adjusted = meso_luck_percentile(
        [ClimbItem(200, 15, 21, actual, destroy, frozenset())]
    )
    assert naive is not None and adjusted is not None
    assert naive > adjusted


def test_uniform_discount_is_percentile_neutral() -> None:
    # 할인을 actual·분포 양쪽에 동일 적용(모든 성수)하면 백분위는 불변 — 0.7 균일 스케일은
    # 순서를 보존한다(손익도 0.7배일 뿐 부호·정렬 동일 = 할인 중립, CONTEXT §165).
    all_stars = frozenset(range(30))
    actual = int(expected_meso(200, 0, 18) * 0.8)
    base = meso_luck_percentile([ClimbItem(200, 0, 18, actual)])
    discounted = meso_luck_percentile(
        [ClimbItem(200, 0, 18, actual * 0.7, frozenset(), all_stars)]
    )
    assert base is not None and discounted is not None
    assert discounted == pytest.approx(base, abs=0.5)


def test_actual_paid_meso_applies_discount_per_attempt() -> None:
    # 실지불 = 시도별 실제 할인 플래그. 할인 시도는 0.7배, 정가 시도는 그대로.
    cost_11, cost_12 = 20_891_500, 38_048_200  # cost(200,11)·cost(200,12)
    full = actual_paid_meso(200, [(11, False), (12, False)])
    assert full == float(actual_meso(200, [11, 12]))
    half_disc = actual_paid_meso(200, [(11, True), (12, False)])
    assert half_disc == pytest.approx(cost_11 * 0.7 + cost_12)
