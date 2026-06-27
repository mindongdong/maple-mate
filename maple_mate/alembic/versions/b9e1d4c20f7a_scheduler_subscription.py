"""scheduler_subscription: per-user DM 구독 테이블 (ADR-0012)

스케줄러 알리미는 채널 알림(channel_settings)과 분기된 첫 사례 — 구독 주체가 본인이고
realm 별 독립, 발송 시각(hour)을 행마다 저장한다. 매시 정각 cron 이 그 시각 구독을 조회해
본인 DM 으로 숙제 체크리스트를 발송한다.

PK = (guild_id, discord_user_id, realm). 같은 유저가 본서버·챌린저스를 따로 켜고 시각도 따로
둘 수 있어 realm 이 PK 에 포함된다(ADR-0009).

Revision ID: b9e1d4c20f7a
Revises: c3d4e5f6a7b8
Create Date: 2026-06-26 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9e1d4c20f7a"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_subscription",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("realm", sa.String(length=16), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("guild_id", "discord_user_id", "realm"),
    )


def downgrade() -> None:
    op.drop_table("scheduler_subscription")
