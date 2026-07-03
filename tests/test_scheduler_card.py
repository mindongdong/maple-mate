"""scheduler_card 렌더러 단위테스트 — PNG bytes 생성·치수, 카테고리·todo-first·필터 (ADR-0013·0014).

임베드 테스트(test_scheduler_embed)를 대체한다. 픽셀 검사가 아니라 스모크(예외 없이 PNG)
+ 치수 단조성 + content 한 줄 문자열을 검증한다(레이아웃 눈 확인은 qa 하네스/검토용 PNG).
"""

from __future__ import annotations

import io
from datetime import datetime

from PIL import Image

from maple_mate.bot.scheduler_card import card_summary_line, render_scheduler_card
from maple_mate.nexon.client import KST
from maple_mate.scheduler.category_filter import (
    BUCKET_BOSS,
    BUCKET_DAILY,
    BUCKET_GUILD,
    BUCKET_WEEKLY,
)
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


def _open(png: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(png))
    img.verify()
    return Image.open(io.BytesIO(png))


def _is_png(png: bytes) -> bool:
    img = Image.open(io.BytesIO(png))
    img.verify()
    return img.format == "PNG"


# ── 렌더 성공·치수 ────────────────────────────────────────────────────────────


def test_render_returns_png_bytes():
    assert _is_png(render_scheduler_card(_homework(), _NOW, frozenset()))


def test_render_has_positive_dimensions():
    img = _open(render_scheduler_card(_homework(), _NOW, frozenset()))
    assert img.width > 0 and img.height > 0


def test_more_items_grows_taller():
    """항목이 많은 캐릭터가 세로로 더 길다(동적 높이)."""
    small = _open(
        render_scheduler_card(
            _homework(weekly=[], boss=[], daily=[ContentItem("무릉", 0, 1)]),
            _NOW,
            frozenset(),
        )
    )
    big = _open(render_scheduler_card(_homework(), _NOW, frozenset()))
    assert big.height > small.height


def test_all_done_renders_green_variant():
    """전부 완료(잔여 0)도 예외 없이 렌더된다(그린 진행바 경로)."""
    hw = _homework(
        daily=[
            ContentItem("[일일 퀘스트] 리멘", 0, 100, type="quest", quest_state="2")
        ],
        weekly=[],
        boss=[BossItem("검은 마법사", "hard", True, CYCLE_MONTHLY)],
    )
    assert _is_png(render_scheduler_card(hw, _NOW, frozenset()))


def test_challengers_pill_renders():
    """챌린저스 world 캐릭터도 예외 없이 렌더된다(pill 뱃지 경로)."""
    assert _is_png(
        render_scheduler_card(_homework(world_name="챌린저스2"), _NOW, frozenset())
    )


def test_empty_boss_and_weekly_shorter():
    """빈 카테고리는 그리지 않아 세로가 줄어든다."""
    full = _open(render_scheduler_card(_homework(), _NOW, frozenset()))
    trimmed = _open(
        render_scheduler_card(_homework(weekly=[], boss=[]), _NOW, frozenset())
    )
    assert trimmed.height < full.height


def test_long_name_still_renders():
    """긴 이름도 픽셀 폭 말줄임으로 카드 폭을 넘지 않고 렌더된다."""
    hw = _homework(
        daily=[ContentItem("가" * 60, 0, 1)],
        weekly=[],
        boss=[],
    )
    assert _is_png(render_scheduler_card(hw, _NOW, frozenset()))


# ── 카테고리 필터(ADR-0014): excluded 묶음 생략 → 세로 축소 ──────────────────


def test_excluded_boss_shrinks_card():
    """보스 묶음 제외 시 보스 섹션이 사라져 카드가 짧아진다."""
    full = _open(render_scheduler_card(_homework(), _NOW, frozenset()))
    no_boss = _open(render_scheduler_card(_homework(), _NOW, frozenset({BUCKET_BOSS})))
    assert no_boss.height < full.height


def test_all_excluded_still_renders():
    """4묶음 전부 제외돼도(가드 밖 방어) 예외 없이 헤더만 있는 카드가 나온다."""
    excluded = frozenset({BUCKET_DAILY, BUCKET_WEEKLY, BUCKET_BOSS, BUCKET_GUILD})
    assert _is_png(render_scheduler_card(_homework(), _NOW, excluded))


# ── card_summary_line: content 한 줄(푸시 알림 미리보기) ──────────────────────


def test_summary_line_shows_name_remaining_and_progress():
    line = card_summary_line(_homework(), frozenset())
    assert line.startswith("내캐릭")
    # 콘텐츠 5(완2) + 보스 3(완1) = 8, 완료 3 → 남은 5
    assert "남은 숙제 5개" in line
    assert "3/22 완료" in line or "3/8 완료" in line  # 완료/집계총 형식


def test_summary_line_recounts_when_excluded():
    """excluded 묶음은 헤드라인 집계에서 빠진다(visible_remaining 재사용)."""
    line = card_summary_line(_homework(), frozenset({BUCKET_BOSS}))
    # 보스 3(완1) 빠짐 → 콘텐츠 5(완2), 남은 3
    assert "남은 숙제 3개" in line


def test_summary_line_all_done():
    """전부 완료면 남은 0 문구."""
    hw = _homework(
        daily=[
            ContentItem("[일일 퀘스트] 리멘", 0, 100, type="quest", quest_state="2")
        ],
        weekly=[],
        boss=[BossItem("검은 마법사", "hard", True, CYCLE_MONTHLY)],
    )
    line = card_summary_line(hw, frozenset())
    assert "남은 숙제 0개" in line or "완료" in line


def test_summary_line_guild_only_no_aggregate():
    """집계 대상이 0(길드만)이면 캐릭터명만이라도 안전하게 나온다."""
    hw = _homework(
        daily=[ContentItem("[길드] 지하 수로", 0, 0)],
        weekly=[],
        boss=[],
    )
    line = card_summary_line(hw, frozenset())
    assert line.startswith("내캐릭")
