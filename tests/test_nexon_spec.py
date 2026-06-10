"""스펙류 클라이언트 메서드 단위테스트 (httpx mock). date 무지정 호출 계약 검증 — handoff §1·§3.1."""

from __future__ import annotations

import httpx

from maple_mate.nexon.client import NexonClient


def _client(handler) -> NexonClient:
    return NexonClient(
        "app_key", throttle=0.0, retry_wait=0.0, transport=httpx.MockTransport(handler)
    )


async def test_character_basic_sends_ocid_and_omits_date_by_default():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/maplestory/v1/character/basic"
        assert request.url.params["ocid"] == "oc1"
        # date 무지정(최신 ready): None 파라미터는 쿼리에서 제거되어야 한다.
        assert "date" not in request.url.params
        assert request.headers["x-nxopen-api-key"] == "app_key"
        return httpx.Response(200, json={"date": None, "character_level": 285})

    async with _client(handler) as client:
        data = await client.character_basic("oc1")
    assert data["character_level"] == 285


async def test_spec_passes_date_when_explicitly_given():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["date"] == "2026-06-02"
        return httpx.Response(200, json={})

    async with _client(handler) as client:
        await client.character_stat("oc1", "2026-06-02")


async def test_union_endpoints_target_user_paths():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.url.params["ocid"] == "oc9"
        return httpx.Response(200, json={})

    async with _client(handler) as client:
        await client.union("oc9")
        await client.union_artifact("oc9")
        await client.union_champion("oc9")

    assert seen == [
        "/maplestory/v1/user/union",
        "/maplestory/v1/user/union-artifact",
        "/maplestory/v1/user/union-champion",
    ]


async def test_character_spec_endpoint_paths():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={})

    async with _client(handler) as client:
        await client.character_ability("oc1")
        await client.character_symbol_equipment("oc1")
        await client.character_hexamatrix("oc1")
        await client.character_hexamatrix_stat("oc1")
        await client.character_item_equipment("oc1")

    assert seen == [
        "/maplestory/v1/character/ability",
        "/maplestory/v1/character/symbol-equipment",
        "/maplestory/v1/character/hexamatrix",
        "/maplestory/v1/character/hexamatrix-stat",
        "/maplestory/v1/character/item-equipment",
    ]
