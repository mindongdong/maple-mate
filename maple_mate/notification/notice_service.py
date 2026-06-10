"""`/공지알림` 비즈니스 로직 (전달-무관: 순수 + DB). discord/apscheduler 타입에 의존하지 않는다.

대상은 **공지사항 + 업데이트**(이벤트 제외 — 이벤트는 `/썬데이`가 담당). design §3.6.
신규 판정은 카테고리별 `notice_id` 최대값 기준(`id > last_id` 만 신규). 최초 가동은 baseline만
기록하고 과거 공지는 발송하지 않는다. notice_state 카테고리: "notice", "notice-update".

순수: 항목 파싱(`parse_notices`)·신규 선별(`select_new`)·최대 id(`latest_id`)·등록일 포맷.
DB: 카테고리별 마지막 발송 id 읽기/쓰기(notice_state), 알림 채널 조회, 채널 토글 upsert.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import func

from ..nexon.client import KST
from .models import ChannelSettings, NoticeState

# notice_state 의 공지/업데이트 마커가 사는 카테고리 키(design §5④). 넥슨 엔드포인트 한 종류당 하나.
NOTICE_CATEGORY = "notice"
NOTICE_UPDATE_CATEGORY = "notice-update"


@dataclass(frozen=True)
class NoticeItem:
    """발송 대상 공지 1건(전달 계층이 임베드로 렌더). 제목 + 링크 + 등록일(design §3.6)."""

    notice_id: int
    title: str
    url: str
    date_text: str


# ── 순수 함수 (단위테스트 대상) ────────────────────────────────────────────


def _format_date(date_iso: str | None) -> str:
    """공지 등록일 ISO 문자열 → `"YYYY-MM-DD HH:MM"` (KST). 파싱 실패는 우아하게 폴백.

    `...+09:00` / `...Z` / 초·밀리초 유무 혼재를 흡수. naive 는 KST 로 간주한다.
    """
    if not date_iso:
        return "날짜 미상"
    try:
        dt = datetime.fromisoformat(date_iso)
    except ValueError:
        return "날짜 미상"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return f"{dt.astimezone(KST):%Y-%m-%d %H:%M}"


def parse_notices(raw: Sequence[dict]) -> list[NoticeItem]:
    """raw 공지 목록 → 유효 항목만(`notice_id` int 필수), `notice_id` 오름차순 정렬.

    넥슨 응답은 최신순(date 내림차순)이지만, 발송은 오래된→최신 순이라 여기서 오름차순으로 뒤집는다.
    notice_id 누락/비정수 항목은 신규 판정 키가 없으므로 조용히 제외.
    """
    items: list[NoticeItem] = []
    for entry in raw:
        notice_id = entry.get("notice_id")
        if not isinstance(notice_id, int):
            continue
        items.append(
            NoticeItem(
                notice_id=notice_id,
                title=entry.get("title") or "",
                url=entry.get("url") or "",
                date_text=_format_date(entry.get("date")),
            )
        )
    items.sort(key=lambda item: item.notice_id)
    return items


def latest_id(items: Sequence[NoticeItem]) -> int | None:
    """목록의 최대 notice_id(baseline·마킹용). 빈 목록이면 None."""
    return items[-1].notice_id if items else None


def select_new(items: Sequence[NoticeItem], last_id: int | None) -> list[NoticeItem]:
    """`last_id` 초과 항목만 신규(오름차순 유지, 다건이면 전부 발송).

    `last_id is None` = 최초 가동(baseline) → 신규로 보지 않는다(빈 리스트). 호출자가 별도로
    `latest_id` 를 마킹해 다음 폴링부터 그 이후만 발송하게 한다(design §3.6 "과거 공지 미발송").
    """
    if last_id is None:
        return []
    return [item for item in items if item.notice_id > last_id]


# ── DB (전달-무관) ────────────────────────────────────────────────────────


async def get_last_notice_id(
    session_factory: async_sessionmaker[AsyncSession], category: str
) -> int | None:
    """카테고리의 마지막 발송 notice_id(notice_state). 미기록/파싱불가면 None(=baseline 신호)."""
    async with session_factory() as session:
        row = await session.get(NoticeState, category)
    if row is None or row.last_identifier is None:
        return None
    try:
        return int(row.last_identifier)
    except ValueError:
        return None


async def set_last_notice_id(
    session_factory: async_sessionmaker[AsyncSession], category: str, notice_id: int
) -> None:
    """카테고리의 마지막 발송 notice_id 마킹(notice_state upsert). 문자열로 저장(컬럼 String).

    `updated_at` 을 set_ 에 명시 — `onupdate=func.now()` 는 on_conflict_do_update 에 발동하지 않아
    명시하지 않으면 갱신 시 타임스탬프가 고정된다(mark_week_sent 와 동일 처리).
    """
    async with session_factory() as session:
        stmt = (
            pg_insert(NoticeState)
            .values(category=category, last_identifier=str(notice_id))
            .on_conflict_do_update(
                index_elements=["category"],
                set_={"last_identifier": str(notice_id), "updated_at": func.now()},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def enabled_notice_channels(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[tuple[int, int]]:
    """공지 알림이 켜진 (guild_id, channel_id) 목록(알림은 채널 단위, design §2)."""
    async with session_factory() as session:
        stmt = select(ChannelSettings.guild_id, ChannelSettings.channel_id).where(
            ChannelSettings.notice_alert.is_(True)
        )
        rows = (await session.execute(stmt)).all()
    return [(row.guild_id, row.channel_id) for row in rows]


async def set_notice_alert(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    channel_id: int,
    enabled: bool,
) -> None:
    """채널의 공지 알림 토글 upsert. `notice_alert` 만 set 해 `sunday_alert` 는 보존."""
    async with session_factory() as session:
        stmt = (
            pg_insert(ChannelSettings)
            .values(guild_id=guild_id, channel_id=channel_id, notice_alert=enabled)
            .on_conflict_do_update(
                index_elements=["guild_id", "channel_id"],
                set_={"notice_alert": enabled},
            )
        )
        await session.execute(stmt)
        await session.commit()
