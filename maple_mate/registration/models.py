"""registration ORM — (guild_id, discord_user_id) 1레코드 (design §5①)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class Registration(Base):
    __tablename__ = "registration"

    # PK = (guild_id, discord_user_id). Discord snowflake = 64bit → BigInteger.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    maple_nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    ocid: Mapped[str] = mapped_column(String(128), nullable=False)  # 등록 시 검증/캐싱
    # 개인 키(Fernet 암호문). 키 미등록이면 NULL → 스펙류만 가능.
    api_key_encrypted: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # 서버 내 닉네임 중복 허용(MVP) → maple_nickname 에 unique 제약 없음.
