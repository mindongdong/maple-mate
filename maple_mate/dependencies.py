"""애플리케이션 의존성 컨테이너 (composition root 산출물).

main.py 가 .env → 엔진/세션·넥슨·암호화를 조립해 `Deps` 로 묶고, 두 전달 계층
(Discord 봇 commands, FastAPI views)이 공유한다. 도메인 service 는 이 안의 값만 받아
discord/http 타입에 의존하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Config
from .nexon.client import NexonClient
from .security.crypto import KeyCipher


@dataclass(frozen=True)
class Deps:
    config: Config
    session_factory: async_sessionmaker[AsyncSession]
    nexon: NexonClient
    cipher: KeyCipher
