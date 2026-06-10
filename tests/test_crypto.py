"""crypto.py Fernet 라운드트립 단위테스트 (handoff §6)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from maple_mate.security.crypto import KeyCipher

_KEY = Fernet.generate_key()
_API_KEY = "live_1234567890abcdef-넥슨개인키-샘플"


def test_encrypt_decrypt_roundtrip():
    cipher = KeyCipher(_KEY)
    token = cipher.encrypt(_API_KEY)
    assert cipher.decrypt(token) == _API_KEY


def test_ciphertext_is_not_plaintext():
    cipher = KeyCipher(_KEY)
    token = cipher.encrypt(_API_KEY)
    assert _API_KEY not in token


def test_ciphertext_differs_each_call():
    cipher = KeyCipher(_KEY)
    assert cipher.encrypt(_API_KEY) != cipher.encrypt(_API_KEY)


def test_accepts_str_master_key():
    cipher = KeyCipher(_KEY.decode())
    assert cipher.decrypt(cipher.encrypt("x")) == "x"


def test_wrong_key_fails_to_decrypt():
    token = KeyCipher(_KEY).encrypt(_API_KEY)
    other = KeyCipher(Fernet.generate_key())
    with pytest.raises(InvalidToken):
        other.decrypt(token)
