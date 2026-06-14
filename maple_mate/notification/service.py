"""썬데이 알림 비즈니스 로직 (전달-무관: 순수 + DB). discord/apscheduler 타입에 의존하지 않는다.

순수: 제목 매칭(`match_sunday`)·주차 식별자(`current_week_id`)·기간 포맷(`format_period`)·
이벤트 선별(`select_sunday_events`). DB: 주차 dedup 마커(notice_state) 읽기/쓰기, 알림 채널
조회, 채널 토글 upsert. 작업지시서(docs/sunday-work-order.md) §2 빌드 단위 #2.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from ..nexon.client import KST, NexonClient
from ..nexon.errors import NexonAPIError
from .models import ChannelSettings, NoticeState

log = logging.getLogger(__name__)

# notice_state 의 썬데이 dedup 마커가 사는 카테고리 키(design §5④).
SUNDAY_CATEGORY = "sunday"

# 상세 본문(contents) HTML 에서 첫 <img src> 추출 — 단·쌍따옴표 모두 허용.
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


@dataclass(frozen=True)
class SundayEvent:
    """발송 대상 이벤트 1건(전달 계층이 임베드로 렌더).

    thumbnail_url=목록의 작은 썸네일, detail_image_url=상세 본문의 큰 배너(둘 다 없을 수 있음).
    """

    title: str
    url: str
    thumbnail_url: str | None
    period_text: str
    detail_image_url: str | None = None


# ── 순수 함수 (단위테스트 대상) ────────────────────────────────────────────


def match_sunday(title: str | None) -> bool:
    """제목이 썬데이 이벤트인지(공백 무시 부분일치, 작업지시서 Q2).

    notice-event 는 진행 중 항목만 반환하므로 기간 필터는 두지 않는다. "썬데이 메이플"·
    "썬데이메이플" 등 공백 변형을 모두 흡수하기 위해 공백 제거 후 부분일치한다.
    """
    if not title:
        return False
    return "썬데이메이플" in title.replace(" ", "")


def current_week_id(now_kst: datetime) -> str:
    """이번 주 dedup 식별자 `"YYYY-Www"` (ISO 연-주차, KST 기준).

    naive datetime 은 KST 로 간주, tz-aware 는 KST 로 변환 후 ISO 주차를 뽑는다.
    연말/연초 경계에서 ISO 연도가 달력 연도와 다를 수 있어 `isocalendar().year` 를 쓴다.
    """
    kst = now_kst if now_kst.tzinfo is None else now_kst.astimezone(KST)
    iso = kst.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _parse_kst(value: str | None) -> datetime | None:
    """ISO 문자열(`...+09:00` / `...Z` / 초·밀리초 유무 혼재)을 KST datetime 으로. 실패 시 None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def format_period(start_iso: str | None, end_iso: str | None) -> str:
    """이벤트 기간 표시 `"YYYY-MM-DD HH:MM ~ YYYY-MM-DD HH:MM"` (KST). 파싱 실패는 우아하게 폴백."""
    start = _parse_kst(start_iso)
    end = _parse_kst(end_iso)
    if start is None and end is None:
        return "기간 미정"
    if start is None:
        return f"~ {end:%Y-%m-%d %H:%M}"
    if end is None:
        return f"{start:%Y-%m-%d %H:%M} ~"
    return f"{start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M}"


def extract_content_image(contents: str | None) -> str | None:
    """상세 본문 HTML 에서 첫 절대(http/https) 이미지 URL. 없으면 None. 순수 — 단위테스트 대상."""
    if not contents:
        return None
    for match in _IMG_SRC_RE.finditer(contents):
        url = match.group(1).strip()
        if url.lower().startswith(("http://", "https://")):
            return url
    return None


async def _detail_image_url(nexon: NexonClient, notice_id: object) -> str | None:
    """이벤트 상세를 페치해 본문 배너 이미지 URL 추출. 상세 페치 실패는 비치명(배너만 생략).

    배너는 보조 정보라, 상세 호출이 실패해도 이벤트 자체는 썸네일로 발송한다(목록 페치 실패와 구분).
    """
    if not isinstance(notice_id, int):
        return None
    try:
        detail = await nexon.notice_event_detail(notice_id)
    except NexonAPIError as exc:
        log.warning("썬데이 상세 페치 실패 (notice_id=%s): %s", notice_id, exc)
        return None
    return extract_content_image(detail.get("contents"))


