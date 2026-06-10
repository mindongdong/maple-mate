"""잠재(큐브+메소재설정) 이력 페치·캐시·집계 (전달-무관). discord/http 타입 비의존.

스타포스(service.py)와 쌍둥이 구조이나 두 가지가 다르다(potential-handoff.md "핵심 차이"):
  - 레벨 매칭 불필요 — 레코드에 `item_level` 이 직접 있음(equipment_level·unmatched 제보 없음).
  - 두 엔드포인트 합산 — `history/cube` + `history/potential` 둘 다 페치(캐시 type 둘).

집계는 순수함수 `aggregate_potential`:
  - 사용 큐브/재설정 횟수.
  - 등업: cube+reset 합쳐 `result == "성공"` 인 레코드를 from-등급별 카운트(레전드리·미상 from 제외).
    from-등급 = before 잠재옵션 최고 등급(= before_potential_option[0].grade, 배열은 등급 내림차순).
    ⚠️ "성공"=등급 상승 가정은 G1 미니스파이크 전엔 미검증(potential-handoff.md). 레전드리(종착)
       from 은 버킷에서 빠지므로 엔드게임 메소 재설정의 동급 재롤은 자연히 등업에서 제외된다.
  - 메소: meso_cost(단가표, G2) 주입 시만 합산. 미주입이면 None('사용 메소' 컬럼 숨김, D3).
  - 단일 대상 보조: 큐브종류 분포·등급별 재설정 횟수(잠재/에디).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..dependencies import Deps
from .cache import is_cache_fresh
from .models import HistoryCache

# 기간·대상은 스타포스와 공유(재사용 — 새로 만들지 않는다).
from .service import (  # noqa: F401  (재노출: 명령 계층이 이 모듈에서 import)
    DEFAULT_PRESET,
    HistoryTarget,
    get_history_targets,
    resolve_period,
)

log = logging.getLogger(__name__)

CUBE_TYPE = "cube"
RESET_TYPE = "potential_reset"

# 잠재 등급 순서(낮음→높음). 등업 from-버킷·정렬에 사용.
GRADE_ORDER = {"레어": 1, "에픽": 2, "유니크": 3, "레전드리": 4}
# 등업 from-등급으로 가능한 등급(레전드리는 종착 — from 이 될 수 없음).
TIERUP_FROM_GRADES = ("레어", "에픽", "유니크")


# ── 파싱 dataclass (frozen, 순수) ──────────────────────────────────────────


@dataclass(frozen=True)
class CubeRecord:
    """큐브 사용 1건(집계용 스냅샷). before/after 는 잠재옵션 등급 목록(등급 내림차순)."""

    cube_type: str
    item_level: int
    item_part: str
    target_item: str
    result: str  # "성공"/"실패"
    pot_grade: str  # potential_option_grade(잠재)
    add_grade: str  # additional_potential_option_grade(에디)
    before_pot: tuple[str, ...]
    after_pot: tuple[str, ...]
    before_add: tuple[str, ...]
    after_add: tuple[str, ...]
    date_create: str


@dataclass(frozen=True)
class ResetRecord:
    """메소 잠재 재설정 1건. 큐브와 거의 동일하나 cube_type 대신 potential_type."""

    potential_type: str  # "잠재능력"/"에디셔널 잠재능력"
    item_level: int
    item_part: str
    target_item: str
    result: str
    pot_grade: str
    add_grade: str
    before_pot: tuple[str, ...]
    after_pot: tuple[str, ...]
    before_add: tuple[str, ...]
    after_add: tuple[str, ...]
    date_create: str


def _grades(options: object) -> tuple[str, ...]:
    """넥슨 옵션 배열 → 등급 문자열 튜플. 이상치(비-dict/비-list)는 건너뜀."""
    if not isinstance(options, list):
        return ()
    return tuple(o.get("grade", "") for o in options if isinstance(o, dict))


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0


def parse_cube_records(records: Sequence[dict], nickname: str) -> list[CubeRecord]:
    """넥슨 cube 레코드 → CubeRecord 목록. character_name==nickname 만(집계 단위=등록 캐릭터)."""
    out: list[CubeRecord] = []
    for r in records:
        if r.get("character_name") != nickname:
            continue
        out.append(
            CubeRecord(
                cube_type=r.get("cube_type", ""),
                item_level=_int(r.get("item_level")),
                item_part=r.get("item_equipment_part", ""),
                target_item=r.get("target_item", ""),
                result=r.get("item_upgrade_result", ""),
                pot_grade=r.get("potential_option_grade", ""),
                add_grade=r.get("additional_potential_option_grade", ""),
                before_pot=_grades(r.get("before_potential_option")),
                after_pot=_grades(r.get("after_potential_option")),
                before_add=_grades(r.get("before_additional_potential_option")),
                after_add=_grades(r.get("after_additional_potential_option")),
                date_create=r.get("date_create", ""),
            )
        )
    return out


def parse_reset_records(records: Sequence[dict], nickname: str) -> list[ResetRecord]:
    """넥슨 potential 레코드 → ResetRecord 목록. character_name==nickname 만."""
    out: list[ResetRecord] = []
    for r in records:
        if r.get("character_name") != nickname:
            continue
        out.append(
            ResetRecord(
                potential_type=r.get("potential_type", ""),
                item_level=_int(r.get("item_level")),
                item_part=r.get("item_equipment_part", ""),
                target_item=r.get("target_item", ""),
                result=r.get("item_upgrade_result", ""),
                pot_grade=r.get("potential_option_grade", ""),
                add_grade=r.get("additional_potential_option_grade", ""),
                before_pot=_grades(r.get("before_potential_option")),
                after_pot=_grades(r.get("after_potential_option")),
                before_add=_grades(r.get("before_additional_potential_option")),
                after_add=_grades(r.get("after_additional_potential_option")),
                date_create=r.get("date_create", ""),
            )
        )
    return out


# ── 페치 + 캐시 (type 둘: cube / potential_reset) ──────────────────────────


async def _cached(
    session_factory: async_sessionmaker[AsyncSession],
    ocid: str,
    cache_type: str,
    query_date: date,
    now: datetime,
) -> list[dict] | None:
    """캐시가 신선하면 그 날짜·type 의 레코드 목록, 아니면 None."""
    async with session_factory() as session:
        row = await session.get(HistoryCache, (ocid, cache_type, query_date))
    if row is None or not is_cache_fresh(query_date, row.fetched_at, now):
        return None
    page = row.payload.get(cache_type) if isinstance(row.payload, dict) else None
    return page if isinstance(page, list) else []


async def _store(
    session_factory: async_sessionmaker[AsyncSession],
    ocid: str,
    cache_type: str,
    query_date: date,
    records: list[dict],
    now: datetime,
) -> None:
    """history_cache upsert(payload={type: records}, fetched_at 갱신)."""
    async with session_factory() as session:
        stmt = (
            pg_insert(HistoryCache)
            .values(
                ocid=ocid,
                type=cache_type,
                date=query_date,
                payload={cache_type: records},
                fetched_at=now,
            )
            .on_conflict_do_update(
                index_elements=["ocid", "type", "date"],
                set_={"payload": {cache_type: records}, "fetched_at": now},
            )
        )
        await session.execute(stmt)
        await session.commit()


async def fetch_potential_records(
    deps: Deps,
    target: HistoryTarget,
    dates: Sequence[date],
    *,
    now: datetime | None = None,
) -> tuple[list[CubeRecord], list[ResetRecord]]:
    """기간 내 등록 캐릭터의 (큐브, 메소재설정) 기록. 날짜·type별 캐시 → 미스 시 개인 키 호출.

    target.api_key_encrypted 가 있어야 한다(호출자가 키 미등록 분리). 하드 실패는
    NexonAPIError 로 전파(명령 계층이 대상별 부분 성공 처리). fetch_starforce_records 패턴 차용.
    """
    if target.api_key_encrypted is None:
        raise ValueError("개인 키 없는 대상은 호출 전 분리해야 합니다")
    now = now or datetime.now(timezone.utc)
    api_key = deps.cipher.decrypt(target.api_key_encrypted)

    cube_raw: list[dict] = []
    reset_raw: list[dict] = []
    for query_date in dates:
        date_iso = query_date.isoformat()

        cached_cube = await _cached(
            deps.session_factory, target.ocid, CUBE_TYPE, query_date, now
        )
        if cached_cube is None:
            cached_cube = await deps.nexon.cube_history(api_key, date_iso)
            await _store(
                deps.session_factory,
                target.ocid,
                CUBE_TYPE,
                query_date,
                cached_cube,
                now,
            )
        cube_raw.extend(cached_cube)

        cached_reset = await _cached(
            deps.session_factory, target.ocid, RESET_TYPE, query_date, now
        )
        if cached_reset is None:
            cached_reset = await deps.nexon.potential_history(api_key, date_iso)
            await _store(
                deps.session_factory,
                target.ocid,
                RESET_TYPE,
                query_date,
                cached_reset,
                now,
            )
        reset_raw.extend(cached_reset)

    return (
        parse_cube_records(cube_raw, target.nickname),
        parse_reset_records(reset_raw, target.nickname),
    )


# ── 집계 (순수) ────────────────────────────────────────────────────────────


class MesoCostModel(Protocol):
    """잠재 메소 단가 모델(G2). potential_cost 모듈이 구조적으로 만족 — 의존성 주입(순수 유지)."""

    def appraisal_cost(self, item_level: int) -> int: ...
    def reset_cost(self, item_level: int, grade: str, potential_type: str) -> int: ...


@dataclass(frozen=True)
class PotentialSummary:
    """대상 1명의 잠재 집계 결과.

    tierups = from-등급별 등업 횟수(레어/에픽/유니크, 0건 제외, 등급 오름차순).
    메소(total/appraisal/reset) = cost 모델 주입 시만 산출(G2). 미주입이면 None('사용 메소' 숨김).
      total_meso = appraisal_meso(큐브 감정비 합) + reset_meso(메소 재설정비 합).
    by_cube_type/by_grade = 단일 대상 보조 노출용(다인 비교 시 미사용).
    """

    cube_count: int
    reset_count: int
    tierups: tuple[tuple[str, int], ...]
    tierup_total: int
    total_meso: int | None
    appraisal_meso: int | None  # 큐브 감정비 합
    reset_meso: int | None  # 메소 잠재/에디 재설정비 합
    by_cube_type: tuple[tuple[str, int], ...]
    by_grade: tuple[tuple[str, int, int], ...]  # (등급, 잠재 횟수, 에디 횟수)

    @property
    def total_resets(self) -> int:
        """잠재 재설정 전체 횟수 = 큐브 사용 + 메소 직접 재설정(둘 다 재설정 행위라 합산)."""
        return self.cube_count + self.reset_count


def _from_grade(before_pot: tuple[str, ...]) -> str | None:
    """등업 전 등급(from) = before 잠재옵션의 최고 등급. 알 수 없으면 None."""
    valid = [g for g in before_pot if g in GRADE_ORDER]
    if not valid:
        return None
    return max(valid, key=lambda g: GRADE_ORDER[g])


def _tierup_from(result: str, before_pot: tuple[str, ...]) -> str | None:
    """등업으로 카운트할 from-등급(레어/에픽/유니크). 등업 아님/레전드리 from 이면 None.

    'result == 성공' 가정(G1 미검증). 레전드리(종착) from 은 등업이 불가하므로 자연 제외 —
    엔드게임 메소 재설정의 동급(레전드리) 재롤 '성공' 은 등업에 포함되지 않는다.
    """
    if result != "성공":
        return None
    g = _from_grade(before_pot)
    return g if g in TIERUP_FROM_GRADES else None


def _cost_grade(before: tuple[str, ...], fallback: str) -> str:
    """재설정 비용 기준 등급 = 재설정 시점(before) 최고 등급. before 비면 fallback(현재 등급)."""
    g = _from_grade(before)
    return g if g is not None else fallback


def aggregate_potential(
    cubes: Sequence[CubeRecord],
    resets: Sequence[ResetRecord],
    *,
    cost: MesoCostModel | None = None,
) -> PotentialSummary:
    """큐브+재설정 → 사용 큐브·재설정·등업(from-등급별)·(메소)·단일 대상 보조 분포. 순수함수."""
    cube_count = len(cubes)
    reset_count = len(resets)

    # 등업: cube+reset 합쳐 성공·등급상승만 from-등급별 카운트.
    bucket: Counter[str] = Counter()
    for rec in (*cubes, *resets):
        g = _tierup_from(rec.result, rec.before_pot)
        if g is not None:
            bucket[g] += 1
    tierups = tuple((g, bucket[g]) for g in TIERUP_FROM_GRADES if bucket[g] > 0)
    tierup_total = sum(c for _, c in tierups)

    # 메소(G2): cost 모델 주입 시만. 큐브=감정비(레벨), 재설정=단가(레벨 구간×등급, 잠재/에디).
    total_meso: int | None
    appraisal_meso: int | None
    reset_meso: int | None
    if cost is None:
        total_meso = appraisal_meso = reset_meso = None
    else:
        appraisal_meso = sum(cost.appraisal_cost(c.item_level) for c in cubes)
        reset_meso = 0
        for r in resets:
            if "에디" in r.potential_type:  # 에디 재설정은 에디 옵션 등급으로 단가 결정
                grade = _cost_grade(r.before_add, r.add_grade)
            else:
                grade = _cost_grade(r.before_pot, r.pot_grade)
            reset_meso += cost.reset_cost(r.item_level, grade, r.potential_type)
        total_meso = appraisal_meso + reset_meso

    # 단일 대상 보조: 큐브종류 분포(내림차순) + 등급별 재설정 횟수(잠재/에디).
    cube_types: Counter[str] = Counter(c.cube_type for c in cubes if c.cube_type)
    by_cube_type = tuple(cube_types.most_common())

    pot_by_grade: Counter[str] = Counter()
    add_by_grade: Counter[str] = Counter()
    for rec in (*cubes, *resets):
        if rec.pot_grade in GRADE_ORDER:
            pot_by_grade[rec.pot_grade] += 1
        if rec.add_grade in GRADE_ORDER:
            add_by_grade[rec.add_grade] += 1
    grades_seen = sorted(
        set(pot_by_grade) | set(add_by_grade),
        key=lambda g: GRADE_ORDER[g],
        reverse=True,
    )
    by_grade = tuple((g, pot_by_grade[g], add_by_grade[g]) for g in grades_seen)

    return PotentialSummary(
        cube_count=cube_count,
        reset_count=reset_count,
        tierups=tierups,
        tierup_total=tierup_total,
        total_meso=total_meso,
        appraisal_meso=appraisal_meso,
        reset_meso=reset_meso,
        by_cube_type=by_cube_type,
        by_grade=by_grade,
    )
