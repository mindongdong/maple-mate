"""썬데이 발송 어댑터 + APScheduler 라이프사이클 (작업지시서 빌드 단위 #3, Q1·Q4·Q7).

전달-무관 service 위에 Discord 발송과 스케줄을 얹는 얇은 어댑터. 봇이 스케줄러를 소유한다
(`start_scheduler`/`shutdown`). 잡 본체(`run_sunday_job`)는 주차 dedup·채널 0개·매칭 0개를
순서대로 가지치기한 뒤 발송→마킹한다. `broadcast_sunday`/`build_event_embeds` 는 미래의
수동 썬데이 HTTP 엔드포인트(설계 §4, 현재 보류)가 재사용할 수 있도록 채널 목록을 받는다.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..bot.embeds import BRAND_COLOR
from ..dependencies import Deps
from ..error_log import service as error_log
from ..nexon.client import KST
from ..nexon.errors import NexonAPIError, to_error_log_type
from . import notice_service, service
from .notice_service import NoticeItem
from .service import SundayEvent

log = logging.getLogger(__name__)

KST_ZONE = ZoneInfo("Asia/Seoul")
# 금요일 10:10 KST 정기 발송.
SUNDAY_DOW = "fri"
SUNDAY_HOUR = 10
SUNDAY_MINUTE = 10
# 봇이 10:10에 꺼져 있었으면 당일 안에 켜질 때 따라잡기(Q4②). 10:10~자정 ≈ 13h50m.
# coalesce=True 와 함께 한 번만 따라잡고, 주차 마커가 중복 발송을 차단한다.
MISFIRE_GRACE_SAME_DAY = 13 * 3600 + 50 * 60

# /공지알림 폴링: 매일 10·12·14·16·18·21시 KST(design §3.6). 발송 대상은 공지+업데이트(이벤트 제외).
NOTICE_HOURS = "10,12,14,16,18,21"
NOTICE_MINUTE = 0
# 한 메시지 임베드 상한(디스코드). 신규 다건이 이를 넘으면 여러 메시지로 쪼개 보낸다.
EMBEDS_PER_MESSAGE = 10


def build_event_embeds(events: Sequence[SundayEvent]) -> list[discord.Embed]:
    """이벤트 → 임베드(클릭 제목 + 기간 + 작은 썸네일 + 상세 배너 큰 이미지). 순수 — 단위테스트 대상(Q6).

    `thumbnail_url`=목록의 작은 썸네일(우상단), `detail_image_url`=상세 본문 배너(본문 하단 큰 이미지).
    둘 다 None 가드 — 없으면 해당 이미지 생략.
    """
    embeds: list[discord.Embed] = []
    for event in events:
        embed = discord.Embed(
            title=event.title,
            url=event.url or None,
            description=event.period_text,
            color=BRAND_COLOR,
        )
        if event.thumbnail_url:
            embed.set_thumbnail(url=event.thumbnail_url)
        if event.detail_image_url:
            embed.set_image(url=event.detail_image_url)
        embeds.append(embed)
    return embeds


async def _resolve_channel(
    bot: discord.Client, guild_id: int, channel_id: int
) -> discord.abc.Messageable | None:
    """채널 해석: 캐시(`get_channel`) → 실패 시 `fetch_channel` 폴백. 끝내 실패면 앱로그만(Q7)."""
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel  # type: ignore[return-value]
    try:
        return await bot.fetch_channel(channel_id)  # type: ignore[return-value]
    except discord.HTTPException as exc:  # NotFound/Forbidden 포함
        log.warning("썬데이 채널 해석 실패 (guild=%s channel=%s): %s", guild_id, channel_id, exc)
        return None


async def broadcast_sunday(
    bot: discord.Client,
    channels: Sequence[tuple[int, int]],
    events: Sequence[SundayEvent],
) -> int:
    """채널 목록에 썬데이 임베드 발송(재사용 가능). 다중 매칭은 단일 메시지 다중 임베드(Q6).

    채널/발송 실패는 앱로그만 남기고 계속(디스코드 발송 실패는 error_log 미적재 — Q7,
    enum·설계 경계 보존). 발송에 성공한 채널 수를 반환.
    """
    embeds = build_event_embeds(events)
    if not embeds:
        return 0
    sent = 0
    for guild_id, channel_id in channels:
        channel = await _resolve_channel(bot, guild_id, channel_id)
        if channel is None:
            continue
        try:
            await channel.send(embeds=embeds)
            sent += 1
        except discord.HTTPException as exc:
            log.warning("썬데이 발송 실패 (guild=%s channel=%s): %s", guild_id, channel_id, exc)
    return sent


async def manual_broadcast_sunday(
    bot: discord.Client, deps: Deps, event: SundayEvent
) -> tuple[int, int]:
    """운영자 수동 발송: 채널 조회 → 즉시 발송 → sent>0 이면 주차 마킹. (sent, total) 반환.

    자동 run_sunday_job 과 달리 already_sent_this_week 체크 없음(운영자 override, #2).
    마킹 게이트도 자동잡(channels>0)과 달리 **sent>0** — 실제 전달 0이면 그 주는
    미처리로 남겨 금요일 자동발송을 살린다(#3·#7). 봇 의존이라 전달-무관 service 가 아닌 여기.
    """
    channels = await service.enabled_sunday_channels(deps.session_factory)
    total = len(channels)
    if total == 0:
        return (0, 0)  # 0채널 → 마킹 안 함(#3)
    sent = await broadcast_sunday(bot, channels, [event])
    if sent > 0:  # sent>0 일 때만 마킹(#7)
        week_id = service.current_week_id(datetime.now(KST))
        await service.mark_week_sent(deps.session_factory, week_id)
    return (sent, total)


async def run_sunday_job(bot: discord.Client, deps: Deps) -> None:
    """정기 잡 본체: 주차 체크→스킵 / 채널 0개→스킵(넥슨 호출 안 함) / 매칭 0개→스킵 / 발송→마킹."""
    session_factory = deps.session_factory
    week_id = service.current_week_id(datetime.now(KST))

    if await service.already_sent_this_week(session_factory, week_id):
        log.info("썬데이 잡 스킵: %s 이미 발송됨", week_id)
        return

    channels = await service.enabled_sunday_channels(session_factory)
    if not channels:
        log.info("썬데이 잡 스킵: 알림 켠 채널 없음(넥슨 호출 안 함)")
        return

    try:
        events = await service.select_sunday_events(deps.nexon)
    except NexonAPIError as exc:
        log.warning("썬데이 이벤트 페치 실패: %s", exc)
        await error_log.record(
            session_factory,
            error_type=to_error_log_type(exc.error_class) or "nexon_api",
            command="썬데이",
            detail=f"{exc.code}: {exc.message}"[:500],
        )
        return  # 최종 실패 → 이번 주 포기(마킹 안 함, Q4①)

    if not events:
        log.info("썬데이 잡 스킵: 매칭 이벤트 0건(마킹 안 함)")
        return

    sent = await broadcast_sunday(bot, channels, events)
    log.info("썬데이 발송: 이벤트 %d건 → 채널 %d/%d", len(events), sent, len(channels))
    # 채널 부분 실패와 무관하게 마킹 강행(Q3③) — 같은 주 재시도 폭주 방지.
    await service.mark_week_sent(session_factory, week_id)


def build_notice_embeds(items: Sequence[NoticeItem]) -> list[discord.Embed]:
    """공지 → 임베드(클릭 제목 + 등록일, design §3.6). 순수 — 단위테스트 대상."""
    return [
        discord.Embed(
            title=item.title,
            url=item.url or None,
            description=item.date_text,
            color=BRAND_COLOR,
        )
        for item in items
    ]


async def broadcast_notices(
    bot: discord.Client,
    channels: Sequence[tuple[int, int]],
    items: Sequence[NoticeItem],
) -> int:
    """채널 목록에 신규 공지 임베드 발송. 다건은 10개씩 묶어 여러 메시지로(디스코드 임베드 상한).

    채널/발송 실패는 앱로그만 남기고 계속(썬데이와 동일 정책 — 디스코드 실패는 error_log 미적재).
    한 채널이라도 발송에 성공하면 카운트. 한 묶음 실패 시 그 채널의 나머지 묶음은 건너뛴다.
    """
    embeds = build_notice_embeds(items)
    if not embeds:
        return 0
    batches = [
        embeds[i : i + EMBEDS_PER_MESSAGE] for i in range(0, len(embeds), EMBEDS_PER_MESSAGE)
    ]
    sent = 0
    for guild_id, channel_id in channels:
        channel = await _resolve_channel(bot, guild_id, channel_id)
        if channel is None:
            continue
        delivered = False
        for batch in batches:
            try:
                await channel.send(embeds=batch)
                delivered = True
            except discord.HTTPException as exc:
                log.warning("공지 발송 실패 (guild=%s channel=%s): %s", guild_id, channel_id, exc)
                break
        if delivered:
            sent += 1
    return sent


async def _poll_notice_category(
    bot: discord.Client,
    deps: Deps,
    channels: Sequence[tuple[int, int]],
    category: str,
    fetch: Callable[[], Awaitable[list[dict]]],
) -> None:
    """한 카테고리(공지 또는 업데이트) 1회 폴링: 페치→파싱→신규선별→발송→마킹.

    페치 실패는 error_log 적재 후 마킹 없이 반환(다음 폴링 재시도). baseline(last_id None)은
    발송 없이 최대 id 만 마킹해 과거 공지 폭주를 막는다(design §3.6).
    """
    try:
        raw = await fetch()
    except NexonAPIError as exc:
        log.warning("공지 폴링 페치 실패 (%s): %s", category, exc)
        await error_log.record(
            deps.session_factory,
            error_type=to_error_log_type(exc.error_class) or "nexon_api",
            command="공지알림",
            detail=f"{category} {exc.code}: {exc.message}"[:500],
        )
        return

    items = notice_service.parse_notices(raw)
    if not items:
        return

    last_id = await notice_service.get_last_notice_id(deps.session_factory, category)
    new_items = notice_service.select_new(items, last_id)
    if new_items:
        sent = await broadcast_notices(bot, channels, new_items)
        log.info("공지 발송(%s): 신규 %d건 → 채널 %d/%d", category, len(new_items), sent, len(channels))
    # 마커는 전진만(절대 후퇴 금지). 페이지가 일시적으로 짧게 와 max id 가 last_id 보다 작아도
    # 마커를 낮추지 않는다 — 낮추면 이미 보낸 공지를 다음 폴링에 중복 재발송하게 됨.
    # baseline(last_id None) 포함, marker > last_id 일 때만 기록(items 비어있지 않으므로 marker 는 int).
    marker = notice_service.latest_id(items)
    if marker is not None and (last_id is None or marker > last_id):
        await notice_service.set_last_notice_id(deps.session_factory, category, marker)


async def run_notice_job(bot: discord.Client, deps: Deps) -> None:
    """정기 잡 본체: 알림 켠 채널 없으면 넥슨 호출 없이 스킵, 있으면 공지·업데이트 두 카테고리 폴링."""
    channels = await notice_service.enabled_notice_channels(deps.session_factory)
    if not channels:
        log.info("공지 잡 스킵: 알림 켠 채널 없음(넥슨 호출 안 함)")
        return

    await _poll_notice_category(
        bot, deps, channels, notice_service.NOTICE_CATEGORY, deps.nexon.notice
    )
    await _poll_notice_category(
        bot, deps, channels, notice_service.NOTICE_UPDATE_CATEGORY, deps.nexon.notice_update
    )


def start_scheduler(bot: discord.Client, deps: Deps) -> AsyncIOScheduler:
    """KST 스케줄러 생성 + 썬데이·공지 잡 등록 후 시작."""
    scheduler = AsyncIOScheduler(timezone=KST_ZONE)
    scheduler.add_job(
        run_sunday_job,
        trigger=CronTrigger(
            day_of_week=SUNDAY_DOW, hour=SUNDAY_HOUR, minute=SUNDAY_MINUTE, timezone=KST_ZONE
        ),
        args=[bot, deps],
        id="sunday",
        name="썬데이 알림",
        misfire_grace_time=MISFIRE_GRACE_SAME_DAY,
        coalesce=True,
    )
    scheduler.add_job(
        run_notice_job,
        trigger=CronTrigger(hour=NOTICE_HOURS, minute=NOTICE_MINUTE, timezone=KST_ZONE),
        args=[bot, deps],
        id="notice",
        name="공지 알림",
        coalesce=True,
        max_instances=1,  # 마커 read-modify-write 가 비트랜잭션이라 중복 실행 시 중복 발송 위험 → 명시.
    )
    scheduler.start()
    log.info(
        "스케줄러 시작: 썬데이(금 %02d:%02d)·공지(%s시) KST 잡 등록",
        SUNDAY_HOUR,
        SUNDAY_MINUTE,
        NOTICE_HOURS,
    )
    return scheduler


def shutdown(scheduler: AsyncIOScheduler) -> None:
    """스케줄러 정지(봇 close 시). 잡 완료를 기다리지 않음."""
    scheduler.shutdown(wait=False)
