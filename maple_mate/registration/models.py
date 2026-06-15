"""registration ORM — 유저/계정 레벨 1레코드 + 캐릭터 N개(멀티 캐릭터 작업지시서 §데이터모델).

- `Registration`: (guild_id, discord_user_id) 1레코드. 개인 키 + 대표 캐릭터 포인터.
- `Character`: (guild_id, discord_user_id, ocid) N레코드. 등록된 메이플 캐릭터(닉·레벨 스냅샷).
  논리적 FK → Registration(부모 행은 캐릭터/키 등록 시 자동 upsert). DB 제약은 두지 않는다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class Registration(Base):
    __tablename__ = "registration"

    # PK = (guild_id, discord_user_id). Discord snowflake = 64bit → BigInteger.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # 개인 키(Fernet 암호문). 키 미등록이면 NULL → 스펙류만 가능. 유저당 1개(계정 공유, 그릴링 1).
    api_key_encrypted: Mapped[str | None] = mapped_column(String, nullable=True)
    # 대표 캐릭터 ocid. NULL=자동(최고 레벨) / 값=수동 지정(/대표지정, 그릴링 5·6).
    representative_ocid: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Character(Base):
    __tablename__ = "character"

    # PK = (guild_id, discord_user_id, ocid). 같은 유저가 같은 캐릭(ocid) 재등록 시 upsert.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ocid: Mapped[str] = mapped_column(String(128), primary_key=True)

    maple_nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    # 등록 시 레벨 스냅샷(그릴링 5). 자동 대표 = 저장 레벨 최고값. 미상 시 NULL(타이브레이크로 처리).
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
