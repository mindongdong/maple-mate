"""스타포스 이력 기간·페치·캐시·집계 (전달-무관). discord/http 타입 비의존.

- resolve_period: 프리셋/커스텀 → 날짜 목록(30일 상한 클램프·미래 컷). 순수.
- get_history_targets: 등록 레코드(개인 키 포함) 조회, 입력순서 보존.
- fetch_starforce_records: 날짜별 캐시 판정 → 미스 시 개인 키 호출 → upsert → 캐릭터 필터.
- aggregate_starforce: 아이템별 시작★→최종★ + 운지수·손익메소(레벨 매칭 성공分만).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..dependencies import Deps
from .cache import is_cache_fresh
from .equipment_level import EXCLUDED_ITEMS, MIN_AGGREGATE_LEVEL
from .expected_cost import actual_meso, expected_meso, meso_luck_percentile, net_meso
from .models import HistoryCache

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
CACHE_TYPE = "starforce"
MAX_PERIOD_DAYS = 365  # 상한 1년(API 롤링 ~2년 윈도우 내). 콜드 조회는 날짜당 1콜이라 느림 → 캐시 의존.

# history_cache 보존 일수 — **조회대상 날짜(date) 기준** 400일(스케일 튜닝 D4).
# fetched_at 기준 90일(deploy-plan 원안)은 기각: 과거 일자 데이터는 불변이라 지우면
# `최근1년` 재조회 시 그 유저 개인 키로 수백 콜이 재발생한다. 400일 = 기간 상한
# 1년(365일) + 여유 — 그보다 오래된 date 는 어떤 프리셋으로도 다시 조회되지 않는다.
HISTORY_CACHE_RETENTION_DAYS = 400


# ── 기간 분해 (순수) ───────────────────────────────────────────────────────

PRESETS = (
    "오늘",
    "어제",
    "최근7일",
    "최근30일",
    "최근90일",
    "최근1년",
    "이번주",
    "이번달",
)
DEFAULT_PRESET = "최근7일"


def _preset_range(preset: str, today: date) -> tuple[date, date]:
    """프리셋 → (시작일, 종료일) 모두 포함. 알 수 없는 프리셋은 기본(최근7일)."""
    if preset == "오늘":
        return today, today
    if preset == "어제":
        y = today - timedelta(days=1)
        return y, y
    if preset == "최근30일":
        return today - timedelta(days=29), today
    if preset == "최근90일":
        return today - timedelta(days=89), today
    if preset == "최근1년":
        return today - timedelta(days=364), today
    if preset == "이번주":  # 월요일 시작
        return today - timedelta(days=today.weekday()), today
    if preset == "이번달":
        return today.replace(day=1), today
    return today - timedelta(days=6), today  # 최근7일(기본)


def resolve_period(
    preset: str,
    start: date | None,
    end: date | None,
    today_kst: date,
) -> list[date]:
    """프리셋 또는 커스텀(start/end) → 날짜 목록(오름차순). 30일 상한·미래 컷.

    start/end 중 하나라도 주어지면 커스텀 모드(프리셋 무시). 미래일은 오늘로 컷,
    범위가 30일을 넘으면 최근 30일로 클램프(종료일 기준 뒤로 30일).
    """
    if start is not None or end is not None:
        e = end or today_kst
        s = start or e
        if s > e:
            s, e = e, s
    else:
        s, e = _preset_range(preset, today_kst)

    if e > today_kst:  # 미래 컷
        e = today_kst
    if s > e:
        s = e
    if (e - s).days > MAX_PERIOD_DAYS - 1:  # 최근 30일로 클램프
        s = e - timedelta(days=MAX_PERIOD_DAYS - 1)

    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


# ── 대상(개인 키 포함) ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class HistoryTarget:
    """이력류 대상 1명. 스펙류 Target 과 달리 개인 키 암호문을 포함한다."""

    guild_id: int
    discord_user_id: int
    nickname: str
    ocid: str
    api_key_encrypted: str | None


async def get_history_targets(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    user_ids: Sequence[int] | None = None,
) -> list[HistoryTarget]:
    """등록자(개인 키 포함) 조회. user_ids 지정 시 입력순서 보존.

    키 없는 등록자(api_key_encrypted is None)도 반환한다 — 호출자가 '키 미등록' 행으로 처리.
    """
    from ..registration.models import Registration

    async with session_factory() as session:
        stmt = select(Registration).where(Registration.guild_id == guild_id)
        if user_ids is not None:
            stmt = stmt.where(Registration.discord_user_id.in_(list(user_ids)))
        rows = (await session.execute(stmt)).scalars().all()

    targets = [
        HistoryTarget(
            guild_id=r.guild_id,
            discord_user_id=r.discord_user_id,
            nickname=r.maple_nickname,
            ocid=r.ocid,
            api_key_encrypted=r.api_key_encrypted,
        )
        for r in rows
    ]
    if user_ids is not None:
        order = {uid: i for i, uid in enumerate(user_ids)}
        targets.sort(key=lambda t: order.get(t.discord_user_id, len(order)))
    return targets


# ── 페치 + 캐시 + 캐릭터 필터 ──────────────────────────────────────────────


@dataclass(frozen=True)
class StarforceAttempt:
    """스타포스 강화 시도 1건(집계용 스냅샷)."""

    target_item: str
    before_star: int
    after_star: int
    result: str  # "성공"/"실패(유지)"/"실패(하락)"/"파괴"
    date_create: str  # ISO8601(KST)
    superior: bool = False  # 슈페리얼 장비 여부(확률·비용공식 상이 → /비틱 집계 제외)


def parse_attempts(records: Sequence[dict], nickname: str) -> list[StarforceAttempt]:
    """넥슨 starforce 레코드 → StarforceAttempt 목록. character_name==nickname 만(순수).

    개인 키는 계정 전체(부캐 포함)를 반환하므로 등록 캐릭터만 필터(집계 단위 = 등록 캐릭터).
    """
    attempts: list[StarforceAttempt] = []
    for r in records:
        if r.get("character_name") != nickname:
            continue
        # superior_item_flag 는 서술형 한글 문자열(실측, docs/api/history.md) —
        # "슈페리얼 장비 미해당"/"슈페리얼 장비 해당". '슈페리얼' 키워드 필수 +
        # '미해당' 제외로 판정: 미상 포맷(빈값·"0" 등)은 일반 장비로 폴백(과잉 제외 방지).
        flag = r.get("superior_item_flag") or ""
        attempts.append(
            StarforceAttempt(
                target_item=r.get("target_item", ""),
                before_star=int(r.get("before_starforce_count", 0)),
                after_star=int(r.get("after_starforce_count", 0)),
                result=r.get("item_upgrade_result", ""),
                date_create=r.get("date_create", ""),
                superior="슈페리얼" in flag and "미해당" not in flag,
            )
        )
    return attempts


async def _cached_records(
    session_factory: async_sessionmaker[AsyncSession],
    ocid: str,
    query_date: date,
    now: datetime,
) -> list[dict] | None:
    """캐시가 신선하면 그 날짜의 레코드 목록, 아니면 None."""
    async with session_factory() as session:
        row = await session.get(HistoryCache, (ocid, CACHE_TYPE, query_date))
    if row is None or not is_cache_fresh(query_date, row.fetched_at, now):
        return None
    page = row.payload.get(CACHE_TYPE) if isinstance(row.payload, dict) else None
    return page if isinstance(page, list) else []


async def _store_records(
    session_factory: async_sessionmaker[AsyncSession],
    ocid: str,
    query_date: date,
    records: list[dict],
    now: datetime,
) -> None:
    """history_cache upsert(원본 payload 래퍼, fetched_at 갱신)."""
    async with session_factory() as session:
        stmt = (
            pg_insert(HistoryCache)
            .values(
                ocid=ocid,
                type=CACHE_TYPE,
                date=query_date,
                payload={CACHE_TYPE: records},
                fetched_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ocid", "type", "date"],
                set_={"payload": {CACHE_TYPE: records}, "fetched_at": now},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def fetch_starforce_records(
    deps: Deps,
    target: HistoryTarget,
    dates: Sequence[date],
    *,
    now: datetime | None = None,
) -> list[StarforceAttempt]:
    """기간 내 등록 캐릭터의 스타포스 시도 목록. 날짜별 캐시 → 미스 시 개인 키 호출.

    target.api_key_encrypted 가 있어야 한다(호출자가 키 미등록 분리). 하드 실패는
    NexonAPIError 로 전파(명령 계층이 대상별 부분 성공 처리).
    """
    if target.api_key_encrypted is None:
        raise ValueError("개인 키 없는 대상은 호출 전 분리해야 합니다")
    now = now or datetime.now(timezone.utc)
    api_key = deps.cipher.decrypt(target.api_key_encrypted)

    records: list[dict] = []
    for query_date in dates:
        cached = await _cached_records(
            deps.session_factory, target.ocid, query_date, now
        )
        if cached is not None:
            records.extend(cached)
            continue
        page = await deps.nexon.starforce_history(api_key, query_date.isoformat())
        await _store_records(deps.session_factory, target.ocid, query_date, page, now)
        records.extend(page)

    return parse_attempts(records, target.nickname)


def history_cache_cutoff(now: datetime) -> date:
    """prune 기준일(오늘 KST − 400일). date 가 이 값 **미만**인 행이 삭제 대상(순수)."""
    return now.astimezone(KST).date() - timedelta(days=HISTORY_CACHE_RETENTION_DAYS)


async def prune_old_history_cache(
    session_factory: async_sessionmaker[AsyncSession], now: datetime
) -> int:
    """조회대상 날짜(date)가 400일 경과한 history_cache 행 단일 DELETE. 삭제 행수 반환.

    운영 요약 일일 잡(error_log prune)에 편승해 실행된다(scheduler.run_ops_summary_job).
    """
    cutoff = history_cache_cutoff(now)
    async with session_factory() as session:
        result = await session.execute(
            delete(HistoryCache).where(HistoryCache.date < cutoff)
        )
        await session.commit()
        return result.rowcount or 0


# ── 집계 (순수) ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StarforceSummary:
    """대상 1명의 스타포스 집계 결과.

    luck_score(메소 백분위)·메소(total/net/expected) 모두 레벨 매칭 시도 기준 — 손익과 일관.
    """

    luck_score: (
        float | None
    )  # 메소 행운 백분위(0~100, 높을수록 운 좋음=싸게 끝냄, ADR-0002)
    total_meso: int  # 총 사용 메소(매칭 시도 Σcost)
    net_meso: int  # 기댓값 대비 손익(total_meso − expected)
    expected: float  # 기댓값(매칭 시도 Σexpected_meso)
    matched_count: int  # 레벨 매칭된 시도 수
    total_count: (
        int  # 집계 대상 시도 수(매칭+미상). 제외분(EXCLUDED/100미만)은 분모에서도 뺀다.
    )
    unmatched_items: tuple[
        str, ...
    ]  # 레벨 미상으로 제외된 장비명(EXCLUDED/저레벨 제외분은 불포함)


def _sort_key(a: StarforceAttempt) -> tuple:
    """시간순 정렬 키. ISO 파싱 실패 시 원문 문자열로 폴백."""
    try:
        return (0, datetime.fromisoformat(a.date_create))
    except ValueError:
        return (1, a.date_create)


def aggregate_starforce(
    attempts: Sequence[StarforceAttempt],
    level_of: Callable[[str], int | None],
    *,
    excluded_items: frozenset[str] = EXCLUDED_ITEMS,
    min_level: int = MIN_AGGREGATE_LEVEL,
) -> StarforceSummary:
    """아이템별 시작★→최종★ 집계 → 운지수·손익메소(레벨 매칭 성공分만).

    레벨 매칭 아이템만 집계(운빨·메소 동일 기준): 아이템별 시작★=첫(시간순) before_star,
    최종★=기간 내 최고 after_star, expected += expected_meso(level, 시작★, 최종★),
    total_meso += Σcost(level, before_star). 미매칭(레벨 미상) 아이템은 unmatched_items 로 분리.
    운빨(luck_score) = 그 아이템들의 실제 총 메소가 가능 분포에서 차지하는 백분위(메소 기반).

    집계 제외(미상과 구분): excluded_items(특정 장비) · min_level 미만 레벨 장비는 통째로 빠진다 —
    총메소·기댓값·운빨은 물론 분모(total_count)·미상 제보에서도 제외(없던 셈).
    """
    by_item: dict[str, list[StarforceAttempt]] = {}
    for a in attempts:
        by_item.setdefault(a.target_item, []).append(a)

    total_meso = 0
    expected = 0.0
    matched_count = 0
    counted = 0  # 집계 대상(매칭+미상) 시도 수 — 제외분은 분모에서도 뺀다
    unmatched: list[str] = []
    luck_items: list[tuple[int, int, int, int]] = []  # (level, 시작★, 최종★, 실제메소)

    for item, item_attempts in by_item.items():
        if item in excluded_items:
            continue  # 명시적 제외 — 집계·분모·제보 모두 제외
        level = level_of(item)
        if level is not None and level < min_level:
            continue  # 저레벨(100 미만) 제외 — 위와 동일
        counted += len(item_attempts)
        if level is None:
            unmatched.append(item)
            continue
        ordered = sorted(item_attempts, key=_sort_key)
        start_star = ordered[0].before_star
        final_star = max(a.after_star for a in item_attempts)
        item_actual = actual_meso(level, [a.before_star for a in item_attempts])
        expected += expected_meso(level, start_star, final_star)
        total_meso += item_actual
        matched_count += len(item_attempts)
        luck_items.append((level, start_star, final_star, item_actual))

    return StarforceSummary(
        luck_score=meso_luck_percentile(luck_items),
        total_meso=total_meso,
        net_meso=net_meso(total_meso, expected),
        expected=expected,
        matched_count=matched_count,
        total_count=counted,
        unmatched_items=tuple(unmatched),
    )
