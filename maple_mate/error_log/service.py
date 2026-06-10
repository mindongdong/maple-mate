"""error_log 적재 (전달-무관). 재시도 발생 건만 기록 (design §5⑤).

비교 명령이 넥슨 장애/타임아웃/rate_limit 으로 최종 실패하면(클라이언트가 이미 1~2회
재시도한 뒤) 이 헬퍼로 한 줄 적재한다. best-effort — 적재 실패가 명령을 깨지 않도록
예외를 삼키고 로깅만 한다(관측 보조이지 사용자 흐름이 아님).
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import ErrorLog

log = logging.getLogger(__name__)


async def record(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    error_type: str,
    command: str | None = None,
    guild_id: int | None = None,
    discord_user_id: int | None = None,
    target_ocid: str | None = None,
    retry_count: int = 1,
    detail: str | None = None,
) -> None:
    """error_log 1행 적재. DB 오류는 삼키고 경고만(관측 보조)."""
    try:
        async with session_factory() as session:
            session.add(
                ErrorLog(
                    command=command,
                    guild_id=guild_id,
                    discord_user_id=discord_user_id,
                    target_ocid=target_ocid,
                    error_type=error_type,
                    retry_count=retry_count,
                    detail=detail,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — 관측 적재 실패가 명령을 깨면 안 됨
        log.warning(
            "error_log 적재 실패 (command=%s, type=%s)",
            command,
            error_type,
            exc_info=True,
        )
