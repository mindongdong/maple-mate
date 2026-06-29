"""개인 DM 발송 공통 헬퍼 — 정기 알림 4종(스케줄러·경험치·공지·썬데이)이 공유 (ADR-0017).

유저 해석(캐시 get_user → fetch 폴백)과 DM 발송을 한 곳에 둔다. 발송 인자는 `**send_kwargs`
로 그대로 `user.send` 에 넘겨 embed/embeds/files 를 자유롭게 보낸다. DM 차단(Forbidden)·기타
HTTP 실패는 앱로그만 남기고 False — 친구 자가발견(결정), 잡 전체를 멈추지 않는다.
"""

from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)


async def fetch_user(bot: discord.Client, user_id: int) -> discord.User | None:
    """DM 대상 유저 해석: 캐시(get_user) → fetch 폴백. 실패는 앱로그만."""
    user = bot.get_user(user_id)
    if user is not None:
        return user
    try:
        return await bot.fetch_user(user_id)
    except discord.HTTPException as exc:
        log.warning("DM 유저 해석 실패 (user=%s): %s", user_id, exc)
        return None


async def send_dm(bot: discord.Client, user_id: int, **send_kwargs) -> bool:
    """본인 DM 발송. DM 차단(Forbidden)·기타 HTTP 실패는 앱로그만 남기고 False."""
    user = await fetch_user(bot, user_id)
    if user is None:
        return False
    try:
        await user.send(**send_kwargs)
        return True
    except discord.HTTPException as exc:  # Forbidden(DM 차단) 포함
        log.warning("DM 발송 실패 (user=%s): %s", user_id, exc)
        return False
