"""경험치 리더보드 페치·집계·prune·백필 (전달-무관). discord/apscheduler 비의존.

- fetch_and_store: 대상별 ranking_overall(ocid, D-1) → 스냅샷 upsert(미등재/미준비는 스킵).
- backfill: 첫 실행 시 과거 ~8일 선적재(이미 있으면 건너뜀).
- build_rows: 순수 — total_exp 내림차순 정렬·순위 부여·어제 Δ 계산·미등재 제외 카운트.
- history_deltas: 그래프용 유저별 7일 Δ 시계열(전달-무관).
- prune_old_snapshots: snapshot_date 가 90일 경과한 행 삭제(09:00 운영 잡 편승).

스냅샷 키 = (guild_id, discord_user_id, snapshot_date). Δ = 어제(D-1) − 그제(D-2) = 어제 하루 획득:
이전 스냅샷 없으면 None('—'), 음수(데이터 보정 등)는 0/None 클램프(작업지시서 파생 결정).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..dependencies import Deps
from ..error_log import service as error_log
from ..nexon.errors import NexonAPIError, to_error_log_type
from ..registration.service import Target
from .models import ExpSnapshot

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 백필 일수(작업지시서 Q11) — 첫 실행 1회 과거 ~8일 선적재.
BACKFILL_DAYS = 8
# 그래프 시계열 일수(작업지시서 Q5·Q12) — 최근 7일 일일 Δ.
HISTORY_DAYS = 7
# 스냅샷 보존 일수(작업지시서 Q12) — 09:00 운영 잡에 편승해 prune.
RETENTION_DAYS = 90


@dataclass(frozen=True)
class LeaderRow:
    """순위표 1행(전달 계층이 표로 렌더). total_exp(정렬키)는 비노출이라 DTO 에 없음(Q2).

    exp_rate 는 레벨 내 경험치 백분율(있을 때만 'Lv.287 (45.2%)'). ranking/overall(주 소스)엔
    비율이 없어 character/basic 으로 best-effort 보강하며, 그 호출이 실패하면 None('Lv.287').
    delta=어제 하루 획득(이전 스냅샷 없으면 None='—'). world_rank=전체 서버 순위(#).
    """

    rank: int
    nickname: str
    level: int
    exp_rate: float | None
    delta: int | None
    world_rank: int | None


def yesterday_kst(now: datetime) -> date:
    """발송 기준일 D-1(KST). 누적은 D-1 마감값(작업지시서 기준일 라벨)."""
    return now.astimezone(KST).date() - timedelta(days=1)


def snapshot_cutoff(now: datetime) -> date:
    """prune 기준일(오늘 KST − 90일). snapshot_date 가 이 값 **미만**인 행이 삭제 대상(순수)."""
    return now.astimezone(KST).date() - timedelta(days=RETENTION_DAYS)


# ── 페치·적재 (전달-무관) ───────────────────────────────────────────────────


async def _upsert_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    discord_user_id: int,
    snapshot_date: date,
    entry: dict,
    exp_rate: float | None,
) -> None:
    """ranking_overall 응답 1건 → (guild, user, date) 스냅샷 upsert(재실행 시 최신값 덮어씀).

    exp_rate 는 character/basic best-effort 보강값(실패 시 None) — 함께 저장한다.
    """
    async with session_factory() as session:
        stmt = (
            pg_insert(ExpSnapshot)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                snapshot_date=snapshot_date,
                character_level=int(entry.get("character_level") or 0),
                total_exp=int(entry.get("character_exp") or 0),
                world_rank=entry.get("ranking"),
                exp_rate=exp_rate,
            )
            .on_conflict_do_update(
                index_elements=["guild_id", "discord_user_id", "snapshot_date"],
                set_={
                    "character_level": int(entry.get("character_level") or 0),
                    "total_exp": int(entry.get("character_exp") or 0),
                    "world_rank": entry.get("ranking"),
                    "exp_rate": exp_rate,
                },
            )
        )
        await session.execute(stmt)
        await session.commit()


async def _fetch_exp_rate(deps: Deps, ocid: str, date_iso: str) -> float | None:
    """character/basic best-effort 보강: character_exp_rate("45.23") → 45.23. 실패 시 None.

    주 소스(ranking/overall)는 이미 성공한 상태라 이 호출은 순수 보강이다 — DATA_NOT_READY(00009)
    포함 어떤 NexonAPIError 든, 파싱 실패든 모두 삼키고 None(error_log 적재·캐릭 제외 안 함).
    """
    try:
        basic = await deps.nexon.character_basic(ocid, date_iso)
    except NexonAPIError as exc:
        log.debug(
            "character/basic best-effort 실패(exp_rate 생략) ocid=%s: %s", ocid, exc
        )
        return None
    raw = basic.get("character_exp_rate")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        log.debug(
            "character_exp_rate 파싱 실패(exp_rate 생략) ocid=%s raw=%r", ocid, raw
        )
        return None


async def _fetch_one_day(deps: Deps, target: Target, snapshot_date: date) -> bool:
    """대상 1명의 1일치 조회→upsert. 미등재/미준비는 False(스킵), 적재 성공은 True.

    주 소스 ranking/overall 성공 후 character/basic 을 best-effort 로 호출해 exp_rate 보강.
    넥슨 장애(타임아웃·429·5xx)·앱키 실패만 error_log.record(작업지시서 readiness 가드).
    """
    date_iso = snapshot_date.isoformat()
    try:
        entry = await deps.nexon.ranking_overall(target.ocid, date_iso)
    except NexonAPIError as exc:
        log_type = to_error_log_type(exc.error_class)
        if (
            log_type is not None
        ):  # 넥슨 가용성·앱키 실패만 적재(미준비/잘못된 닉은 제외)
            await error_log.record(
                deps.session_factory,
                error_type=log_type,
                command="경험치",
                guild_id=target.guild_id,
                discord_user_id=target.discord_user_id,
                target_ocid=target.ocid,
                detail=f"{date_iso} {exc.code}: {exc.message}"[:500],
            )
        return False
    if entry is None:  # 빈 ranking = 미등재/미준비 → 그날 그 캐릭 제외(에러 아님)
        return False
    exp_rate = await _fetch_exp_rate(deps, target.ocid, date_iso)
    await _upsert_snapshot(
        deps.session_factory,
        guild_id=target.guild_id,
        discord_user_id=target.discord_user_id,
        snapshot_date=snapshot_date,
        entry=entry,
        exp_rate=exp_rate,
    )
    return True


async def fetch_and_store(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    date_iso: str,
) -> int:
    """대상 전원의 date 스냅샷 조회→upsert. 미등재/미준비로 건너뛴 대상 수(스킵 카운트) 반환."""
    snapshot_date = date.fromisoformat(date_iso)
    skipped = 0
    for target in targets:
        stored = await _fetch_one_day(deps, target, snapshot_date)
        if not stored:
            skipped += 1
    return skipped


async def _existing_dates(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    dates: Sequence[date],
) -> set[date]:
    """대상 1명에 대해 주어진 날짜들 중 이미 적재된 snapshot_date 집합(백필 중복 콜 방지)."""
    async with session_factory() as session:
        stmt = select(ExpSnapshot.snapshot_date).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.discord_user_id == discord_user_id,
            ExpSnapshot.snapshot_date.in_(list(dates)),
        )
        rows = (await session.execute(stmt)).scalars().all()
    return set(rows)


async def backfill(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    days: int = BACKFILL_DAYS,
) -> None:
    """첫 실행 1회: 과거 D-1~D-`days` 를 대상별로 선적재(이미 있으면 건너뜀, 작업지시서 Q11).

    그래프 첫날부터 데이터가 채워지도록 한다. 미등재/미준비·넥슨 장애는 _fetch_one_day 가 처리.
    """
    today = datetime.now(KST).date()
    dates = [today - timedelta(days=d) for d in range(1, days + 1)]
    for target in targets:
        existing = await _existing_dates(
            deps.session_factory, target.guild_id, target.discord_user_id, dates
        )
        for snapshot_date in dates:
            if snapshot_date in existing:
                continue
            await _fetch_one_day(deps, target, snapshot_date)


# ── 조회 + 순수 집계 ────────────────────────────────────────────────────────


async def has_snapshots(
    session_factory: async_sessionmaker[AsyncSession], guild_id: int
) -> bool:
    """길드에 스냅샷이 하나라도 있는지(첫 실행 백필 게이트, 작업지시서 Q11)."""
    async with session_factory() as session:
        stmt = select(ExpSnapshot.snapshot_date).where(ExpSnapshot.guild_id == guild_id)
        return (await session.execute(stmt.limit(1))).first() is not None


async def snapshots_on(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    snapshot_date: date,
) -> list[ExpSnapshot]:
    """길드의 특정 일자 스냅샷 전부(순서 무관 — build_rows 가 정렬)."""
    async with session_factory() as session:
        stmt = select(ExpSnapshot).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.snapshot_date == snapshot_date,
        )
        return list((await session.execute(stmt)).scalars().all())


def build_rows(
    today_snaps: Sequence[ExpSnapshot],
    prev_snaps: Sequence[ExpSnapshot],
    *,
    nicknames: dict[int, str],
) -> tuple[list[LeaderRow], int]:
    """순수: 오늘 스냅샷을 total_exp 내림차순 정렬·순위 부여·어제 Δ 계산. (행, 미등재수) 반환.

    미등재 제외 카운트 = nicknames(등록자 전원) 중 today_snaps 에 없는 인원 수. Δ=오늘−어제
    (어제 스냅샷 없으면 None='—', 음수는 None 클램프). 닉은 nicknames 로 해석(스냅샷에 닉 없음).
    """
    prev_exp = {s.discord_user_id: s.total_exp for s in prev_snaps}
    ordered = sorted(today_snaps, key=lambda s: s.total_exp, reverse=True)
    rows: list[LeaderRow] = []
    for rank, snap in enumerate(ordered, start=1):
        prior = prev_exp.get(snap.discord_user_id)
        delta: int | None
        if prior is None:
            delta = None  # 이전 스냅샷 없음 → '—'
        else:
            diff = snap.total_exp - prior
            delta = diff if diff > 0 else None  # 음수/0 은 None 클램프(획득 없음/보정)
        rows.append(
            LeaderRow(
                rank=rank,
                nickname=nicknames.get(snap.discord_user_id, "?"),
                level=snap.character_level,
                exp_rate=snap.exp_rate,  # character/basic best-effort 보강(없으면 None)
                delta=delta,
                world_rank=snap.world_rank,
            )
        )
    ranked_ids = {s.discord_user_id for s in today_snaps}
    excluded = sum(1 for uid in nicknames if uid not in ranked_ids)
    return rows, excluded


async def history_deltas(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    nicknames: dict[int, str],
    today: date,
    *,
    days: int = HISTORY_DAYS,
) -> dict[str, list[tuple[date, int | None]]]:
    """그래프용 유저별 최근 `days`일 일일 Δ 시계열(닉 → [(날짜, Δ|None), ...]).

    `today` = 기준일(D-1, '어제')이고 그래프 오른쪽 끝. 표시 구간은 `today-(days-1)..today`
    (어제를 포함한 최근 7일). 각 표시일 d 의 Δ = total_exp(d) − total_exp(d-1)(이전일 스냅샷
    없으면 None). Δ 계산을 위해 가장 이른 표시일의 직전일까지 한 칸 더 읽는다. 등록자(nicknames)
    전원을 키로 내며, 스냅샷이 없는 날은 None(빈 데이터·첫날 그래프 가드).
    """
    display_dates = [today - timedelta(days=d) for d in range(days - 1, -1, -1)]
    first = display_dates[0] - timedelta(days=1)  # Δ 계산용 직전일
    async with session_factory() as session:
        stmt = select(
            ExpSnapshot.discord_user_id,
            ExpSnapshot.snapshot_date,
            ExpSnapshot.total_exp,
        ).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.snapshot_date >= first,
            ExpSnapshot.snapshot_date <= display_dates[-1],
        )
        rows = (await session.execute(stmt)).all()

    by_user: dict[int, dict[date, int]] = {}
    for uid, snap_date, total in rows:
        by_user.setdefault(uid, {})[snap_date] = total

    series: dict[str, list[tuple[date, int | None]]] = {}
    for uid, nickname in nicknames.items():
        exp_by_date = by_user.get(uid, {})
        points: list[tuple[date, int | None]] = []
        for d in display_dates:
            today_exp = exp_by_date.get(d)
            prev_exp = exp_by_date.get(d - timedelta(days=1))
            if today_exp is None or prev_exp is None:
                points.append((d, None))
            else:
                diff = today_exp - prev_exp
                points.append((d, diff if diff > 0 else 0))
        series[nickname] = points
    return series


# ── prune (09:00 운영 잡 편승) ───────────────────────────────────────────────


async def prune_old_snapshots(
    session_factory: async_sessionmaker[AsyncSession],
    now: datetime,
    days: int = RETENTION_DAYS,
) -> int:
    """snapshot_date 가 90일 경과한 exp_snapshot 행 단일 DELETE. 삭제 행수 반환(작업지시서 Q12)."""
    cutoff = now.astimezone(KST).date() - timedelta(days=days)
    async with session_factory() as session:
        result = await session.execute(
            delete(ExpSnapshot).where(ExpSnapshot.snapshot_date < cutoff)
        )
        await session.commit()
        return result.rowcount or 0
