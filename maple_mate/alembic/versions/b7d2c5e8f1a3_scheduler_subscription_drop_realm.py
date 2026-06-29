"""scheduler_subscription: realm 제거 — PK (guild,user,realm) → (guild,user) (ADR-0017)

스케줄러 알림이 등록 캐릭터 전부(본+챌)를 한 구독으로 받도록 realm 분리를 폐기한다
(ADR-0012 결정 3·ADR-0009 스케줄러 한정 되돌림). 기존 dual-realm 구독 행은 (guild,user)별
최신 updated_at 1행으로 병합(나머지 삭제) 후 realm 컬럼을 drop 한다.

⚠️ 병합 시 사라진 realm 행(시각·제외집합)은 복구 불가(데이터 손실 허용 — 드묾). 다운그레이드는
realm 컬럼을 'main' 기본값으로 복구해 **스키마는 가역**이나 병합 손실은 비가역이다.

Revision ID: b7d2c5e8f1a3
Revises: e4c1f0a9b3d7
Create Date: 2026-06-29 12:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2c5e8f1a3"
down_revision: str | None = "e4c1f0a9b3d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) (guild,user)별 다중 realm 행 병합 — 최신 updated_at 1행 유지, 나머지 삭제.
    #    동률은 realm 사전순 작은 쪽을 남긴다(결정적). 단일 realm 행은 영향 없음.
    op.execute(
        """
        DELETE FROM scheduler_subscription a
        USING scheduler_subscription b
        WHERE a.guild_id = b.guild_id
          AND a.discord_user_id = b.discord_user_id
          AND a.realm <> b.realm
          AND (a.updated_at < b.updated_at
               OR (a.updated_at = b.updated_at AND a.realm > b.realm))
        """
    )

    # 2) PK 재정의: (guild, user, realm) → (guild, user).
    op.drop_constraint(
        "scheduler_subscription_pkey", "scheduler_subscription", type_="primary"
    )
    op.create_primary_key(
        "scheduler_subscription_pkey",
        "scheduler_subscription",
        ["guild_id", "discord_user_id"],
    )

    # 3) realm 컬럼 drop.
    op.drop_column("scheduler_subscription", "realm")


def downgrade() -> None:
    # 1) realm 컬럼 복구(NOT NULL). server_default 로 기존 행을 '본서버'로 백필 후 default 제거
    #    (모델엔 server_default 없음 — 앱이 매 insert realm 명시했었음). 병합 손실은 복구 불가.
    op.add_column(
        "scheduler_subscription",
        sa.Column(
            "realm", sa.String(length=16), nullable=False, server_default="본서버"
        ),
    )
    op.alter_column("scheduler_subscription", "realm", server_default=None)

    # 2) PK 재정의: (guild, user) → (guild, user, realm).
    op.drop_constraint(
        "scheduler_subscription_pkey", "scheduler_subscription", type_="primary"
    )
    op.create_primary_key(
        "scheduler_subscription_pkey",
        "scheduler_subscription",
        ["guild_id", "discord_user_id", "realm"],
    )
