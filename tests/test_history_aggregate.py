"""캐릭터 필터·결과 파싱·아이템별 집계(시작/최종★·matched/total) 단위테스트."""
from __future__ import annotations

import pytest

from maple_mate.history.expected_cost import expected_meso
from maple_mate.history.service import (
    StarforceAttempt,
    aggregate_starforce,
    parse_attempts,
)


def _record(name: str, before: int, after: int, result: str, when: str) -> dict:
    return {
        "character_name": name,
        "before_starforce_count": before,
        "after_starforce_count": after,
        "item_upgrade_result": result,
        "target_item": "하이네스 워리어헬름",
        "date_create": when,
    }


# ── parse_attempts: 캐릭터 필터 + 결과 파싱 ────────────────────────────────


def test_parse_attempts_filters_by_character_name() -> None:
    records = [
        _record("손바", 19, 19, "실패(유지)", "2026-05-31T17:46:44+09:00"),
        _record("부캐", 10, 11, "성공", "2026-05-31T18:00:00+09:00"),
    ]
    attempts = parse_attempts(records, "손바")
    assert len(attempts) == 1
    assert attempts[0].before_star == 19
    assert attempts[0].result == "실패(유지)"


def test_parse_attempts_keeps_result_suffix_variants() -> None:
    records = [
        _record("손바", 19, 19, "실패(유지)", "2026-05-31T17:00:00+09:00"),
        _record("손바", 22, 12, "파괴", "2026-05-31T17:01:00+09:00"),
        _record("손바", 12, 11, "실패(하락)", "2026-05-31T17:02:00+09:00"),
        _record("손바", 11, 12, "성공", "2026-05-31T17:03:00+09:00"),
    ]
    results = [a.result for a in parse_attempts(records, "손바")]
    assert results == ["실패(유지)", "파괴", "실패(하락)", "성공"]


def test_parse_attempts_empty_when_no_match() -> None:
    records = [_record("다른캐릭", 0, 1, "성공", "2026-05-31T17:00:00+09:00")]
    assert parse_attempts(records, "손바") == []


# ── aggregate_starforce: 시작/최종★ · matched/total · 운지수 ────────────────


def _attempt(item: str, before: int, after: int, when: str, *, success: bool = True) -> StarforceAttempt:
    return StarforceAttempt(
        target_item=item,
        before_star=before,
        after_star=after,
        result="성공" if success else "실패(유지)",
        date_create=when,
    )


