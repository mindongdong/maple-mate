"""scripts/refresh_challengers.resolve — 기존 ocid 우선, 무효일 때만 닉네임 재조회."""

from __future__ import annotations

import pytest

from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from scripts.refresh_challengers import Refreshed, resolve


class FakeNexon:
    def __init__(self, basics: dict[str, dict | NexonAPIError], ids: dict[str, str]):
        self.basics = basics
        self.ids = ids
        self.id_calls: list[str] = []

    async def character_basic(self, ocid: str) -> dict:
        result = self.basics[ocid]
        if isinstance(result, NexonAPIError):
            raise result
        return result

    async def get_ocid(self, nickname: str) -> str:
        self.id_calls.append(nickname)
        return self.ids[nickname]


def _err(error_class: ErrorClass) -> NexonAPIError:
    return NexonAPIError("X", "x", error_class=error_class)


async def test_same_ocid_refreshes_world_and_level():
    nexon = FakeNexon({"old": {"world_name": "스카니아", "character_level": "275"}}, {})
    assert await resolve(nexon, "old", "닉") == Refreshed("old", "스카니아", 275)
    assert nexon.id_calls == []  # 기존 ocid 유효 → 닉 재조회 없음


@pytest.mark.parametrize("cls", [ErrorClass.INVALID_ID, ErrorClass.INVALID_PARAM])
async def test_stale_ocid_falls_back_to_nickname(cls):
    nexon = FakeNexon(
        {"old": _err(cls), "new": {"world_name": "루나", "character_level": 260}},
        {"닉": "new"},
    )
    assert await resolve(nexon, "old", "닉") == Refreshed("new", "루나", 260)
    assert nexon.id_calls == ["닉"]


async def test_outage_does_not_fall_back():
    nexon = FakeNexon({"old": _err(ErrorClass.NEXON_API)}, {"닉": "new"})
    with pytest.raises(NexonAPIError):
        await resolve(nexon, "old", "닉")
    assert nexon.id_calls == []  # 장애는 닉 재조회로 넘기지 않음(오연결 방지)


_EMPTY_BASIC = {"world_name": None, "character_level": None}  # 이전된 옛 ocid 실측 응답


async def test_empty_basic_falls_back_to_nickname():
    nexon = FakeNexon(
        {"old": _EMPTY_BASIC, "new": {"world_name": "크로아", "character_level": 285}},
        {"닉": "new"},
    )
    assert await resolve(nexon, "old", "닉") == Refreshed("new", "크로아", 285)
    assert nexon.id_calls == ["닉"]


async def test_empty_basic_after_fallback_fails():
    nexon = FakeNexon({"old": _EMPTY_BASIC, "new": _EMPTY_BASIC}, {"닉": "new"})
    with pytest.raises(NexonAPIError) as info:
        await resolve(nexon, "old", "닉")
    assert info.value.error_class is ErrorClass.INVALID_ID
