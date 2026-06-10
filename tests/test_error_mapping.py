"""넥슨 에러코드 → 분류 매핑 단위테스트 (handoff §3.1·§6)."""

from __future__ import annotations

import pytest

from maple_mate.nexon.errors import ErrorClass, classify, to_error_log_type


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("OPENAPI00001", ErrorClass.NEXON_API),
        ("OPENAPI00002", ErrorClass.AUTH_INVALID),
        ("OPENAPI00003", ErrorClass.INVALID_ID),
        ("OPENAPI00004", ErrorClass.INVALID_PARAM),
        ("OPENAPI00005", ErrorClass.AUTH_INVALID),
        ("OPENAPI00006", ErrorClass.NEXON_API),
        ("OPENAPI00007", ErrorClass.RATE_LIMIT),
        ("OPENAPI00009", ErrorClass.DATA_NOT_READY),
        ("OPENAPI00010", ErrorClass.NEXON_API),
        ("OPENAPI00011", ErrorClass.NEXON_API),
    ],
)
def test_classify_known_codes(code, expected):
    assert classify(code) == expected


def test_classify_is_case_insensitive():
    assert classify("openapi00005") == ErrorClass.AUTH_INVALID


def test_classify_unknown_and_none():
    assert classify("OPENAPI99999") == ErrorClass.UNKNOWN
    assert classify(None) == ErrorClass.UNKNOWN
    assert classify("") == ErrorClass.UNKNOWN


def test_error_log_type_only_for_logged_classes():
    assert to_error_log_type(ErrorClass.AUTH_INVALID) == "auth_invalid"
    assert to_error_log_type(ErrorClass.RATE_LIMIT) == "rate_limit"
    assert to_error_log_type(ErrorClass.NEXON_API) == "nexon_api"
    assert to_error_log_type(ErrorClass.TIMEOUT) == "timeout"
    # 데이터 미준비/파라미터 오류는 로깅 대상이 아님
    assert to_error_log_type(ErrorClass.DATA_NOT_READY) is None
    assert to_error_log_type(ErrorClass.INVALID_PARAM) is None
