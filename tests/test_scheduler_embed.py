"""build_embed 단위테스트 — 필드 파생 카테고리(퀘/회수/길드/보스 cycle), 진행바 없음 (ADR-0013)."""

from __future__ import annotations

from datetime import datetime

from maple_mate.bot.embeds import BRAND_COLOR
from maple_mate.nexon.client import KST
from maple_mate.registration.realm import Realm
from maple_mate.scheduler.broadcast import _DONE_COLOR, build_embed
from maple_mate.scheduler.service import (
    CYCLE_DAILY,
    CYCLE_MONTHLY,
    CYCLE_WEEKLY,
    BossItem,
    ContentItem,
    Homework,
)

_NOW = datetime(2026, 6, 26, 21, 0, tzinfo=KST)


def _homework(**over) -> Homework:
    base = dict(
        character_name="내캐릭",
        world_name="스카니아",
        character_level=285,
        daily=[
            ContentItem("몬스터파크", 2, 14),  # 회수 진행중
            ContentItem("[일일 퀘스트] 소멸", 0, 100, type="quest", quest_state="1"),
            ContentItem("[일일 퀘스트] 리멘", 0, 100, type="quest", quest_state="2"),
        ],
        weekly=[
            ContentItem("[길드] 지하 수로", 0, 0),  # 길드(점수제)
            ContentItem("에르다 스펙트럼", 0, 1),  # 이진 미완료
            ContentItem("에픽 던전 : 하이마운틴", 5, 0),  # 이진 완료(now>0)
        ],
        boss=[
            BossItem("스우", "hard", False, CYCLE_WEEKLY),
            BossItem("검은 마법사", "hard", True, CYCLE_MONTHLY),
            BossItem("핑크빈", "chaos", False, CYCLE_DAILY),
        ],
        weekly_boss_clear_count=8,
        weekly_boss_clear_limit=12,
    )
    base.update(over)
    return Homework(**base)


def _field(embed, prefix):
    return next(f for f in embed.fields if f.name.startswith(prefix))


def test_embed_category_fields_present():
    names = [f.name for f in build_embed(_homework(), Realm.MAIN, _NOW).fields]
    assert any(n.startswith("📝 일일 퀘스트") for n in names)
    assert any(n.startswith("🎯 일일 회수") for n in names)
    assert any(n.startswith("⚔️ 주간 콘텐츠") for n in names)
    assert any(n.startswith("🏰 길드 콘텐츠") for n in names)
    assert any(n.startswith("🗡 주간 보스") for n in names)
    assert any(n.startswith("🗡 일간 보스") for n in names)
    assert any(n.startswith("🗡 월간 보스") for n in names)


def test_embed_no_progress_bar_anywhere():
    embed = build_embed(_homework(), Realm.MAIN, _NOW)
    blob = " ".join(f.name for f in embed.fields)
    assert "▰" not in blob and "▱" not in blob  # 진행바 제거


def test_embed_daily_quest_field_todo_first():
    f = _field(build_embed(_homework(), Realm.MAIN, _NOW), "📝 일일 퀘스트")
    assert "남은 1" in f.name and "1/2" in f.name  # 리멘 완료, 소멸 미완
    assert "⬜ 소멸" in f.value
    assert "✅ 완료 1개 · 리멘" in f.value


def test_embed_count_field_shows_gauge():
    f = _field(build_embed(_homework(), Realm.MAIN, _NOW), "🎯 일일 회수")
    assert "🟡 몬스터파크 `2/14`" in f.value


def test_embed_weekly_content_includes_epic_dungeon():
    f = _field(build_embed(_homework(), Realm.MAIN, _NOW), "⚔️ 주간 콘텐츠")
    assert "남은 1" in f.name and "1/2" in f.name  # 에르다 미완, 에픽 완료
    assert "⬜ 에르다 스펙트럼" in f.value
    assert "✅ 완료 1개 · 에픽 던전 : 하이마운틴" in f.value


def test_embed_guild_field_score_no_count_header():
    f = _field(build_embed(_homework(), Realm.MAIN, _NOW), "🏰 길드 콘텐츠")
    assert f.name == "🏰 길드 콘텐츠"  # 점수제 → 헤더 카운트 없음
    assert "⬜ 지하 수로" in f.value


def test_embed_weekly_boss_has_clear_counter():
    f = _field(build_embed(_homework(), Realm.MAIN, _NOW), "🗡 주간 보스")
    assert "(처치 8/12)" in f.name
    assert "⬜ 스우(하드)" in f.value


def test_embed_daily_boss_no_clear_counter():
    f = _field(build_embed(_homework(), Realm.MAIN, _NOW), "🗡 일간 보스")
    assert "(처치" not in f.name  # 일간 보스엔 주간 카운터 없음
    assert "⬜ 핑크빈(카오스)" in f.value


def test_embed_subtitle_has_level_world_and_remaining():
    desc = build_embed(_homework(), Realm.MAIN, _NOW).description or ""
    assert "Lv.285" in desc and "스카니아" in desc
    assert "🔥 남은 숙제 5개 (3/8 완료)" in desc  # 콘텐츠5(완2)+보스3(완1)


def test_embed_color_orange_when_remaining():
    assert build_embed(_homework(), Realm.MAIN, _NOW).color == BRAND_COLOR


def test_embed_color_green_and_check_mark_when_all_done():
    hw = _homework(
        daily=[
            ContentItem("[일일 퀘스트] 리멘", 0, 100, type="quest", quest_state="2")
        ],
        weekly=[],
        boss=[BossItem("검은 마법사", "hard", True, CYCLE_MONTHLY)],
    )
    embed = build_embed(hw, Realm.MAIN, _NOW)
    assert embed.color == _DONE_COLOR  # 잔여 0 → 초록
    assert "✅ 남은 숙제 0개 (2/2 완료)" in (embed.description or "")


def test_embed_main_title_no_prefix():
    embed = build_embed(_homework(), Realm.MAIN, _NOW)
    assert embed.title == "🗓 내캐릭 의 스케줄러 숙제"


def test_embed_challengers_title_prefix():
    embed = build_embed(_homework(), Realm.CHALLENGERS, _NOW)
    assert embed.title.startswith("🏆 챌린저스")
    assert "스케줄러 숙제" in embed.title


def test_embed_omits_empty_categories():
    embed = build_embed(_homework(weekly=[], boss=[]), Realm.MAIN, _NOW)
    names = [f.name for f in embed.fields]
    assert all(("보스" not in n and "길드" not in n and "주간" not in n) for n in names)
    assert any(n.startswith("📝 일일 퀘스트") for n in names)


def test_embed_footer_has_source():
    embed = build_embed(_homework(), Realm.MAIN, _NOW)
    assert "NEXON Open API" in (embed.footer.text or "")
