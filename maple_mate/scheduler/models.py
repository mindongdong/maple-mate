"""scheduler ORM — per-user DM 구독 1레코드 (ADR-0012).

채널 알림(`channel_settings`)과 분기된 첫 사례: 구독 주체가 채널이 아니라 **본인**이고,
realm 별로 독립이며 발송 시각(`hour`)을 행마다 저장한다. 매시 정각 cron 이 그 시각 구독을 조회해
본인 DM 으로 숙제 체크리스트를 보낸다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database.core import Base


class SchedulerSubscription(Base):
    __tablename__ = "scheduler_subscription"

    # PK = (guild_id, discord_user_id, realm). 본서버·챌린저스를 따로 켜고 시각도 따로 둘 수
    # 있어 realm 이 PK 에 포함된다(ADR-0012 결정 3, ADR-0009). realm = Realm.value 디스크리미넌트.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    realm: Mapped[str] = mapped_column(String(16), primary_key=True)

    # 발송 시각(KST 시 단위, 0–23). 기본값(21)은 앱이 켜기 upsert 마다 명시 → 서버 default 없음.
    hour: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