def test_aggregate_start_and_final_star() -> None:
    attempts = [
        _attempt("itemA", 0, 1, "2026-05-01T10:00:00+09:00"),
        _attempt("itemA", 1, 2, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(attempts, lambda item: 200 if item == "itemA" else None)
    # 시작★=0, 최종★=2 → expected = 누적 0→2.
    assert summary.expected == pytest.approx(expected_meso(200, 0, 2))
    # 총 사용 메소 = cost(200,0)+cost(200,1).
    assert summary.total_meso == 223_200 + 445_400
    assert summary.matched_count == 2
    assert summary.total_count == 2
    assert summary.unmatched_items == ()
    # 2시도로 2★ 도달(최소 비용) → 메소 운빨은 평균(50) 이상.
    assert summary.luck_score is not None and summary.luck_score > 50


def test_aggregate_start_star_is_earliest_chronologically() -> None:
    # 입력 순서가 뒤섞여 있어도 시작★ = 가장 이른 시각의 before_star.
    attempts = [
        _attempt("itemA", 5, 6, "2026-05-02T10:00:00+09:00"),
        _attempt("itemA", 3, 4, "2026-05-01T10:00:00+09:00"),  # 가장 이른
    ]
    summary = aggregate_starforce(attempts, lambda item: 200)
    # 시작★=3, 최종★=6.
    assert summary.expected == pytest.approx(expected_meso(200, 3, 6))


def test_aggregate_final_star_is_max_after_ignoring_destruction_dip() -> None:
    # 파괴로 after 가 12로 떨어져도 최종★ = 기간 내 최고 after.
    attempts = [
        _attempt("itemA", 17, 18, "2026-05-01T10:00:00+09:00"),
        _attempt("itemA", 18, 12, "2026-05-01T11:00:00+09:00"),  # 파괴
    ]
    summary = aggregate_starforce(attempts, lambda item: 200)
    assert summary.expected == pytest.approx(expected_meso(200, 17, 18))


def test_aggregate_unmatched_item_excluded_but_counted_in_total() -> None:
    attempts = [
        _attempt("matched", 0, 1, "2026-05-01T10:00:00+09:00"),
        _attempt("unknown", 0, 1, "2026-05-01T10:00:00+09:00"),
        _attempt("unknown", 1, 2, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(attempts, lambda item: 200 if item == "matched" else None)
    assert summary.matched_count == 1
    assert summary.total_count == 3
    assert summary.unmatched_items == ("unknown",)


def test_aggregate_all_unmatched_has_no_meso_and_no_luck() -> None:
    # 메소 운빨은 레벨 매칭 아이템 기반 → 전부 미매칭이면 None(메소도 0).
    attempts = [_attempt("unknown", 0, 1, "2026-05-01T10:00:00+09:00")]
    summary = aggregate_starforce(attempts, lambda item: None)
    assert summary.total_meso == 0
    assert summary.expected == 0.0
    assert summary.matched_count == 0
    assert summary.unmatched_items == ("unknown",)
    assert summary.luck_score is None  # 매칭 아이템 0 → 메소 운빨 산출 불가


def test_aggregate_excludes_listed_items() -> None:
    # 명시적 제외 장비(슈피겔만의 평범한 목걸이)는 집계·분모·제보에서 통째로 빠진다(미상과 구분).
    attempts = [
        _attempt("matched", 0, 1, "2026-05-01T10:00:00+09:00"),
        _attempt("슈피겔만의 평범한 목걸이", 0, 1, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(attempts, lambda item: 200 if item == "matched" else None)
    assert summary.matched_count == 1
    assert summary.total_count == 1  # 제외분은 분모에서도 빠짐(2가 아님)
    assert summary.unmatched_items == ()  # 미상으로 제보되지 않음


def test_aggregate_excludes_below_min_level() -> None:
    # 100 미만 레벨 장비는 집계에서 통째로 제외(분모·제보 포함).
    attempts = [
        _attempt("matched", 0, 1, "2026-05-01T10:00:00+09:00"),
        _attempt("저레벨", 0, 5, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(attempts, lambda item: 200 if item == "matched" else 80)
    assert summary.matched_count == 1
    assert summary.total_count == 1
    assert summary.unmatched_items == ()


def test_aggregate_level_100_is_included() -> None:
    # 경계: 정확히 100 레벨은 포함(미만이 아님).
    attempts = [_attempt("백제장비", 0, 1, "2026-05-01T10:00:00+09:00")]
    summary = aggregate_starforce(attempts, lambda item: 100)
    assert summary.matched_count == 1
    assert summary.total_count == 1


def test_aggregate_luck_uses_matched_items_only() -> None:
    # 운빨·메소 모두 레벨 매칭 아이템만 — 미매칭 아이템은 양쪽에서 제외(손익과 동일 기준).
    matched_only = [_attempt("matched", 0, 2, "2026-05-01T10:00:00+09:00")]
    with_unmatched = matched_only + [
        _attempt("unknown", 14, 14, "2026-05-01T11:00:00+09:00"),
    ]
    lv = lambda item: 200 if item == "matched" else None  # noqa: E731
    s1 = aggregate_starforce(matched_only, lv)
    s2 = aggregate_starforce(with_unmatched, lv)
    # 미매칭을 추가해도 운빨은 동일(매칭 아이템만 반영). total_count만 증가.
    assert s1.luck_score == s2.luck_score
    assert s2.matched_count == 1 and s2.total_count == 2
    assert s2.unmatched_items == ("unknown",)
