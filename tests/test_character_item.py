"""아이템 파싱 + 정적 부위표 단위테스트 (handoff §6: 0성 vs 스타포스 불가 구분)."""
from __future__ import annotations

from maple_mate.character import item
from maple_mate.character.equipment_slots import SLOT_CHOICES, starforce_capable
from maple_mate.character.item import (
    combine_options,
    fetch_item,
    find_slot_item,
    parse_item,
    summarize_add_option,
    summarize_upgrade,
    summarize_upgrade_stats,
)


# ── 정적 부위표 ──────────────────────────────────────────────────────


def test_slot_choices_within_discord_cap():
    assert len(SLOT_CHOICES) <= 25
    assert "반지1" in SLOT_CHOICES and "펜던트2" in SLOT_CHOICES


def test_starforce_capable_allowlist():
    assert starforce_capable("모자") is True
    assert starforce_capable("반지1") is True
    # 불가 부위
    assert starforce_capable("엠블렘") is False
    assert starforce_capable("훈장") is False
    assert starforce_capable("포켓 아이템") is False
    assert starforce_capable("기계 심장") is False


def test_starforce_capable_special_ring_excluded():
    # 반지 슬롯이라도 특수 반지(special_ring_level>0)는 스타포스 불가.
    assert starforce_capable("반지2", special_ring_level=5) is False
    assert starforce_capable("반지2", special_ring_level=0) is True


# ── 0성 vs 불가 구분 (핵심) ──────────────────────────────────────────


def test_zero_star_shown_on_capable_slot():
    raw = {"item_name": "0성 반지", "starforce": "0", "special_ring_level": 0}
    view = parse_item(raw, "반지1")
    assert view.starforce == "0"  # 진짜 0성 → 표시


def test_starforce_hidden_on_incapable_slot():
    raw = {"item_name": "칠흑의 보스 엠블렘", "starforce": "0"}
    view = parse_item(raw, "엠블렘")
    assert view.starforce is None  # 불가 부위 → starforce='0' 이어도 숨김


def test_starforce_hidden_on_special_ring():
    raw = {"item_name": "리스트레인트 링", "starforce": "0", "special_ring_level": 4}
    view = parse_item(raw, "반지3")
    assert view.starforce is None


def test_starforce_value_shown_when_enhanced():
    raw = {"item_name": "앱솔랩스 모자", "starforce": "22"}
    assert parse_item(raw, "모자").starforce == "22"


# ── 잠재/에디셔널/옵션/업그레이드 ──────────────────────────────────


def test_potential_shown_when_grade_present_hidden_when_null():
    raw = {
        "item_name": "x",
        "starforce": "0",
        "potential_option_grade": "레전드리",
        "potential_option_1": "INT +12%",
        "potential_option_2": "INT +9%",
        "potential_option_3": None,
        "additional_potential_option_grade": None,  # 잠재 불가/미설정 → 숨김
    }
    view = parse_item(raw, "모자")
    assert view.potential is not None
    assert view.potential.grade == "레전드리"
    assert view.potential.options == ("INT +12%", "INT +9%")
    assert view.additional_potential is None


def test_summarize_add_option_nonzero_only():
    option = {
        "str": "0",
        "int": "60",
        "boss_damage": "30",
        "magic_power": "0",
        "all_stat": "3",
    }
    summary = summarize_add_option(option)
    assert summary == "INT +60, 올스탯 +3%, 보스데미지 +30%"


def test_summarize_add_option_empty():
    assert summarize_add_option(None) is None
    assert summarize_add_option({"str": "0", "int": "0"}) is None


def test_summarize_upgrade():
    raw = {
        "scroll_upgrade": "8",
        "scroll_upgradeable_count": "0",
        "starforce_scroll_flag": "사용",
        "golden_hammer_flag": "적용",
    }
    assert summarize_upgrade(raw) == "주문서 8회 · 놀라운 강화 사용 · 황금망치"


