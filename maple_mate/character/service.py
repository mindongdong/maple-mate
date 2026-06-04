"""캐릭터 스펙 조회 + 변환 (전달-무관). `/스펙` 6종 조합.

순수 변환(전투력 추출·심볼 집계·HEXA 파싱)은 단위테스트 대상(handoff §6). 넥슨 호출은
date 무지정(최신 ready). `/아이템` 장비 파싱은 item.py 로 분리.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..nexon.client import NexonClient


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
    hexa_cores: tuple[tuple[str, int, str], ...]  # (코어명, 레벨, 종류)
    hexa_stats: tuple[str, ...]  # 포맷된 스탯 코어 라인
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
    """HEXA 스탯 코어 → 'main Lv.x / sub1 Lv.y / sub2 Lv.z' 라인 목록(순수함수)."""
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
        date=basic.get("date"),
    )
