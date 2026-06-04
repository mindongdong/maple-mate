"""③ channel_settings — 채널별 알림 토글 (design §5③). 알림은 채널 단위(§2)."""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ChannelSettings(Base):
    __tablename__ = "channel_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    notice_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sunday_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
