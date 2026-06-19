"""유니온 변환 로직 단위테스트 (handoff §6: 챔피언 등급 분포 카운트)."""

from __future__ import annotations

from datetime import datetime

from maple_mate.nexon.client import KST
from maple_mate.nexon.errors import ErrorClass, NexonAPIError
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
    """fetch_union 은 user/union(D-1 명시) + union-champion(최신) 만 호출한다.

    union(ocid, date=...) 은 union_by_date[date] 가 있으면 그걸, 없으면 기본 payload 를
    돌린다. payload 가 Exception 이면 raise(미준비/에러 시뮬). 호출된 date 들은 union_dates 에 기록.
    """

    def __init__(self, union, champion, *, union_by_date=None):
        self._union = union
        self._champion = champion
        self._union_by_date = union_by_date or {}
        self.union_dates = []

    async def union(self, ocid, date=None):
        self.union_dates.append(date)
        payload = self._union_by_date.get(date, self._union)
        if isinstance(payload, Exception):
            raise payload
        return payload

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
        champion={
            "union_champion": [{"champion_grade": "SSS"}, {"champion_grade": "S"}]
        },
    )
    info = await fetch_union(nexon, "oc1")
    assert info.union_level == 8750
    assert info.union_grade == "그랜드 마스터 1"
    assert info.artifact_level == 45
    assert info.champion_grades == (("SSS", 1), ("S", 1))
    assert info.date is None


async def test_fetch_union_nullable_fields_pass_through():
    nexon = _FakeNexon(
        union={
            "union_level": None,
            "union_grade": None,
            "date": "2026-06-02T00:00:00+09:00",
        },
        champion={"union_champion": []},
    )
    info = await fetch_union(nexon, "oc1")
    assert info.union_level is None
    assert info.artifact_level is None  # union 응답에 없으면 None
    assert info.champion_grades == ()
    assert info.date == "2026-06-02T00:00:00+09:00"


async def test_fetch_union_calls_user_union_with_explicit_d1():
    # 넥슨이 date 무지정 user/union 을 200+null 로 회귀시킴 → 봇은 D-1 을 명시 호출해야 한다.
    now = datetime(2026, 6, 19, 12, 0, tzinfo=KST)  # D-1 = 2026-06-18
    nexon = _FakeNexon(
        union={
            "union_level": 9333,
            "union_artifact_level": 53,
            "date": "2026-06-18T00:00:00+09:00",
        },
        champion={"union_champion": [{"champion_grade": "SSS"}]},
    )
    info = await fetch_union(nexon, "oc1", now=now)
    assert nexon.union_dates == ["2026-06-18"]  # D-1 단일 호출(데이터 있으면 폴백 없음)
    assert info.union_level == 9333
    assert info.artifact_level == 53
    assert info.date == "2026-06-18T00:00:00+09:00"


async def test_fetch_union_falls_back_to_d2_when_d1_returns_null():
    # D-1 이 200+null(넥슨 회귀)이면 D-2 로 1회 폴백해 데이터를 회수한다.
    now = datetime(2026, 6, 19, 12, 0, tzinfo=KST)  # D-1=06-18, D-2=06-17
    nexon = _FakeNexon(
        union={"union_level": None, "union_artifact_level": None, "date": None},
        champion={"union_champion": []},
        union_by_date={
            "2026-06-17": {
                "union_level": 9333,
                "union_artifact_level": 53,
                "date": "2026-06-17T00:00:00+09:00",
            }
        },
    )
    info = await fetch_union(nexon, "oc1", now=now)
    assert nexon.union_dates == ["2026-06-18", "2026-06-17"]
    assert info.union_level == 9333
    assert info.date == "2026-06-17T00:00:00+09:00"


async def test_fetch_union_falls_back_when_d1_not_ready():
    # 새벽 0~2시 D-1 미생성(OPENAPI00009) → D-2 로 폴백(stale ocid 오분류 없이).
    now = datetime(2026, 6, 19, 1, 0, tzinfo=KST)
    nexon = _FakeNexon(
        union={
            "union_level": 9000,
            "union_artifact_level": 50,
            "date": "2026-06-17T00:00:00+09:00",
        },
        champion={"union_champion": []},
        union_by_date={
            "2026-06-18": NexonAPIError(
                "OPENAPI00009", "not ready", error_class=ErrorClass.DATA_NOT_READY
            )
        },
    )
    info = await fetch_union(nexon, "oc1", now=now)
    assert nexon.union_dates == ["2026-06-18", "2026-06-17"]
    assert info.union_level == 9000


async def test_fetch_union_propagates_invalid_ocid():
    # 잘못된 ocid(INVALID_ID)는 흡수하지 말고 raise → 호출자(_fetch_one)가 닉 재조회.
    import pytest

    now = datetime(2026, 6, 19, 12, 0, tzinfo=KST)
    nexon = _FakeNexon(
        union=NexonAPIError(
            "OPENAPI00003", "invalid id", error_class=ErrorClass.INVALID_ID
        ),
        champion={"union_champion": []},
    )
    with pytest.raises(NexonAPIError):
        await fetch_union(nexon, "stale", now=now)
    assert nexon.union_dates == ["2026-06-18"]  # 폴백 없이 즉시 전파
