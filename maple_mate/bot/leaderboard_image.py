"""경험치 리더보드 PNG 렌더(순수, `asyncio.to_thread` 전제, 작업지시서 빌드 단위 #4).

- render_table: 길드 누적 순위표(table_image 재사용). 컬럼 순위·닉·Lv.·어제Δ·전체순위(#).
- render_delta_graph: 최근 7일 일일 Δ 라인 그래프(PIL 직접 — 코드베이스 최초의 선그래프).
  축·격자·범례·유저별 색 순환. 빈/단일 유저 데이터 가드.
둘 다 입력은 service 의 LeaderRow / history_deltas 시계열, 출력은 PNG BytesIO.
"""

from __future__ import annotations

import io
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from ..character.service import format_eok
from .table_image import _BG, _GRID, _GRID_SUB, _HEADER_TEXT, _TEXT, _load_fonts
from .table_image import render_table_image as _render_table_image

_RGB = tuple[int, int, int]


def _level_text(level: int, exp_rate: float | None) -> str:
    """`Lv.287 (45.2%)` — exp_rate 없으면 비율 생략(`Lv.287`). ranking 소스엔 비율 없음."""
    if exp_rate is None:
        return f"Lv.{level}"
    return f"Lv.{level} ({exp_rate:.1f}%)"


def _delta_text(delta: int | None) -> str:
    """어제 Δ 표기 — 양수는 `+9351억`(format_eok 재사용), None/0 은 '—'."""
    if not delta:
        return "—"
    return f"+{format_eok(delta)}"


def _world_rank_text(world_rank: int | None) -> str:
    """전체 서버 순위 `#129,978` — 미상이면 '—'."""
    if world_rank is None:
        return "—"
    return f"#{world_rank:,}"


def render_table(rows: list, ref_date: date) -> io.BytesIO:
    """순위표 PNG(table_image 재사용). rows=service.LeaderRow 목록(이미 정렬·순위 부여됨)."""
    headers = ["순위", "닉네임", "레벨", "어제 획득", "전체 순위"]
    aligns = ["center", "left", "left", "right", "right"]
    table_rows = [
        [
            str(r.rank),
            r.nickname,
            _level_text(r.level, r.exp_rate),
            _delta_text(r.delta),
            _world_rank_text(r.world_rank),
        ]
        for r in rows
    ]
    png = _render_table_image(headers, table_rows, aligns=aligns)
    return io.BytesIO(png)


# ── 7일 Δ 라인 그래프(PIL 직접) ──────────────────────────────────────────────

# 라인 색 고정 팔레트(순환) — 다크 배경 위 대비 좋은 톤(작업지시서 그래프 라벨).
_LINE_COLORS: tuple[_RGB, ...] = (
    (255, 168, 76),  # 메이플 오렌지
    (74, 165, 225),  # 블루
    (121, 201, 64),  # 그린
    (240, 110, 170),  # 핑크
    (159, 112, 216),  # 퍼플
    (250, 204, 21),  # 골드
    (96, 214, 200),  # 틸
    (225, 96, 96),  # 레드
)

_GRAPH_W = 920
_GRAPH_H = 480
_MARGIN_L = 110  # y축 라벨 공간
_MARGIN_R = 24
_MARGIN_T = 48  # 제목 공간
_MARGIN_B = 96  # x축 라벨 + 범례 공간
_DOT_R = 4
_LINE_W = 3


def _nice_max(value: int) -> int:
    """y축 상단 눈금값(1·2·5 × 10^n 중 value 이상 최소값). value<=0 이면 1."""
    if value <= 0:
        return 1
    magnitude = 10 ** (len(str(value)) - 1)
    for factor in (1, 2, 5, 10):
        candidate = factor * magnitude
        if candidate >= value:
            return candidate
    return 10 * magnitude


