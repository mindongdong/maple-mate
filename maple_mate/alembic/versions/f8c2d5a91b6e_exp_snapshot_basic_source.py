"""exp_snapshot: ranking/overall 소스 폐기 — total_exp·world_rank 제거 + 최근 8일 리페어

경험치 스냅샷의 단일 소스를 character/basic(date) 로 전환한다(ADR-0020). 종전 ranking/overall
레벨은 하루 뒤처진 값(그날 아침 발표 = 전날 마감 집계)이라 basic 의 exp% 와 짝지어질 때 레벨업
날 가짜 하락점을 만들었다. total_exp(Δ 정렬키)·world_rank(전체 순위)는 ADR-0011 에서 이미 표시
폐기됐고 이번 소스 전환으로 생산자도 사라져 컬럼을 제거한다.

리페어: 최근 8일 행을 삭제한다 — 기존 행의 character_level 이 하루 뒤처진 랭킹 값이라서,
비우면 다음 실행(매일 10:00 잡 또는 /경험치 온디맨드)의 멱등 backfill(D-1~D-8)이 basic 레벨로
재적재한다. 8일 초과 과거 행은 표시 창(그래프 7일) 밖이라 그대로 둔다(레벨이 하루 뒤처진 채
남지만 소비자 없음, 90일 후 prune).

⚠️ 다운그레이드는 컬럼을 복원하지만 값은 채우지 못하고(total_exp=0 백필), 삭제된 최근 8일
행도 복원하지 않는다(손실 허용, 비상 롤백 — 구버전의 매 실행 backfill 이 랭킹 소스로 재적재).

Revision ID: f8c2d5a91b6e
Revises: a9c4e7f21b3d
Create Date: 2026-07-03 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c2d5a91b6e"
down_revision: str | None = "a9c4e7f21b3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 리페어 삭제 — 표시 창(그래프 7일 ⊂ 백필 8일)의 랭킹 소스 행을 비워 재적재를 유도.
    #    CURRENT_DATE 는 DB 서버 타임존(UTC 가능성) 기준이라 KST 대비 하루 이를 수 있어
    #    -9일로 한 칸 여유를 둔다(백필 창 밖 과잉 삭제분은 표시 소비자 없음).
    op.execute(
        "DELETE FROM exp_snapshot WHERE snapshot_date >= CURRENT_DATE - INTERVAL '9 days'"
    )
    # 2) ranking/overall 파생 컬럼 제거.
    op.drop_column("exp_snapshot", "total_exp")
    op.drop_column("exp_snapshot", "world_rank")


def downgrade() -> None:
    # 컬럼 복원(값은 미복원 — total_exp 는 0 백필 후 default 제거, world_rank 는 NULL).
    op.add_column(
        "exp_snapshot",
        sa.Column("total_exp", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.alter_column("exp_snapshot", "total_exp", server_default=None)
    op.add_column("exp_snapshot", sa.Column("world_rank", sa.Integer(), nullable=True))
