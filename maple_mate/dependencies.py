"""애플리케이션 의존성 컨테이너 (composition root 산출물).

main.py 가 .env → 엔진/세션·넥슨·암호화를 조립해 `Deps` 로 묶고, 두 전달 계층
(Discord 봇 commands, FastAPI views)이 공유한다. 도메인 service 는 이 안의 값만 받아
discord/http 타입에 의존하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
    # /스펙 주간 최고 전투력용 (ocid, date)→전투력 인메모리 캐시. 과거 스냅샷은 불변이라
    # 프로세스 수명 동안 영구 보관(재기동 시 콜드스타트). frozen 이라도 dict 내용 변경은 허용.
    combat_power_cache: dict[tuple[str, str], int] = field(default_factory=dict)
