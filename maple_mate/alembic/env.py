"""Alembic 마이그레이션 환경 (async / asyncpg).

.env 의 DATABASE_URL 을 로드하고, Base.metadata 를 target 으로 autogenerate/upgrade 한다.
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from maple_mate.database.core import Base, normalize_db_url

# 도메인 모델 모듈 임포트 → 테이블이 Base.metadata 에 등록(autogenerate/compare 용).
# 새 도메인 추가 시 여기에 models 임포트를 한 줄 추가.
import maple_mate.registration.models  # noqa: E402,F401
import maple_mate.history.models  # noqa: E402,F401
import maple_mate.notification.models  # noqa: E402,F401
import maple_mate.error_log.models  # noqa: E402,F401

load_dotenv()  # .env → os.environ (DATABASE_URL)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if database_url:
    # 운영(Render)은 postgresql:// 를 주므로 asyncpg 로 정규화 — async_engine_from_config 가
    # 동기 드라이버(psycopg2, 미설치)로 떨어지지 않게 한다.
    config.set_main_option("sqlalchemy.url", normalize_db_url(database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
