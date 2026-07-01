"""notification ORM — 채널 알림 토글 + 공지/썬데이 발송 상태 + 개인 DM 구독 (design §5③④, ADR-0017).

- ChannelSettings: 채널별 공지/썬데이/경험치 알림 on/off (알림은 채널 단위, design §2).
- NoticeState: 카테고리별 마지막 발송 식별자 + 썬데이 마지막 발송 주차(키-값).
- NotificationSubscription: 경험치·공지·썬데이의 **개인 DM 구독**(행 존재=구독, 시각 없음, ADR-0017).
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


class NotificationSubscription(Base):
    __tablename__ = "notification_subscription"

    # PK = (guild_id, discord_user_id, kind). 행 존재 = 구독(별도 on/off 컬럼 없음, ADR-0017 결정 5).
    # kind ∈ {"exp","notice","sunday"} — service 의 KIND_* 상수로 고정. 시각·realm 컬럼 없음
    # (고정 주기 콘텐츠라 사용자 시각 불필요; 스케줄러 DM 은 별 테이블 scheduler_subscription).
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
