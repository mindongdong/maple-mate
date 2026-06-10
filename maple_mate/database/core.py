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


def normalize_db_url(url: str) -> str:
    """DSN 스킴을 asyncpg 드라이버로 정규화(순수함수).

    Render 등이 주는 기본 URL(`postgres://`·`postgresql://`)을 `postgresql+asyncpg://` 로
    바꾼다. 이미 드라이버가 명시된 경우(`postgresql+asyncpg://`·`postgresql+psycopg://` 등)는
    그대로 둔다. 그 외 스킴(sqlite 등)도 손대지 않는다.
    """
    if url.startswith("postgres://"):  # 일부 제공자(Heroku 계열) 표기
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):  # 드라이버 미지정 → asyncpg 명시
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def make_engine(database_url: str) -> AsyncEngine:
    """DATABASE_URL 로 async 엔진 생성(스킴은 asyncpg 로 정규화)."""
    return create_async_engine(normalize_db_url(database_url), pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
