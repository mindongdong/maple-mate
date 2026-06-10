"""정적 부위표 (handoff §3.6, Spike 0 A8). 게임 지식 기반 직접 작성 — 외부 의존 없음.

⚠️ API 는 '0성'과 '스타포스 불가 부위'를 구분하는 신호가 없다(starforce='0' 양쪽 공통).
→ 슬롯명 allowlist 로 스타포스 표시를 보정한다(불가 부위는 스타포스 항목 숨김).
잠재능력은 potential_option_grade==null 로 동적 판정(불가/미설정 부위는 등급이 null)하므로
별도 정적 '잠재 불가표'는 두지 않는다(단순함 우선 — 신뢰 가능한 동적 신호 존재).

매칭 키는 item_equipment_slot(부위 카테고리가 아닌 슬롯) — 반지1~4·펜던트2 를 슬롯으로 구분.
"""

from __future__ import annotations

# /아이템 드롭다운 부위 = 표준 슬롯 개별(반지 4·펜던트 2 각각). Discord 25 choices 상한 내(24개).
SLOT_CHOICES: tuple[str, ...] = (
    "모자",
    "얼굴장식",
    "눈장식",
    "귀고리",
    "상의",
    "하의",
    "신발",
    "장갑",
    "망토",
    "벨트",
    "어깨장식",
    "무기",
    "보조무기",
    "엠블렘",
    "펜던트",
    "펜던트2",
    "반지1",
    "반지2",
    "반지3",
    "반지4",
    "훈장",
    "뱃지",
    "포켓 아이템",
    "기계 심장",
)

# 스타포스 강화가 구조적으로 가능한 슬롯(allowlist). 그 외(엠블렘·훈장·뱃지·포켓·기계심장)는
# starforce='0' 이어도 '0성'이 아니라 '불가 부위' → 스타포스 항목을 숨긴다.
# 특수 반지(시드링 등)는 반지 슬롯이라 여기 포함되지만 special_ring_level>0 으로 동적 제외.
STARFORCE_CAPABLE_SLOTS: frozenset[str] = frozenset(
    {
        "모자",
        "얼굴장식",
        "눈장식",
        "귀고리",
        "상의",
        "하의",
        "신발",
        "장갑",
        "망토",
        "벨트",
        "어깨장식",
        "무기",
        "보조무기",
        "펜던트",
        "펜던트2",
        "반지1",
        "반지2",
        "반지3",
        "반지4",
    }
)


def starforce_capable(slot: str, *, special_ring_level: int = 0) -> bool:
    """슬롯이 스타포스 가능 부위인지(정적표) + 특수 반지 동적 제외(순수함수)."""
    if special_ring_level and special_ring_level > 0:
        return False
    return slot in STARFORCE_CAPABLE_SLOTS
