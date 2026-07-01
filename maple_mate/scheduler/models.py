"""scheduler ORM — per-user DM 구독 1레코드 (ADR-0012, realm 제거 ADR-0017).

채널 알림(`channel_settings`)과 분기된 첫 사례: 구독 주체가 채널이 아니라 **본인**이고,
발송 시각(`hour`)을 행마다 저장한다. 매시 정각 cron 이 그 시각 구독을 조회해 본인 DM 으로
숙제 체크리스트를 보낸다. 한 구독 = 등록 캐릭터 전부(본+챌, realm 분리 폐기 — ADR-0017).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class SchedulerSubscription(Base):
    __tablename__ = "scheduler_subscription"

    # PK = (guild_id, discord_user_id). realm 제거(ADR-0017) — 한 구독이 등록 캐릭터 전부를
    # 받으므로 realm 별 분리가 사라졌다(ADR-0012 결정 3 되돌림). 뱃지는 캐릭터 world 로 파생.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # 발송 시각(KST 시 단위, 0–23). 기본값(21)은 앱이 켜기 upsert 마다 명시 → 서버 default 없음.
    hour: Mapped[int] = mapped_column(Integer, nullable=False)

    # 숨김 묶음 CSV(예: "보스,길드"). NULL/빈=제외 없음=전부 표시(ADR-0014 결정 4 — 하위·상위호환).
    excluded_categories: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