def test_summarize_upgrade_none_when_pristine():
    raw = {"scroll_upgrade": "0", "starforce_scroll_flag": "미사용", "golden_hammer_flag": "미적용"}
    assert summarize_upgrade(raw) is None


# ── 작 스탯(item_etc_option) 요약 / 같은 옵션 합산 ──────────────────


def test_summarize_upgrade_stats_main_stats_only():
    # HP/MP/방어력은 노이즈로 제외, 주스탯·공·마력만.
    etc = {"str": "29", "dex": "22", "int": "17", "luk": "0", "max_hp": "230",
           "max_mp": "280", "attack_power": "25", "magic_power": "17", "armor": "24"}
    assert summarize_upgrade_stats(etc) == "STR +29, DEX +22, INT +17, 공격력 +25, 마력 +17"


def test_summarize_upgrade_stats_empty():
    assert summarize_upgrade_stats(None) is None
    assert summarize_upgrade_stats({"str": "0", "max_hp": "100"}) is None  # 주스탯 0 → None


def test_combine_options_sums_same_name_and_unit():
    options = ("스킬 재사용 대기시간 -2초", "스킬 재사용 대기시간 -1초", "최대 HP +9%")
    assert combine_options(options) == ("스킬 재사용 대기시간 -3초", "최대 HP +9%")


def test_combine_options_sums_flat_values():
    assert combine_options(("공격력 +11", "이동속도 +6", "공격력 +10")) == (
        "공격력 +21",
        "이동속도 +6",
    )


def test_combine_options_normalizes_colon_format():
    # 'INT : +12%' 콜론 포맷도 합산·정규화.
    assert combine_options(("INT : +12%", "INT : +9%")) == ("INT +21%",)


def test_combine_options_keeps_different_units_separate():
    assert combine_options(("공격력 +11", "공격력 +5%")) == ("공격력 +11", "공격력 +5%")


def test_combine_options_passthrough_when_unparseable():
    assert combine_options(("특수 효과",)) == ("특수 효과",)


def test_combine_options_preserves_duplicate_unparseable_lines():
    # 부호 수치 없는 동일 줄도 인덱스 키로 중복 보존(데이터 손실 방지).
    assert combine_options(("특수 효과", "특수 효과")) == ("특수 효과", "특수 효과")


def test_parse_item_includes_icon_url_and_upgrade_stats():
    raw = {
        "item_name": "하이네스 워리어헬름",
        "item_icon": "https://open.api.nexon.com/static/maplestory/item/icon/ABC",
        "starforce": "19",
        "item_etc_option": {"str": "29", "attack_power": "25"},
    }
    view = parse_item(raw, "모자")
    assert view.icon_url.endswith("/ABC")
    assert view.upgrade_stats == "STR +29, 공격력 +25"


# ── 슬롯 매칭 / fetch ────────────────────────────────────────────────


def test_find_slot_item_matches_by_slot_not_part():
    payload = {
        "item_equipment": [
            {"item_equipment_part": "반지", "item_equipment_slot": "반지1", "item_name": "반지A"},
            {"item_equipment_part": "반지", "item_equipment_slot": "반지2", "item_name": "반지B"},
        ]
    }
    assert find_slot_item(payload, "반지2")["item_name"] == "반지B"
    assert find_slot_item(payload, "반지4") is None


class _FakeNexon:
    def __init__(self, payload):
        self._payload = payload

    async def character_item_equipment(self, ocid):
        return self._payload


async def test_fetch_item_found_and_not_worn():
    payload = {
        "date": None,
        "item_equipment": [
            {"item_equipment_slot": "모자", "item_name": "앱솔랩스 모자", "starforce": "22"}
        ],
    }
    nexon = _FakeNexon(payload)
    found = await fetch_item(nexon, "oc1", "모자")
    assert found.found is True and found.item.starforce == "22"

    empty = await fetch_item(nexon, "oc1", "반지4")
    assert empty.found is False and empty.item is None
