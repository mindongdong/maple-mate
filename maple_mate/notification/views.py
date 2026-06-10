"""수동 썬데이 발송 HTTP 라우터 (FastAPI). 설계 §4 "수동 썬데이 발송", 핸드오프 #4·#6.

운영자가 Bearer 토큰으로 인증해 단일 썬데이 이벤트를 즉시 발송한다. 인증은
security.auth.verify_operator_token, 발송 오케스트레이션은 scheduler.manual_broadcast_sunday
에 위임하고 여기서는 바디 검증·매핑만 담당한다. api/core.py 가 이 라우터를 include 한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..security.auth import verify_operator_token
from .scheduler import manual_broadcast_sunday
from .service import SundayEvent

router = APIRouter()


class SundayBroadcastBody(BaseModel):
    """수동 발송 바디 — 단일 이벤트(#4). title 필수, 나머지 선택."""

    title: str = Field(min_length=1)  # 빈/누락 → pydantic 422(#6)
    link: str | None = None
    period: str | None = None
    image: str | None = (
        None  # 본문 하단 큰 배너 이미지 URL(선택). 자동 /썬데이의 detail_image_url 대응
    )


def _to_event(body: SundayBroadcastBody) -> SundayEvent:
    """바디 → SundayEvent 순수 매퍼(단위테스트 대상).

    period 미입력 시 format_period 폴백과 동일한 "기간 미정"으로 채운다. image 가 있으면
    detail_image_url(본문 하단 큰 배너)로 그대로 싣는다 — 운영자가 이벤트 페이지에서 복사한
    이미지 URL. 작은 썸네일(thumbnail_url)은 수동에선 받지 않는다.
    """
    return SundayEvent(
        title=body.title,
        url=body.link or "",
        thumbnail_url=None,
        period_text=body.period or "기간 미정",
        detail_image_url=body.image or None,
    )


@router.post("/sunday/broadcast", dependencies=[Depends(verify_operator_token)])
async def manual_sunday(body: SundayBroadcastBody, request: Request) -> dict[str, int]:
    sent, total = await manual_broadcast_sunday(
        request.app.state.bot, request.app.state.deps, _to_event(body)
    )
    return {"sent": sent, "total": total}
