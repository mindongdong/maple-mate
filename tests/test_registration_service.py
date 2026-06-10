"""registration.service 전달-무관 로직 단위테스트 (Nexon mock, DB 불요 — handoff §6).

DB upsert 는 통합 영역이라 여기서 제외(순수/모킹 가능한 부분만). resolve_ocid·키검증·암호화 검증.
"""

from __future__ import annotations

from cryptography.fernet import Fernet

from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration import service
from maple_mate.security.crypto import KeyCipher


class FakeNexon:
    def __init__(self, *, ocids=None, valid_keys=None, raise_on_verify=None):
        self._ocids = ocids or {}
        self._valid_keys = valid_keys or {}
        self._raise_on_verify = raise_on_verify

    async def get_ocid(self, name):
        if name in self._ocids:
            return self._ocids[name]
        raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)

    async def verify_personal_key(self, key):
        if self._raise_on_verify is not None:
            raise self._raise_on_verify
        return self._valid_keys.get(key, False)


CIPHER = KeyCipher(Fernet.generate_key())


async def test_resolve_ocid_success():
    nexon = FakeNexon(ocids={"손가락": "ocid_son"})
    ocid, err = await service.resolve_ocid(nexon, "손가락")
    assert ocid == "ocid_son" and err is None


async def test_resolve_ocid_missing_nickname_returns_message():
    nexon = FakeNexon(ocids={})
    ocid, err = await service.resolve_ocid(nexon, "없는닉")
    assert ocid is None and "찾을 수 없" in err


async def test_resolve_ocid_api_error_returns_retry_message():
    nexon = FakeNexon(raise_on_verify=None)

    async def boom(_name):
        raise NexonAPIError("OPENAPI00001", "internal", http_status=500)

    nexon.get_ocid = boom  # type: ignore[assignment]
    ocid, err = await service.resolve_ocid(nexon, "x")
    assert ocid is None and "잠시 후" in err


async def test_verify_and_encrypt_valid_key_roundtrips():
    nexon = FakeNexon(valid_keys={"goodkey": True})
    enc, err = await service.verify_and_encrypt_key(nexon, CIPHER, "goodkey")
    assert err is None and enc is not None
    assert CIPHER.decrypt(enc) == "goodkey"


async def test_verify_and_encrypt_invalid_key_rejected():
    nexon = FakeNexon(valid_keys={"goodkey": True})  # badkey → False
    enc, err = await service.verify_and_encrypt_key(nexon, CIPHER, "badkey")
    assert enc is None and "무효" in err


async def test_verify_and_encrypt_api_error_returns_message():
    nexon = FakeNexon(
        raise_on_verify=NexonAPIError("OPENAPI00001", "internal", http_status=500)
    )
    enc, err = await service.verify_and_encrypt_key(nexon, CIPHER, "k")
    assert enc is None and "잠시 후" in err
