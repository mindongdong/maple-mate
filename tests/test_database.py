"""normalize_db_url 순수함수 단위테스트 (배포 1-3: Render DSN → asyncpg 정규화)."""

from __future__ import annotations

from maple_mate.database.core import normalize_db_url


def test_postgresql_scheme_gets_asyncpg():
    # Render 내부 connectionString 기본형(postgresql://) → asyncpg 명시.
    assert (
        normalize_db_url("postgresql://u:p@host:5432/db")
        == "postgresql+asyncpg://u:p@host:5432/db"
    )


def test_postgres_scheme_gets_asyncpg():
    # 일부 제공자(Heroku 계열)의 postgres:// 표기도 처리.
    assert (
        normalize_db_url("postgres://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"
    )


def test_already_asyncpg_unchanged():
    url = "postgresql+asyncpg://u:p@host/db"
    assert normalize_db_url(url) == url


def test_other_driver_unchanged():
    # 드라이버가 명시된 경우는 존중(임의로 asyncpg 로 바꾸지 않음).
    url = "postgresql+psycopg://u:p@host/db"
    assert normalize_db_url(url) == url
