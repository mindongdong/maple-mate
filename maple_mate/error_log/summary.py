"""운영 요약 집계 + DB 조회/prune — 순수 도메인 (Phase 5, design §6).

discord import 금지. aggregate 는 외부 의존 없는 순수 함수(단위테스트 1급 대상).
분류 정책: 앱키(auth_invalid & discord_user_id IS NULL) / 미상(unmatched_equipment)
/ 헬스(그 외 전부, 예상 밖 타입 방어 포함). 친구 개인 키(auth_invalid & user 채워짐) 제외.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..nexon.client import KST  # timezone(+9), discord 비의존
from .models import ErrorLog

RETENTION_DAYS = 90
UNMATCHED_TOP_N = 10
_HEALTH_TYPES = ("nexon_api", "timeout", "rate_limit")


@dataclass(frozen=True)
class HealthEntry:
    error_type: str
    count: int
    by_command: tuple[tuple[str, int], ...]  # (command, 횟수) 내림차순
    recent_detail: str | None               # 가장 최근 행 detail(입력 순서 마지막)


@dataclass(frozen=True)
class OpsSummary:
    app_key_failures: int                   # auth_invalid AND discord_user_id IS NULL
    app_key_recent_detail: str | None
    unmatched: tuple[tuple[str, int], ...]  # (장비명, 횟수) 빈도 내림차순, 상위 N
    unmatched_kinds: int                    # distinct 종 수("외 N종" 계산용)
    health: tuple[HealthEntry, ...]         # 타입별, count 내림차순

    @property
    def is_empty(self) -> bool:
        return not (self.app_key_failures or self.unmatched or self.health)


def aggregate(rows: Sequence[ErrorLog]) -> OpsSummary:
    """전날 error_log 행 → 선별 집계(순수). 친구 개인 키 auth_invalid 는 버린다.

    입력 rows 는 timestamp 오름차순 정렬 보장 → last-wins 로 "최근" 판정(timestamp 비교 불필요).
    이 전제 덕에 타임존 없는 테스트용 ErrorLog 로도 동일하게 검증된다.
    """
    # 앱키
    app_key_count = 0
    app_key_recent_detail: str | None = None

    # 미상 장비: {장비명: 횟수}
    unmatched_counts: dict[str, int] = {}

    # 헬스: {error_type: {"count": int, "commands": {cmd_str: int}, "recent_detail": str|None}}
    health_data: dict[str, dict] = {}

    for row in rows:
        if row.error_type == "auth_invalid":
            if row.discord_user_id is None:
                # 봇 앱 키 실패 — 유지
                app_key_count += 1
                app_key_recent_detail = row.detail  # last-wins
            # 채워짐 = 친구 개인 키 — 제외(자가 발견)
        elif row.error_type == "unmatched_equipment":
            if row.detail is None:
                continue  # detail(장비명) 없으면 스킵
            unmatched_counts[row.detail] = unmatched_counts.get(row.detail, 0) + 1
        else:
            # 헬스: nexon_api/timeout/rate_limit + 예상 밖 타입 방어
            etype = row.error_type
            if etype not in health_data:
                health_data[etype] = {"count": 0, "commands": {}, "recent_detail": None}
            entry = health_data[etype]
            entry["count"] += 1
            # command None → "기타" 로 치환(by_command 타입이 str)
            cmd_key = row.command if row.command is not None else "기타"
            entry["commands"][cmd_key] = entry["commands"].get(cmd_key, 0) + 1
            entry["recent_detail"] = row.detail  # last-wins

    # 미상: distinct 종 수 계산 후 빈도 내림차순·동률이면 장비명 오름차순·상위 N
    unmatched_kinds = len(unmatched_counts)
    unmatched_sorted = sorted(
        unmatched_counts.items(),
        key=lambda x: (-x[1], x[0]),
    )[:UNMATCHED_TOP_N]

    # 헬스: 각 그룹 by_command 정렬(내림차순, 동률이면 command 오름차순)
    health_entries = []
    for etype, data in health_data.items():
        by_command = tuple(
            sorted(data["commands"].items(), key=lambda x: (-x[1], x[0]))
        )
        health_entries.append(
            HealthEntry(
                error_type=etype,
                count=data["count"],
                by_command=by_command,
                recent_detail=data["recent_detail"],
            )
        )
    # 헬스 그룹: count 내림차순, 동률이면 error_type 오름차순
    health_entries.sort(key=lambda e: (-e.count, e.error_type))

    return OpsSummary(
        app_key_failures=app_key_count,
        app_key_recent_detail=app_key_recent_detail,
        unmatched=tuple(unmatched_sorted),
        unmatched_kinds=unmatched_kinds,
        health=tuple(health_entries),
    )


async def fetch_yesterday_errors(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> list[ErrorLog]:
    """전날(KST 00:00~24:00) 행 조회. timestamp 오름차순 정렬 반환(aggregate last-wins 전제)."""
    now_kst = now.astimezone(KST)
    today0 = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = today0 - timedelta(days=1), today0
    async with session_factory() as session:
        stmt = (
            select(ErrorLog)
            .where(ErrorLog.timestamp >= start, ErrorLog.timestamp < end)
            .order_by(ErrorLog.timestamp)
        )
        return list((await session.execute(stmt)).scalars().all())


async def prune_old_errors(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> int:
    """RETENTION_DAYS 경과 행 단일 DELETE. 삭제 행수 반환(앱로그용)."""
    cutoff = now.astimezone(KST) - timedelta(days=RETENTION_DAYS)
    async with session_factory() as session:
        result = await session.execute(
            delete(ErrorLog).where(ErrorLog.timestamp < cutoff)
        )
        await session.commit()
        return result.rowcount or 0
