"""challengers realm: exp_snapshot.realm column + PK 확장

리더보드를 realm(본서버/챌린저스)별로 완전 분리하려면 같은 (guild,user,date) 에 두 realm
스냅샷이 공존해야 한다(결정 8, ADR-0009). exp_snapshot PK 에 realm 을 더한다 — ADR-0006 의
"PK (guild,user,date) 불변"을 의도적으로 되돌린다(ADR-0009 에 근거 기록).

realm 은 Realm.value("본서버"/"챌린저스") 디스크리미넌트. 기존 행은 전부 본서버(server_default
로 백필 후 default 제거 — 앱이 매 insert 마다 realm 을 명시). PK NOT NULL 요구로 nullable 불가.

⚠️ 다운그레이드는 챌린저스 행을 삭제해 (guild,user,date) 유일성을 복원한다(손실 허용).

Revision ID: c3d4e5f6a7b8
Revises: a7f3e1c92b04
Create Date: 2026-06-19 16:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "a7f3e1c92b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) realm 컬럼 추가(NOT NULL). server_default 로 기존 행을 '본서버'로 백필한 뒤
    #    default 를 제거한다 → 모델엔 server_default 없음(드리프트 0). 앱이 매 insert realm 명시.
    op.add_column(
        "exp_snapshot",
        sa.Column(
            "realm", sa.String(length=16), nullable=False, server_default="본서버"
        ),
    )
    op.alter_column("exp_snapshot", "realm", server_default=None)

    # 2) PK 재정의: (guild, user, date) → (guild, user, date, realm).
    op.drop_constraint("exp_snapshot_pkey", "exp_snapshot", type_="primary")
    op.create_primary_key(
        "exp_snapshot_pkey",
        "exp_snapshot",
        ["guild_id", "discord_user_id", "snapshot_date", "realm"],
    )


def downgrade() -> None:
    op.drop_constraint("exp_snapshot_pkey", "exp_snapshot", type_="primary")
    # 챌린저스 행 삭제 → (guild,user,date) 유일성 복원(손실 허용, 비상 롤백).
    op.execute("DELETE FROM exp_snapshot WHERE realm <> '본서버'")
    op.create_primary_key(
        "exp_snapshot_pkey",
        "exp_snapshot",
        ["guild_id", "discord_user_id", "snapshot_date"],
    )
    op.drop_column("exp_snapshot", "realm")
