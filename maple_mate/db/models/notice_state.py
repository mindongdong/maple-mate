"""④ notice_state — 공지/썬데이 발송 상태 (design §5④).

카테고리별 마지막 발송 식별자 + 썬데이 마지막 발송 주차를 키-값으로 보관.
category 예: "notice", "notice-update"(공지 카테고리별 마지막 식별자), "sunday"(마지막 발송 주차).
Phase 1 에서는 테이블만 생성(알림은 Phase 4).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NoticeState(Base):
    __tablename__ = "notice_state"

    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
