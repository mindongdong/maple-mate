"""challengers realm: character.world snapshot column

realm(본서버/챌린저스) 판정 신호인 world_name 을 등록 시 character 행에 스냅샷한다(ADR-0009).
nullable 비파괴 추가 — 기존 행은 NULL(= 본서버, 레거시). 백필 없음: 챌린저스 서버는 6/18
신설이라 마이그레이션 시점의 모든 행은 본서버다. lazy 갱신은 재등록(register_character) 편승.

⚠️ "character" 는 SQL 예약어 → 원시 SQL 에서 큰따옴표 인용 필요(SQLAlchemy DDL 은 자동 인용).

Revision ID: a7f3e1c92b04
Revises: f3a9c2b81d40
Create Date: 2026-06-19 15:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7f3e1c92b04"
down_revision: str | None = "f3a9c2b81d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("character", sa.Column("world", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("character", "world")
