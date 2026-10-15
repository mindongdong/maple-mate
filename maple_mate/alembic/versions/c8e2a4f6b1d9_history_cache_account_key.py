"""history_cache: 캐시 이름표 ocid 앵커 → 계정 식별자(account_key) (ADR-0024)

이력(스타포스·잠재)은 개인 키 = 계정 단위 데이터인데, 캐시 키가 "최초 등록 캐릭터 ocid"(ADR-0007 앵커)라
① 앵커 캐릭터 삭제 시 콜드 재조회 ② 다른 계정 키로 교체해도 이전 계정 캐시 반환 ③ 서로 다른 키가 같은
앵커를 공유하면 기록 혼입 — 이 있었다. 컬럼을 account_key 로 **이름만 바꾼다**(PK 유지, 데이터 보존).
기존 행의 값은 아직 ocid 라 새 키(HMAC hex)와 매칭되지 않는다 → 배포 직후
`scripts/migrate_history_cache_keys.py --apply` 로 안전한 행만 옮긴다(옮기지 못한 행은 400일 prune).

Revision ID: c8e2a4f6b1d9
Revises: 0b6e2f4c8d19
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c8e2a4f6b1d9"
down_revision: str | None = "0b6e2f4c8d19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("history_cache", "ocid", new_column_name="account_key")


def downgrade() -> None:
    op.alter_column("history_cache", "account_key", new_column_name="ocid")
