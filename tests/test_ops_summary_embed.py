"""build_ops_summary_embed 단위테스트 — discord.Embed 구성만, DB 없음 (Phase 5).

OpsSummary/HealthEntry 를 직접 만들어 입력. 순수 함수라 DB·봇 mock 불필요.
"""
from __future__ import annotations

from datetime import date

from maple_mate.bot.embeds import BRAND_COLOR
from maple_mate.error_log.summary import HealthEntry, OpsSummary
from maple_mate.notification.scheduler import build_ops_summary_embed

_REF = date(2026, 6, 8)


def _empty_summary() -> OpsSummary:
    return OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(),
        unmatched_kinds=0,
        health=(),
    )


# ─── 빈 요약 → None ────────────────────────────────────────────────────────────


def test_empty_summary_returns_none():
    assert build_ops_summary_embed(_empty_summary(), _REF) is None


# ─── 색 분기 ───────────────────────────────────────────────────────────────────


def test_app_key_failure_color_is_red():
    s = OpsSummary(
        app_key_failures=1,
        app_key_recent_detail=None,
        unmatched=(),
        unmatched_kinds=0,
        health=(),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    import discord
    assert embed.color == discord.Color.red()


def test_no_app_key_failure_color_is_brand():
    s = OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(("검", 1),),
        unmatched_kinds=1,
        health=(),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    assert embed.color == BRAND_COLOR


# ─── 섹션 순서: 앱키 → 미상 → 헬스 ───────────────────────────────────────────


def test_field_order_app_key_then_unmatched_then_health():
    health_entry = HealthEntry(
        error_type="nexon_api",
        count=2,
        by_command=(("스타포스", 2),),
        recent_detail="err",
    )
    s = OpsSummary(
        app_key_failures=1,
        app_key_recent_detail="app_err",
        unmatched=(("활", 3),),
        unmatched_kinds=1,
        health=(health_entry,),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    names = [f.name for f in embed.fields]
    assert names[0] == "🚨 봇 앱 키 실패"
    assert names[1] == "🔧 미상 장비 레벨"
    assert names[2] == "⚠️ nexon_api"


def test_only_present_sections_rendered():
    """앱키 없이 헬스만 있으면 필드 1개."""
    health_entry = HealthEntry(
        error_type="timeout",
        count=1,
        by_command=(),
        recent_detail=None,
    )
    s = OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(),
        unmatched_kinds=0,
        health=(health_entry,),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    assert len(embed.fields) == 1
    assert embed.fields[0].name == "⚠️ timeout"


# ─── "외 N종" 문자열 ───────────────────────────────────────────────────────────


def test_unmatched_extra_kinds_suffix():
    """unmatched_kinds > len(unmatched) 면 '…외 N종' 줄 추가."""
    # 상위 2종, 전체 5종
    s = OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(("검", 3), ("활", 2)),
        unmatched_kinds=5,
        health=(),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    field = embed.fields[0]
    assert "…외 3종" in field.value


def test_unmatched_no_extra_kinds_when_fits():
    """unmatched_kinds == len(unmatched) 면 '외' 줄 없음."""
    s = OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(("지팡이", 1),),
        unmatched_kinds=1,
        health=(),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    assert "외" not in embed.fields[0].value


# ─── 헬스 command 분해 문자열 ─────────────────────────────────────────────────


def test_health_by_command_in_field_value():
    """by_command 항목이 'cmd cnt' 형식으로 필드 value 에 포함된다."""
    health_entry = HealthEntry(
        error_type="rate_limit",
        count=3,
        by_command=(("스타포스", 2), ("잠재", 1)),
        recent_detail=None,
    )
    s = OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(),
        unmatched_kinds=0,
        health=(health_entry,),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    field_value = embed.fields[0].value
    assert "스타포스 2" in field_value
    assert "잠재 1" in field_value


def test_health_recent_detail_in_field_value():
    """recent_detail 이 있으면 필드 value 에 포함."""
    health_entry = HealthEntry(
        error_type="nexon_api",
        count=1,
        by_command=(),
        recent_detail="ERR_001: 서버 점검 중",
    )
    s = OpsSummary(
        app_key_failures=0,
        app_key_recent_detail=None,
        unmatched=(),
        unmatched_kinds=0,
        health=(health_entry,),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    assert "ERR_001: 서버 점검 중" in embed.fields[0].value


# ─── footer ───────────────────────────────────────────────────────────────────


def test_footer_contains_ref_date():
    s = OpsSummary(
        app_key_failures=1,
        app_key_recent_detail=None,
        unmatched=(),
        unmatched_kinds=0,
        health=(),
    )
    embed = build_ops_summary_embed(s, _REF)
    assert embed is not None
    assert "2026-06-08" in embed.footer.text
    assert "KST" in embed.footer.text
