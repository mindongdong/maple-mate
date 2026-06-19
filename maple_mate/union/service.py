"""유니온 조회 + 변환 (전달-무관). `/유니온`: 레벨 + 아티팩트 레벨 + 챔피언 등급분포.

Spike 0(handoff §3.4): champion_grade 관측값 = "SSS","S" 등. 등급 문자열을 **그대로** 집계
(하드코딩 매핑 금지 — 등장하는 값을 센다). 표시 순서만 알려진 등급 순서로 정렬한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..nexon.client import KST, NexonClient
from ..nexon.errors import ErrorClass, NexonAPIError

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


async def _union_latest(nexon: NexonClient, ocid: str, now: datetime) -> dict:
    """user/union 최신값을 **명시적 D-1(KST)** 로 가져온다(미준비면 D-2 폴백).

    ⚠️ 넥슨이 user/union 의 date 무지정(=최신) 호출을 2026-06 업데이트 이후 일부 캐릭터에
    대해 200 + 전부 null 로 회귀시켰다(실측: 손바·라딘라면). date 를 명시하면 정상 반환되므로
    항상 D-1 을 넘긴다. 오늘/미래 date 는 OPENAPI00004 로 거부되고(전일 데이터는 익일 02시부터),
    새벽 0~2시엔 D-1 이 아직 미생성일 수 있어 그 경우 D-2 로 1회 폴백한다.

    - 그 날짜만 미준비/무효(DATA_NOT_READY·INVALID_PARAM)면 하루 더 과거로 폴백.
    - 잘못된 ocid(INVALID_ID)·장애 등 하드 에러는 그대로 raise → 호출자(_fetch_one)가
      닉 재조회/실패 처리. (INVALID_PARAM 을 여기서 흡수하지 않으면 stale ocid 로 오분류된다.)
    - D-1·D-2 모두 200 이지만 null 이면(특수 직업군 등 유니온 데이터 없음) 마지막 응답을
      그대로 돌려 빈칸으로 렌더한다.
    """
    d1 = now.astimezone(KST).date() - timedelta(days=1)
    latest: dict | None = None
    last_exc: NexonAPIError | None = None
    for day in (d1, d1 - timedelta(days=1)):
        try:
            latest = await nexon.union(ocid, date=day.isoformat())
        except NexonAPIError as exc:
            if exc.error_class in (ErrorClass.DATA_NOT_READY, ErrorClass.INVALID_PARAM):
                last_exc = exc
                continue
            raise
        if latest.get("union_level") is not None:
            return latest
    if latest is not None:
        return latest
    raise last_exc  # type: ignore[misc]  # 두 날짜 모두 미준비 → DATA_NOT_READY 등으로 전파


async def fetch_union(
    nexon: NexonClient, ocid: str, now: datetime | None = None
) -> UnionInfo:
    """user/union(명시적 D-1) + union-champion(최신) 조합.

    아티팩트 '레벨'은 user/union 응답의 `union_artifact_level` 에 있다(docs/api/union.md §user/union).
    union-artifact 엔드포인트는 효과/크리스탈/잔여 AP 만 반환하고 레벨은 없으므로, 불필요한 호출을
    피하려 union 응답에서 직접 읽는다(필요 항목: 레벨 + 아티팩트 레벨 + 챔피언 분포 — design §3.3).

    union 은 date 무지정이 깨져 D-1 명시로 호출하지만(_union_latest), union-champion 은 date
    무지정이 정상이라 그대로 둔다(영향 범위 = user/union 단일 엔드포인트, 실측).
    """
    union = await _union_latest(nexon, ocid, now or datetime.now(KST))
    champion = await nexon.union_champion(ocid)

    counts = count_champion_grades(champion.get("union_champion"))
    return UnionInfo(
        union_level=union.get("union_level"),
        union_grade=union.get("union_grade"),
        artifact_level=union.get("union_artifact_level"),
        champion_grades=tuple(order_grades(counts)),
        date=union.get("date"),
    )
