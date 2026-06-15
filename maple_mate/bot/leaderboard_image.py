"""경험치 리더보드 PNG 렌더(순수, `asyncio.to_thread` 전제, 작업지시서 빌드 단위 #4).

- render_table: 길드 누적 순위표(table_image 재사용). 컬럼 순위·닉·Lv.(exp%)·하루 경험치.
- render_progress_graph: 최근 7일 진행도(레벨+exp%)를 7일 전 대비로 정규화한 %p 라인 그래프
  (PIL 직접). 각 라인은 창 내 첫 가용일=0 출발(부채꼴), 범례에 유저별 일평균 %/일.
둘 다 입력은 service 의 LeaderRow / history_progress 시계열, 출력은 PNG BytesIO.
"""

from __future__ import annotations

import io
import math
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


# 순위표 컬럼(작업지시서 F1·F2) — 전체 순위 제거, '어제 획득'→'하루 경험치'.
# world_rank 는 스냅샷엔 계속 저장하되 표엔 미표시.
_TABLE_HEADERS = ["순위", "닉네임", "레벨", "하루 경험치"]
_TABLE_ALIGNS = ["center", "left", "left", "right"]


def render_table(rows: list, ref_date: date) -> io.BytesIO:
    """순위표 PNG(table_image 재사용). rows=service.LeaderRow 목록(이미 정렬·순위 부여됨)."""
    table_rows = [
        [
            str(r.rank),
            r.nickname,
            _level_text(r.level, r.exp_rate),
            _delta_text(r.delta),
        ]
        for r in rows
    ]
    png = _render_table_image(_TABLE_HEADERS, table_rows, aligns=_TABLE_ALIGNS)
    return io.BytesIO(png)


# ── 7일 진행도 라인 그래프(PIL 직접) ─────────────────────────────────────────

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


def _normalize_progress(
    points: list[tuple[date, float | None]],
) -> list[tuple[date, float | None]]:
    """창 내 첫 가용 progress 를 baseline(0)으로 빼서 %p 로 변환 → [(날짜, %p|None), ...].

    progress = 레벨+exp%/100(연속). baseline 이전·결손 구간은 None(선 끊김). 데이터가 하나도
    없으면 전부 None. %p = (progress-baseline)*100 (100%p = 1레벨). 전원 0 출발이라 부채꼴이 된다.
    """
    baseline = next((p for _, p in points if p is not None), None)
    if baseline is None:
        return [(d, None) for d, _ in points]
    return [(d, (p - baseline) * 100 if p is not None else None) for d, p in points]


def _daily_average(norm_points: list[tuple[date, float | None]]) -> float:
    """정규화된 %p 시계열의 일평균 %/일 = 끝점 %p ÷ (첫~끝 데이터일 간격). 데이터 0/1개면 0.

    progress 가 연속이라 구간 내 레벨업도 자연 합산된다(끝점 %p 가 곧 총 진행량).
    """
    data = [(d, v) for d, v in norm_points if v is not None]
    if len(data) < 2:
        return 0.0
    first_date, _ = data[0]
    last_date, last_value = data[-1]
    gaps = (last_date - first_date).days
    return last_value / gaps if gaps > 0 else 0.0


