"""스펙 변환 로직 단위테스트 (handoff §6: 전투력 추출·심볼 집계·HEXA 파싱)."""

from __future__ import annotations

from datetime import date

from maple_mate.character.service import (
    extract_combat_power,
    fetch_combat_power_on,
    fetch_spec,
    fetch_weekly_max_power,
    format_eok,
    hexa_core_levels_by_type,
    hexa_stat_triples,
    parse_abilities,
    parse_hexa_cores,
    parse_hexa_stats,
    summarize_symbols,
)
from maple_mate.nexon.errors import ErrorClass, NexonAPIError


def test_extract_combat_power_finds_entry():
    stat = {
        "final_stat": [
            {"stat_name": "최대 HP", "stat_value": "99999"},
            {"stat_name": "전투력", "stat_value": "12345678901"},
        ]
    }
    assert extract_combat_power(stat) == "12345678901"


def test_extract_combat_power_missing_returns_none():
    assert (
        extract_combat_power({"final_stat": [{"stat_name": "마력", "stat_value": "1"}]})
        is None
    )
    assert extract_combat_power({}) is None


def test_format_eok():
    assert format_eok("12345678901") == "123억 4567만"
    assert format_eok(50000) == "5만"
    assert format_eok("5000") == "5000"
    assert format_eok(0) == "0"
    assert format_eok(None) == "—"
    assert format_eok("비수치") == "비수치"


def test_summarize_symbols_counts_and_force():
    symbols = [
        {"symbol_name": "아케인심볼 : 소멸의 여로", "symbol_force": "165"},
        {"symbol_name": "아케인심볼 : 츄츄 아일랜드", "symbol_force": "135"},
        {"symbol_name": "사크레드심볼 : 세르니움", "symbol_force": "200"},
    ]
    summary = summarize_symbols(symbols)
    assert summary.total_force == 500
    assert summary.counts == (("아케인", 2), ("사크레드", 1))


def test_summarize_symbols_empty():
    summary = summarize_symbols(None)
    assert summary.total_force == 0 and summary.counts == ()


def test_parse_abilities():
    ability = {
        "ability_grade": "레전드리",
        "ability_info": [
            {"ability_value": "버프 지속 +50%"},
            {"ability_value": "STR +12"},
            {"ability_value": ""},  # 빈 값 무시
        ],
    }
    grade, values = parse_abilities(ability)
    assert grade == "레전드리"
    assert values == ("버프 지속 +50%", "STR +12")


def test_parse_hexa_cores():
    hexa = {
        "character_hexa_core_equipment": [
            {
                "hexa_core_name": "인페르노 마스터리",
                "hexa_core_level": 30,
                "hexa_core_type": "마스터리",
            },
            {
                "hexa_core_name": "인페르노 강화",
                "hexa_core_level": 10,
                "hexa_core_type": "강화",
            },
        ]
    }
    cores = parse_hexa_cores(hexa)
    assert cores == (
        ("인페르노 마스터리", 30, "마스터리"),
        ("인페르노 강화", 10, "강화"),
    )


def test_hexa_core_levels_grouped_by_type():
    # 실호출 구조: 스킬·마스터리·강화·공용 (API 순서). 타입별로 레벨만 묶어 숫자 나열.
    hexa = {
        "character_hexa_core_equipment": [
            {
                "hexa_core_type": "스킬 코어",
                "hexa_core_level": 1,
                "hexa_core_name": "크로노",
            },
            {
                "hexa_core_type": "스킬 코어",
                "hexa_core_level": 4,
                "hexa_core_name": "바이템",
            },
            {"hexa_core_type": "마스터리 코어", "hexa_core_level": 29},
            {"hexa_core_type": "마스터리 코어", "hexa_core_level": 19},
            {"hexa_core_type": "마스터리 코어", "hexa_core_level": 1},
            {"hexa_core_type": "마스터리 코어", "hexa_core_level": 23},
            {"hexa_core_type": "강화 코어", "hexa_core_level": 15},
            {"hexa_core_type": "공용 코어", "hexa_core_level": 5},
        ]
    }
    # 타입별 레벨 정수 튜플(색칩 렌더용).
    assert hexa_core_levels_by_type(hexa) == (
        ("스킬", (1, 4)),
        ("마스터리", (29, 19, 1, 23)),
        ("강화", (15,)),
        ("공용", (5,)),
    )


def test_hexa_stat_triples_numbers_only():
    hexa_stat = {
        "character_hexa_stat_core": [
            {
                "main_stat_name": "크리티컬 데미지",
                "main_stat_level": 4,
                "sub_stat_level_1": 10,
                "sub_stat_level_2": 6,
            }
        ],
        "character_hexa_stat_core_2": [
            {"main_stat_level": 8, "sub_stat_level_1": 9, "sub_stat_level_2": 3}
        ],
        "character_hexa_stat_core_3": [],
    }
    # 스탯명 제거, (메인, 서브1, 서브2) 정수 튜플(누적막대 렌더용).
    assert hexa_stat_triples(hexa_stat) == ((4, 10, 6), (8, 9, 3))


def test_parse_hexa_stats_formats_lines():
    hexa_stat = {
        "character_hexa_stat_core": [
            {
                "main_stat_name": "마력",
                "main_stat_level": 10,
                "sub_stat_name_1": "보스 몬스터 데미지",
                "sub_stat_level_1": 5,
                "sub_stat_name_2": "방어율 무시",
                "sub_stat_level_2": 5,
            }
        ],
        "character_hexa_stat_core_2": [],
        "character_hexa_stat_core_3": [],
    }
    lines = parse_hexa_stats(hexa_stat)
    assert lines == ("마력 Lv.10 / 보스 몬스터 데미지 Lv.5 / 방어율 무시 Lv.5",)


