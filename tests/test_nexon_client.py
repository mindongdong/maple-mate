"""넥슨 클라이언트 단위테스트 (httpx mock). 실호출 없음 — handoff §6."""
from __future__ import annotations

import httpx
import pytest

from maple_mate.nexon.client import NexonClient
from maple_mate.nexon.errors import ErrorClass, NexonAPIError


def _client(handler, **kwargs) -> NexonClient:
    # throttle/retry_wait=0 으로 테스트를 빠르게.
    return NexonClient(
        "app_key",
        throttle=0.0,
        retry_wait=0.0,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _error_response(status: int, code: str, message: str = "msg") -> httpx.Response:
    return httpx.Response(status, json={"error": {"name": code, "message": message}})


async def test_get_ocid_parses_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/maplestory/v1/id"
        assert request.url.params["character_name"] == "손가락"
        return httpx.Response(200, json={"ocid": "abc123"})

    async with _client(handler) as client:
        assert await client.get_ocid("손가락") == "abc123"


async def test_request_sends_app_key_header_by_default():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-nxopen-api-key"] == "app_key"
        return httpx.Response(200, json={"ocid": "x"})

    async with _client(handler) as client:
        await client.get_ocid("c")


async def test_verify_personal_key_sends_count_and_date_with_personal_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/maplestory/v1/history/starforce"
        assert request.url.params["count"] == "10"
        # date 누락 시 실 API 가 OPENAPI00004 → 반드시 date(YYYY-MM-DD) 전달.
        assert "date" in request.url.params
        assert len(request.url.params["date"]) == 10
        assert request.headers["x-nxopen-api-key"] == "personal_key"
        return httpx.Response(200, json={"count": 0, "starforce_history": []})

    async with _client(handler) as client:
        assert await client.verify_personal_key("personal_key") is True


async def test_verify_personal_key_data_not_ready_treated_as_valid():
    def handler(request: httpx.Request) -> httpx.Response:
        return _error_response(400, "OPENAPI00009", "Please wait until the data is ready")

    async with _client(handler) as client:
        # 데이터 미준비여도 키 인증은 성공 → 유효로 간주.
        assert await client.verify_personal_key("personal_key") is True


async def test_verify_personal_key_invalid_returns_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return _error_response(400, "OPENAPI00005", "The apikey is not valid.")

    async with _client(handler) as client:
        assert await client.verify_personal_key("bad_key") is False


async def test_verify_personal_key_other_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return _error_response(500, "OPENAPI00001", "internal")

    async with _client(handler) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.verify_personal_key("k")
    assert exc.value.error_class is ErrorClass.NEXON_API


async def test_rate_limit_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _error_response(429, "OPENAPI00007", "try again later")
        return httpx.Response(200, json={"ocid": "ok"})

    async with _client(handler, max_retry=3) as client:
        assert await client.get_ocid("c") == "ok"
    assert calls["n"] == 2  # 첫 429 → 재시도 → 200


async def test_rate_limit_exhausts_retries_and_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return _error_response(429, "OPENAPI00007", "try again later")

    async with _client(handler, max_retry=2) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.get_ocid("c")
    assert exc.value.error_class is ErrorClass.RATE_LIMIT


async def test_data_not_ready_raises_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _error_response(400, "OPENAPI00009", "Please wait until the data is ready")

    async with _client(handler) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.get_ocid("c")
    assert exc.value.error_class is ErrorClass.DATA_NOT_READY


async def test_invalid_param_for_missing_nickname():
    def handler(request: httpx.Request) -> httpx.Response:
        return _error_response(400, "OPENAPI00004", "Please input valid parameter")

    async with _client(handler) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.get_ocid("없는닉")
    assert exc.value.error_class is ErrorClass.INVALID_PARAM


async def test_timeout_is_retried_then_raises_timeout():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("timeout")

    async with _client(handler, max_retry=2) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.get_ocid("c")
    assert exc.value.error_class is ErrorClass.TIMEOUT
    assert calls["n"] == 3  # 최초 1 + 재시도 2


async def test_fetch_image_downloads_and_caches():
    calls = {"n": 0}
    url = "https://open.api.nexon.com/static/maplestory/item/icon/ABC"

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, content=b"\x89PNG-bytes", headers={"content-type": "image/png"})

    async with _client(handler) as client:
        assert await client.fetch_image(url) == b"\x89PNG-bytes"
        assert await client.fetch_image(url) == b"\x89PNG-bytes"
    assert calls["n"] == 1  # 두 번째는 캐시 → 네트워크 1회만


async def test_fetch_image_failure_raises_timeout_class():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with _client(handler, max_retry=1) as client:
        with pytest.raises(NexonAPIError) as exc:
            await client.fetch_image("https://x/icon")
    assert exc.value.error_class is ErrorClass.TIMEOUT


async def test_fetch_image_rejects_non_image_body_and_does_not_cache():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text="<html>점검중</html>", headers={"content-type": "text/html"})

    async with _client(handler) as client:
        with pytest.raises(NexonAPIError):
            await client.fetch_image("https://x/icon")  # 비이미지 → 실패
        with pytest.raises(NexonAPIError):
            await client.fetch_image("https://x/icon")  # 캐시 오염 없음 → 다시 네트워크
    assert calls["n"] == 2
