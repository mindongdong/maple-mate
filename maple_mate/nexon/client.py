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
from datetime import datetime, timedelta, timezone

import httpx

from .errors import ErrorClass, NexonAPIError, classify

log = logging.getLogger(__name__)

BASE_URL = "https://open.api.nexon.com"
KST = timezone(timedelta(hours=9))


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
        self._image_cache: dict[str, bytes] = {}  # 정적 아이콘 URL → bytes (불변 자산이라 영구 캐시)

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

    async def fetch_image(self, url: str) -> bytes:
        """장비 아이콘 등 정적 이미지 다운로드 (메모리 캐시).

        API 데이터 호출과 달리 스로틀/에러분류 미적용 — 정적 자산이라 단순 GET + 네트워크 재시도.
        실패는 NexonAPIError(TIMEOUT)로 raise (호출자가 잡아 아이콘 없이 렌더).
        """
        cached = self._image_cache.get(url)
        if cached is not None:
            return cached
        attempt = 0
        while True:
            try:
                response = await self._client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:  # Timeout/Transport/HTTPStatus/InvalidURL 등 전부
                if attempt < self._max_retry:
                    attempt += 1
                    await asyncio.sleep(self._retry_wait * attempt)
                    continue
                raise NexonAPIError(
                    "IMAGE_FETCH", str(exc), http_status=None, error_class=ErrorClass.TIMEOUT
                ) from exc
            # 비이미지 응답(점검 HTML 등)은 캐시 오염 방지 위해 실패 처리 — 캐시하지 않음.
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise NexonAPIError(
                    "IMAGE_FETCH",
                    f"비이미지 응답({content_type or '미상'})",
                    http_status=response.status_code,
                    error_class=ErrorClass.TIMEOUT,
                )
            self._image_cache[url] = response.content
            return response.content

    # ── Phase 1 에서 쓰는 엔드포인트 ──────────────────────────────────

    async def get_ocid(self, character_name: str) -> str:
        """닉네임 → ocid (스펙류 공통, 앱 키). 없는 닉이면 NexonAPIError(INVALID_PARAM)."""
        data = await self._request("maplestory/v1/id", character_name=character_name)
        return data["ocid"]

    async def verify_personal_key(self, api_key: str) -> bool:
        """개인 키 유효성 검증 (handoff §5): history/starforce count=10 + date=오늘(KST).

        - 200 → True (빈 배열이어도 유효).
        - OPENAPI00005(auth_invalid) → False.
        - OPENAPI00009(data_not_ready) → True (키 인증은 성공, 데이터만 미준비 → 유효로 간주).
        - 그 외 에러(장애/429 등)는 그대로 raise (호출자가 "잠시 후 재시도" 안내).

        ⚠️ date 를 빼면 실 API 가 OPENAPI00004 를 반환(문서의 "당일 기본값"과 불일치, 실호출로 확인)
        → 반드시 date(오늘 KST) 를 전달한다.
        """
        today = datetime.now(KST).date().isoformat()
        try:
            await self._request(
                "maplestory/v1/history/starforce", api_key=api_key, count=10, date=today
            )
            return True
        except NexonAPIError as exc:
            if exc.error_class is ErrorClass.AUTH_INVALID:
                return False
            if exc.error_class is ErrorClass.DATA_NOT_READY:
                return True
            raise

    # ── Phase 3 이력류 (개인 키 오버라이드, date 별 1일치) ───────────────────
    #
    # 개인 키 = 그 계정 이력(ocid 파라미터 없음). date 는 정확히 그 하루치만 반환(실측).
    # count=1000(max) 으로 하루치 한 번에. next_cursor 비-null 이면 cursor 누적(date 빼고)
    # — 친구 그룹 일일 <1000 이라 보통 1콜이나 고볼륨 일자 대비.

    async def starforce_history(
        self, api_key: str, date_iso: str, count: int = 1000
    ) -> list[dict]:
        """개인 키로 그 계정 starforce 이력(해당 KST 1일). next_cursor 누적, null→[]."""
        records: list[dict] = []
        cursor: str | None = None
        while True:
            if cursor is None:
                data = await self._request(
                    "maplestory/v1/history/starforce",
                    api_key=api_key,
                    count=count,
                    date=date_iso,
                )
            else:  # cursor 전달 시 date 제외(실측: date 우선·cursor 무시)
                data = await self._request(
                    "maplestory/v1/history/starforce",
                    api_key=api_key,
                    count=count,
                    cursor=cursor,
                )
            page = data.get("starforce_history")
            if isinstance(page, list):
                records.extend(page)
            cursor = data.get("next_cursor")
            if not cursor:
                return records

    async def _history(
        self, path: str, wrapper: str, api_key: str, date_iso: str, count: int
    ) -> list[dict]:
        """이력류 공통 페치(starforce_history 와 동일 규약). next_cursor 누적, null→[]."""
        records: list[dict] = []
        cursor: str | None = None
        while True:
            if cursor is None:
                data = await self._request(path, api_key=api_key, count=count, date=date_iso)
            else:  # cursor 전달 시 date 제외(실측: date 우선·cursor 무시)
                data = await self._request(path, api_key=api_key, count=count, cursor=cursor)
            page = data.get(wrapper)
            if isinstance(page, list):
                records.extend(page)
            cursor = data.get("next_cursor")
            if not cursor:
                return records

    async def cube_history(
        self, api_key: str, date_iso: str, count: int = 1000
    ) -> list[dict]:
        """개인 키로 그 계정 cube 이력(해당 KST 1일). next_cursor 누적, null→[]."""
        return await self._history(
            "maplestory/v1/history/cube", "cube_history", api_key, date_iso, count
        )

    async def potential_history(
        self, api_key: str, date_iso: str, count: int = 1000
    ) -> list[dict]:
        """개인 키로 그 계정 potential(메소 재설정) 이력(해당 KST 1일). null→[]."""
        return await self._history(
            "maplestory/v1/history/potential", "potential_history", api_key, date_iso, count
        )

    # ── Phase 2 스펙류 (앱 키 + ocid, date 무지정=최신 ready) ──────────────
    #
    # Spike 0(handoff §3.1): "1AM 이후 D-1" 경계는 soft. 봇은 D-1 을 직접 계산해
    # date 로 넘기지 않고 무지정(최신) 호출한다. `_request` 가 None 파라미터를 제거하므로
    # date=None 이면 쿼리에서 빠진다 → 200 + 응답 date:null(최신 스냅샷).
    # OPENAPI00009("data not ready") 는 호출자가 "전일 미생성"으로 안내(에러 아님).

    async def _spec(self, path: str, ocid: str, date: str | None = None) -> dict:
        return await self._request(path, ocid=ocid, date=date)

    async def character_basic(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/basic", ocid, date)

    async def character_stat(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/stat", ocid, date)

    async def character_ability(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/ability", ocid, date)

    async def character_symbol_equipment(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/symbol-equipment", ocid, date)

    async def character_hexamatrix(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/hexamatrix", ocid, date)

    async def character_hexamatrix_stat(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/hexamatrix-stat", ocid, date)

    async def character_item_equipment(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/character/item-equipment", ocid, date)

    async def union(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/user/union", ocid, date)

    async def union_artifact(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/user/union-artifact", ocid, date)

    async def union_champion(self, ocid: str, date: str | None = None) -> dict:
        return await self._spec("maplestory/v1/user/union-champion", ocid, date)

    # ── Phase 4 알림 (앱 키, 진행 중 이벤트 목록) ──────────────────────────
    #
    # notice-event 는 파라미터 없이 "현재 진행 중" 항목만 반환(docs/api/notice.md). 따라서
    # 봇은 기간 필터를 따로 두지 않고 제목 매칭만 한다(작업지시서 Q2). 래퍼 키 `event_notice`.

    async def notice_event(self) -> list[dict]:
        """진행 중 이벤트 공지 목록(`event_notice` 리스트). 없으면 빈 리스트."""
        data = await self._request("maplestory/v1/notice-event")
        events = data.get("event_notice")
        return events if isinstance(events, list) else []

    async def notice_event_detail(self, notice_id: int) -> dict:
        """이벤트 상세(`contents` HTML 포함). 본문 배너 이미지 URL 추출에 사용."""
        return await self._request("maplestory/v1/notice-event/detail", notice_id=notice_id)

    # `/공지알림` 폴링 대상(이벤트 제외). 둘 다 파라미터 없이 최신순(date 내림차순) 목록 반환
    # (docs/api/notice.md, Spike 0 실호출 확정). 래퍼 키: notice=`notice`, 업데이트=`update_notice`.

    async def notice(self) -> list[dict]:
        """공지사항 목록(`notice` 리스트, 최신순). 없으면 빈 리스트."""
        data = await self._request("maplestory/v1/notice")
        items = data.get("notice")
        return items if isinstance(items, list) else []

    async def notice_update(self) -> list[dict]:
        """업데이트 공지 목록(`update_notice` 리스트, 최신순). 없으면 빈 리스트."""
        data = await self._request("maplestory/v1/notice-update")
        items = data.get("update_notice")
        return items if isinstance(items, list) else []