class _FakeNexon:
    def __init__(self, payloads):
        self._p = payloads

    async def character_basic(self, ocid):
        return self._p["basic"]

    async def character_stat(self, ocid):
        return self._p["stat"]

    async def character_ability(self, ocid):
        return self._p["ability"]

    async def character_symbol_equipment(self, ocid):
        return self._p["symbol"]

    async def character_hexamatrix(self, ocid):
        return self._p["hexa"]

    async def character_hexamatrix_stat(self, ocid):
        return self._p["hexa_stat"]


async def test_fetch_spec_assembles_all_sections():
    nexon = _FakeNexon(
        {
            "basic": {
                "character_level": 285,
                "character_class": "아크메이지(불,독)",
                "world_name": "스카니아",
                "date": None,
            },
            "stat": {
                "final_stat": [{"stat_name": "전투력", "stat_value": "9000000000"}]
            },
            "ability": {
                "ability_grade": "레전드리",
                "ability_info": [{"ability_value": "STR +12"}],
            },
            "symbol": {
                "symbol": [{"symbol_name": "아케인심볼 : 여로", "symbol_force": "165"}]
            },
            "hexa": {
                "character_hexa_core_equipment": [
                    {
                        "hexa_core_name": "코어",
                        "hexa_core_level": 30,
                        "hexa_core_type": "마스터리",
                    }
                ]
            },
            "hexa_stat": {
                "character_hexa_stat_core": [
                    {"main_stat_name": "마력", "main_stat_level": 10}
                ]
            },
        }
    )
    info = await fetch_spec(nexon, "oc1")
    assert info.level == 285
    assert info.combat_power == "9000000000"
    assert info.ability_grade == "레전드리"
    assert info.symbols.total_force == 165
    assert info.hexa_cores == (("코어", 30, "마스터리"),)
    assert info.hexa_stats == ("마력 Lv.10",)
    # 비교용 타입묶음/트리플도 채워진다(정수 튜플).
    assert info.hexa_core_by_type == (("마스터리", (30,)),)
    assert info.hexa_stat_triples == ((10, 0, 0),)


# ── 주간(7일) 최고 전투력 + (ocid, date) 인메모리 캐시 ──────────────────────


class _FakeStatClient:
    """character_stat(ocid, date)만 흉내. date→전투력 문자열 매핑, not_ready 집합은 00009 raise."""

    def __init__(self, by_date, *, not_ready=()):
        self._by_date = by_date
        self._not_ready = set(not_ready)
        self.calls: list[str | None] = []  # 호출된 date 기록(캐시 검증용)

    async def character_stat(self, ocid, date=None):
        self.calls.append(date)
        if date in self._not_ready:
            raise NexonAPIError(
                "OPENAPI00009", "wait", error_class=ErrorClass.DATA_NOT_READY
            )
        raw = self._by_date.get(date)
        if raw is None:
            return {"final_stat": []}
        return {"final_stat": [{"stat_name": "전투력", "stat_value": raw}]}


async def test_fetch_combat_power_on_parses_and_caches():
    client = _FakeStatClient({"2026-06-01": "180000000"})
    cache: dict = {}
    assert (
        await fetch_combat_power_on(client, "oc1", "2026-06-01", cache=cache)
        == 180000000
    )
    assert cache[("oc1", "2026-06-01")] == 180000000
    # 두 번째 호출은 캐시 히트 → API 추가 호출 없음(과거 스냅샷 불변).
    assert (
        await fetch_combat_power_on(client, "oc1", "2026-06-01", cache=cache)
        == 180000000
    )
    assert client.calls == ["2026-06-01"]


async def test_fetch_combat_power_on_not_ready_returns_none_and_not_cached():
    client = _FakeStatClient({}, not_ready={"2026-06-01"})
    cache: dict = {}
    assert await fetch_combat_power_on(client, "oc1", "2026-06-01", cache=cache) is None
    assert cache == {}  # 미준비는 캐시 안 함 → 다음에 재시도


async def test_fetch_weekly_max_power_picks_max_over_window():
    # today=2026-06-08 → D-1..D-7 = 06-07 … 06-01
    by_date = {
        "2026-06-07": "150000000",
        "2026-06-06": "210000000",  # 그 주 메인 프리셋 켠 날 = 최고
        "2026-06-05": "140000000",
    }
    not_ready = {"2026-06-04", "2026-06-03", "2026-06-02", "2026-06-01"}
    client = _FakeStatClient(by_date, not_ready=not_ready)
    got = await fetch_weekly_max_power(
        client, "oc1", date(2026, 6, 8), latest=145000000
    )
    assert got == 210000000


async def test_fetch_weekly_max_power_falls_back_to_latest():
    # 7일치가 모두 latest 보다 낮거나 미준비 → latest 유지(그레이스풀 폴백).
    client = _FakeStatClient(
        {"2026-06-07": "100000000"},
        not_ready={f"2026-06-0{d}" for d in range(1, 7)},  # 06-01..06-06
    )
    got = await fetch_weekly_max_power(
        client, "oc1", date(2026, 6, 8), latest=185000000
    )
    assert got == 185000000


async def test_fetch_weekly_max_power_none_when_no_data_and_no_latest():
    client = _FakeStatClient({}, not_ready={f"2026-06-0{d}" for d in range(1, 8)})
    assert (
        await fetch_weekly_max_power(client, "oc1", date(2026, 6, 8), latest=None)
        is None
    )
