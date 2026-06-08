"""스타포스 확률표·비용공식·도달가능스타 단위테스트.

cost() 는 기댓값/{레벨}_기댓값.png "강화비용" 컬럼을 재현해야 한다(알려진 정답 oracle).
값 출처: 200·250레벨 검증 이미지(정가 plain). 교차검증 완료(200/0=223,200, 250/0=435,000).
"""
from __future__ import annotations

import pytest

from maple_mate.history.starforce_data import (
    MAX_STAR,
    STARFORCE_PROB,
    cost,
    reachable_star,
)

# 기댓값/200레벨_기댓값.png "강화비용" 컬럼 (성수 → 메소).
_COST_200 = {
    0: 223_200, 1: 445_400, 2: 667_700, 3: 889_900, 4: 1_112_100,
    5: 1_334_300, 6: 1_556_600, 7: 1_778_800, 8: 2_001_000, 9: 2_223_200,
    10: 9_083_700, 11: 20_891_500, 12: 38_048_200, 14: 111_984_100,
}
# 기댓값/250레벨_기댓값.png "강화비용" 컬럼.
_COST_250 = {
    0: 435_000, 1: 869_100, 2: 1_303_100, 3: 1_737_100, 4: 2_171_100,
    5: 2_605_200, 6: 3_039_200, 7: 3_473_200, 8: 3_907_300, 9: 4_341_300,
    10: 17_740_600, 11: 40_802_800, 12: 74_312_000, 13: 123_728_500, 14: 218_718_100,
}


@pytest.mark.parametrize("star,expected", _COST_200.items())
def test_cost_level_200_matches_image(star: int, expected: int) -> None:
    assert cost(200, star) == expected


@pytest.mark.parametrize("star,expected", _COST_250.items())
def test_cost_level_250_matches_image(star: int, expected: int) -> None:
    assert cost(250, star) == expected


def test_cost_rejects_out_of_range_star() -> None:
    with pytest.raises(ValueError):
        cost(200, MAX_STAR)
    with pytest.raises(ValueError):
        cost(200, -1)


@pytest.mark.parametrize(
    "level,expected",
    [(94, 5), (95, 10), (107, 10), (108, 15), (127, 15), (128, 20), (137, 20), (138, 30), (250, 30)],
)
def test_reachable_star_boundaries(level: int, expected: int) -> None:
    assert reachable_star(level) == expected


def test_prob_table_shape_and_rows_sum_to_one() -> None:
    assert len(STARFORCE_PROB) == 30
    for star, (success, maintain, destroy) in enumerate(STARFORCE_PROB):
        assert success + maintain + destroy == pytest.approx(1.0), star


def test_destroy_only_from_star_15() -> None:
    for star in range(15):
        assert STARFORCE_PROB[star][2] == 0.0, star
    for star in range(15, 30):
        assert STARFORCE_PROB[star][2] > 0.0, star
