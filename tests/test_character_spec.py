"""스펙 변환 로직 단위테스트 (handoff §6: 전투력 추출·심볼 집계·HEXA 파싱)."""
from __future__ import annotations

from maple_mate.character.service import (
    extract_combat_power,
    fetch_spec,
    format_eok,
    parse_abilities,
    parse_hexa_cores,
    parse_hexa_stats,
    summarize_symbols,
)


def test_extract_combat_power_finds_entry():
    stat = {
        "final_stat": [
            {"stat_name": "최대 HP", "stat_value": "99999"},
            {"stat_name": "전투력", "stat_value": "12345678901"},
        ]
    }
    assert extract_combat_power(stat) == "12345678901"


def test_extract_combat_power_missing_returns_none():
    assert extract_combat_power({"final_stat": [{"stat_name": "마력", "stat_value": "1"}]}) is None
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
            {"hexa_core_name": "인페르노 마스터리", "hexa_core_level": 30, "hexa_core_type": "마스터리"},
            {"hexa_core_name": "인페르노 강화", "hexa_core_level": 10, "hexa_core_type": "강화"},
        ]
    }
    cores = parse_hexa_cores(hexa)
    assert cores == (("인페르노 마스터리", 30, "마스터리"), ("인페르노 강화", 10, "강화"))


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
            "basic": {"character_level": 285, "character_class": "아크메이지(불,독)", "world_name": "스카니아", "date": None},
            "stat": {"final_stat": [{"stat_name": "전투력", "stat_value": "9000000000"}]},
            "ability": {"ability_grade": "레전드리", "ability_info": [{"ability_value": "STR +12"}]},
            "symbol": {"symbol": [{"symbol_name": "아케인심볼 : 여로", "symbol_force": "165"}]},
            "hexa": {"character_hexa_core_equipment": [{"hexa_core_name": "코어", "hexa_core_level": 30, "hexa_core_type": "마스터리"}]},
            "hexa_stat": {"character_hexa_stat_core": [{"main_stat_name": "마력", "main_stat_level": 10}]},
        }
    )
    info = await fetch_spec(nexon, "oc1")
    assert info.level == 285
    assert info.combat_power == "9000000000"
    assert info.ability_grade == "레전드리"
    assert info.symbols.total_force == 165
    assert info.hexa_cores == (("코어", 30, "마스터리"),)
    assert info.hexa_stats == ("마력 Lv.10",)
