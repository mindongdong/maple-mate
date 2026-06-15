"""대표 해석(pick_representative) 순수함수 단위테스트 (DB 불요).

대표 우선순위(작업지시서): 지정 우선 → 레벨 최고 → created_at 오름차순 → ocid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from maple_mate.registration.service import pick_representative

_BASE = datetime(2026, 6, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Char:
    ocid: str
    level: int | None
    created_at: datetime


def _c(ocid: str, level: int | None, *, days: int = 0) -> _Char:
    return _Char(ocid=ocid, level=level, created_at=_BASE + timedelta(days=days))


def test_empty_returns_none() -> None:
    assert pick_representative([], None) is None
    assert pick_representative([], "anything") is None


def test_manual_representative_wins_even_if_lower_level() -> None:
    chars = [_c("a", 280), _c("b", 200)]
    rep = pick_representative(chars, "b")
    assert rep is not None and rep.ocid == "b"


def test_manual_pointer_to_missing_falls_back_to_highest_level() -> None:
    chars = [_c("a", 280), _c("b", 200)]
    rep = pick_representative(chars, "gone")  # 가리키는 캐릭 부재
    assert rep is not None and rep.ocid == "a"


def test_auto_picks_highest_level() -> None:
    chars = [_c("a", 200), _c("b", 285), _c("c", 100)]
    rep = pick_representative(chars, None)
    assert rep is not None and rep.ocid == "b"


def test_null_level_treated_as_lowest() -> None:
    chars = [_c("a", None), _c("b", 1)]
    rep = pick_representative(chars, None)
    assert rep is not None and rep.ocid == "b"


def test_level_tie_breaks_by_created_at_then_ocid() -> None:
    # 같은 레벨: 먼저 등록(created_at 작은) 우선.
    chars = [_c("late", 250, days=5), _c("early", 250, days=1)]
    rep = pick_representative(chars, None)
    assert rep is not None and rep.ocid == "early"


def test_level_and_created_at_tie_breaks_by_ocid() -> None:
    chars = [_c("zzz", 250, days=1), _c("aaa", 250, days=1)]
    rep = pick_representative(chars, None)
    assert rep is not None and rep.ocid == "aaa"


def test_all_null_levels_tie_breaks_deterministically() -> None:
    chars = [_c("b", None, days=2), _c("a", None, days=1)]
    rep = pick_representative(chars, None)
    assert rep is not None and rep.ocid == "a"  # created_at 더 이른 쪽
