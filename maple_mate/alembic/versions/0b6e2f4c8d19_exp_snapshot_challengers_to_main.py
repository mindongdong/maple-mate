"""exp_snapshot: 챌린저스 realm 행을 본서버로 편입

챌린저스 시즌 종료로 캐릭터가 일반 서버로 이전돼 챌린저스 판정을 끈다(realm.CHALLENGERS_ENABLED).
이후 스냅샷은 전부 본서버로 적재되므로, 기존 챌린저스 행도 본서버로 바꿔 본서버 리더보드 그래프
(최근 7일)의 이력이 끊기지 않게 한다. realm 은 PK 밖 일반 컬럼이라 충돌 없음.

⚠️ 다운그레이드는 no-op — 어느 행이 챌린저스였는지 복원할 수 없다(단방향).

Revision ID: 0b6e2f4c8d19
Revises: f8c2d5a91b6e
Create Date: 2026-09-28 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0b6e2f4c8d19"
down_revision: str | None = "f8c2d5a91b6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE exp_snapshot SET realm = '본서버' WHERE realm = '챌린저스'")


def downgrade() -> None:
    pass
