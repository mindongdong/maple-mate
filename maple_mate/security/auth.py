"""운영자 Bearer 토큰 검증 — 상수시간 비교 (수동 썬데이 HTTP, 핸드오프 #5).

security/__init__.py 가 예고한 "OPERATOR_TOKEN 상수시간 비교" 자리. FastAPI 의존성으로
수동 발송 라우트에 부착한다.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import HTTPException, Request

log = logging.getLogger(__name__)


def verify_operator_token(request: Request) -> None:
    """Authorization: Bearer <token> 를 operator_token 과 상수시간 비교. 실패 시 401.

    FastAPI 의존성(Depends)으로 라우트에 부착. 누락·형식오류·불일치 모두 동일 401
    (유효 토큰 존재 노출 차단, #5). expected 는 config fail-fast 로 항상 비어있지 않다.
    """
    header = request.headers.get("Authorization", "")
    expected = request.app.state.deps.config.operator_token
    token = header[7:] if header.startswith("Bearer ") else ""
    if not token or not secrets.compare_digest(token, expected):
        log.warning("수동 썬데이: 인증 실패")  # 앱로그만, error_log 미적재(#5)
        raise HTTPException(status_code=401, detail="unauthorized")
