"""장비 레벨 매칭 (Q5). target_item(이름) → base_equipment_level.

스타포스 이력엔 레벨 필드가 없어(실측), 비용공식에 넣을 장비 레벨을 다음 순서로 구한다:
  (set) 세트명 부분일치 — 이름에 세트명이 포함되면 무조건 고정 레벨(EQUIPMENT_SET_LEVEL).
  (A) 현재 장착 — item-equipment 의 같은 이름 장비 base_equipment_level (가장 정확).
  (B) 자동 학습 — 과거에 관측한 장비명→레벨(learned_equipment_level). 교체·탈착된 구장비 매칭.
  (C) 큐레이션 시드 — 세트로 안 잡히는 단품 장신구(부트스트랩).
  (D) 모두 실패 → None → 그 시도 제외("N건 중 M건") + error_log 제보.

집계 제외(매칭과 별개): EXCLUDED_ITEMS(특정 장비) 와 MIN_AGGREGATE_LEVEL(100 미만) 은
집계에서 통째로 빠진다(분모·제보에서도 제외) — 매칭 실패('미상')와 구분된다. 처리는 service.aggregate_starforce.

match_level 은 순수함수 — 호출자가 (A)현재장착·(B)학습을 합쳐 `equipped` 로 넘기고 (C)는 seed.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..nexon.client import NexonClient
from .models import LearnedEquipmentLevel

# 대표 장비 세트 → 고정 착용 레벨. 아이템명에 세트명이 포함되면 무조건 이 레벨로 매칭(최우선).
# 세트 방어구는 직업군별 부위 명칭이 달라(에테르넬 나이트아머/메일/헬름…) 정확 일치 시드로는
# 누락이 잦다 → 세트명 부분일치로 일괄 커버한다. 세트 레벨은 부위·직업 무관 고정이라 안전.
EQUIPMENT_SET_LEVEL: dict[str, int] = {
    "에테르넬": 250,
    "아케인": 200,  # 아케인셰이드
    "앱솔랩스": 160,
    "파프니르": 150,
    "하이네스": 150,
    "트릭스터": 150,
    "이글아이": 150,
    "마이스터": 140,
}

# 집계에서 항상 제외(레벨 무관). 저급·이벤트성 등 강화 투자 비교에 부적합한 장비.
EXCLUDED_ITEMS: frozenset[str] = frozenset(
    {
        "슈피겔만의 평범한 목걸이",
    }
)

# 이 레벨 미만(100 미만) 장비는 집계에서 제외 — 강화 비용 비교에 무의미.
MIN_AGGREGATE_LEVEL = 100

# 정확 일치 시드 — 부위별 레벨이 제각각인 보스 장신구 세트(보스장신구·여명·칠흑·광휘) + 제네시스 무기.
# 레벨은 사용자 제공·넥슨 API 학습값과 교차검증(충돌 0). 세트로 레벨이 고정되는 방어구/마이스터는 위 표가 담당.
EQUIPMENT_LEVEL_SEED: dict[str, int] = {
    # 250 — 광휘의 보스 세트
    "근원의 속삭임": 250,
    "죽음의 맹세": 250,
    "불멸의 유산": 250,
    "황홀한 악몽": 250,
    "오만의 원죄": 250,
    # 200 — 제네시스 무기 · 칠흑의 보스 세트
    "제네시스 라피스": 200,
    "제네시스 라즐리": 200,
    "컴플리트 언더컨트롤": 200,
    "몽환의 벨트": 200,
    "커맨더 포스 이어링": 200,
    "거대한 공포": 200,
    # 160 — 보스 장신구
    "가디언 엔젤 링": 160,
    "에스텔라 이어링": 160,
    "여명의 가디언 엔젤 링": 160,
    "루즈 컨트롤 머신 마크": 160,
    "마력이 깃든 안대": 160,
    "고통의 근원": 160,
    # 150
    "분노한 자쿰의 벨트": 150,
    # 145
    "파풀라투스 마크": 145,
    # 140 — 보스 장신구
    "골든 클로버 벨트": 140,
    "도미네이터 펜던트": 140,
    "트와일라이트 마크": 140,
    "데이브레이크 펜던트": 140,
    # 135
    "블랙빈 마크": 135,
    # 130
    "데아 시두스 이어링": 130,
    "지옥의 불꽃": 130,
    # 120
    "혼테일의 목걸이": 120,
    "카오스 혼테일의 목걸이": 120,
    "매커네이터 펜던트": 120,
    "고귀한 이피아의 반지": 120,
    "로얄 블랙메탈 숄더": 120,
    # 110
    "응축된 힘의 결정석": 110,
    "실버블라썸 링": 110,
    # 100
    "아쿠아틱 레터 눈장식": 100,
}


def _set_level(target_item: str) -> int | None:
    """아이템명에 세트명이 포함되면 그 세트의 고정 레벨(무조건). 없으면 None."""
    for set_name, level in EQUIPMENT_SET_LEVEL.items():
        if set_name in target_item:
            return level
    return None


def match_level(
    target_item: str,
    equipped: dict[str, int],
    seed: dict[str, int] = EQUIPMENT_LEVEL_SEED,
) -> int | None:
    """세트명(무조건) → 현재 장착/학습 → 시드 → None. 순수함수."""
    set_level = _set_level(target_item)
    if set_level is not None:
        return set_level
    level = equipped.get(target_item)
    if level is not None:
        return level
    return seed.get(target_item)


async def fetch_equipped_levels(nexon: NexonClient, ocid: str) -> dict[str, int]:
    """character/item-equipment → {item_name: base_equipment_level}. (A) 소스.

    레벨이 없는(또는 비정상) 항목은 건너뛴다. 같은 이름 중복 시 마지막 값(현 장착 1셋이라 무관).
    """
    data = await nexon.character_item_equipment(ocid)
    levels: dict[str, int] = {}
    for item in data.get("item_equipment") or []:
        name = item.get("item_name")
        base = (item.get("item_base_option") or {}).get("base_equipment_level")
        if name and isinstance(base, int):
            levels[name] = base
    return levels


async def load_learned_levels(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """학습된 장비명→레벨 전체 로드 (B 소스). 명령당 1회 호출."""
    async with session_factory() as session:
        rows = (await session.execute(select(LearnedEquipmentLevel))).scalars().all()
    return {r.item_name: r.base_equipment_level for r in rows}


async def learn_equipment_levels(
    session_factory: async_sessionmaker[AsyncSession], levels: dict[str, int]
) -> None:
    """관측한 장비명→레벨을 upsert(자동 학습). 레벨은 장비명당 고정이라 최신값으로 덮어쓴다."""
    if not levels:
        return
    async with session_factory() as session:
        for name, level in levels.items():
            stmt = (
                pg_insert(LearnedEquipmentLevel)
                .values(item_name=name, base_equipment_level=level)
                .on_conflict_do_update(
                    index_elements=["item_name"],
                    set_={"base_equipment_level": level, "observed_at": func.now()},
                )
            )
            await session.execute(stmt)
        await session.commit()