def render_progress_graph(
    series: dict[str, list[tuple[date, float | None]]], ref_date: date
) -> io.BytesIO:
    """유저별 최근 7일 진행량(%p) 라인 그래프 PNG. series=닉 → [(날짜, progress|None), ...].

    각 라인은 창 내 첫 가용일을 0 으로 정규화해(부채꼴) 7일 전 대비 레벨 진행량(%p, 100%p=1레벨)을
    그린다. 범례엔 유저별 일평균 %/일. 데이터 0개 유저는 자연히 제외(전부 None)되고, 전원 데이터가
    없으면 안내 문구만. None 구간은 선이 끊긴다. 레벨업 마커 없음(연속값이라 톱니/리셋 없음).
    """
    regular, bold = _load_fonts(28)
    small, _ = _load_fonts(20)
    img = Image.new("RGB", (_GRAPH_W, _GRAPH_H), _BG)
    draw = ImageDraw.Draw(img)

    plot_l, plot_r = _MARGIN_L, _GRAPH_W - _MARGIN_R
    plot_t, plot_b = _MARGIN_T, _GRAPH_H - _MARGIN_B
    plot_w, plot_h = plot_r - plot_l, plot_b - plot_t

    title = "최근 7일 경험치 진행량 (7일 전 대비)"
    draw.text((plot_l, 12), title, font=bold, fill=_HEADER_TEXT)

    # x축 날짜: 어떤 시리즈든 동일 날짜축이라 첫 시리즈에서 뽑는다(없으면 가드).
    dates = [d for d, _ in next(iter(series.values()), [])]

    # 유저별 정규화(0 출발) %p 라인. 데이터 0개 유저는 라인·범례 모두에서 제외(작업지시서 파생결정).
    normalized = {nick: _normalize_progress(pts) for nick, pts in series.items()}
    normalized = {
        nick: pts
        for nick, pts in normalized.items()
        if any(v is not None for _, v in pts)
    }
    averages = {nick: _daily_average(pts) for nick, pts in normalized.items()}
    all_values = [v for pts in normalized.values() for _, v in pts if v is not None]

    # 빈 데이터 가드: 가용 progress 가 하나도 없으면 안내만.
    if not dates or not all_values:
        draw.line([(plot_l, plot_b), (plot_r, plot_b)], fill=_GRID, width=1)
        draw.line([(plot_l, plot_t), (plot_l, plot_b)], fill=_GRID, width=1)
        msg = "표시할 진행량 데이터가 아직 없어요."
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

    # 전원 0 출발이라 max %p>=0. ceil 로 라인이 축 상단을 넘지 않게(0 이면 _nice_max=1).
    y_max = _nice_max(math.ceil(max(all_values)))

    # y축 격자 + 라벨(0..y_max 5등분, +N%).
    steps = 5
    for i in range(steps + 1):
        frac = i / steps
        y = plot_b - frac * plot_h
        draw.line([(plot_l, y), (plot_r, y)], fill=_GRID_SUB, width=1)
        val = int(round(y_max * frac))
        label = f"+{val}%" if val > 0 else "0%"
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

    def y_of(value: float) -> float:
        return plot_b - (value / y_max) * plot_h

    # 유저별 라인 + 점(None 구간은 선 끊김). 단일 점은 점만 찍힘.
    for idx, (nickname, points) in enumerate(normalized.items()):
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

    _draw_legend(draw, normalized, averages, small, _GRAPH_H - _MARGIN_B + 44)

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def _draw_legend(
    draw: ImageDraw.ImageDraw,
    series: dict[str, list[tuple[date, float | None]]],
    averages: dict[str, float],
    font: ImageFont.FreeTypeFont,
    y: float,
) -> None:
    """범례(닉별 색 칩 + '닉 · 평균 N%/일') 가로 나열, 폭 초과 시 다음 줄로 줄바꿈."""
    chip = 16
    gap = 10
    item_gap = 26
    x = _MARGIN_L
    line_h = 26
    for idx, nickname in enumerate(series):
        color = _LINE_COLORS[idx % len(_LINE_COLORS)]
        label = f"{nickname} · 평균 {averages.get(nickname, 0.0):.1f}%/일"
        label_w = draw.textlength(label, font=font)
        item_w = chip + gap + label_w
        if x + item_w > _GRAPH_W - _MARGIN_R and x > _MARGIN_L:
            x = _MARGIN_L
            y += line_h
        draw.rectangle([x, y, x + chip, y + chip], fill=color)
        draw.text((x + chip + gap, y - 4), label, font=font, fill=_TEXT)
        x += item_w + item_gap
