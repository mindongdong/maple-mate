"""`/비틱` 아이템 단위 집계 (순수). discord/http 타입 비의존.

이력류 집계(`history/service.aggregate_starforce`)가 대상 1명을 한 행으로 합치는 것과 달리,
비틱은 **아이템 1개 = 자랑 카드 1장** 단위로 분해한다(작업지시서 빌드 1):

- group_starforce: 이름별 그룹 → 시간순 시작★(첫 before)→끝★(마지막 after) + ★도전 집계
  → 손익(net = 기대 − 실제, 양수=이득) 내림차순. 레벨 미상·슈페리얼은 목록 제외(Q10·파생).
- group_potential: (이름, 레벨) 그룹 → 재설정 횟수(큐브+메소 합산) 내림차순 + 큐브종류 분포
  + 비용(재설정비/감정비 분리) + 종류별(잠재/에디) 시작 등급→끝 등급·옵션 섹션(Q7).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from ..history.expected_cost import actual_meso, expected_meso
from ..history.potential_service import (
    GRADE_ORDER,
    CubeRecord,
    MesoCostModel,
    ResetRecord,
)

# ── 스타포스 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StarforceBitik:
    """아이템 1개의 스타포스 자랑 카드 데이터(Q6 구성)."""

    item: str
    level: int
    start_star: int  # 기간 내 첫 시도의 before_star (파생 결정)
    end_star: int  # 기간 내 마지막 시도의 after_star
    attempt_count: int  # 강화 n번
    destroy_count: int  # 파괴 n번
    actual_meso: int  # 실제 사용 메소(정가, Σcost)
    expected_meso: int  # 구간 기대 메소(끝≤시작이면 0 → 전액 손해)
    net_meso: int  # 기대 − 실제 (양수=이득, 음수=손해)
    challenge_star: int  # 도전성 = max(before_star) + 1
    challenge_success: int  # before==max 시도의 성공 수
    challenge_fail: int  # before==max 시도의 실패(유지/하락/파괴) 수


@dataclass(frozen=True)
class ExcludedItems:
    """목록 제외 아이템(Q10·슈페리얼 파생). unmatched 만 error_log 제보 대상."""

    unmatched: tuple[str, ...]  # 레벨 미상(미장착·파괴·판매)
    superior: tuple[str, ...]  # 슈페리얼(확률표·비용공식 상이)

    @property
    def count(self) -> int:
        return len(self.unmatched) + len(self.superior)


def _sort_key(date_create: str) -> tuple:
    """시간순 정렬 키. ISO 파싱 실패 시 원문 문자열로 폴백(history.service 와 동일 규약)."""
    try:
        return (0, datetime.fromisoformat(date_create))
    except ValueError:
        return (1, date_create)


def group_starforce(
    attempts: Sequence,  # Sequence[StarforceAttempt]
    level_of: Callable[[str], int | None],
) -> tuple[list[StarforceBitik], ExcludedItems]:
    """이름별 그룹 → 시작/끝/도전 집계 → net 내림차순. 제외(레벨 미상·슈페리얼) 분리.

    동명 장비 2개는 한 그룹으로 병합된다(개체 ID 부재 — 알려진 제약, 작업지시서 잔류 리스크).
    """
    by_item: dict[str, list] = {}
    for a in attempts:
        by_item.setdefault(a.target_item, []).append(a)

    bitiks: list[StarforceBitik] = []
    unmatched: list[str] = []
    superior: list[str] = []
    for item, item_attempts in by_item.items():
        if any(a.superior for a in item_attempts):
            superior.append(item)
            continue
        level = level_of(item)
        if level is None:
            unmatched.append(item)
            continue
        ordered = sorted(item_attempts, key=lambda a: _sort_key(a.date_create))
        start_star = ordered[0].before_star
        end_star = ordered[-1].after_star

        challenge_star = max(a.before_star for a in ordered) + 1
        challengers = [a for a in ordered if a.before_star == challenge_star - 1]
        success = sum(1 for a in challengers if a.result == "성공")

        actual = actual_meso(level, [a.before_star for a in ordered])
        # 끝≤시작이면 expected_meso 가 0 → net = −actual (전액 손해, 분기 불필요).
        expected = round(expected_meso(level, start_star, end_star))
        bitiks.append(
            StarforceBitik(
                item=item,
                level=level,
                start_star=start_star,
                end_star=end_star,
                attempt_count=len(ordered),
                destroy_count=sum(1 for a in ordered if a.result == "파괴"),
                actual_meso=actual,
                expected_meso=expected,
                net_meso=expected - actual,
                challenge_star=challenge_star,
                challenge_success=success,
                challenge_fail=len(challengers) - success,
            )
        )

    bitiks.sort(key=lambda b: b.net_meso, reverse=True)
    return bitiks, ExcludedItems(unmatched=tuple(unmatched), superior=tuple(superior))


# ── 잠재 ───────────────────────────────────────────────────────────────────

POTENTIAL_KIND = "잠재능력"
ADDITIONAL_KIND = "에디셔널 잠재능력"


@dataclass(frozen=True)
class PotentialSection:
    """종류(잠재/에디) 1개의 시작→끝 진행(Q7: 시작=등급만, 끝=등급+옵션 풀표시)."""

    kind: str  # POTENTIAL_KIND / ADDITIONAL_KIND
    start_grade: str  # 첫 레코드의 before 최고 등급(미상이면 "")
    end_grade: str  # 마지막 레코드의 after 최고 등급
    end_options: tuple[str, ...]  # 마지막 레코드의 after 옵션 텍스트(보통 3줄)


@dataclass(frozen=True)
class PotentialBitik:
    """아이템 1개의 잠재 자랑 카드 데이터."""

    item: str
    item_level: int
    reset_count: int  # 큐브 + 메소 재설정 합산(정렬 기준)
    cube_counts: tuple[tuple[str, int], ...]  # (큐브종류, 횟수) 내림차순
    meso_reset_count: int
    reset_meso: int  # 메소 재설정비 합(본문)
    appraisal_meso: int  # 큐브 감정비 합(별도 줄 "+ 감정 n 메소")
    sections: tuple[PotentialSection, ...]  # 기록 있는 종류만(잠재 → 에디 순)


def _top_grade(grades: tuple[str, ...]) -> str:
    """등급 목록의 최고 등급. 알 수 없으면 ""(potential_service._from_grade 와 동일 규약)."""
    valid = [g for g in grades if g in GRADE_ORDER]
    if not valid:
        return ""
    return max(valid, key=lambda g: GRADE_ORDER[g])


def _kind_of(record: CubeRecord | ResetRecord) -> str:
    """레코드가 굴린 잠재 종류. 큐브는 cube_type, 메소 재설정은 potential_type 으로 판정."""
    label = (
        record.cube_type if isinstance(record, CubeRecord) else record.potential_type
    )
    return ADDITIONAL_KIND if "에디" in label else POTENTIAL_KIND


def _section(kind: str, records: list[CubeRecord | ResetRecord]) -> PotentialSection:
    """종류 1개 섹션: 첫 레코드 before 등급 → 마지막 레코드 after 등급+옵션."""
    first, last = records[0], records[-1]
    if kind == ADDITIONAL_KIND:
        start = _top_grade(first.before_add) or first.add_grade
        end = _top_grade(last.after_add) or last.add_grade
        options = last.after_add_values
    else:
        start = _top_grade(first.before_pot) or first.pot_grade
        end = _top_grade(last.after_pot) or last.pot_grade
        options = last.after_pot_values
    return PotentialSection(
        kind=kind, start_grade=start, end_grade=end, end_options=options
    )


def _reset_cost_grade(r: ResetRecord) -> str:
    """재설정 단가 기준 등급 = 재설정 시점(before) 최고 등급, 비면 현재 등급 폴백."""
    if "에디" in r.potential_type:
        return _top_grade(r.before_add) or r.add_grade
    return _top_grade(r.before_pot) or r.pot_grade


def group_potential(
    cubes: Sequence[CubeRecord],
    resets: Sequence[ResetRecord],
    *,
    cost: MesoCostModel,
) -> list[PotentialBitik]:
    """(이름, 레벨) 그룹 → 재설정 횟수 내림차순. 비용·큐브 분포·섹션 포함(순수)."""
    by_item: dict[tuple[str, int], list[CubeRecord | ResetRecord]] = {}
    for rec in (*cubes, *resets):
        by_item.setdefault((rec.target_item, rec.item_level), []).append(rec)

    bitiks: list[PotentialBitik] = []
    for (item, level), records in by_item.items():
        ordered = sorted(records, key=lambda r: _sort_key(r.date_create))
        item_cubes = [r for r in ordered if isinstance(r, CubeRecord)]
        item_resets = [r for r in ordered if isinstance(r, ResetRecord)]

        cube_types: Counter[str] = Counter(
            c.cube_type for c in item_cubes if c.cube_type
        )

        by_kind: dict[str, list[CubeRecord | ResetRecord]] = {}
        for rec in ordered:
            by_kind.setdefault(_kind_of(rec), []).append(rec)
        sections = tuple(
            _section(kind, by_kind[kind])
            for kind in (POTENTIAL_KIND, ADDITIONAL_KIND)
            if kind in by_kind
        )

        bitiks.append(
            PotentialBitik(
                item=item,
                item_level=level,
                reset_count=len(ordered),
                cube_counts=tuple(cube_types.most_common()),
                meso_reset_count=len(item_resets),
                reset_meso=sum(
                    cost.reset_cost(
                        r.item_level, _reset_cost_grade(r), r.potential_type
                    )
                    for r in item_resets
                ),
                appraisal_meso=sum(
                    cost.appraisal_cost(c.item_level) for c in item_cubes
                ),
                sections=sections,
            )
        )

    bitiks.sort(key=lambda b: b.reset_count, reverse=True)
    return bitiks
