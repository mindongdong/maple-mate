"""대표 해석(pick_representative) 순수함수 단위테스트 (DB 불요).

대표 우선순위(작업지시서): 지정 우선 → 레벨 최고 → created_at 오름차순 → ocid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from maple_mate.registration.realm import Realm
from maple_mate.registration.service import pick_representative

_BASE = datetime(2026, 6, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Char:
    ocid: str
    level: int | None
    created_at: datetime
    world: str | None = None


def _c(
    ocid: str, level: int | None, *, days: int = 0, world: str | None = None
) -> _Char:
    return _Char(
        ocid=ocid, level=level, created_at=_BASE + timedelta(days=days), world=world
    )


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


# ── realm 인지 해석 (결정 4, ADR-0009) ─────────────────────────────────────


def test_main_realm_excludes_challengers() -> None:
    # 본서버 모드는 챌린저스 캐릭터를 후보에서 배제(핵심 불변식: 누수 0).
    chars = [_c("main", 287, world="스카니아"), _c("chal", 260, world="챌린저스3")]
    rep = pick_representative(chars, None, Realm.MAIN)
    assert rep is not None and rep.ocid == "main"


def test_challengers_realm_only_challengers() -> None:
    chars = [_c("main", 287, world="스카니아"), _c("chal", 260, world="챌린저스3")]
    rep = pick_representative(chars, None, Realm.CHALLENGERS)
    assert rep is not None and rep.ocid == "chal"


def test_legacy_null_world_counts_as_main() -> None:
    chars = [_c("legacy", 200, world=None), _c("chal", 260, world="챌린저스3")]
    assert pick_representative(chars, None, Realm.MAIN).ocid == "legacy"
    assert pick_representative(chars, None, Realm.CHALLENGERS).ocid == "chal"


def test_manual_pin_only_effective_in_its_realm() -> None:
    # 핀이 본서버 캐릭터를 가리켜도, 챌린저스 모드에선 무시되고 챌린저스 자동 대표가 된다.
    chars = [
        _c("main", 200, world="스카니아"),
        _c("chalA", 260, days=1, world="챌린저스3"),
        _c("chalB", 250, days=2, world="챌린저스3"),
    ]
    # 본서버 핀("main") → 챌린저스 모드에선 무시 → 챌린저스 최고레벨(chalA).
    assert pick_representative(chars, "main", Realm.CHALLENGERS).ocid == "chalA"
    # 본서버 모드에선 핀("main")이 효력.
    assert pick_representative(chars, "main", Realm.MAIN).ocid == "main"


def test_no_character_in_realm_returns_none() -> None:
    # 본서버 캐릭터만 있는 유저는 챌린저스 모드에서 대상 제외(None).
    chars = [_c("main", 287, world="스카니아")]
    assert pick_representative(chars, None, Realm.CHALLENGERS) is None


def test_challengers_pin_within_realm_wins() -> None:
    chars = [
        _c("chalA", 260, days=1, world="챌린저스3"),
        _c("chalB", 250, days=2, world="챌린저스3"),
    ]
    # 챌린저스 핀이 챌린저스 캐릭터를 가리키면 레벨 낮아도 효력.
    assert pick_representative(chars, "chalB", Realm.CHALLENGERS).ocid == "chalB"
