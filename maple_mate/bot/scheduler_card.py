"""스케줄러 숙제 PNG 카드 렌더 (전달-무관 순수 렌더, `asyncio.to_thread` 호출 전제, ADR-0013).

임베드(build_embed) 표현 매체를 PIL PNG 카드로 전환한다. 정보 구조·표시 규칙은 불변 — 카테고리
파생(퀘/회수/이진/길드·보스 cycle)·todo-first 정렬·excluded 필터·전부완료 상태색·챌린저스 뱃지를
그대로 보존한다. service 의 마크다운 문자열 함수(content_field_value 등)는 임베드 전용이라 쓰지
않고, 구조화 DTO(ContentItem/BossItem)와 순수 분류·집계 함수만 재사용한다.

레이아웃(위→아래): 헤더(캐릭터명 + Lv·월드, 챌린저스 pill) · 진행 요약(남은 N + 진행바) ·
섹션(액센트바 + 이름 + 카운트) · 항목 행(드로잉 체크박스 + 이름, 완료 흐림, 회수형 게이지,
길드 점수) · 보스 2컬럼 그리드 · 푸터(구분선 + 기준 시각·출처). 이모지 미사용(전부 드로잉).
팔레트·폰트는 bitik_card/table_image 와 공유.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from ..registration.realm import is_challengers
from ..scheduler import service
from ..scheduler.category_filter import (
    BUCKET_BOSS,
    BUCKET_DAILY,
    BUCKET_GUILD,
    BUCKET_WEEKLY,
)
from ..scheduler.service import BossItem, ContentItem, Homework
from .embeds import append_source, format_footer
from .table_image import _load_fonts

_RGB = tuple[int, int, int]

# ── 팔레트 (bitik_card/table_image 와 동일 시각 언어) ─────────────────────────
_BG = (30, 31, 34)
_PANEL = (43, 45, 49)  # #2b2d31 근사
_TEXT = (223, 225, 228)
_MUTED = (148, 155, 164)
_FAINT = (100, 105, 114)  # 완료 항목 흐림
_ORANGE = (255, 156, 56)  # 브랜드 오렌지(잔여 상태색)
_GREEN = (87, 242, 135)  # 전부 완료 상태색(잔여 0)
_DIVIDER = (66, 69, 76)
_TRACK = (58, 61, 67)  # 진행바 트랙(빈 부분)
_CHECK_DONE = (46, 125, 80)  # 완료 체크박스 채움
_CHECK_MARK = (220, 255, 230)  # 완료 체크 표시
_CHECK_OUTLINE = (120, 126, 136)  # 미완료 체크박스 테두리

# 섹션 액센트(그룹 구분용 소량 색) — 카운트·액센트바에 공유.
_C_QUEST = (94, 200, 200)
_C_CONTENT = (122, 162, 247)
_C_WEEKLY = (199, 146, 234)
_C_GUILD = (240, 192, 64)
_C_BOSS = (240, 120, 120)

# 챌린저스 pill.
_PILL_BG = (72, 52, 24)
_PILL_TEXT = (255, 190, 96)

# ── 치수 ──────────────────────────────────────────────────────────────
_W = 780  # 패널 폭
_MARGIN = 16  # 카드 바깥 여백(라운드 그림자 여유)
_PAD = 44  # 패널 안쪽 좌우/상하 여백
_RADIUS = 18

_TITLE_SIZE = 40
_BODY_SIZE = 30
_SMALL_SIZE = 25
_TINY_SIZE = 22

_CHECKBOX = 26
_BOSS_CHECKBOX = 22
_ROW_H = 42  # 항목 행 높이
_BOSS_ROW_H = 38  # 보스 2컬럼 행 높이
_SECTION_H = 46  # 섹션 헤더 높이
_GAUGE_W = 170  # 회수형 진행중 미니 게이지 폭


class _Fonts:
    """카드가 쓰는 폰트 묶음(한 번 로드해 재사용)."""

    def __init__(self) -> None:
        self.title_r, self.title_b = _load_fonts(_TITLE_SIZE)
        self.of_b = _load_fonts(34)[1]  # "의 오늘 숙제"
        self.remain_b = _load_fonts(32)[1]  # "남은 숙제 N"
        self.body_r, self.body_b = _load_fonts(_BODY_SIZE)
        self.small_r, self.small_b = _load_fonts(_SMALL_SIZE)
        self.tiny_r, _ = _load_fonts(_TINY_SIZE)


# ── 픽셀 폭 말줄임(임베드 18자 → 카드 폭 기준) ────────────────────────────────


def _ellipsize(
    draw: ImageDraw.ImageDraw, name: str, font: ImageFont.FreeTypeFont, max_w: float
) -> str:
    """프리픽스 제거 후 픽셀 폭이 max_w 를 넘으면 `…` 로 자른다(카드 폭 최대 활용). 순수 근사."""
    name = service.strip_prefix(name)
    if draw.textlength(name, font=font) <= max_w:
        return name
    ell = "…"
    while name and draw.textlength(name + ell, font=font) > max_w:
        name = name[:-1]
    return name + ell


# ── todo-first 정렬(임베드 문자열 함수 대신 구조화 소비) ──────────────────────


def _ordered_contents(
    items: Sequence[ContentItem],
) -> tuple[list[ContentItem], list[ContentItem], list[ContentItem]]:
    """(진행중 게이지 내림차순, 미완료, 완료) — content_field_value 정렬 규칙 이식(qs0 제외). 순수."""
    active = [c for c in items if not c.excluded]
    in_progress = sorted(
        (c for c in active if c.in_progress),
        key=lambda c: c.now_count / c.max_count,
        reverse=True,
    )
    todo = [c for c in active if not c.done and not c.in_progress]
    done = [c for c in active if c.done]
    return in_progress, todo, done


def _ordered_bosses(items: Sequence[BossItem]) -> list[BossItem]:
    """미처치 먼저 → 처치(boss_cycle_value 정렬 규칙 이식). 순수."""
    return [b for b in items if not b.done] + [b for b in items if b.done]


# ── 그리기 프리미티브 ─────────────────────────────────────────────────────────


def _checkbox(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, done: bool) -> None:
    if done:
        draw.rounded_rectangle([x, y, x + size, y + size], radius=6, fill=_CHECK_DONE)
        s = size
        draw.line(
            [(x + s * 0.26, y + s * 0.52), (x + s * 0.43, y + s * 0.70)],
            fill=_CHECK_MARK,
            width=3,
        )
        draw.line(
            [(x + s * 0.43, y + s * 0.70), (x + s * 0.76, y + s * 0.30)],
            fill=_CHECK_MARK,
            width=3,
        )
    else:
        draw.rounded_rectangle(
            [x, y, x + size, y + size], radius=6, outline=_CHECK_OUTLINE, width=2
        )


def _progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    ratio: float,
    fill: _RGB,
) -> None:
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=_TRACK)
    if ratio > 0:
        draw.rounded_rectangle(
            [x, y, x + max(h, int(w * min(ratio, 1.0))), y + h],
            radius=h // 2,
            fill=fill,
        )


# ── content 한 줄(푸시 알림 미리보기) ─────────────────────────────────────────


def card_summary_line(hw: Homework, excluded: frozenset[str]) -> str:
    """`캐릭터 — 남은 숙제 N개 (D/T 완료)` 한 줄. 집계 0이면 캐릭터명만. 순수(visible_remaining 재사용)."""
    done, total = service.visible_remaining(hw, excluded)
    if total <= 0:
        return hw.character_name
    remaining = total - done
    return f"{hw.character_name} — 남은 숙제 {remaining}개 ({done}/{total} 완료)"


# ── 카드 렌더 ─────────────────────────────────────────────────────────────────


def _estimate_height(hw: Homework) -> int:
    """섹션별 항목 수로 캔버스 최소 필요 높이를 산출(항상 실제보다 넉넉하게). 순수.

    정확한 픽셀 계산 없이 각 요소를 상한 추정으로 더한다:
    - 헤더·진행요약·디바이더: 고정 300px
    - ContentItem: 각 50px(in_progress 행 = ROW_H+8, todo/done = ROW_H)
    - 섹션 헤더(최대 9개): SECTION_H × 9 = 414px
    - 보스 행(2컬럼, 올림): ceil(len) × BOSS_ROW_H
    - 길드 마진·푸터·여유: 300px
    excluded 를 고려하지 않아 항상 보수적(크게) 추정 — 낭비보다 정보 손실이 더 나쁘다.
    """
    n_content = len(hw.daily) + len(hw.weekly)
    n_boss = len(hw.boss)
    boss_rows = (n_boss + 1) // 2 if n_boss else 0
    # 9개 섹션 헤더 + 항목당 50px + 보스 행 + 고정 여유
    return 300 + 9 * _SECTION_H + n_content * 50 + boss_rows * _BOSS_ROW_H + 300


def render_scheduler_card(
    hw: Homework, now: datetime, excluded: frozenset[str] = frozenset()
) -> bytes:
    """Homework → 필드 파생 카테고리 PNG 카드 bytes(ADR-0013). 빈 카테고리·excluded 묶음은 생략.

    build_embed 와 정보 구조 동일 — 섹션 순서·카운트·todo-first·전부완료 상태색·챌린저스 뱃지를
    보존한다. 높이는 그리며 결정(동적) → 마지막에 crop. `asyncio.to_thread` 로 호출(루프 비차단).
    """
    f = _Fonts()
    # 항목 수 기반으로 필요 높이를 추정한 뒤 실제 사용 높이로 crop(bitik_card 관행).
    # 고정 상한이 아니라 동적 산출 — 항목이 많아도 캔버스를 넘어 하단이 잘리지 않는다.
    est_h = _estimate_height(hw)
    img = Image.new("RGB", (_W + 2 * _MARGIN, est_h), _BG)
    draw = ImageDraw.Draw(img)
    x0, y0 = _MARGIN, _MARGIN
    left = x0 + _PAD
    right = x0 + _W - _PAD
    inner_w = _W - 2 * _PAD

    draw.rounded_rectangle(
        [x0, y0, x0 + _W, est_h - _MARGIN], radius=_RADIUS, fill=_PANEL
    )

    y = y0 + _PAD
    y = _draw_header(draw, hw, f, left, right, y)
    y = _draw_progress(draw, hw, excluded, f, left, right, inner_w, y)
    y = _draw_sections(draw, hw, excluded, f, left, right, inner_w, y)
    y = _draw_footer(draw, now, f, left, right, y)

    final_h = y + _PAD - 16
    return _finish(img, x0, final_h)


def _draw_header(
    draw: ImageDraw.ImageDraw,
    hw: Homework,
    f: _Fonts,
    left: int,
    right: int,
    y: int,
) -> int:
    """캐릭터명(오렌지 볼드) + '의 오늘 숙제' + 챌린저스 pill · 우측 Lv·월드(muted)."""
    draw.text((left, y), hw.character_name, font=f.title_b, fill=_ORANGE)
    nx = left + draw.textlength(hw.character_name, font=f.title_b)
    draw.text((nx + 10, y + 6), "의 오늘 숙제", font=f.of_b, fill=_TEXT)

    if is_challengers(hw.world_name):
        _draw_pill(draw, "챌린저스", f.small_b, left, y + 54)

    meta_parts = [f"Lv.{hw.character_level}"] if hw.character_level else []
    if hw.world_name:
        meta_parts.append(hw.world_name)
    meta = " · ".join(meta_parts)
    if meta:
        draw.text(
            (right - draw.textlength(meta, font=f.small_r), y + 12),
            meta,
            font=f.small_r,
            fill=_MUTED,
        )
    return y + (94 if is_challengers(hw.world_name) else 66)


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    label: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
) -> None:
    """작은 라운드 pill(챌린저스 뱃지) — 🏆 제목 프리픽스의 이관(ADR-0017)."""
    tw = draw.textlength(label, font=font)
    pad = 12
    h = font.size + 10
    draw.rounded_rectangle(
        [x, y, x + tw + 2 * pad, y + h], radius=h // 2, fill=_PILL_BG
    )
    draw.text((x + pad, y + 4), label, font=font, fill=_PILL_TEXT)


def _draw_progress(
    draw: ImageDraw.ImageDraw,
    hw: Homework,
    excluded: frozenset[str],
    f: _Fonts,
    left: int,
    right: int,
    inner_w: int,
    y: int,
) -> int:
    """진행 요약: '남은 숙제 N' 볼드 + 우측 'D/T 완료' + 풀폭 진행바. 전부완료면 그린."""
    done, total = service.visible_remaining(hw, excluded)
    remaining = total - done
    ratio = (done / total) if total > 0 else 0.0
    bar_color = _GREEN if (total > 0 and done >= total) else _ORANGE

    head = f"남은 숙제 {remaining}" if total > 0 else "집계할 숙제 없음"
    draw.text((left, y), head, font=f.remain_b, fill=_TEXT)
    if total > 0:
        done_lbl = f"{done}/{total} 완료"
        draw.text(
            (right - draw.textlength(done_lbl, font=f.small_r), y + 6),
            done_lbl,
            font=f.small_r,
            fill=_MUTED,
        )
    y += 48
    _progress_bar(draw, left, y, inner_w, 14, ratio, bar_color)
    return y + 40


def _draw_sections(
    draw: ImageDraw.ImageDraw,
    hw: Homework,
    excluded: frozenset[str],
    f: _Fonts,
    left: int,
    right: int,
    inner_w: int,
    y: int,
) -> int:
    """build_embed 와 동일한 섹션 순서·구성으로 각 카테고리를 그린다(빈 건 생략)."""
    y = _divider(draw, left, right, y)

    if BUCKET_DAILY not in excluded:
        y = _content_section(
            draw,
            _C_QUEST,
            "일일 퀘스트",
            service.by_category(hw.daily, service.CAT_QUEST),
            f,
            left,
            right,
            inner_w,
            y,
        )
        y = _content_section(
            draw,
            _C_CONTENT,
            "일일 콘텐츠",
            service.by_category(hw.daily, service.CAT_COUNT)
            + service.by_category(hw.daily, service.CAT_BINARY),
            f,
            left,
            right,
            inner_w,
            y,
        )
    if BUCKET_WEEKLY not in excluded:
        y = _content_section(
            draw,
            _C_WEEKLY,
            "주간 퀘스트",
            service.by_category(hw.weekly, service.CAT_QUEST),
            f,
            left,
            right,
            inner_w,
            y,
        )
        y = _content_section(
            draw,
            _C_WEEKLY,
            "주간 콘텐츠",
            service.by_category(hw.weekly, service.CAT_BINARY)
            + service.by_category(hw.weekly, service.CAT_COUNT),
            f,
            left,
            right,
            inner_w,
            y,
        )
    if BUCKET_GUILD not in excluded:
        y = _guild_section(
            draw,
            "길드 콘텐츠",
            service.by_category(hw.daily, service.CAT_GUILD)
            + service.by_category(hw.weekly, service.CAT_GUILD),
            f,
            left,
            right,
            y,
        )
    if BUCKET_BOSS not in excluded:
        clear = (
            hw.weekly_boss_clear_count,
            service.weekly_boss_limit(hw.weekly_boss_clear_limit),
        )
        y = _boss_section(
            draw,
            "주간 보스",
            service.bosses_by_cycle(hw.boss, service.CYCLE_WEEKLY),
            f,
            left,
            right,
            inner_w,
            y,
            clear=clear,
        )
        y = _boss_section(
            draw,
            "일간 보스",
            service.bosses_by_cycle(hw.boss, service.CYCLE_DAILY),
            f,
            left,
            right,
            inner_w,
            y,
        )
        y = _boss_section(
            draw,
            "월간 보스",
            service.bosses_by_cycle(hw.boss, service.CYCLE_MONTHLY),
            f,
            left,
            right,
            inner_w,
            y,
        )
        y = _boss_section(
            draw,
            "기타 보스",
            service.bosses_other_cycle(hw.boss),
            f,
            left,
            right,
            inner_w,
            y,
        )
    return y


def _section_header(
    draw: ImageDraw.ImageDraw,
    color: _RGB,
    label: str,
    count: str | None,
    f: _Fonts,
    left: int,
    right: int,
    y: int,
) -> int:
    """색 액센트바 + 섹션명 볼드 + 우측 카운트(액센트색)."""
    draw.rounded_rectangle([left, y + 8, left + 10, y + 26], radius=3, fill=color)
    draw.text((left + 24, y), label, font=f.body_b, fill=_TEXT)
    if count:
        draw.text(
            (right - draw.textlength(count, font=f.small_b), y + 4),
            count,
            font=f.small_b,
            fill=color,
        )
    return y + _SECTION_H


def _content_section(
    draw: ImageDraw.ImageDraw,
    color: _RGB,
    label: str,
    items: Sequence[ContentItem],
    f: _Fonts,
    left: int,
    right: int,
    inner_w: int,
    y: int,
) -> int:
    """퀘스트/회수/완료미완료 섹션 — 헤더 D/T + todo-first 행. 표시할 게 없으면 통째로 생략."""
    if not items:
        return y
    done, total = service.field_counts(items)
    if total == 0:  # 전부 qs0(기타)
        return y
    y = _section_header(draw, color, label, f"{done}/{total}", f, left, right, y)

    in_progress, todo, done_items = _ordered_contents(items)
    # 이름 끝 = 게이지 시작 - gap(12) — 이름 말줄임 폭을 게이지 x 기준으로 잡아 겹침 방지
    gauge_x = right - _GAUGE_W - 84
    name_max = gauge_x - (left + 44) - 12
    for c in in_progress:  # 회수형 진행중: 이름 + 미니 게이지 + n/m
        _checkbox(draw, left + 4, y + 2, _CHECKBOX, False)
        name = _ellipsize(draw, c.name, f.body_r, name_max)
        draw.text((left + 44, y), name, font=f.body_r, fill=_TEXT)
        ratio = c.now_count / c.max_count if c.max_count else 0.0
        _progress_bar(draw, gauge_x, y + 10, _GAUGE_W, 10, ratio, color)
        gauge = f"{c.now_count}/{c.max_count}"
        draw.text(
            (right - draw.textlength(gauge, font=f.small_r), y + 4),
            gauge,
            font=f.small_r,
            fill=_MUTED,
        )
        y += _ROW_H + 8
    for c in todo:
        y = _todo_row(draw, c.name, False, f, left, inner_w, y)
    for c in done_items:
        y = _todo_row(draw, c.name, True, f, left, inner_w, y)
    return y + 8


def _todo_row(
    draw: ImageDraw.ImageDraw,
    raw_name: str,
    done: bool,
    f: _Fonts,
    left: int,
    inner_w: int,
    y: int,
) -> int:
    """드로잉 체크박스 + 이름(완료는 흐림). 픽셀 폭 말줄임."""
    _checkbox(draw, left + 4, y + 2, _CHECKBOX, done)
    color = _FAINT if done else _TEXT
    name = _ellipsize(draw, raw_name, f.body_r, inner_w - 44)
    draw.text((left + 44, y), name, font=f.body_r, fill=color)
    return y + _ROW_H


def _guild_section(
    draw: ImageDraw.ImageDraw,
    label: str,
    items: Sequence[ContentItem],
    f: _Fonts,
    left: int,
    right: int,
    y: int,
) -> int:
    """길드 콘텐츠(점수제) — 체크박스 없이 이름 + 점수(골드 볼드 우측). now==0 은 muted 이름만."""
    if not items:
        return y
    y = _section_header(draw, _C_GUILD, label, None, f, left, right, y)
    for c in items:
        # 점수 실측 폭만큼 이름 말줄임 폭을 줄여 점수와 겹치지 않게 한다.
        score_w = (
            draw.textlength(f"{c.now_count:,}", font=f.body_b) + 16
            if c.now_count
            else 0
        )
        name = _ellipsize(draw, c.name, f.body_r, right - (left + 44) - score_w)
        if c.now_count == 0:
            draw.text((left + 44, y), name, font=f.body_r, fill=_MUTED)
        else:
            draw.text((left + 44, y), name, font=f.body_r, fill=_TEXT)
            score = f"{c.now_count:,}"
            draw.text(
                (right - draw.textlength(score, font=f.body_b), y),
                score,
                font=f.body_b,
                fill=_C_GUILD,
            )
        y += _ROW_H + 8
    return y + 8


def _boss_section(
    draw: ImageDraw.ImageDraw,
    label: str,
    items: Sequence[BossItem],
    f: _Fonts,
    left: int,
    right: int,
    inner_w: int,
    y: int,
    *,
    clear: tuple[int, int] | None = None,
) -> int:
    """보스 cycle 섹션 — 헤더 처치/총(+주간 처치 c/limit) + 2컬럼 그리드(미처치 먼저)."""
    if not items:
        return y
    done, total = service.boss_counts(items)
    count = f"{done}/{total}"
    if clear is not None:
        count += f" · 처치 {clear[0]}/{clear[1]}"
    y = _section_header(draw, _C_BOSS, label, count, f, left, right, y)

    ordered = _ordered_bosses(items)
    col_w = inner_w // 2
    name_max = col_w - 44
    for i, b in enumerate(ordered):
        cx = left + (i % 2) * col_w
        cy = y + (i // 2) * _BOSS_ROW_H
        _checkbox(draw, cx + 4, cy + 2, _BOSS_CHECKBOX, b.done)
        color = _FAINT if b.done else _TEXT
        draw.text(
            (cx + 38, cy), _boss_label(draw, b, f, name_max), font=f.small_r, fill=color
        )
    rows = (len(ordered) + 1) // 2
    return y + rows * _BOSS_ROW_H + 12


def _boss_label(draw: ImageDraw.ImageDraw, b: BossItem, f: _Fonts, max_w: float) -> str:
    """`이름(난이도)` — 난이도 미상이면 괄호 생략. 픽셀 폭 말줄임."""
    diff = service.difficulty_ko(b.difficulty)
    suffix = f"({diff})" if diff else ""
    suffix_w = draw.textlength(suffix, font=f.small_r)
    name = _ellipsize(draw, b.name, f.small_r, max_w - suffix_w)
    return f"{name}{suffix}"


def _divider(draw: ImageDraw.ImageDraw, left: int, right: int, y: int) -> int:
    draw.line([(left, y), (right, y)], fill=_DIVIDER, width=2)
    return y + 24


def _draw_footer(
    draw: ImageDraw.ImageDraw,
    now: datetime,
    f: _Fonts,
    left: int,
    right: int,
    y: int,
) -> int:
    """구분선 + 'HH:00 기준 · NEXON Open API'(build_embed 푸터 문자열 그대로)."""
    y = _divider(draw, left, right, y)
    footer = append_source(format_footer(now, now))
    draw.text((left, y), footer, font=f.tiny_r, fill=_FAINT)
    return y + 40


def _finish(img: Image.Image, x0: int, final_h: int) -> bytes:
    """사용 높이로 crop 하고 패널 바닥을 라운드로 재마감 → PNG bytes."""
    out = Image.new("RGB", (img.width, final_h + _MARGIN), _BG)
    out.paste(img.crop((0, 0, img.width, final_h)), (0, 0))
    d = ImageDraw.Draw(out)
    # 바닥만 라운드로 다시 그려 crop 으로 잘린 하단 모서리를 복원.
    d.rounded_rectangle(
        [x0, final_h - 36, x0 + _W, final_h], radius=_RADIUS, fill=_PANEL
    )
    buffer = io.BytesIO()
    out.save(buffer, "PNG")
    return buffer.getvalue()
