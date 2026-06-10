"""유니온 조회 + 변환 (전달-무관). `/유니온`: 레벨 + 아티팩트 레벨 + 챔피언 등급분포.

Spike 0(handoff §3.4): champion_grade 관측값 = "SSS","S" 등. 등급 문자열을 **그대로** 집계
(하드코딩 매핑 금지 — 등장하는 값을 센다). 표시 순서만 알려진 등급 순서로 정렬한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..nexon.client import NexonClient

# 표시 순서(정렬 전용). 새 등급이 등장하면 알 수 없는 값으로 뒤에 알파벳순 붙는다 — 집계 자체는
# 관측값 기준이라 이 목록에 없어도 카운트된다.
_GRADE_ORDER = ("SSS", "SS", "S", "A", "B", "C", "D")


@dataclass(frozen=True)
class UnionInfo:
    union_level: int | None
    union_grade: str | None
    artifact_level: int | None
    champion_grades: tuple[tuple[str, int], ...]  # (등급, 개수) — 표시 순서 정렬됨
    date: str | None  # 넥슨 응답 date(무지정 호출은 null) → 푸터용


def count_champion_grades(union_champion: list[dict] | None) -> dict[str, int]:
    """union_champion[].champion_grade 등장값 집계(순수함수). 빈 입력 → {}."""
    counts: dict[str, int] = {}
    for champ in union_champion or []:
        grade = champ.get("champion_grade")
        if grade:
            counts[grade] = counts.get(grade, 0) + 1
    return counts


def order_grades(counts: dict[str, int]) -> list[tuple[str, int]]:
    """등급 카운트를 표시 순서로 정렬(순수함수). 알려진 순서 먼저, 미지 등급은 알파벳순 뒤로."""
    known = [(g, counts[g]) for g in _GRADE_ORDER if g in counts]
    unknown = sorted((g, c) for g, c in counts.items() if g not in _GRADE_ORDER)
    return known + unknown


async def fetch_union(nexon: NexonClient, ocid: str) -> UnionInfo:
    """user/union + union-champion 조합 (date 무지정=최신).

    아티팩트 '레벨'은 user/union 응답의 `union_artifact_level` 에 있다(docs/api/union.md §user/union).
    union-artifact 엔드포인트는 효과/크리스탈/잔여 AP 만 반환하고 레벨은 없으므로, 불필요한 호출을
    피하려 union 응답에서 직접 읽는다(필요 항목: 레벨 + 아티팩트 레벨 + 챔피언 분포 — design §3.3).
    """
    union = await nexon.union(ocid)
    champion = await nexon.union_champion(ocid)

    counts = count_champion_grades(champion.get("union_champion"))
    return UnionInfo(
        union_level=union.get("union_level"),
        union_grade=union.get("union_grade"),
        artifact_level=union.get("union_artifact_level"),
        champion_grades=tuple(order_grades(counts)),
        date=union.get("date"),
    )