def render_delta_graph(
    series: dict[str, list[tuple[date, int | None]]], ref_date: date
) -> io.BytesIO:
    """유저별 최근 7일 일일 Δ 라인 그래프 PNG. series=닉 → [(날짜, Δ|None), ...].

    빈 데이터(첫날·전원 None)·단일 유저도 안전하게 그린다(빈 그래프엔 안내 문구). None 구간은
    선이 끊기고, 활동 없는 날(Δ=0)은 0 바닥선에 그린다. 누적 라인 금지(일일 Δ 만).
    """
    regular, bold = _load_fonts(28)
    small, _ = _load_fonts(20)
    img = Image.new("RGB", (_GRAPH_W, _GRAPH_H), _BG)
    draw = ImageDraw.Draw(img)

    plot_l, plot_r = _MARGIN_L, _GRAPH_W - _MARGIN_R
    plot_t, plot_b = _MARGIN_T, _GRAPH_H - _MARGIN_B
    plot_w, plot_h = plot_r - plot_l, plot_b - plot_t

    title = f"최근 7일 일일 경험치 획득 (기준: 어제 {ref_date:%m/%d} KST)"
    draw.text((plot_l, 12), title, font=bold, fill=_HEADER_TEXT)

    # x축 날짜: 어떤 시리즈든 동일 날짜축이라 첫 시리즈에서 뽑는다(없으면 가드).
    dates = [d for d, _ in next(iter(series.values()), [])]
    all_values = [
        v for points in series.values() for _, v in points if v is not None and v > 0
    ]

    # 빈 데이터 가드: 점이 하나도 없으면 안내만.
    if not dates or not all_values:
        draw.line([(plot_l, plot_b), (plot_r, plot_b)], fill=_GRID, width=1)
        draw.line([(plot_l, plot_t), (plot_l, plot_b)], fill=_GRID, width=1)
        msg = "표시할 획득 데이터가 아직 없어요."
        tw = draw.textlength(msg, font=regular)
        draw.text(
            ((_GRAPH_W - tw) / 2, plot_t + plot_h / 2 - 14),
            msg,
            font=regular,
            fill=_TEXT,
        )
        buffer = io.BytesIO()
        img.save(buffer, "PNG")
        buffer.seek(0)
        return buffer

    y_max = _nice_max(max(all_values))

    # y축 격자 + 라벨(0..y_max 5등분).
    steps = 5
    for i in range(steps + 1):
        frac = i / steps
        y = plot_b - frac * plot_h
        draw.line([(plot_l, y), (plot_r, y)], fill=_GRID_SUB, width=1)
        label = format_eok(int(round(y_max * frac)))
        lw = draw.textlength(label, font=small)
        draw.text((plot_l - 10 - lw, y - 10), label, font=small, fill=_TEXT)

    # x축 + y축 본선.
    draw.line([(plot_l, plot_b), (plot_r, plot_b)], fill=_GRID, width=1)
    draw.line([(plot_l, plot_t), (plot_l, plot_b)], fill=_GRID, width=1)

    n = len(dates)
    xs = [plot_l + (plot_w * i / (n - 1) if n > 1 else plot_w / 2) for i in range(n)]

    # x축 날짜 라벨(MM/DD).
    for x, d in zip(xs, dates):
        label = f"{d:%m/%d}"
        lw = draw.textlength(label, font=small)
        draw.text((x - lw / 2, plot_b + 10), label, font=small, fill=_TEXT)

    def y_of(value: int) -> float:
        return plot_b - (value / y_max) * plot_h

    # 유저별 라인 + 점(None 구간은 선 끊김). 단일 유저(점 1개)는 점만 찍힘.
    for idx, (nickname, points) in enumerate(series.items()):
        color = _LINE_COLORS[idx % len(_LINE_COLORS)]
        prev_xy: tuple[float, float] | None = None
        for x, (_, value) in zip(xs, points):
            if value is None:
                prev_xy = None
                continue
            xy = (x, y_of(value))
            if prev_xy is not None:
                draw.line([prev_xy, xy], fill=color, width=_LINE_W)
            draw.ellipse(
                [xy[0] - _DOT_R, xy[1] - _DOT_R, xy[0] + _DOT_R, xy[1] + _DOT_R],
                fill=color,
            )
            prev_xy = xy

    _draw_legend(draw, series, small, _GRAPH_H - _MARGIN_B + 44)

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _draw_legend(
    draw: ImageDraw.ImageDraw,
    series: dict[str, list[tuple[date, int | None]]],
    font: ImageFont.FreeTypeFont,
    y: float,
) -> None:
    """범례(닉별 색 칩 + 닉) 가로 나열, 폭 초과 시 다음 줄로 줄바꿈."""
    chip = 16
    gap = 10
    item_gap = 26
    x = _MARGIN_L
    line_h = 26
    for idx, nickname in enumerate(series):
        color = _LINE_COLORS[idx % len(_LINE_COLORS)]
        label_w = draw.textlength(nickname, font=font)
        item_w = chip + gap + label_w
        if x + item_w > _GRAPH_W - _MARGIN_R and x > _MARGIN_L:
            x = _MARGIN_L
            y += line_h
        draw.rectangle([x, y, x + chip, y + chip], fill=color)
        draw.text((x + chip + gap, y - 4), nickname, font=font, fill=_TEXT)
        x += item_w + item_gap
