"""scheduler_card 렌더러 단위테스트 — PNG bytes 생성·치수, 표시 규칙 헬퍼, 카테고리·todo-first·필터 (ADR-0013·0014).

임베드 테스트(test_scheduler_embed)를 대체한다. 스모크(예외 없이 PNG)
+ 치수 단조성 + content 한 줄 문자열 + 순수 헬퍼 직접 단위 테스트로 표시 규칙을 고정한다.
레이아웃 픽셀 검사는 qa 하네스/검토용 PNG로 눈확인.
"""

from __future__ import annotations

import io
from datetime import datetime
from unittest.mock import MagicMock

from PIL import Image

from maple_mate.bot.scheduler_card import (
    _boss_label,
    _ordered_bosses,
    _ordered_contents,
    card_summary_line,
    render_scheduler_card,
)
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
    assert "3/8 완료" in line  # 집계: 콘텐츠 5 + 보스 3 = 8(길드 제외)


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


# ── 긴 카드(52행+) 클리핑 회귀 ───────────────────────────────────────────────


def _tall_homework() -> Homework:
    """60행+ 픽스처 — 최종 높이가 과거 고정 캔버스 상한(2600px)을 확실히 넘는 규모."""
    daily = (
        [
            ContentItem(
                f"[일일 퀘스트] 퀘스트{i:02d}", 0, 100, type="quest", quest_state="1"
            )
            for i in range(22)
        ]
        + [ContentItem(f"몬스터파크{i:02d}", i, 14) for i in range(1, 8)]
        + [ContentItem(f"이진콘텐츠{i:02d}", 0, 1) for i in range(10)]
    )
    weekly = [
        ContentItem(f"[주간 퀘스트] 항목{i:02d}", 0, 100, type="quest", quest_state="1")
        for i in range(12)
    ] + [
        ContentItem("[길드] 기부", 5000, 0),
        ContentItem("[길드] 출석", 1000, 0),
    ]
    boss = [
        BossItem(f"보스{i:02d}", "hard", i % 3 == 0, CYCLE_WEEKLY) for i in range(10)
    ] + [BossItem(f"일보스{i:02d}", "normal", False, CYCLE_DAILY) for i in range(6)]
    return Homework(
        character_name="긴카드픽스처",
        world_name="스카니아",
        character_level=285,
        daily=daily,
        weekly=weekly,
        boss=boss,
        weekly_boss_clear_count=3,
        weekly_boss_clear_limit=12,
    )


def test_tall_card_renders_without_clipping():
    """52행+ 카드가 정보 손실 없이 렌더된다.

    캔버스가 콘텐츠보다 작으면 crop 확장 영역이 순수 검정(0,0,0)으로 채워진다.
    팔레트는 검정을 쓰지 않으므로 중앙 컬럼에 검정 픽셀이 하나라도 있으면 클리핑이다.
    """
    png = render_scheduler_card(_tall_homework(), _NOW, frozenset())
    img = _open(png)
    x = img.width // 2
    black_rows = [y for y in range(img.height) if img.getpixel((x, y)) == (0, 0, 0)]
    assert not black_rows, f"순수 검정 픽셀 행 발견(클리핑 흔적): {black_rows[:5]}"


def test_tall_card_height_matches_content():
    """작은 카드보다 52행+ 카드의 높이가 충분히 크다."""
    small_png = render_scheduler_card(
        _homework(daily=[ContentItem("무릉", 0, 1)], weekly=[], boss=[]),
        _NOW,
        frozenset(),
    )
    tall_png = render_scheduler_card(_tall_homework(), _NOW, frozenset())
    small_h = _open(small_png).height
    tall_h = _open(tall_png).height
    assert tall_h > small_h * 2, (
        f"tall({tall_h}) 은 small({small_h}) 의 2배 이상이어야 함"
    )


# ── 표시 규칙 순수 헬퍼 직접 단위 테스트 ─────────────────────────────────────


