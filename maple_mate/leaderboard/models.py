"""leaderboard ORM — 캐릭터별·일자별 경험치 진행도 스냅샷 (작업지시서 빌드 단위 #1·#3).

스냅샷 키 = (guild_id, discord_user_id, ocid, snapshot_date) — 캐릭터(ocid) 차원 포함
(`/내캐릭터 경험치`, ADR-0018). 같은 ocid 가 복수 길드/유저면 각각 행(친구 그룹 단일 길드 전제,
작업지시서 파생 결정). 값 = character/basic(date) 의 그날 마감 (레벨, 레벨 내 exp%) 단일
소스(ADR-0020 — 종전 ranking/overall 의 total_exp·world_rank 는 표시 폐기와 함께 제거).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class ExpSnapshot(Base):
    __tablename__ = "exp_snapshot"

    # PK = (guild_id, discord_user_id, ocid, snapshot_date). Discord snowflake = 64bit → BigInteger.
    # ocid(캐릭터 차원)는 ADR-0018(수집 = 등록 전 캐릭터) — 같은 유저의 캐릭터 N개가 같은 날
    # 공존한다. realm 은 PK 에서 강등(ADR-0009 의 "두 realm 대표 공존"을 ocid 가 더 정밀하게 해결).
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ocid: Mapped[str] = mapped_column(String(128), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    # Realm.value("본서버"/"챌린저스") 디스크리미넌트 — 서버 리더보드의 realm 필터용 일반 컬럼.
    realm: Mapped[str] = mapped_column(String(16), nullable=False)

    character_level: Mapped[int] = mapped_column(Integer, nullable=False)
    # 레벨 내 경험치 백분율(character/basic 의 character_exp_rate, "45.23"→45.23).
    # 레벨과 같은 응답에서 오지만 필드 결손 방어로 nullable(결손이면 그날 그래프 선 끊김).
    exp_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
