"""error_log ORM — 재시도 발생 건 적재 (design §5⑤).

error_type ∈ {nexon_api, auth_invalid, timeout, rate_limit, internal, unmatched_equipment}.
재시도가 발생한 건만 기록(첫 시도 성공은 미기록). detail: 미매칭 장비명 등. 컬럼은 단순 문자열.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class ErrorLog(Base):
    __tablename__ = "error_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    command: Mapped[str | None] = mapped_column(String(64), nullable=True)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    discord_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_ocid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_type: Mapped[str] = mapped_column(String(32), nullable=False)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
