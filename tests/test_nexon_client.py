"""넥슨 클라이언트 단위테스트 (httpx mock). 실호출 없음 — handoff §6."""

from __future__ import annotations

import asyncio
import time

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
        return _error_response(
            400, "OPENAPI00009", "Please wait until the data is ready"
        )

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
        return _error_response(
            400, "OPENAPI00009", "Please wait until the data is ready"
        )

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
        return httpx.Response(
            200, content=b"\x89PNG-bytes", headers={"content-type": "image/png"}
        )

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


# ── 키별 스로틀 버킷 (스케일 튜닝 3-1, ADR-0004) ──────────────────────


def _bucket_probe_handler(times: dict[str, list[float]]):
    """요청 키별 도달 시각(monotonic) 기록. /id·/history 둘 다 응답 가능한 바디."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.headers["x-nxopen-api-key"]
        times.setdefault(key, []).append(time.monotonic())
        return httpx.Response(
            200, json={"ocid": "x", "starforce_history": [], "next_cursor": None}
        )

    return handler


async def test_same_key_calls_keep_bucket_interval():
    times: dict[str, list[float]] = {}
    client = NexonClient(
        "app_key",
        throttle=0.05,
        personal_throttle=0.1,
        retry_wait=0.0,
        transport=httpx.MockTransport(_bucket_probe_handler(times)),
    )
    async with client:
        await asyncio.gather(
            *(client.starforce_history("pk", "2026-06-01") for _ in range(3))
        )
        await asyncio.gather(client.get_ocid("a"), client.get_ocid("b"))

    personal = sorted(times["pk"])
    assert len(personal) == 3
    assert all(b - a >= 0.1 - 0.02 for a, b in zip(personal, personal[1:]))
    app = sorted(times["app_key"])
    assert len(app) == 2
    assert all(b - a >= 0.05 - 0.02 for a, b in zip(app, app[1:]))


async def test_app_key_not_blocked_by_personal_key_burst():
    # 개인 키 연타(0.2s 간격 × 3)가 버킷을 점유하는 동안 앱 키 호출은 대기 없이 통과.
    # 구 전역 단일 버킷이면 앱 호출이 개인 키 대기열 뒤로 밀려 ≥0.2s 걸린다.
    times: dict[str, list[float]] = {}
    client = NexonClient(
        "app_key",
        throttle=0.05,
        retry_wait=0.0,
        transport=httpx.MockTransport(_bucket_probe_handler(times)),
    )
    async with client:
        burst = asyncio.gather(
            *(client.starforce_history("pk", "2026-06-01") for _ in range(3))
        )
        await asyncio.sleep(0.05)  # 버스트가 개인 키 버킷을 점유한 시점
        t0 = time.monotonic()
        await client.get_ocid("아무개")
        app_latency = time.monotonic() - t0
        await burst
    assert app_latency < 0.15


async def test_personal_keys_have_independent_buckets():
    # 서로 다른 개인 키는 서로 비차단 — 같은 시각에 나란히 시작 가능.
    times: dict[str, list[float]] = {}
    client = NexonClient(
        "app_key",
        throttle=0.0,
        retry_wait=0.0,
        transport=httpx.MockTransport(_bucket_probe_handler(times)),
    )
    async with client:
        t0 = time.monotonic()
        await asyncio.gather(
            *(client.starforce_history(f"pk{i}", "2026-06-01") for i in range(3))
        )
        elapsed = time.monotonic() - t0
    assert elapsed < 0.15  # 같은 버킷에 직렬화됐다면 ≥0.4s(0.2×2)


# ── 최신 스펙 30분 캐시 (스케일 튜닝 3-2, D5) ─────────────────────────


def _spec_handler(calls: dict[str, int]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] = calls.get("n", 0) + 1
        return httpx.Response(200, json={"date": None, "character_level": 280})

    return handler


async def test_spec_without_date_is_cached_within_ttl():
    calls: dict[str, int] = {}
    async with _client(_spec_handler(calls)) as client:
        first = await client.character_basic("oc1")
        second = await client.character_basic("oc1")
    assert first == second
    assert calls["n"] == 1  # 30분 내 동일 (path, ocid) 재호출 → HTTP 0회


async def test_spec_cache_keyed_by_path_and_ocid():
    calls: dict[str, int] = {}
    async with _client(_spec_handler(calls)) as client:
        await client.character_basic("oc1")
        await client.character_basic("oc2")  # 다른 ocid → 비적중
        await client.character_stat("oc1")  # 다른 path → 비적중
    assert calls["n"] == 3


async def test_spec_cache_expires_after_ttl(monkeypatch):
    from maple_mate.nexon import client as client_mod

    clock = {"t": 1000.0}

    class _FakeTime:
        @staticmethod
        def monotonic() -> float:
            return clock["t"]

    monkeypatch.setattr(client_mod, "time", _FakeTime)
    calls: dict[str, int] = {}
    async with _client(_spec_handler(calls)) as client:
        await client.character_basic("oc1")
        clock["t"] += client_mod.SPEC_CACHE_TTL - 1
        await client.character_basic("oc1")  # TTL 직전 → 캐시
        assert calls["n"] == 1
        clock["t"] += 2
        await client.character_basic("oc1")  # TTL 경과 → 재조회
    assert calls["n"] == 2


async def test_spec_with_date_is_not_cached():
    calls: dict[str, int] = {}
    async with _client(_spec_handler(calls)) as client:
        await client.character_basic("oc1", date="2026-06-01")
        await client.character_basic("oc1", date="2026-06-01")
    assert calls["n"] == 2  # date 지정 호출은 비캐시


async def test_fetch_image_rejects_non_image_body_and_does_not_cache():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200, text="<html>점검중</html>", headers={"content-type": "text/html"}
        )

    async with _client(handler) as client:
        with pytest.raises(NexonAPIError):
            await client.fetch_image("https://x/icon")  # 비이미지 → 실패
        with pytest.raises(NexonAPIError):
            await client.fetch_image("https://x/icon")  # 캐시 오염 없음 → 다시 네트워크
    assert calls["n"] == 2
