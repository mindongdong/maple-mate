"""② history_cache — 이력류 원본 JSON 캐시 (design §5②).

PK = (ocid, type, date). ocid 기준 공유(서버 무관). 과거 일자=불변, 오늘(KST)=5분 TTL.
TTL 판정 로직은 maple_mate/nexon/cache.py 의 순수함수가 담당.
Phase 1 에서는 테이블만 생성(이력류 명령은 Phase 3).
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class HistoryCache(Base):
    __tablename__ = "history_cache"

    ocid: Mapped[str] = mapped_column(String(128), primary_key=True)
    # type ∈ {starforce, cube, potential_reset}
    type: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)  # 조회 기준일(YYYY-MM-DD, KST)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # 넥슨 원본 JSON
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
