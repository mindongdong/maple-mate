"""leaderboard ORM — 일자별 누적 경험치 스냅샷 (작업지시서 빌드 단위 #1·#3).

스냅샷 키 = (guild_id, discord_user_id, snapshot_date) — 같은 ocid 가 복수 길드면 길드별 행
(친구 그룹 단일 길드 전제, 작업지시서 파생 결정). total_exp 는 누적(14자리)이라 BigInteger,
정렬키로만 쓰고 표에는 노출하지 않는다(Q2). world_rank 는 응답 ranking 값(미등재면 행 자체 없음).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class ExpSnapshot(Base):
    __tablename__ = "exp_snapshot"

    # PK = (guild_id, discord_user_id, snapshot_date, realm). Discord snowflake = 64bit → BigInteger.
    # realm(본서버/챌린저스)은 리더보드 2개 완전 분리를 위해 PK 에 포함(ADR-0009 — ADR-0006 PK
    # 불변을 의도적으로 되돌림). 같은 유저의 두 realm 대표가 같은 날 공존할 수 있어 필요하다.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    # Realm.value("본서버"/"챌린저스") 디스크리미넌트. 레거시 행은 마이그레이션이 '본서버'로 백필.
    realm: Mapped[str] = mapped_column(String(16), primary_key=True)

    character_level: Mapped[int] = mapped_column(Integer, nullable=False)
    # 누적 총 경험치(스파이크 실측 72조@Lv287) → BigInteger. 정렬키, 표 비노출.
    total_exp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 종합 랭킹의 전체 서버 순위(응답 ranking). 미관측 케이스 방어로 nullable.
    world_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 레벨 내 경험치 백분율(character/basic 의 character_exp_rate, "45.23"→45.23).
    # ranking/overall(주 소스)엔 없고 best-effort 보강이라 실패 시 None → nullable.
    exp_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
