"""비교 렌더 헬퍼 단위테스트 (페이지 분할·실패필드·푸터)."""
from __future__ import annotations

from maple_mate.bot import comparison
from maple_mate.registration.service import Target, TargetOutcome


def _outcome(nick="닉", *, ok=True, error=None):
    target = Target(guild_id=1, discord_user_id=2, nickname=nick, ocid="oc")
    return TargetOutcome(target=target, data={"x": 1} if ok else None, error=error)


def test_field_pages_single_page_when_small():
    pages = comparison.field_pages("T", [("a", "x"), ("b", "y")], per_page=10)
    assert len(pages) == 1
    assert pages[0].title == "T"
    assert len(pages[0].fields) == 2


def test_field_pages_splits_by_count():
    fields = [(f"n{i}", "v") for i in range(12)]
    pages = comparison.field_pages("T", fields, per_page=5)
    assert len(pages) == 3  # 5 + 5 + 2
    assert pages[0].title == "T (1/3)"


def test_field_pages_splits_by_char_budget_even_under_count_cap():
    big = "x" * 1000
    fields = [(f"n{i}", big) for i in range(10)]  # ~10000자 > 4500 예산
    pages = comparison.field_pages("T", fields, per_page=50)  # 개수론 1장이지만
    assert len(pages) >= 2  # 누적 문자수 예산이 강제 분할


def test_field_pages_empty_yields_one_empty_page():
    pages = comparison.field_pages("T", [])
    assert len(pages) == 1
    assert len(pages[0].fields) == 0


def test_field_pages_clips_oversized_value():
    pages = comparison.field_pages("T", [("a", "z" * 5000)])
    assert len(pages[0].fields[0].value) <= 1024


def test_attach_failures_adds_grouped_field_to_each_page():
    pages = comparison.field_pages("T", [("a", "x")])
    outcomes = [_outcome("성공", ok=True), _outcome("실패자", ok=False, error="닉 변경?")]
    comparison.attach_failures(pages, outcomes)
    failure_fields = [f for f in pages[0].fields if "조회 실패" in f.name]
    assert len(failure_fields) == 1
    assert "실패자" in failure_fields[0].value


def test_attach_failures_noop_when_all_ok():
    pages = comparison.field_pages("T", [("a", "x")])
    comparison.attach_failures(pages, [_outcome(ok=True)])
    assert all("조회 실패" not in f.name for f in pages[0].fields)


def test_data_footer_null_is_latest():
    assert comparison.data_footer(None) == "최신 기준"
    assert comparison.data_footer("") == "최신 기준"


def test_all_failed_embed_lists_reasons():
    embed = comparison.all_failed_embed("유니온 비교", [_outcome("떡볶이", ok=False, error="미등록")])
    assert "떡볶이" in embed.description and "미등록" in embed.description
