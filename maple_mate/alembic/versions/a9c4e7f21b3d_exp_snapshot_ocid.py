"""my character exp: exp_snapshot.ocid PK 확장 + realm PK 강등

`/내캐릭터 경험치`(캐릭터별 추이)를 위해 스냅샷에 캐릭터(ocid) 차원을 더한다(ADR-0018 결정 6).
PK (guild, user, date, realm) → (guild, user, ocid, date). ocid 가 행 유일성을 더 정밀하게
보장하므로 realm 은 PK 에서 강등해 일반 컬럼으로 존치한다(서버 리더보드 필터용 디스크리미넌트
— ADR-0009 의 "두 realm 대표가 같은 날 공존" 문제를 ocid 가 포섭).

기존 행 백필 = 그 (guild, user, realm) 의 **현재 대표 ocid**(get_targets 와 동일 규칙: 수동
핀이 그 realm 이면 그것, 아니면 레벨 최고 → created_at → ocid). 과거에 다른 대표였던 기간의
행도 현재 대표 이름표를 달게 되는 근사는 ADR-0018 에 명기된 감수 사항. 대표를 해석할 수 없는
고아 행(등록 해제 유저 등)은 삭제한다(리더보드에 이미 안 잡히는 데이터).

⚠️ 다운그레이드는 같은 (guild, user, date, realm) 키의 복수 캐릭터 행 중 대표 ocid 행 우선,
없으면 total_exp 최대 행만 남기고 삭제한다(손실 허용, 비상 롤백).
⚠️ "character" 는 SQL 예약어 → 원시 SQL 에서는 반드시 큰따옴표로 인용한다.

Revision ID: a9c4e7f21b3d
Revises: b7d2c5e8f1a3
Create Date: 2026-07-03 10:00:00.000000

"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c4e7f21b3d"
down_revision: str | None = "b7d2c5e8f1a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger(__name__)


def upgrade() -> None:
    # 1) ocid 컬럼 추가(임시 nullable — 백필 후 NOT NULL 로 조인다).
    op.add_column(
        "exp_snapshot", sa.Column("ocid", sa.String(length=128), nullable=True)
    )

    # 2) 백필: 각 (guild, user, realm) 그룹의 기존 행에 그 realm 의 현재 대표 ocid 주입.
    #    realm 판정 = world 접두 '챌린저스'(NULL/그 외 = 본서버, ADR-0009). 대표 우선순위 =
    #    수동 핀(representative_ocid) 일치 → 레벨 → created_at → ocid(결정적 타이브레이크).
    op.execute(
        """
        UPDATE exp_snapshot es
        SET ocid = rep.ocid
        FROM (
            SELECT DISTINCT ON (ch.guild_id, ch.discord_user_id, char_realm)
                ch.guild_id, ch.discord_user_id, ch.ocid,
                CASE WHEN ch.world LIKE '챌린저스%' THEN '챌린저스'
                     ELSE '본서버' END AS char_realm
            FROM "character" ch
            LEFT JOIN registration reg
              ON reg.guild_id = ch.guild_id
             AND reg.discord_user_id = ch.discord_user_id
            ORDER BY ch.guild_id, ch.discord_user_id, char_realm,
                (ch.ocid = reg.representative_ocid) DESC NULLS LAST,
                ch.level DESC NULLS LAST,
                ch.created_at ASC,
                ch.ocid ASC
        ) rep
        WHERE es.guild_id = rep.guild_id
          AND es.discord_user_id = rep.discord_user_id
          AND es.realm = rep.char_realm
        """
    )

    # 3) 고아 행 삭제: 그 realm 대표를 해석할 수 없는 스냅샷(등록 해제 유저 등).
    result = op.get_bind().execute(
        sa.text("DELETE FROM exp_snapshot WHERE ocid IS NULL")
    )
    log.info("exp_snapshot 고아 행 삭제: %d건 (대표 해석 불가)", result.rowcount)

    # 4) NOT NULL + PK 재정의: (guild, user, date, realm) → (guild, user, ocid, date).
    op.alter_column("exp_snapshot", "ocid", nullable=False)
    op.drop_constraint("exp_snapshot_pkey", "exp_snapshot", type_="primary")
    op.create_primary_key(
        "exp_snapshot_pkey",
        "exp_snapshot",
        ["guild_id", "discord_user_id", "ocid", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_constraint("exp_snapshot_pkey", "exp_snapshot", type_="primary")
    # (guild, user, date, realm) 당 1행만 남긴다: 대표 ocid 행 우선, 없으면 total_exp 최대 행
    # (ocid ASC 는 결정적 타이브레이크). 나머지 캐릭터 행은 삭제(손실 허용, 비상 롤백).
    op.execute(
        """
        DELETE FROM exp_snapshot es
        USING (
            SELECT DISTINCT ON (s.guild_id, s.discord_user_id, s.snapshot_date, s.realm)
                s.guild_id, s.discord_user_id, s.snapshot_date, s.realm, s.ocid
            FROM exp_snapshot s
            LEFT JOIN registration reg
              ON reg.guild_id = s.guild_id
             AND reg.discord_user_id = s.discord_user_id
            ORDER BY s.guild_id, s.discord_user_id, s.snapshot_date, s.realm,
                (s.ocid = reg.representative_ocid) DESC NULLS LAST,
                s.total_exp DESC,
                s.ocid ASC
        ) keep
        WHERE es.guild_id = keep.guild_id
          AND es.discord_user_id = keep.discord_user_id
          AND es.snapshot_date = keep.snapshot_date
          AND es.realm = keep.realm
          AND es.ocid <> keep.ocid
        """
    )
    op.create_primary_key(
        "exp_snapshot_pkey",
        "exp_snapshot",
        ["guild_id", "discord_user_id", "snapshot_date", "realm"],
    )
    op.drop_column("exp_snapshot", "ocid")
