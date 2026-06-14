"""ranking_overall 파싱 단위테스트 (httpx mock). 스파이크 실측 응답형 재현 — 작업지시서 #2."""

from __future__ import annotations

import httpx
import pytest

from maple_mate.nexon.client import NexonClient
from maple_mate.nexon.errors import ErrorClass, NexonAPIError

# 스파이크 실측 응답(spike/raw/R_overall_d1.json) 1건.
_ENTRY = {
    "date": "2026-06-13",
    "world_name": "크로아",
    "ranking": 129978,
    "character_name": "손바",
    "character_level": 287,
    "character_exp": 72295476476158,
    "class_name": "초월자",
    "sub_class_name": "제로",
    "character_popularity": 2,
    "character_guildname": "거울",
}


def _client(handler, **kwargs) -> NexonClient:
    return NexonClient(
        "app_key",
        throttle=0.0,
        retry_wait=0.0,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def test_ranking_overall_sends_app_key_ocid_and_date():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/maplestory/v1/ranking/overall"
        assert request.url.params["ocid"] == "oc1"
        # date 무지정 시 실 API 가 400 OPENAPI00004 → 반드시 명시적 D-1 전달(스파이크 G0).
        assert request.url.params["date"] == "2026-06-13"
        assert request.headers["x-nxopen-api-key"] == "app_key"
        return httpx.Response(200, json={"ranking": [_ENTRY]})

    async with _client(handler) as client:
        entry = await client.ranking_overall("oc1", "2026-06-13")
    assert entry is not None
    assert entry["character_exp"] == 72295476476158
    assert entry["ranking"] == 129978
    assert entry["character_level"] == 287


async def test_ranking_overall_returns_zeroth_entry_only():
    # ocid+date 응답엔 대상 1건만 — [0] 이 곧 그 캐릭터(닉 매칭 불요).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ranking": [_ENTRY]})

    async with _client(handler) as client:
        entry = await client.ranking_overall("oc1", "2026-06-13")
    assert entry["character_name"] == "손바"


async def test_ranking_overall_empty_list_is_none():
    # 빈 ranking = 미등재/미준비 → None(에러 아님).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ranking": []})

    async with _client(handler) as client:
        assert await client.ranking_overall("oc1", "2026-06-13") is None


async def test_ranking_overall_missing_key_is_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with _client(handler) as client:
        assert await client.ranking_overall("oc1", "2026-06-13") is None


async def test_ranking_overall_nexon_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500, json={"error": {"name": "OPENAPI00001", "message": "internal"}}
        )

    async with _client(handler) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.ranking_overall("oc1", "2026-06-13")
    assert exc.value.error_class is ErrorClass.NEXON_API