async def select_sunday_events(nexon: NexonClient) -> list[SundayEvent]:
    """진행 중 이벤트를 페치해 썬데이만 선별(매칭 0건이면 빈 리스트).

    매칭된 항목은 상세를 1회 더 호출해 본문 배너 이미지 URL 까지 채운다(상세 실패는 비치명).
    목록 페치 실패는 NexonAPIError 로 그대로 전파(잡 본체가 잡아 error_log 적재).
    """
    events = await nexon.notice_event()
    selected: list[SundayEvent] = []
    for event in events:
        title = event.get("title")
        if not match_sunday(title):
            continue
        selected.append(
            SundayEvent(
                title=title or "",
                url=event.get("url") or "",
                thumbnail_url=event.get("thumbnail_url"),
                period_text=format_period(
                    event.get("date_event_start"), event.get("date_event_end")
                ),
                detail_image_url=await _detail_image_url(nexon, event.get("notice_id")),
            )
        )
    return selected


# ── DB (전달-무관) ────────────────────────────────────────────────────────


async def already_sent_this_week(
    session_factory: async_sessionmaker[AsyncSession], week_id: str
) -> bool:
    """이번 주 썬데이가 이미 발송됐는지(notice_state 마커 == week_id)."""
    async with session_factory() as session:
        row = await session.get(NoticeState, SUNDAY_CATEGORY)
    return row is not None and row.last_identifier == week_id


async def mark_week_sent(
    session_factory: async_sessionmaker[AsyncSession], week_id: str
) -> None:
    """이번 주를 발송 완료로 마킹(notice_state upsert). 채널 부분 실패와 무관하게 강행(Q3③)."""
    async with session_factory() as session:
        stmt = (
            pg_insert(NoticeState)
            .values(category=SUNDAY_CATEGORY, last_identifier=week_id)
            .on_conflict_do_update(
                index_elements=["category"],
                set_={"last_identifier": week_id, "updated_at": func.now()},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def enabled_sunday_channels(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[tuple[int, int]]:
    """썬데이 알림이 켜진 (guild_id, channel_id) 목록(알림은 채널 단위, design §2)."""
    async with session_factory() as session:
        stmt = select(ChannelSettings.guild_id, ChannelSettings.channel_id).where(
            ChannelSettings.sunday_alert.is_(True)
        )
        rows = (await session.execute(stmt)).all()
    return [(row.guild_id, row.channel_id) for row in rows]


async def set_sunday_alert(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    channel_id: int,
    enabled: bool,
) -> None:
    """채널의 썬데이 알림 토글 upsert. `sunday_alert` 만 set 해 `notice_alert` 는 보존(Q5)."""
    async with session_factory() as session:
        stmt = (
            pg_insert(ChannelSettings)
            .values(guild_id=guild_id, channel_id=channel_id, sunday_alert=enabled)
            .on_conflict_do_update(
                index_elements=["guild_id", "channel_id"],
                set_={"sunday_alert": enabled},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def enabled_exp_channels(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[tuple[int, int]]:
    """경험치 리더보드 알림이 켜진 (guild_id, channel_id) 목록(알림은 채널 단위, 작업지시서 Q8)."""
    async with session_factory() as session:
        stmt = select(ChannelSettings.guild_id, ChannelSettings.channel_id).where(
            ChannelSettings.exp_alert.is_(True)
        )
        rows = (await session.execute(stmt)).all()
    return [(row.guild_id, row.channel_id) for row in rows]


async def set_exp_alert(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    channel_id: int,
    enabled: bool,
) -> None:
    """채널의 경험치 리더보드 알림 토글 upsert. `exp_alert` 만 set 해 다른 토글은 보존(Q8)."""
    async with session_factory() as session:
        stmt = (
            pg_insert(ChannelSettings)
            .values(guild_id=guild_id, channel_id=channel_id, exp_alert=enabled)
            .on_conflict_do_update(
                index_elements=["guild_id", "channel_id"],
                set_={"exp_alert": enabled},
            )
        )
        await session.execute(stmt)
        await session.commit()
