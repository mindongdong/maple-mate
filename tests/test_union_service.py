"""유니온 변환 로직 단위테스트 (handoff §6: 챔피언 등급 분포 카운트)."""
from __future__ import annotations

from maple_mate.union.service import (
    count_champion_grades,
    fetch_union,
    order_grades,
)


def test_count_champion_grades_counts_observed_values():
    champs = [
        {"champion_grade": "SSS"},
        {"champion_grade": "SSS"},
        {"champion_grade": "S"},
        {"champion_grade": None},  # 무시
        {},  # 무시
    ]
    assert count_champion_grades(champs) == {"SSS": 2, "S": 1}


def test_count_champion_grades_empty_inputs():
    assert count_champion_grades(None) == {}
    assert count_champion_grades([]) == {}


def test_order_grades_known_order_then_unknown_alpha():
    counts = {"S": 3, "SSS": 2, "A": 1, "Z특": 1}
    # 알려진 등급(SSS>S>A) 먼저, 미지 등급은 뒤에 알파벳순.
    assert order_grades(counts) == [("SSS", 2), ("S", 3), ("A", 1), ("Z특", 1)]


class _FakeNexon:
    """fetch_union 은 user/union + union-champion 만 호출한다(아티팩트 레벨은 union 응답에 존재)."""

    def __init__(self, union, champion):
        self._union = union
        self._champion = champion

    async def union(self, ocid):
        return self._union

    async def union_champion(self, ocid):
        return self._champion


async def test_fetch_union_assembles_artifact_level_from_union_response():
    nexon = _FakeNexon(
        union={
            "union_level": 8750,
            "union_grade": "그랜드 마스터 1",
            "union_artifact_level": 45,  # 아티팩트 레벨은 user/union 에 있음(docs/api/union.md)
            "date": None,
        },
        champion={"union_champion": [{"champion_grade": "SSS"}, {"champion_grade": "S"}]},
    )
    info = await fetch_union(nexon, "oc1")
    assert info.union_level == 8750
    assert info.union_grade == "그랜드 마스터 1"
    assert info.artifact_level == 45
    assert info.champion_grades == (("SSS", 1), ("S", 1))
    assert info.date is None


async def test_fetch_union_nullable_fields_pass_through():
    nexon = _FakeNexon(
        union={"union_level": None, "union_grade": None, "date": "2026-06-02T00:00:00+09:00"},
        champion={"union_champion": []},
    )
    info = await fetch_union(nexon, "oc1")
    assert info.union_level is None
    assert info.artifact_level is None  # union 응답에 없으면 None
    assert info.champion_grades == ()
    assert info.date == "2026-06-02T00:00:00+09:00"
