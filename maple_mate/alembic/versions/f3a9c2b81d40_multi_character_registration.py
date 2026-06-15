"""multi character registration: character table + representative_ocid

기존 registration(닉·ocid·키 융합) 1행을 (1) character 테이블 N행으로 분해하고
(2) registration 에 representative_ocid(대표 포인터)를 더한다. 비파괴 제자리 변환:
기존 행은 character 1개 + representative_ocid NULL(자동=최고레벨)로 백필되어 day-1 동작 동일.

⚠️ "character" 는 SQL 예약어 → 원시 SQL 에서는 반드시 큰따옴표로 인용한다(SQLAlchemy
DDL/ORM 은 자동 인용).

Revision ID: f3a9c2b81d40
Revises: e7aed951afb2
Create Date: 2026-06-15 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c2b81d40"
down_revision: str | None = "e7aed951afb2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) character 테이블 생성(N개 캐릭터). PK = (guild_id, discord_user_id, ocid).
    op.create_table(
        "character",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("ocid", sa.String(length=128), nullable=False),
        sa.Column("maple_nickname", sa.String(length=64), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint("guild_id", "discord_user_id", "ocid"),
    )

    # 2) 백필: 기존 등록 1행 → character 1행(레벨 미상 NULL). created_at 보존 →
    #    이력류 캐시 앵커(min(created_at))가 마이그레이션 전후로 안정.
    op.execute(
        """
        INSERT INTO "character"
            (guild_id, discord_user_id, ocid, maple_nickname, level, created_at, updated_at)
        SELECT guild_id, discord_user_id, ocid, maple_nickname, NULL, created_at, now()
        FROM registration
        """
    )

    # 3) 대표 포인터 컬럼 추가(NULL = 자동 = 최고 레벨).
    op.add_column(
        "registration",
        sa.Column("representative_ocid", sa.String(length=128), nullable=True),
    )

    # 4) 융합 컬럼 제거 — 닉/ocid 는 character 로 이전됨.
    op.drop_column("registration", "maple_nickname")
    op.drop_column("registration", "ocid")


def downgrade() -> None:
    # 역순: 융합 컬럼 복원(우선 nullable) → character 에서 대표 우선 백필 → NOT NULL → character drop.
    op.add_column(
        "registration", sa.Column("ocid", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "registration", sa.Column("maple_nickname", sa.String(length=64), nullable=True)
    )

    # N개 캐릭터를 1개로 접는다(손실 허용 — 비상 롤백). 대표 우선순위:
    # 대표 지정 일치 → 레벨 높은 순 → 먼저 등록(created_at) → ocid(결정적 타이브레이크).
    op.execute(
        """
        UPDATE registration r
        SET maple_nickname = c.maple_nickname, ocid = c.ocid
        FROM (
            SELECT DISTINCT ON (ch.guild_id, ch.discord_user_id)
                ch.guild_id, ch.discord_user_id, ch.ocid, ch.maple_nickname
            FROM "character" ch
            JOIN registration reg
              ON reg.guild_id = ch.guild_id
             AND reg.discord_user_id = ch.discord_user_id
            ORDER BY ch.guild_id, ch.discord_user_id,
                (ch.ocid = reg.representative_ocid) DESC NULLS LAST,
                ch.level DESC NULLS LAST,
                ch.created_at ASC,
                ch.ocid ASC
        ) c
        WHERE r.guild_id = c.guild_id AND r.discord_user_id = c.discord_user_id
        """
    )

    # 캐릭터가 없던 등록(키만 등록 등)은 옛 스키마(닉·ocid NOT NULL)로 표현 불가 → 삭제.
    op.execute("DELETE FROM registration WHERE maple_nickname IS NULL OR ocid IS NULL")

    op.alter_column("registration", "maple_nickname", nullable=False)
    op.alter_column("registration", "ocid", nullable=False)
    op.drop_column("registration", "representative_ocid")
    op.drop_table("character")
