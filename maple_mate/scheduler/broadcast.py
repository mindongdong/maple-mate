"""스케줄러 알리미 Discord 어댑터 + 명령 본체 공유 (작업지시서 #4).

전달-무관 service 위에 넥슨 페치·PNG 카드·DM 발송을 얹는 얇은 어댑터. `build_homeworks` 는
`/스케줄러` 온디맨드와 매시 정각 DM 잡이 공유하는 산출물 빌더(결정 6) — realm 캐릭터 전부를
캐릭터별 Homework 리스트로 낸다. `build_card_payload` 는 그 Homework 를 (content 한 줄, PNG
카드 bytes)로 렌더한다(ADR-0013). `run_scheduler_reminder_job` 은 그 시각 구독 0개면 스킵(넥슨
0콜) → 구독별 캐릭터 전부 빌드 → 캐릭터당 카드 DM. 키없음·4xx·빈 숙제·DM 차단은 모두 **조용히
스킵 + 앱로그만**(결정 7 — "친구 개인 키 실패는 자가 발견").
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime

import discord

from ..bot.dm import send_dm
from ..bot.scheduler_card import card_summary_line, render_scheduler_card
from ..dependencies import Deps
from ..nexon.client import KST
from ..nexon.errors import NexonAPIError
from . import service
from .service import Homework

log = logging.getLogger(__name__)

# 카드 첨부 파일명(발송마다 fresh discord.File 로 감싼다 — BytesIO 1회용, leaderboard 전례).
_CARD_FILE = "scheduler_card.png"


def _card_file(png: bytes) -> discord.File:
    """PNG bytes → 발송용 discord.File(발송마다 fresh — BytesIO 1회용, leaderboard 전례)."""
    return discord.File(io.BytesIO(png), filename=_CARD_FILE)


async def build_card_payload(
    hw: Homework,
    now: datetime,
    excluded: frozenset[str] = frozenset(),
) -> tuple[str, bytes]:
    """Homework → (content 한 줄, PNG 카드 bytes). 온디맨드·DM 잡 공유(build_embed 후신, ADR-0013).

    렌더는 순수 PIL 이라 이벤트 루프를 막지 않게 `asyncio.to_thread` 로 돌린다(leaderboard 규약).
    content 는 푸시 알림 미리보기용 한 줄(`캐릭터 — 남은 숙제 N개 (D/T 완료)`), 카드가 곧 메시지다
    (임베드 셸 없음). 카테고리 파생·todo-first·excluded 필터·전부완료 상태색·챌린저스 뱃지는 카드
    렌더러가 보존한다. 페치는 불변(표시 전용).
    """
    content = card_summary_line(hw, excluded)
    png = await asyncio.to_thread(render_scheduler_card, hw, now, excluded)
    return content, png


async def build_homeworks(
    deps: Deps, guild_id: int, user_id: int
) -> tuple[list[Homework], str | None]:
    """본인 키 + 등록 캐릭터 전부 → 각 캐릭터 오늘 스케줄러 페치 → 파싱. 온디맨드·DM 잡 공유.

    성공이면 (homeworks, None) — 캐릭터별 Homework 리스트(is_empty 포함 가능, 캐릭터 4xx 는
    조용히 스킵하고 나머지는 계속). 가드 실패(미등록·키없음·캐릭터 0)면 ([], 사용자메시지).
    개인 키 4xx(비대상·저활동)는 raise 하지 않고 error_log 미적재(결정 7 — 운영 요약 제외 철학).
    """
    key_encrypted, chars, error = await service.resolve_self_characters(
        deps.session_factory, guild_id, user_id
    )
    if error is not None:
        return [], error
    api_key = deps.cipher.decrypt(key_encrypted)  # type: ignore[arg-type]
    homeworks: list[Homework] = []
    for ocid, _nickname in chars:
        try:
            data = await deps.nexon.scheduler_character_state(
                api_key, ocid
            )  # 오늘=무지정
        except NexonAPIError as exc:
            log.warning(
                "스케줄러 조회 실패 (guild=%s user=%s ocid=%s): %s",
                guild_id,
                user_id,
                ocid,
                exc,
            )
            continue  # 캐릭터별 4xx → 조용히 스킵(나머지 캐릭터는 계속)
        homeworks.append(service.parse_homework(data))
    return homeworks, None


async def run_scheduler_reminder_job(bot: discord.Client, deps: Deps) -> None:
    """매시 정각 잡: now.hour 구독 조회 → 0개면 스킵 → 구독별 등록 캐릭터 전부 빌드 → 캐릭터당 DM.

    캐릭터마다 PNG 카드 1개를 별도 DM 으로 보낸다(캐릭터 4개면 DM 4개). is_empty(등록 숙제 0개)·
    실패(키없음·4xx)·DM 차단은 모두 조용히 스킵(결정 7). 한 캐릭터/구독 실패가 다음을 막지 않는다.
    """
    now = datetime.now(KST)
    subs = await service.subscriptions_at_hour(deps.session_factory, now.hour)
    if not subs:
        log.info("스케줄러 알리미 스킵: %d시 구독 없음(넥슨 호출 안 함)", now.hour)
        return

    sent = 0
    for sub in subs:
        homeworks, _error = await build_homeworks(
            deps, sub.guild_id, sub.discord_user_id
        )
        for homework in homeworks:
            if service.is_empty_filtered(homework, sub.excluded):
                continue  # 필터 후 빈 캐릭터 스킵(빈 DM 금지)
            content, png = await build_card_payload(homework, now, sub.excluded)
            if await send_dm(
                bot, sub.discord_user_id, content=content, file=_card_file(png)
            ):
                sent += 1
    log.info(
        "스케줄러 알리미: %d시 구독 %d건, 캐릭터 %d개 DM 발송",
        now.hour,
        len(subs),
        sent,
    )
