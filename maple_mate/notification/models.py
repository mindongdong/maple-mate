"""notification ORM — 채널 알림 토글 + 공지/썬데이 발송 상태 (design §5③④).

- ChannelSettings: 채널별 공지/썬데이 알림 on/off (알림은 채널 단위, design §2).
- NoticeState: 카테고리별 마지막 발송 식별자 + 썬데이 마지막 발송 주차(키-값).
Phase 1 은 테이블만 생성(발송 로직은 Phase 4).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class ChannelSettings(Base):
    __tablename__ = "channel_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    notice_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    sunday_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    exp_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class NoticeState(Base):
    __tablename__ = "notice_state"

    # category 예: "notice", "notice-update"(공지 카테고리별 마지막 식별자), "sunday"(마지막 발송 주차)
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
