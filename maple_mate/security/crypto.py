"""개인 넥슨 API 키 암복호화 (빌드 단위 #5).

Fernet 대칭 암호화. 마스터 키는 DB 밖 .env(FERNET_MASTER_KEY)에 둔다(design §6, ADR-0001).
이력류 해제용 개인 키를 at-rest 로 저장할 때 암호화하고, 조회 시 복호화한다.
"""

from __future__ import annotations

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

__all__ = ["KeyCipher", "InvalidToken"]

_ACCOUNT_KEY_LABEL = b"maple-mate/history-cache-account-key/v1"


class KeyCipher:
    """Fernet 기반 문자열 암복호화기.

    master_key: cryptography Fernet.generate_key() 로 만든 urlsafe-base64 키(str 또는 bytes).
    """

    def __init__(self, master_key: str | bytes):
        key_bytes = master_key.encode() if isinstance(master_key, str) else master_key
        self._fernet = Fernet(key_bytes)  # 잘못된 키면 여기서 ValueError
        # 계정 식별자 전용 서브키 — 마스터 키에서 용도 라벨로 파생(별도 시크릿 없이 용도 분리).
        self._account_key_secret = hmac.new(
            key_bytes, _ACCOUNT_KEY_LABEL, hashlib.sha256
        ).digest()

    def encrypt(self, plaintext: str) -> str:
        """평문 → 암호문 토큰(str). 매 호출 IV/타임스탬프가 달라 결과가 매번 다르다."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        """암호문 토큰 → 평문. 변조/다른 키면 InvalidToken."""
        return self._fernet.decrypt(token.encode()).decode()

    def account_key(self, api_key: str) -> str:
        """평문 API 키 → 계정 식별자(HMAC-SHA256 hex 64자, ADR-0024).

        같은 키면 항상 같은 값, 다른 키면 다른 값 — 이력 캐시(`history_cache`)의 이름표로 쓴다.
        암호문은 매번 달라(IV) 식별자로 못 쓰므로 따로 만든다. 일방향이라 값에서 키를 복원할 수 없다.
        """
        return hmac.new(
            self._account_key_secret, api_key.encode(), hashlib.sha256
        ).hexdigest()
