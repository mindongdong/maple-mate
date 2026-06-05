"""`/아이템` 장비 파싱 (전달-무관). item-equipment 응답에서 선택 슬롯 1개를 뽑아 수치 나열.

**우열 판정 안 함**(design §3.2) — 표시만. 스타포스는 정적 부위표로 보정(0성 vs 불가),
잠재/에디셔널 잠재는 grade==null 이면 숨김(불가/미설정 동적 판정). 순수 파싱은 단위테스트 대상.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..nexon.client import NexonClient
from . import equipment_slots


@dataclass(frozen=True)
class PotentialView:
    grade: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class ItemSlotView:
    slot: str
    item_name: str
    icon_url: str | None  # 장비 아이콘 이미지 URL(카드 렌더용)
    starforce: str | None  # None=스타포스 불가 부위(숨김) / 문자열=강화 단계
    potential: PotentialView | None  # None=잠재 없음/불가
    additional_potential: PotentialView | None
    add_option: str | None  # 추가옵션 요약(없으면 None)
    upgrade: str | None  # 주문서/업그레이드 요약(없으면 None)
    upgrade_stats: str | None  # 주문서 작으로 오른 스탯 요약(item_etc_option, 없으면 None)


@dataclass(frozen=True)
class ItemResult:
    found: bool  # 해당 슬롯에 장비 착용 여부
    slot: str
    item: ItemSlotView | None
    date: str | None


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0


# 추가옵션 표시 순서/라벨/접미사(%, 빈문자=고정수치).
_ADD_OPTION_LABELS: tuple[tuple[str, str, str], ...] = (
    ("str", "STR", ""),
    ("dex", "DEX", ""),
    ("int", "INT", ""),
    ("luk", "LUK", ""),
    ("all_stat", "올스탯", "%"),
    ("max_hp", "HP", ""),
    ("max_mp", "MP", ""),
    ("attack_power", "공격력", ""),
    ("magic_power", "마력", ""),
    ("boss_damage", "보스데미지", "%"),
    ("damage", "데미지", "%"),
    ("armor", "방어력", ""),
)


def summarize_add_option(option: dict | None) -> str | None:
    """item_add_option(추가옵션) → 'INT +60, 보스데미지 +30%' 요약(순수함수). 0/없음 → None."""
    if not option:
        return None
    parts: list[str] = []
    for key, label, suffix in _ADD_OPTION_LABELS:
        if _to_int(option.get(key)) != 0:
            parts.append(f"{label} +{option.get(key)}{suffix}")
    return ", ".join(parts) or None


# 작(주문서)으로 오른 스탯 표시 라벨 — 주요 스탯/공·마력만(HP/MP/방어력 등 노이즈 제외).
_UPGRADE_STAT_LABELS: tuple[tuple[str, str], ...] = (
    ("str", "STR"),
    ("dex", "DEX"),
    ("int", "INT"),
    ("luk", "LUK"),
    ("attack_power", "공격력"),
    ("magic_power", "마력"),
)


def summarize_upgrade_stats(option: dict | None) -> str | None:
    """item_etc_option(주문서 작으로 오른 스탯) → 'STR +29, 공격력 +25' 요약. 주요 스탯만, 0/없음 → None."""
    if not option:
        return None
    parts = [
        f"{label} {_to_int(option.get(key)):+d}"
        for key, label in _UPGRADE_STAT_LABELS
        if _to_int(option.get(key)) != 0
    ]
    return ", ".join(parts) or None


# 옵션 문자열에서 부호 있는 수치 추출: "스킬 재사용 대기시간 -2초" → (이름, -2, "초").
_OPT_VALUE_RE = re.compile(r"^(.+?)\s*:?\s*([+-]\d+)\s*(.*)$")


def combine_options(options: tuple[str, ...]) -> tuple[str, ...]:
    """같은 옵션(이름+단위)을 합산 표기 (순수함수, 첫 등장 순서 보존).

    '스킬 재사용 대기시간 -2초' + '-1초' → '스킬 재사용 대기시간 -3초',
    '공격력 +11' + '공격력 +10' → '공격력 +21'. 부호 수치를 못 찾으면 원문 유지.
    """
    order: list[tuple[str, object]] = []
    sums: dict[tuple[str, object], int] = {}
    passthrough: dict[tuple[str, object], str] = {}
    for idx, opt in enumerate(options):
        match = _OPT_VALUE_RE.match(opt)
        if match is None:
            key = ("\x00raw", idx)  # 파싱 불가 → 원문 그대로(인덱스 키로 중복도 보존)
            order.append(key)
            passthrough[key] = opt
            continue
        name = match.group(1).strip().rstrip(":").strip()
        unit = match.group(3).strip()
        key = (name, unit)
        if key not in sums:
            order.append(key)
            sums[key] = 0
        sums[key] += int(match.group(2))
    result: list[str] = []
    for key in order:
        if key in passthrough:
            result.append(passthrough[key])
        else:
            name, unit = key
            result.append(f"{name} {sums[key]:+d}{unit}")
    return tuple(result)


def summarize_upgrade(raw: dict) -> str | None:
    """주문서/업그레이드 요약(순수함수): 작 횟수·놀강·황금망치. 없으면 None."""
    parts: list[str] = []
    scroll = raw.get("scroll_upgrade")
    if scroll and scroll != "0":
        remain = raw.get("scroll_upgradeable_count")
        suffix = f" (남은 {remain})" if remain and remain != "0" else ""
        parts.append(f"주문서 {scroll}회{suffix}")
    if raw.get("starforce_scroll_flag") == "사용":
        parts.append("놀라운 강화 사용")
    if raw.get("golden_hammer_flag") == "적용":
        parts.append("황금망치")
    return " · ".join(parts) or None


def _potential(grade: str | None, options: list[str | None]) -> PotentialView | None:
    """잠재 등급+옵션 → PotentialView. grade 가 falsy(잠재 불가/미설정)면 None(숨김)."""
    if not grade:
        return None
    return PotentialView(grade=grade, options=tuple(o for o in options if o))


def find_slot_item(item_equipment: dict, slot: str) -> dict | None:
    """item_equipment.item_equipment 에서 슬롯명이 일치하는 장비(순수함수). 미착용 → None."""
    for raw in item_equipment.get("item_equipment") or []:
        if raw.get("item_equipment_slot") == slot:
            return raw
    return None


def parse_item(raw: dict, slot: str) -> ItemSlotView:
    """장비 1개 → 표시용 뷰(순수함수). 스타포스는 정적표 보정, 잠재는 grade null 이면 숨김."""
    capable = equipment_slots.starforce_capable(
        slot, special_ring_level=_to_int(raw.get("special_ring_level"))
    )
    starforce = raw.get("starforce") if capable else None
    return ItemSlotView(
        slot=slot,
        item_name=raw.get("item_name", "?"),
        icon_url=raw.get("item_icon"),
        starforce=starforce,
        potential=_potential(
            raw.get("potential_option_grade"),
            [raw.get("potential_option_1"), raw.get("potential_option_2"), raw.get("potential_option_3")],
        ),
        additional_potential=_potential(
            raw.get("additional_potential_option_grade"),
            [
                raw.get("additional_potential_option_1"),
                raw.get("additional_potential_option_2"),
                raw.get("additional_potential_option_3"),
            ],
        ),
        add_option=summarize_add_option(raw.get("item_add_option")),
        upgrade=summarize_upgrade(raw),
        upgrade_stats=summarize_upgrade_stats(raw.get("item_etc_option")),
    )


async def fetch_item(nexon: NexonClient, ocid: str, slot: str) -> ItemResult:
    """item-equipment 조회 후 선택 슬롯 1개 파싱 (date 무지정). 미착용도 정상 결과."""
    data = await nexon.character_item_equipment(ocid)
    raw = find_slot_item(data, slot)
    item = parse_item(raw, slot) if raw is not None else None
    return ItemResult(found=raw is not None, slot=slot, item=item, date=data.get("date"))
