"""넥슨 에러코드 → 의미 분류 매핑 + 예외 (빌드 단위 #4, handoff §3.1).

출처: docs/api/README.md 에러코드 표 + Spike 0 확정.
- OPENAPI00005(키 무효) → auth_invalid → "키 미등록/무효"
- OPENAPI00009("data not ready") → data_not_ready → 에러 아님, "전일 미생성/기록 없음"
- OPENAPI00007(429) → rate_limit → 재시도 대상
- OPENAPI00004(파라미터 오류) → invalid_param → 잘못된 닉/날짜/범위(없는 닉 포함)
- OPENAPI00003 → invalid_id → 잘못된 식별자/cursor
- OPENAPI00001/00006/00011 → nexon_api(장애). 00010(서비스 점검 중)도 같은 가용성 장애로
  보아 nexon_api 로 분류(README 열거 집합엔 없으나 사용자 응대가 00011과 동일해 의도적 확장).
"""

from __future__ import annotations

from enum import Enum


class ErrorClass(str, Enum):
    AUTH_INVALID = "auth_invalid"
    RATE_LIMIT = "rate_limit"
    DATA_NOT_READY = "data_not_ready"
    INVALID_PARAM = "invalid_param"
    INVALID_ID = "invalid_id"
    NEXON_API = "nexon_api"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# OPENAPIxxxxx → ErrorClass
_CODE_MAP: dict[str, ErrorClass] = {
    "OPENAPI00001": ErrorClass.NEXON_API,
    "OPENAPI00002": ErrorClass.AUTH_INVALID,
    "OPENAPI00003": ErrorClass.INVALID_ID,
    "OPENAPI00004": ErrorClass.INVALID_PARAM,
    "OPENAPI00005": ErrorClass.AUTH_INVALID,
    "OPENAPI00006": ErrorClass.NEXON_API,
    "OPENAPI00007": ErrorClass.RATE_LIMIT,
    "OPENAPI00009": ErrorClass.DATA_NOT_READY,
    "OPENAPI00010": ErrorClass.NEXON_API,
    "OPENAPI00011": ErrorClass.NEXON_API,
}


def classify(code: str | None) -> ErrorClass:
    """넥슨 에러코드 문자열을 의미 분류로. 알 수 없으면 UNKNOWN."""
    if not code:
        return ErrorClass.UNKNOWN
    return _CODE_MAP.get(code.strip().upper(), ErrorClass.UNKNOWN)


# error_log.error_type 으로 적재 가능한 분류(design §5⑤ 집합). data_not_ready/invalid_param 등은
# 사용자 응대/"기록 없음" 처리라 로깅 대상이 아님 → None.
_ERROR_LOG_TYPES = {
    ErrorClass.AUTH_INVALID: "auth_invalid",
    ErrorClass.RATE_LIMIT: "rate_limit",
    ErrorClass.NEXON_API: "nexon_api",
    ErrorClass.TIMEOUT: "timeout",
}


def to_error_log_type(error_class: ErrorClass) -> str | None:
    """error_log 에 적재할 error_type 문자열. 로깅 대상이 아니면 None."""
    return _ERROR_LOG_TYPES.get(error_class)


class NexonAPIError(Exception):
    """넥슨 API 비정상 응답. error_class 로 분기 처리."""

    def __init__(
        self,
        code: str | None,
        message: str | None,
        *,
        http_status: int | None = None,
        error_class: ErrorClass | None = None,
    ):
        self.code = code
        self.message = message or ""
        self.http_status = http_status
        self.error_class = error_class or classify(code)
        super().__init__(f"[{http_status}] {code}: {self.message}")
