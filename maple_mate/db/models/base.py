"""ORM 선언적 베이스. 모든 모델의 메타데이터 루트 (alembic target_metadata)."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
