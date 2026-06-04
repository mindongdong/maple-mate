"""봇 커맨드가 공유하는 의존성 컨테이너."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Config
from ..crypto import KeyCipher
from ..nexon.client import NexonClient


@dataclass(frozen=True)
class BotDeps:
    config: Config
    session_factory: async_sessionmaker[AsyncSession]
    nexon: NexonClient
    cipher: KeyCipher