def test_ordered_contents_sort_order():
    """진행중(게이지 내림차순) → 미완료 → 완료 순서 단언 — content_field_value 정렬 이식."""
    items = [
        ContentItem("완료항목", 5, 5),  # done
        ContentItem("미완료항목", 0, 1),  # todo (이진)
        ContentItem("낮은게이지", 2, 14),  # in_progress 비율 2/14 ≈ 0.14
        ContentItem("높은게이지", 10, 14),  # in_progress 비율 10/14 ≈ 0.71
    ]
    in_progress, todo, done = _ordered_contents(items)

    # 진행중: 높은게이지 먼저(내림차순)
    assert [c.name for c in in_progress] == ["높은게이지", "낮은게이지"]
    # 미완료
    assert [c.name for c in todo] == ["미완료항목"]
    # 완료
    assert [c.name for c in done] == ["완료항목"]


def test_ordered_contents_excludes_qs0():
    """qs0(미해금 퀘스트, excluded=True) 항목은 세 버킷 모두에 나타나지 않는다."""
    items = [
        ContentItem("일반퀘", 0, 100, type="quest", quest_state="1"),  # in_progress
        ContentItem("기타퀘", 0, 100, type="quest", quest_state="0"),  # excluded → 무시
    ]
    in_progress, todo, done = _ordered_contents(items)
    all_names = [c.name for c in in_progress + todo + done]
    assert "기타퀘" not in all_names
    assert "일반퀘" not in [c.name for c in in_progress]  # 퀘스트는 in_progress 아님
    assert "일반퀘" in [c.name for c in todo]


def test_ordered_bosses_undone_first():
    """미처치 보스가 처치된 보스보다 앞에 온다 — boss_cycle_value 정렬 이식."""
    bosses = [
        BossItem("완료보스", "hard", True, CYCLE_WEEKLY),
        BossItem("미처치1", "hard", False, CYCLE_WEEKLY),
        BossItem("완료보스2", "normal", True, CYCLE_WEEKLY),
        BossItem("미처치2", "chaos", False, CYCLE_WEEKLY),
    ]
    ordered = _ordered_bosses(bosses)
    names = [b.name for b in ordered]
    # 미처치가 모두 앞에
    assert names.index("미처치1") < names.index("완료보스")
    assert names.index("미처치2") < names.index("완료보스")
    assert names.index("미처치1") < names.index("완료보스2")
    assert names.index("미처치2") < names.index("완료보스2")


def test_boss_label_difficulty_ko_suffix():
    """보스 라벨이 '이름(난이도한글)' 형식으로 합성된다 — draw.textlength mock 으로 순수 테스트."""
    from maple_mate.scheduler.service import difficulty_ko

    b = BossItem("스우", "hard", False, CYCLE_WEEKLY)
    # draw.textlength 를 항상 0 반환으로 mock → 말줄임 없이 이름 그대로 통과
    draw_mock = MagicMock()
    draw_mock.textlength.return_value = 0.0
    font_mock = MagicMock()
    font_mock.size = 25

    label = _boss_label(draw_mock, b, font_mock, 500)  # type: ignore[arg-type]
    assert label == f"스우({difficulty_ko('hard')})", f"라벨 형식 불일치: {label!r}"


def test_boss_label_unknown_difficulty_no_bracket():
    """난이도 미상(빈 문자열)이면 괄호를 붙이지 않는다."""
    from maple_mate.scheduler.service import difficulty_ko

    assert difficulty_ko("") == ""  # 미상은 원문 유지(빈 문자열 → 빈 문자열)
    b = BossItem("미지의보스", "", False, CYCLE_WEEKLY)
    draw_mock = MagicMock()
    draw_mock.textlength.return_value = 0.0
    font_mock = MagicMock()
    font_mock.size = 25

    label = _boss_label(draw_mock, b, font_mock, 500)  # type: ignore[arg-type]
    assert "(" not in label, f"괄호가 없어야 하는데 있음: {label!r}"
    assert label == "미지의보스"
