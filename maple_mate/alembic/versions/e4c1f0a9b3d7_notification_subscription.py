"""notification_subscription: 경험치·공지·썬데이 개인 DM 구독 (ADR-0017)

경험치·공지·썬데이를 채널 발송과 병행해 **본인 DM 으로도** 받는 구독. 행 존재 = 구독
(별도 on/off 컬럼 없음), kind ∈ {"exp","notice","sunday"}. 시각·realm 컬럼 없음 — 콘텐츠
주기가 고정이라 사용자 시각이 불필요하다(스케줄러 DM 은 별 테이블 scheduler_subscription).

PK = (guild_id, discord_user_id, kind). 공지·썬데이는 글로벌 콘텐츠라 발송 시 user_id distinct
로 다중 길드 중복을 막고(저장은 guild 별), 경험치는 길드별 리더보드라 (guild, user)로 보낸다.

Revision ID: e4c1f0a9b3d7
Revises: d5b3a8e417c2
Create Date: 2026-06-29 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4c1f0a9b3d7"
down_revision: str | None = "d5b3a8e417c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_subscription",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("guild_id", "discord_user_id", "kind"),
    )


def downgrade() -> None:
    op.drop_table("notification_subscription")
