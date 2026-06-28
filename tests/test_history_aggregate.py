"""캐릭터 필터·결과 파싱·아이템별 집계(시작/최종★·matched/total) 단위테스트."""

from __future__ import annotations

import pytest

from maple_mate.history.expected_cost import expected_meso
from maple_mate.history.service import (
    StarforceAttempt,
    _event_masks,
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


# ── parse_attempts: 계정 전체(닉 필터 없음) + 결과 파싱 ─────────────────────


def test_parse_attempts_returns_all_with_character_name() -> None:
    # 계정 전체화 — 닉 필터 없이 전 캐릭터 반환, character_name 보존(집계 그룹 키).
    records = [
        _record("손바", 19, 19, "실패(유지)", "2026-05-31T17:46:44+09:00"),
        _record("부캐", 10, 11, "성공", "2026-05-31T18:00:00+09:00"),
    ]
    attempts = parse_attempts(records)
    assert len(attempts) == 2
    assert {a.character_name for a in attempts} == {"손바", "부캐"}


def test_parse_attempts_keeps_result_suffix_variants() -> None:
    records = [
        _record("손바", 19, 19, "실패(유지)", "2026-05-31T17:00:00+09:00"),
        _record("손바", 22, 12, "파괴", "2026-05-31T17:01:00+09:00"),
        _record("손바", 12, 11, "실패(하락)", "2026-05-31T17:02:00+09:00"),
        _record("손바", 11, 12, "성공", "2026-05-31T17:03:00+09:00"),
    ]
    results = [a.result for a in parse_attempts(records)]
    assert results == ["실패(유지)", "파괴", "실패(하락)", "성공"]


def test_parse_attempts_preserves_all_characters() -> None:
    records = [_record("다른캐릭", 0, 1, "성공", "2026-05-31T17:00:00+09:00")]
    attempts = parse_attempts(records)
    assert len(attempts) == 1
    assert attempts[0].character_name == "다른캐릭"


def test_parse_attempts_parses_event_flags_in_range() -> None:
    # 파괴감소·할인이 별 객체로 분리되며, 이 시도의 before_star 가 범위에 들면 적용(ADR-0016).
    rec = _record("손바", 17, 18, "성공", "2026-05-31T17:00:00+09:00")
    rec["starforce_event_list"] = [
        {
            "destroy_decrease_rate": "30",
            "starforce_event_range": "15,16,17,18,19,20,21",
        },
        {"cost_discount_rate": "30", "starforce_event_range": "0~29"},
    ]
    a = parse_attempts([rec])[0]
    assert a.destroy_reduced is True  # 17 ∈ 15~21
    assert a.cost_discount is True  # 17 ∈ 0~29


def test_parse_attempts_event_out_of_range_not_applied() -> None:
    rec = _record("손바", 22, 23, "성공", "2026-05-31T17:00:00+09:00")
    rec["starforce_event_list"] = [
        {
            "destroy_decrease_rate": "30",
            "starforce_event_range": "15,16,17,18,19,20,21",
        },
    ]
    a = parse_attempts([rec])[0]
    assert a.destroy_reduced is False  # 22 ∉ 15~21


def test_parse_attempts_guards_non_list_event_list() -> None:
    # 빈 배열·null·비배열 모두 미적용으로 폴백(실측 가드).
    for bad in ([], None, "이상값", 0):
        rec = _record("손바", 17, 18, "성공", "2026-05-31T17:00:00+09:00")
        rec["starforce_event_list"] = bad
        a = parse_attempts([rec])[0]
        assert a.destroy_reduced is False and a.cost_discount is False


# ── aggregate_starforce: 시작/최종★ · matched/total · 운지수 ────────────────


def _attempt(
    item: str, before: int, after: int, when: str, *, success: bool = True
) -> StarforceAttempt:
    return StarforceAttempt(
        target_item=item,
        before_star=before,
        after_star=after,
        result="성공" if success else "실패(유지)",
        date_create=when,
    )


def test_aggregate_groups_same_item_by_character() -> None:
    # 계정 전체화: 동명 장비라도 캐릭터가 다르면 별도 그룹 — 시작/최종★ 병합 안 됨(버그 차단).
    attempts = [
        StarforceAttempt(
            target_item="재사용장비",
            before_star=11,
            after_star=12,
            result="성공",
            date_create="2026-05-01T10:00:00+09:00",
            character_name="본캐",
        ),
        StarforceAttempt(
            target_item="재사용장비",
            before_star=13,
            after_star=14,
            result="성공",
            date_create="2026-05-01T11:00:00+09:00",
            character_name="부캐",
        ),
    ]
    summary = aggregate_starforce(attempts, lambda item: 200)
    # 그룹이 합쳐지면 시작11→최종14(과대). 캐릭터별 분리면 (11→12)+(13→14).
    assert summary.expected == pytest.approx(
        expected_meso(200, 11, 12) + expected_meso(200, 13, 14)
    )
    assert summary.matched_count == 2


def test_aggregate_start_and_final_star() -> None:
    attempts = [
        _attempt("itemA", 11, 12, "2026-05-01T10:00:00+09:00"),
        _attempt("itemA", 12, 13, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(
        attempts, lambda item: 200 if item == "itemA" else None
    )
    # 시작★=11, 최종★=13 → expected = 누적 11→13.
    assert summary.expected == pytest.approx(expected_meso(200, 11, 13))
    # 총 사용 메소 = cost(200,11)+cost(200,12).
    assert summary.total_meso == 20_891_500 + 38_048_200
    assert summary.matched_count == 2
    assert summary.total_count == 2
    assert summary.unmatched_items == ()
    # 2시도로 2★ 도달(최소 비용) → 메소 운빨은 평균(50) 이상.
    assert summary.luck_score is not None and summary.luck_score > 50


def test_aggregate_start_star_is_earliest_chronologically() -> None:
    # 입력 순서가 뒤섞여 있어도 시작★ = 가장 이른 시각의 before_star.
    attempts = [
        _attempt("itemA", 16, 17, "2026-05-02T10:00:00+09:00"),
        _attempt("itemA", 14, 15, "2026-05-01T10:00:00+09:00"),  # 가장 이른
    ]
    summary = aggregate_starforce(attempts, lambda item: 200)
    # 시작★=14, 최종★=17.
    assert summary.expected == pytest.approx(expected_meso(200, 14, 17))


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
        _attempt("matched", 11, 12, "2026-05-01T10:00:00+09:00"),
        _attempt("unknown", 11, 12, "2026-05-01T10:00:00+09:00"),
        _attempt("unknown", 12, 13, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(
        attempts, lambda item: 200 if item == "matched" else None
    )
    assert summary.matched_count == 1
    assert summary.total_count == 3
    assert summary.unmatched_items == ("unknown",)


def test_aggregate_all_unmatched_has_no_meso_and_no_luck() -> None:
    # 메소 운빨은 레벨 매칭 아이템 기반 → 전부 미매칭이면 None(메소도 0).
    attempts = [_attempt("unknown", 11, 12, "2026-05-01T10:00:00+09:00")]
    summary = aggregate_starforce(attempts, lambda item: None)
    assert summary.total_meso == 0
    assert summary.expected == 0.0
    assert summary.matched_count == 0
    assert summary.unmatched_items == ("unknown",)
    assert summary.luck_score is None  # 매칭 아이템 0 → 메소 운빨 산출 불가


def test_aggregate_excludes_listed_items() -> None:
    # 명시적 제외 장비(슈피겔만의 평범한 목걸이)는 집계·분모·제보에서 통째로 빠진다(미상과 구분).
    attempts = [
        _attempt("matched", 11, 12, "2026-05-01T10:00:00+09:00"),
        _attempt("슈피겔만의 평범한 목걸이", 11, 12, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(
        attempts, lambda item: 200 if item == "matched" else None
    )
    assert summary.matched_count == 1
    assert summary.total_count == 1  # 제외분은 분모에서도 빠짐(2가 아님)
    assert summary.unmatched_items == ()  # 미상으로 제보되지 않음


def test_aggregate_excludes_below_min_level() -> None:
    # 100 미만 레벨 장비는 집계에서 통째로 제외(분모·제보 포함).
    attempts = [
        _attempt("matched", 11, 12, "2026-05-01T10:00:00+09:00"),
        _attempt("저레벨", 11, 12, "2026-05-01T11:00:00+09:00"),
    ]
    summary = aggregate_starforce(
        attempts, lambda item: 200 if item == "matched" else 80
    )
    assert summary.matched_count == 1
    assert summary.total_count == 1
    assert summary.unmatched_items == ()


def test_aggregate_level_100_is_included() -> None:
    # 경계: 정확히 100 레벨은 포함(미만이 아님).
    attempts = [_attempt("백제장비", 11, 12, "2026-05-01T10:00:00+09:00")]
    summary = aggregate_starforce(attempts, lambda item: 100)
    assert summary.matched_count == 1
    assert summary.total_count == 1


def test_aggregate_luck_uses_matched_items_only() -> None:
    # 운빨·메소 모두 레벨 매칭 아이템만 — 미매칭 아이템은 양쪽에서 제외(손익과 동일 기준).
    matched_only = [_attempt("matched", 11, 13, "2026-05-01T10:00:00+09:00")]
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


# ── 10성 필터 · 이벤트 마스크 · 실지불 (ADR-0016) ──────────────────────────


def test_aggregate_excludes_below_10_star() -> None:
    # 10성 미만 시도는 통째로 제외, 10→11(before=10)부터 집계. 경계: 9→10 제외 / 10→11 포함.
    attempts = [
        _attempt("itemA", 8, 9, "2026-05-01T10:00:00+09:00"),  # before 8 <10 제외
        _attempt(
            "itemA", 9, 10, "2026-05-01T11:00:00+09:00"
        ),  # before 9 <10 제외(9→10)
        _attempt("itemA", 10, 11, "2026-05-01T12:00:00+09:00"),  # before 10 포함(10→11)
        _attempt("itemA", 11, 12, "2026-05-01T13:00:00+09:00"),  # 포함
    ]
    summary = aggregate_starforce(attempts, lambda item: 200)
    assert summary.matched_count == 2  # 10→11, 11→12
    assert summary.total_count == 2
    # 시작★=10(필터 후 첫·가장 이른), 최종★=12.
    assert summary.expected == pytest.approx(expected_meso(200, 10, 12))


def test_aggregate_all_below_10_star_is_empty() -> None:
    # 저성만 강화(9→10 포함) → 집계 대상 0(기록없음 분기는 커맨드 계층에서 처리).
    attempts = [
        _attempt("itemA", 0, 1, "2026-05-01T10:00:00+09:00"),
        _attempt("itemA", 9, 10, "2026-05-01T11:00:00+09:00"),  # 9→10 도 제외
    ]
    summary = aggregate_starforce(attempts, lambda item: 200)
    assert summary.matched_count == 0 and summary.total_count == 0
    assert summary.total_meso == 0
    assert summary.luck_score is None


def test_aggregate_unmatched_only_includes_10_star_items() -> None:
    # 10성 미만 미상은 필터로 진입 차단, 10성+ 미상만 unmatched 에 담긴다(시드 보강 신호).
    attempts = [
        _attempt(
            "저성미상", 0, 1, "2026-05-01T10:00:00+09:00"
        ),  # <10 → 미상 제보 안 됨
        _attempt("고성미상", 15, 16, "2026-05-01T11:00:00+09:00"),  # 10+ 미상 → 제보
    ]
    summary = aggregate_starforce(attempts, lambda item: None)
    assert summary.unmatched_items == ("고성미상",)
    assert summary.total_count == 1  # 저성미상은 분모에서도 빠짐


def test_aggregate_discount_reduces_total_meso() -> None:
    # 할인 시도의 실지불은 정가의 0.7배(ADR-0016 실지불).
    full = StarforceAttempt("itemA", 11, 12, "성공", "2026-05-01T10:00:00+09:00")
    disc = StarforceAttempt(
        "itemA", 11, 12, "성공", "2026-05-01T10:00:00+09:00", cost_discount=True
    )
    s_full = aggregate_starforce([full], lambda item: 200)
    s_disc = aggregate_starforce([disc], lambda item: 200)
    assert s_disc.total_meso == round(s_full.total_meso * 0.7)


def test_event_masks_majority_and_tie() -> None:
    # 성수별 과반 투표: 17성 2/3 과반→포함, 18성 1/2 동률→포함(보수적), 19성 0/2→제외.
    def at(before: int, *, destroy: bool = False) -> StarforceAttempt:
        return StarforceAttempt(
            "x",
            before,
            before + 1,
            "성공",
            "2026-05-01T10:00:00+09:00",
            destroy_reduced=destroy,
        )

    attempts = [
        at(17, destroy=True),
        at(17, destroy=True),
        at(17, destroy=False),
        at(18, destroy=True),
        at(18, destroy=False),
        at(19, destroy=False),
        at(19, destroy=False),
    ]
    destroy_stars, discount_stars = _event_masks(attempts)
    assert destroy_stars == frozenset({17, 18})  # 17 과반, 18 동률→True
    assert 19 not in destroy_stars
    assert discount_stars == frozenset()  # 할인 플래그 전무
