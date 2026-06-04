"""넥슨 Open API httpx 클라이언트 (빌드 단위 #4).

- 기본 헤더에 봇 앱 키. 이력류는 호출 시 `api_key` 인자로 개인 키를 오버라이드(ocid 파라미터 없음).
- Spike 0 제약 반영: 스로틀(호출 시작 간격) + 429(rate_limit) 백오프 재시도 + 네트워크/타임아웃 재시도.
  test_ 키 한도가 ~5/sec 였고 live 한도는 미확인 → 보수적 기본값을 생성자 인자로 노출.
- 비정상 응답은 NexonAPIError 로 변환(error_class 로 호출자가 분기).
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from .errors import ErrorClass, NexonAPIError, classify

log = logging.getLogger(__name__)

BASE_URL = "https://open.api.nexon.com"


def _extract_error(response: httpx.Response) -> tuple[str | None, str | None]:
    """넥슨 표준 에러 바디 { "error": { name, message } } 에서 (code, message) 추출."""
    try:
        body = response.json()
    except ValueError:  # JSON 아님(점검 HTML 등) → 원문 텍스트로 폴백
        log.debug("non-JSON error body (%s): %s", response.status_code, response.text[:200])
        return None, response.text
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return err.get("name"), err.get("message")
    return None, str(body)


class NexonClient:
    def __init__(
        self,
        app_key: str,
        *,
        throttle: float = 0.25,
        max_retry: int = 3,
        retry_wait: float = 2.0,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._app_key = app_key
        self._throttle = throttle
        self._max_retry = max_retry
        self._retry_wait = retry_wait
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"x-nxopen-api-key": app_key},
            timeout=timeout,
            transport=transport,
        )
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0  # time.monotonic() 기준 다음 호출 허용 시각

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "NexonClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _await_throttle(self) -> None:
        if self._throttle <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_allowed = time.monotonic() + self._throttle

    async def _request(self, path: str, *, api_key: str | None = None, **params: object) -> dict:
        """GET 호출. 스로틀 + 재시도. 비정상 응답은 NexonAPIError 로 raise."""
        query = {k: v for k, v in params.items() if v is not None}
        headers = {"x-nxopen-api-key": api_key} if api_key else None
        attempt = 0
        while True:
            await self._await_throttle()
            try:
                response = await self._client.get(path, params=query, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < self._max_retry:
                    attempt += 1
                    await asyncio.sleep(self._retry_wait * attempt)
                    continue
                raise NexonAPIError(
                    "TIMEOUT", str(exc), http_status=None, error_class=ErrorClass.TIMEOUT
                ) from exc

            if response.status_code == 200:
                return response.json()

            code, message = _extract_error(response)
            error_class = classify(code)
            # rate_limit(429) 는 백오프 후 재시도
            if error_class is ErrorClass.RATE_LIMIT and attempt < self._max_retry:
                attempt += 1
                log.warning("rate_limit(%s) — %.1fs 후 재시도 %d/%d", code, self._retry_wait * attempt, attempt, self._max_retry)
                await asyncio.sleep(self._retry_wait * attempt)
                continue
            raise NexonAPIError(code, message, http_status=response.status_code, error_class=error_class)

    # ── Phase 1 에서 쓰는 엔드포인트 ──────────────────────────────────

    async def get_ocid(self, character_name: str) -> str:
        """닉네임 → ocid (스펙류 공통, 앱 키). 없는 닉이면 NexonAPIError(INVALID_PARAM)."""
        data = await self._request("maplestory/v1/id", character_name=character_name)
        return data["ocid"]

    async def verify_personal_key(self, api_key: str) -> bool:
        """개인 키 유효성 검증 (handoff §5): history/starforce count=10 호출.

        - 200 → True (빈 배열이어도 유효).
        - OPENAPI00005(auth_invalid) → False.
        - 그 외 에러(장애/429 등)는 그대로 raise (호출자가 "잠시 후 재시도" 안내).
        """
        try:
            await self._request("maplestory/v1/history/starforce", api_key=api_key, count=10)
            return True
        except NexonAPIError as exc:
            if exc.error_class is ErrorClass.AUTH_INVALID:
                return False
            raise
