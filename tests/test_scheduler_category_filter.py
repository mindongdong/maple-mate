"""category_filter 단위테스트 — 묶음 매핑·parse/merge tri-state·CSV·가드 (ADR-0014, 작업지시서 #1·#5).

순수 함수만 다룬다(DB·발송 없음). Choice 는 discord app_commands 로 만든다.
"""

from __future__ import annotations

from discord import app_commands

from maple_mate.scheduler import category_filter as cf


def _on() -> app_commands.Choice[str]:
    return app_commands.Choice(name="켜기", value="on")


def _off() -> app_commands.Choice[str]:
    return app_commands.Choice(name="끄기", value="off")


# ── 묶음 상수 ────────────────────────────────────────────────────────────────


def test_all_buckets_order_and_membership():
    assert cf.ALL_BUCKETS == (
        cf.BUCKET_DAILY,
        cf.BUCKET_WEEKLY,
        cf.BUCKET_BOSS,
        cf.BUCKET_GUILD,
    )
    assert cf.ALL_BUCKETS == ("일일", "주간", "보스", "길드")


def test_category_on_off_choice_values():
    assert [c.value for c in cf.CATEGORY_ON_OFF] == ["on", "off"]
    assert [c.name for c in cf.CATEGORY_ON_OFF] == ["켜기", "끄기"]


# ── parse_ondemand: off 만 제외, None/on = 표시(무상태) ───────────────────────


def test_parse_ondemand_off_only_excluded():
    excluded = cf.parse_ondemand(None, None, _off(), None)
    assert excluded == frozenset({cf.BUCKET_BOSS})


def test_parse_ondemand_on_and_none_are_visible():
    assert cf.parse_ondemand(_on(), None, None, None) == frozenset()
    assert cf.parse_ondemand(None, None, None, None) == frozenset()


def test_parse_ondemand_multiple_off():
    excluded = cf.parse_ondemand(_off(), None, _off(), _off())
    assert excluded == frozenset({cf.BUCKET_DAILY, cf.BUCKET_BOSS, cf.BUCKET_GUILD})


# ── merge_excluded: tri-state (off 추가 / on 제거 / None 유지) ────────────────


def test_merge_off_adds_to_stored():
    out = cf.merge_excluded(
        frozenset({cf.BUCKET_GUILD}), daily=None, weekly=None, boss=_off(), guild=None
    )
    assert out == frozenset({cf.BUCKET_GUILD, cf.BUCKET_BOSS})


def test_merge_on_removes_from_stored():
    out = cf.merge_excluded(
        frozenset({cf.BUCKET_GUILD, cf.BUCKET_BOSS}),
        daily=None,
        weekly=None,
        boss=None,
        guild=_on(),
    )
    assert out == frozenset({cf.BUCKET_BOSS})


def test_merge_none_keeps_stored():
    stored = frozenset({cf.BUCKET_BOSS, cf.BUCKET_GUILD})
    out = cf.merge_excluded(stored, daily=None, weekly=None, boss=None, guild=None)
    assert out == stored  # 시각만 바꿔도 꺼둔 묶음 유지


def test_merge_initial_baseline_empty():
    out = cf.merge_excluded(
        frozenset(), daily=None, weekly=_off(), boss=None, guild=None
    )
    assert out == frozenset({cf.BUCKET_WEEKLY})  # 신규 구독 baseline=전부 켜짐


# ── CSV 라운드트립 + 상위호환 ─────────────────────────────────────────────────


def test_to_csv_empty_is_none():
    assert cf.to_csv(frozenset()) is None


def test_to_csv_stable_order():
    assert cf.to_csv(frozenset({cf.BUCKET_GUILD, cf.BUCKET_DAILY})) == "일일,길드"


def test_from_csv_none_and_blank_empty():
    assert cf.from_csv(None) == frozenset()
    assert cf.from_csv("") == frozenset()
    assert cf.from_csv("  ") == frozenset()


def test_csv_roundtrip():
    excluded = frozenset({cf.BUCKET_BOSS, cf.BUCKET_GUILD})
    assert cf.from_csv(cf.to_csv(excluded)) == excluded


def test_from_csv_ignores_unknown_tokens():
    assert cf.from_csv("보스,미상,길드") == frozenset({cf.BUCKET_BOSS, cf.BUCKET_GUILD})


# ── 가드 + 요약 ──────────────────────────────────────────────────────────────


def test_is_all_excluded():
    assert cf.is_all_excluded(frozenset(cf.ALL_BUCKETS)) is True
    assert cf.is_all_excluded(frozenset({"일일", "주간", "보스"})) is False
    assert cf.is_all_excluded(frozenset()) is False


def test_summarize_shown_and_hidden():
    assert (
        cf.summarize(frozenset({cf.BUCKET_GUILD}))
        == "표시: 일일·주간·보스 / 숨김: 길드"
    )


def test_summarize_all_shown_no_hidden_clause():
    assert cf.summarize(frozenset()) == "표시: 일일·주간·보스·길드"
