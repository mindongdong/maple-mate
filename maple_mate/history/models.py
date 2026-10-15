"""history_cache ORM — 이력류 원본 JSON 캐시 (design §5②).

PK = (account_key, type, date). account_key = 개인 API 키에서 만든 계정 식별자(ADR-0024 — 이력은 키=계정
단위라 캐릭터 ocid 앵커를 대체). 과거 일자=불변, 오늘(KST)=5분 TTL.
TTL 판정 로직은 같은 도메인의 cache.py 순수함수가 담당. Phase 1 은 테이블만 생성.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class LearnedEquipmentLevel(Base):
    """관측된 장비명→레벨 (레벨 3단 매칭 자동 학습).

    item-equipment 조회에서 본 장비의 base_equipment_level 을 적재해 둔다. 나중에 교체·탈착돼
    현재 장착에 없는 장비도 이 표로 매칭(레벨은 장비명당 고정이라 안전). 시드는 부트스트랩일 뿐,
    실데이터로 커버리지가 점진 확장된다.
    """

    __tablename__ = "learned_equipment_level"

    item_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    base_equipment_level: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class HistoryCache(Base):
    __tablename__ = "history_cache"

    # 계정 식별자 = KeyCipher.account_key(평문 키) — HMAC hex 64자(ADR-0024). 길이 128 은 이전
    # ocid 앵커 시절 컬럼을 rename 만 해 유지(이전 행은 이전 스크립트가 옮기거나 400일 prune).
    account_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    # type ∈ {starforce, cube, potential_reset}
    type: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date_type] = mapped_column(
        Date, primary_key=True
    )  # 조회 기준일(YYYY-MM-DD, KST)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # 넥슨 원본 JSON
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
