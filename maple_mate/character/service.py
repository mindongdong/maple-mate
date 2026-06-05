"""캐릭터 스펙 조회 + 변환 (전달-무관). `/스펙` 6종 조합.

순수 변환(전투력 추출·심볼 집계·HEXA 파싱)은 단위테스트 대상(handoff §6). 넥슨 호출은
date 무지정(최신 ready). `/아이템` 장비 파싱은 item.py 로 분리.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from ..nexon.client import NexonClient
from ..nexon.errors import ErrorClass, NexonAPIError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolSummary:
    total_force: int
    counts: tuple[tuple[str, int], ...]  # (분류, 개수) — 아케인/사크레드/어센틱/기타


@dataclass(frozen=True)
class SpecInfo:
    level: int | None
    job: str | None
    world: str | None
    combat_power: str | None  # character/stat 의 raw 문자열(전투력)
    ability_grade: str | None
    abilities: tuple[str, ...]
    symbols: SymbolSummary
    hexa_cores: tuple[tuple[str, int, str], ...]  # (코어명, 레벨, 종류) — 단일 상세용
    hexa_stats: tuple[str, ...]  # 스탯명 포함 라인 — 단일 상세용
    hexa_core_by_type: tuple[tuple[str, tuple[int, ...]], ...]  # (타입, (레벨들)) — 비교 색칩용
    hexa_stat_triples: tuple[tuple[int, int, int], ...]  # (메인, 서브1, 서브2) — 비교 누적막대용
    date: str | None


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def extract_combat_power(stat: dict) -> str | None:
    """character/stat 의 final_stat 에서 stat_name=='전투력' 의 stat_value(문자열) 추출.

    Spike 0(handoff §3.3): stat_value 는 문자열. 없으면 None.
    """
    for entry in stat.get("final_stat") or []:
        if entry.get("stat_name") == "전투력":
            return entry.get("stat_value")
    return None


def format_eok(value: str | int | None) -> str:
    """전투력 등 큰 수를 '억/만' 한글 표기로(표시 전용 순수함수). None→'—', 비수치→원문."""
    if value is None:
        return "—"
    try:
        n = int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return str(value)
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    eok, rest = divmod(n, 10**8)
    man = rest // 10**4
    parts: list[str] = []
    if eok:
        parts.append(f"{eok}억")
    if man:
        parts.append(f"{man}만")
    if not parts:
        parts.append(str(n))
    return sign + " ".join(parts)


def _symbol_category(name: str) -> str:
    if "아케인" in name:
        return "아케인"
    if "사크레드" in name:
        return "사크레드"
    if "어센틱" in name:
        return "어센틱"
    return "기타"


def summarize_symbols(symbol_list: list[dict] | None) -> SymbolSummary:
    """심볼 목록 → 총 포스 + 분류별 개수(순수함수)."""
    total = 0
    counts: dict[str, int] = {}
    for symbol in symbol_list or []:
        total += _to_int(symbol.get("symbol_force"))
        category = _symbol_category(symbol.get("symbol_name") or "")
        counts[category] = counts.get(category, 0) + 1
    ordered = [(c, counts[c]) for c in ("아케인", "사크레드", "어센틱", "기타") if c in counts]
    return SymbolSummary(total_force=total, counts=tuple(ordered))


def parse_abilities(ability: dict) -> tuple[str | None, tuple[str, ...]]:
    """어빌리티 등급 + 현재 어빌리티 값 목록(순수함수)."""
    grade = ability.get("ability_grade")
    values = tuple(
        a.get("ability_value", "")
        for a in (ability.get("ability_info") or [])
        if a.get("ability_value")
    )
    return grade, values


def parse_hexa_cores(hexamatrix: dict) -> tuple[tuple[str, int, str], ...]:
    """HEXA 코어 목록(순수함수) — (이름, 레벨, 종류)."""
    return tuple(
        (
            core.get("hexa_core_name", "?"),
            core.get("hexa_core_level", 0),
            core.get("hexa_core_type", ""),
        )
        for core in (hexamatrix.get("character_hexa_core_equipment") or [])
    )


_HEXA_STAT_KEYS = (
    "character_hexa_stat_core",
    "character_hexa_stat_core_2",
    "character_hexa_stat_core_3",
)


def parse_hexa_stats(hexamatrix_stat: dict) -> tuple[str, ...]:
    """HEXA 스탯 코어 → 'main Lv.x / sub1 Lv.y / sub2 Lv.z' 라인 목록(순수함수, 단일 상세용)."""
    lines: list[str] = []
    for key in _HEXA_STAT_KEYS:
        for core in hexamatrix_stat.get(key) or []:
            parts: list[str] = []
            main = core.get("main_stat_name")
            if main:
                parts.append(f"{main} Lv.{core.get('main_stat_level', 0)}")
            sub1 = core.get("sub_stat_name_1")
            if sub1:
                parts.append(f"{sub1} Lv.{core.get('sub_stat_level_1', 0)}")
            sub2 = core.get("sub_stat_name_2")
            if sub2:
                parts.append(f"{sub2} Lv.{core.get('sub_stat_level_2', 0)}")
            if parts:
                lines.append(" / ".join(parts))
    return tuple(lines)


# HEXA 코어 타입(실호출 확정: '스킬 코어'·'마스터리 코어'·'강화 코어'·'공용 코어', API 순서 고정).
# 직업이 달라도 타입별 개수·순서가 같아(스킬2·마스터리4·강화4·공용3=13) 슬롯 라벨로 비교 가능.
_CORE_TYPE_SHORT = {
    "스킬 코어": "스킬",
    "마스터리 코어": "마스터리",
    "강화 코어": "강화",
    "공용 코어": "공용",
}


def hexa_core_levels_by_type(hexamatrix: dict) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """HEXA 코어를 타입별로 묶어 레벨(정수)만 나열(순수함수, 비교 색칩용). 스킬명 제거.

    예: (('스킬', (1, 4)), ('마스터리', (29, 19, 1, 23)), ('강화', (15, 2, 1, 1)),
    ('공용', (1, 5, 4))). 타입 순서 = API 등장 순(스킬·마스터리·강화·공용).
    """
    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for core in hexamatrix.get("character_hexa_core_equipment") or []:
        raw_type = core.get("hexa_core_type", "")
        short = _CORE_TYPE_SHORT.get(raw_type, raw_type or "코어")
        if short not in groups:
            groups[short] = []
            order.append(short)
        groups[short].append(_to_int(core.get("hexa_core_level")))
    return tuple((t, tuple(groups[t])) for t in order)


def hexa_stat_triples(hexamatrix_stat: dict) -> tuple[tuple[int, int, int], ...]:
    """HEXA 스탯 코어를 (메인, 서브1, 서브2) 레벨 정수 튜플로(순수함수, 비교 누적막대용).

    예: ((4, 10, 6), (8, 9, 3), (4, 10, 6)). 코어당 세 값의 합 = 20.
    """
    triples: list[tuple[int, int, int]] = []
    for key in _HEXA_STAT_KEYS:
        for core in hexamatrix_stat.get(key) or []:
            triples.append(
                (
                    _to_int(core.get("main_stat_level")),
                    _to_int(core.get("sub_stat_level_1")),
                    _to_int(core.get("sub_stat_level_2")),
                )
            )
    return tuple(triples)


# ── 주간(7일) 최고 전투력 (date 별 character/stat + 인메모리 캐시) ────────────────
#
# 전투력은 character/stat 의 활성 프리셋·단일 스냅샷 값뿐이라 "프리셋별 최고"는 불가(API 한계).
# 대신 지난 7일치 스냅샷을 각각 조회해 최댓값을 취하면, 그 주에 메인(보스) 프리셋을 한 번이라도
# 켰던 날의 높은 전투력을 잡아낸다. 과거 일자 스냅샷은 불변이라 (ocid,date) 키로 영구 캐시한다.

CombatPowerCache = dict[tuple[str, str], int]
WEEKLY_DAYS = 7


async def fetch_combat_power_on(
    nexon: NexonClient,
    ocid: str,
    date_iso: str,
    *,
    cache: CombatPowerCache | None = None,
) -> int | None:
    """특정 일자(KST `YYYY-MM-DD`)의 전투력 정수. 미준비(00009)·전투력 없음 → None.

    (ocid, date) 인메모리 캐시: 과거 일자 스냅샷은 불변이라 무효화 없이 영구 보관한다.
    성공한 정수값만 저장(미준비/파싱불가는 저장 안 해 다음에 재시도). DATA_NOT_READY 외
    넥슨 에러는 호출자로 전파한다(상위에서 best-effort 처리).
    """
    key = (ocid, date_iso)
    if cache is not None and key in cache:
        return cache[key]
    try:
        stat = await nexon.character_stat(ocid, date=date_iso)
    except NexonAPIError as exc:
        if exc.error_class is ErrorClass.DATA_NOT_READY:
            return None
        raise
    raw = extract_combat_power(stat)
    if raw is None:
        return None
    try:
        power = int(str(raw).replace(",", ""))
    except (ValueError, TypeError):
        return None
    if cache is not None:
        cache[key] = power
    return power


async def fetch_weekly_max_power(
    nexon: NexonClient,
    ocid: str,
    today: date,
    *,
    cache: CombatPowerCache | None = None,
    latest: int | None = None,
    days: int = WEEKLY_DAYS,
) -> int | None:
    """지난 `days`일(D-1~D-`days`, KST) 중 최고 전투력 정수. 후보 없으면 None.

    각 일자는 fetch_combat_power_on(캐시 적용)으로 조회하고 미준비 일자는 건너뛴다. `latest`
    (무지정 최신 호출에서 이미 받은 전투력)를 후보에 포함해 ① 최신값보다 낮게 표기되지 않도록,
    ② 7일치가 모두 실패해도 그레이스풀 폴백되도록 한다. 개별 일자의 하드 에러는 무시(로그만).
    """
    candidates: list[int] = [latest] if latest is not None else []
    for d in range(1, days + 1):
        date_iso = (today - timedelta(days=d)).isoformat()
        try:
            power = await fetch_combat_power_on(nexon, ocid, date_iso, cache=cache)
        except NexonAPIError as exc:
            log.debug("주간 전투력 %s %s 조회 실패(무시): %s", ocid, date_iso, exc)
            continue
        if power is not None:
            candidates.append(power)
    return max(candidates) if candidates else None


async def fetch_spec(nexon: NexonClient, ocid: str) -> SpecInfo:
    """character basic·stat·ability·symbol·hexamatrix·hexamatrix-stat 조합 (date 무지정)."""
    basic = await nexon.character_basic(ocid)
    stat = await nexon.character_stat(ocid)
    ability = await nexon.character_ability(ocid)
    symbol = await nexon.character_symbol_equipment(ocid)
    hexa = await nexon.character_hexamatrix(ocid)
    hexa_stat = await nexon.character_hexamatrix_stat(ocid)

    grade, abilities = parse_abilities(ability)
    return SpecInfo(
        level=basic.get("character_level"),
        job=basic.get("character_class"),
        world=basic.get("world_name"),
        combat_power=extract_combat_power(stat),
        ability_grade=grade,
        abilities=abilities,
        symbols=summarize_symbols(symbol.get("symbol")),
        hexa_cores=parse_hexa_cores(hexa),
        hexa_stats=parse_hexa_stats(hexa_stat),
        hexa_core_by_type=hexa_core_levels_by_type(hexa),
        hexa_stat_triples=hexa_stat_triples(hexa_stat),
        date=basic.get("date"),
    )
