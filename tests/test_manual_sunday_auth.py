"""verify_operator_token 단위테스트 — Bearer 검증 정상/누락/접두오류/불일치 (핸드오프 #5).

상수시간 비교 자체(secrets.compare_digest)는 표준 라이브러리 신뢰. 여기선 분기만 검증한다.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from maple_mate.security.auth import verify_operator_token

TOKEN = "s3cret-operator-token"


def _request(authorization: str | None):
    """fake Request: headers.get 과 app.state.deps.config.operator_token 만 흉내낸다."""
    headers = {"Authorization": authorization} if authorization is not None else {}
    config = SimpleNamespace(operator_token=TOKEN)
    app = SimpleNamespace(state=SimpleNamespace(deps=SimpleNamespace(config=config)))
    return SimpleNamespace(headers=headers, app=app)


def test_valid_token_passes():
    verify_operator_token(_request(f"Bearer {TOKEN}"))  # 예외 없이 통과


def test_missing_header_401():
    with pytest.raises(HTTPException) as exc:
        verify_operator_token(_request(None))
    assert exc.value.status_code == 401


def test_no_bearer_prefix_401():
    with pytest.raises(HTTPException) as exc:
        verify_operator_token(_request(TOKEN))  # "Bearer " 접두 없음
    assert exc.value.status_code == 401


def test_wrong_token_401():
    with pytest.raises(HTTPException) as exc:
        verify_operator_token(_request("Bearer wrong-token"))
    assert exc.value.status_code == 401
