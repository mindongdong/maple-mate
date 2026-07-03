"""스타포스 이력 기간·페치·캐시·집계 (전달-무관). discord/http 타입 비의존.

- resolve_period: 프리셋/커스텀 → 날짜 목록(30일 상한 클램프·미래 컷). 순수.
- get_history_targets: 유저별 1대상(개인 키 + 대표 닉 + 캐시 앵커 ocid), 입력순서 보존.
- fetch_starforce_records: 날짜별 캐시 판정 → 미스 시 개인 키 호출 → upsert → 계정 전체 파싱.
- aggregate_starforce: (캐릭터, 아이템)별 시작★→최종★ + 운지수·손익메소(레벨 매칭 성공分만).
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
from .expected_cost import (
    ClimbItem,
    actual_paid_meso,
    expected_meso,
    meso_luck_percentile,
    net_meso,
)
from .models import HistoryCache
from .starforce_data import parse_event_range

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
    """이력류 대상 1명(계정 단위). 스펙류 Target 과 달리 개인 키 암호문을 포함한다.

    nickname = 표시용 대표 닉(이력은 계정 전체 합산이라 헤더 라벨용). ocid = **안정적 캐시 앵커**
    (최초 등록 = min(created_at) 캐릭터의 ocid) — 닉변경/대표변경에도 캐시 키가 흔들리지 않는다.
    """

    guild_id: int
    discord_user_id: int
    nickname: str
    ocid: str
    api_key_encrypted: str | None
    level: int | None = None  # 대표 레벨 — 무인자 상한 선정 기준(ADR-0008)


async def get_history_targets(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    user_ids: Sequence[int] | None = None,
) -> list[HistoryTarget]:
    """등록자(개인 키 포함) 조회 — 유저별 1대상(계정 단위). user_ids 지정 시 입력순서 보존.

    nickname = 대표 닉(표시용), ocid = 캐시 앵커(최초 등록 캐릭터). 키 없는 등록자도 반환한다
    (호출자가 '키 미등록' 행으로 처리). 캐릭터 0개 등록(키만)은 표시 불가라 제외한다.
    """
    from ..registration.models import Character, Registration
    from ..registration.service import pick_representative

    async with session_factory() as session:
        reg_stmt = select(Registration).where(Registration.guild_id == guild_id)
        char_stmt = select(Character).where(Character.guild_id == guild_id)
        if user_ids is not None:
            ids = list(user_ids)
            reg_stmt = reg_stmt.where(Registration.discord_user_id.in_(ids))
            char_stmt = char_stmt.where(Character.discord_user_id.in_(ids))
        regs = (await session.execute(reg_stmt)).scalars().all()
        chars = (await session.execute(char_stmt)).scalars().all()

    by_user: dict[int, list[Character]] = {}
    for c in chars:
        by_user.setdefault(c.discord_user_id, []).append(c)

    targets: list[HistoryTarget] = []
    for reg in regs:
        clist = by_user.get(reg.discord_user_id)
        if not clist:
            continue  # 캐릭터 없는 등록(키만) → 표시 불가
        rep = pick_representative(clist, reg.representative_ocid)
        anchor = min(clist, key=lambda c: (c.created_at, c.ocid))  # 안정 캐시 앵커
        targets.append(
            HistoryTarget(
                guild_id=reg.guild_id,
                discord_user_id=reg.discord_user_id,
                nickname=rep.maple_nickname
                if rep is not None
                else anchor.maple_nickname,
                ocid=anchor.ocid,
                api_key_encrypted=reg.api_key_encrypted,
                level=rep.level if rep is not None else anchor.level,
            )
        )
    if user_ids is not None:
        order = {uid: i for i, uid in enumerate(user_ids)}
        targets.sort(key=lambda t: order.get(t.discord_user_id, len(order)))
    return targets


# ── 페치 + 캐시 + 캐릭터 필터 ──────────────────────────────────────────────


@dataclass(frozen=True)
class StarforceAttempt:
    """스타포스 강화 시도 1건(집계용 스냅샷). character_name 으로 계정 내 캐릭터를 구분한다."""

    target_item: str
    before_star: int
    after_star: int
    result: str  # "성공"/"실패(유지)"/"실패(하락)"/"파괴"
    date_create: str  # ISO8601(KST)
    character_name: str = ""  # 계정 전체화 — 동명 장비를 캐릭터별로 분리(집계 그룹 키)
    superior: bool = False  # 슈페리얼 장비 여부(확률·비용공식 상이 → /비틱 집계 제외)
    world_name: str = (
        ""  # realm 신호(ADR-0009) — 파싱만 보존(/스타포스 realm 필터는 ADR-0015로 제거)
    )
    # 이벤트 보정(ADR-0016) — 이 시도의 before_star 가 이벤트 적용 범위에 들었는지(파싱 시 확정).
    destroy_reduced: bool = False  # 파괴확률 감소 이벤트 적용 시도
    cost_discount: bool = False  # 강화비용 할인 이벤트 적용 시도


def _attempt_events(event_list: object, before_star: int) -> tuple[bool, bool]:
    """starforce_event_list + before_star → (파괴감소 적용?, 비용할인 적용?).

    실측: event_list 는 성공률/파괴감소/비용할인이 각각 별 객체로 분리되며, 각 객체의
    starforce_event_range 가 적용 성수를 명시한다(docs/api/history.md). 이 시도의 before_star 가
    그 객체 범위에 들고 해당 rate 가 있으면 적용으로 본다. 비배열·비dict·범위 미상은 미적용 폴백.
    """
    if not isinstance(event_list, list):
        return False, False
    destroy = discount = False
    for ev in event_list:
        if not isinstance(ev, dict):
            continue
        if before_star not in parse_event_range(ev.get("starforce_event_range")):
            continue
        if ev.get("destroy_decrease_rate"):
            destroy = True
        if ev.get("cost_discount_rate"):
            discount = True
    return destroy, discount


def parse_attempts(records: Sequence[dict]) -> list[StarforceAttempt]:
    """넥슨 starforce 레코드 → StarforceAttempt 목록(계정 전체, 순수).

    개인 키는 계정 전체(부캐 포함)를 반환한다. 이력류는 계정 전체 합산이므로 닉 필터를 하지 않고
    character_name 을 보존한다(집계는 (character_name, target_item) 그룹핑, /비틱만 대표 닉 필터).
    """
    attempts: list[StarforceAttempt] = []
    for r in records:
        # superior_item_flag 는 서술형 한글 문자열(실측, docs/api/history.md) —
        # "슈페리얼 장비 미해당"/"슈페리얼 장비 해당". '슈페리얼' 키워드 필수 +
        # '미해당' 제외로 판정: 미상 포맷(빈값·"0" 등)은 일반 장비로 폴백(과잉 제외 방지).
        flag = r.get("superior_item_flag") or ""
        before_star = int(r.get("before_starforce_count", 0))
        destroy_reduced, cost_discount = _attempt_events(
            r.get("starforce_event_list"), before_star
        )
        attempts.append(
            StarforceAttempt(
                target_item=r.get("target_item", ""),
                before_star=before_star,
                after_star=int(r.get("after_starforce_count", 0)),
                result=r.get("item_upgrade_result", ""),
                date_create=r.get("date_create", ""),
                character_name=r.get("character_name", ""),
                superior="슈페리얼" in flag and "미해당" not in flag,
                world_name=r.get("world_name", ""),
                destroy_reduced=destroy_reduced,
                cost_discount=cost_discount,
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

    return parse_attempts(records)  # 계정 전체(닉 필터 없음)


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

# 10성 이상 시도만 집계한다(ADR-0016, 개정으로 11→10). before_star 는 강화 시작 성수라
# before_star≥10 = "10→11 강화부터 포함"(9→10 제외) — 사용자 선호. 저성 잡음·레벨 미상
# 장비(전수 ≤7성)는 여전히 제외. 10성 floor 에서도 파괴 바닥 12성·파괴→12 복귀가 모두 ≥10 이라
# 등반이 자기완결한다. (10성엔 1+1 이벤트가 드물게 섞일 수 있으나 미모델 — 영향 경미.)
MIN_AGGREGATE_STAR = 10


@dataclass(frozen=True)
class StarforceSummary:
    """대상 1명의 스타포스 집계 결과.

    luck_score(메소 백분위)·메소(total/net/expected) 모두 10성 이상 레벨 매칭 시도 기준 — 손익과 일관.
    이벤트 보정(ADR-0016): 기대·분포는 강화 당시 이벤트 조건, total_meso 는 실지불(할인 반영).
    """

    luck_score: (
        float | None
    )  # 메소 행운 백분위(0~100, 높을수록 운 좋음=싸게 끝냄, ADR-0002·0016)
    total_meso: int  # 총 사용 메소(매칭 시도 Σ실지불, 할인 반영)
    net_meso: (
        int  # 기댓값 대비 손익(total_meso − expected, 둘 다 이벤트 조건 → 할인 중립)
    )
    expected: float  # 기댓값(매칭 시도 Σexpected_meso, 이벤트 보정)
    matched_count: int  # 10성+ 레벨 매칭된 시도 수
    total_count: int  # 집계 대상 시도 수(매칭+미상). 10성 필터로 미상 거의 소멸 → 보통 matched 와 동일.
    unmatched_items: tuple[
        str, ...
    ]  # 레벨 미상으로 제외된 10성+ 장비명(EXCLUDED/저레벨/저성 제외분은 불포함)


def _sort_key(a: StarforceAttempt) -> tuple:
    """시간순 정렬 키. ISO 파싱 실패 시 원문 문자열로 폴백."""
    try:
        return (0, datetime.fromisoformat(a.date_create))
    except ValueError:
        return (1, a.date_create)


def _event_masks(
    item_attempts: Sequence[StarforceAttempt],
) -> tuple[frozenset[int], frozenset[int]]:
    """아이템 시도 묶음 → (destroy_stars, discount_stars). 성수별 과반 투표(ADR-0016 §3-3).

    성수 s의 before_star=s 시도 중 과반이 이벤트 보유면 그 성수를 마스크에 넣는다. 동률은 True
    (이벤트 인정=보수적 — 이벤트를 무시하면 기대가 부풀어 거짓 '운 좋음'이 되므로 인정 쪽으로).
    카운터팩추얼 재등반(시뮬·기대)의 성수별 조건 가정에만 쓰인다(실지불은 각 시도 실제 플래그).
    """
    destroy_total: dict[int, int] = {}
    destroy_on: dict[int, int] = {}
    discount_total: dict[int, int] = {}
    discount_on: dict[int, int] = {}
    for a in item_attempts:
        s = a.before_star
        destroy_total[s] = destroy_total.get(s, 0) + 1
        discount_total[s] = discount_total.get(s, 0) + 1
        if a.destroy_reduced:
            destroy_on[s] = destroy_on.get(s, 0) + 1
        if a.cost_discount:
            discount_on[s] = discount_on.get(s, 0) + 1
    destroy_stars = frozenset(
        s for s, total in destroy_total.items() if destroy_on.get(s, 0) * 2 >= total
    )
    discount_stars = frozenset(
        s for s, total in discount_total.items() if discount_on.get(s, 0) * 2 >= total
    )
    return destroy_stars, discount_stars


def aggregate_starforce(
    attempts: Sequence[StarforceAttempt],
    level_of: Callable[[str], int | None],
    *,
    excluded_items: frozenset[str] = EXCLUDED_ITEMS,
    min_level: int = MIN_AGGREGATE_LEVEL,
    min_star: int = MIN_AGGREGATE_STAR,
) -> StarforceSummary:
    """아이템별 시작★→최종★ 집계 → 운빨·손익메소(10성+ 레벨 매칭 시도, 이벤트 보정).

    먼저 10성 미만 시도를 통째로 거른다(min_star, ADR-0016). 남은 레벨 매칭 아이템만 집계:
    시작★=첫(시간순) before_star, 최종★=기간 내 최고 after_star, 아이템별 성수 이벤트 마스크로
    expected += expected_meso(이벤트 보정), total_meso += Σ실지불(할인 반영). 미매칭(레벨 미상)
    아이템은 unmatched_items 로 분리. 운빨(luck_score) = 실지불 총합이 같은 이벤트 조건 분포에서
    차지하는 백분위(메소 기반).

    계정 전체화: 그룹 키 = (character_name, target_item). 동명 장비를 캐릭터별로 분리해
    서로 다른 캐릭터의 같은 이름 장비가 한 묶음으로 합쳐지는 버그를 막는다.

    집계 제외(미상과 구분): 10성 미만 시도 · excluded_items(특정 장비) · min_level 미만 레벨 장비는
    통째로 빠진다 — 총메소·기댓값·운빨은 물론 분모(total_count)·미상 제보에서도 제외(없던 셈).
    """
    attempts = [a for a in attempts if a.before_star >= min_star]  # 10성+ 필터(최우선)

    by_group: dict[tuple[str, str], list[StarforceAttempt]] = {}
    for a in attempts:
        by_group.setdefault((a.character_name, a.target_item), []).append(a)

    total_meso = 0.0
    expected = 0.0
    matched_count = 0
    counted = 0  # 집계 대상(매칭+미상) 시도 수 — 제외분은 분모에서도 뺀다
    unmatched: list[str] = []
    luck_items: list[ClimbItem] = []

    for (_char_name, item), item_attempts in by_group.items():
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
        destroy_stars, discount_stars = _event_masks(item_attempts)
        item_actual = actual_paid_meso(
            level, [(a.before_star, a.cost_discount) for a in item_attempts]
        )
        expected += expected_meso(
            level, start_star, final_star, destroy_stars, discount_stars
        )
        total_meso += item_actual
        matched_count += len(item_attempts)
        luck_items.append(
            ClimbItem(
                level,
                start_star,
                final_star,
                item_actual,
                destroy_stars,
                discount_stars,
            )
        )

    return StarforceSummary(
        luck_score=meso_luck_percentile(luck_items),
        total_meso=round(total_meso),
        net_meso=net_meso(total_meso, expected),
        expected=expected,
        matched_count=matched_count,
        total_count=counted,
        unmatched_items=tuple(unmatched),
    )
