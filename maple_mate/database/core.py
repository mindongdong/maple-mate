"""DB 코어 — 선언적 Base + async engine/session factory (SQLAlchemy 2.0 + asyncpg).

dispatch 의 `database/core.py` 격. 모든 도메인 모델은 여기 `Base` 를 상속한다.
도메인 모델 모듈을 임포트하면 그 테이블이 `Base.metadata` 에 등록된다(alembic 이 이를 사용).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> AsyncEngine:
    """DATABASE_URL(postgresql+asyncpg://...) 로 async 엔진 생성."""
    return create_async_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
