"""scheduler_subscription.excluded_categories: 숙제 카테고리 필터 (ADR-0014)

구독에 숨길 사용자 묶음(일일·주간·보스·길드)을 CSV 한 컬럼으로 저장한다 — 예 "보스,길드".
NULL=제외 없음=전부 표시라 기존 행은 행동 변화 0(하위호환), 나중에 5번째 카테고리가 생겨도
기존 구독자에게 기본 표시(opt-out 상위호환). nullable 이라 백필 불요.

Revision ID: d5b3a8e417c2
Revises: b9e1d4c20f7a
Create Date: 2026-06-28 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5b3a8e417c2"
down_revision: str | None = "b9e1d4c20f7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scheduler_subscription",
        sa.Column("excluded_categories", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduler_subscription", "excluded_categories")
