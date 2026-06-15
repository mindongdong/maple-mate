"""경험치 리더보드 PNG 렌더 — 최근 7일 레벨 추이 그래프(matplotlib, `asyncio.to_thread` 전제).

render_progress_graph: 등록 캐릭터들의 일별 연속 레벨(= character_level + exp%/100)을 절대값
그대로 multi-user 라인으로 그린다. 각 점에 `Lv.287 (69%)` 라벨, 범례에 유저별 일평균 %/일.
입력은 service.history_progress 시계열(닉 → [(date, progress|None)]), 출력은 PNG BytesIO.
다크 팔레트·한글 폰트는 table_image 와 공유한다. None 구간은 선이 끊기고, 데이터 0개 유저는 제외.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import date

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from .table_image import _BG, _FONT_CANDIDATES, _GRID, _GRID_SUB, _HEADER_TEXT, _TEXT

log = logging.getLogger(__name__)

_RGB = tuple[int, int, int]

# 라인 색 팔레트(순환) — 다크 배경 대비 좋은 톤(표 그래프와 동일 계열).
_LINE_COLORS: tuple[str, ...] = (
    "#ffa84c",  # 메이플 오렌지
    "#4aa5e1",  # 블루
    "#79c940",  # 그린
    "#f06eaa",  # 핑크
    "#9f70d8",  # 퍼플
    "#facc15",  # 골드
    "#60d6c8",  # 틸
    "#e16060",  # 레드
)

# 한글 폰트 파일(matplotlib FontProperties 용) — 표와 동일 후보 중 첫 존재 경로(없으면 기본).
_FONT_FILE = next((p for p, *_ in _FONT_CANDIDATES if os.path.exists(p)), None)
if (
    _FONT_FILE is None
):  # 슬림 컨테이너에 fonts-nanum 누락 시 한글이 깨짐(tofu) → 로그로 가시화
    log.warning(
        "한글 폰트 후보를 찾지 못했어요 — 그래프 한글이 깨질 수 있어요(fonts-nanum 설치 필요)"
    )

_FIG_W, _FIG_H, _DPI = 9.2, 4.8, 150


def _hex(rgb: _RGB) -> str:
    """(r,g,b) 0-255 → matplotlib 용 '#rrggbb'."""
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _font(size: float) -> FontProperties:
    """한글 폰트 FontProperties(파일 미발견 시 기본 폰트)."""
    return FontProperties(fname=_FONT_FILE, size=size)


def _progress_label(progress: float) -> str:
    """연속 progress(레벨 + exp%/100) → `Lv.287 (69%)`. 정수 레벨 + 정수 exp%."""
    level = int(progress)
    pct = min(round((progress - level) * 100), 99)  # 99.5%↑ 가 '(100%)'로 보이지 않게
    return f"Lv.{level} ({pct}%)"


def _daily_average(points: list[tuple[date, float | None]]) -> float:
    """일평균 %/일 = (마지막 − 처음 가용 레벨) × 100 ÷ 사이 일수. 데이터 0/1개면 0(1.0레벨=100%).

    progress 가 연속이라 구간 내 레벨업도 자연 합산된다(처음~끝 레벨 차이가 곧 총 진행량).
    """
    data = [(d, v) for d, v in points if v is not None]
    if len(data) < 2:
        return 0.0
    (first_date, first_value), (last_date, last_value) = data[0], data[-1]
    gaps = (last_date - first_date).days
    return (last_value - first_value) * 100 / gaps if gaps > 0 else 0.0


def _to_png(fig: Figure) -> io.BytesIO:
    """Figure → PNG BytesIO(Agg 캔버스, pyplot 전역상태 비사용 → 워커스레드 안전)."""
    buffer = io.BytesIO()
    FigureCanvasAgg(fig).print_png(buffer)
    buffer.seek(0)
    return buffer


def render_progress_graph(
    series: dict[str, list[tuple[date, float | None]]], ref_date: date
) -> io.BytesIO:
    """유저별 최근 7일 연속 레벨(= 레벨 + exp%/100) 라인 그래프 PNG. series=닉 → [(날짜, progress|None)].

    Y축은 절대 레벨, 각 점에 `Lv.287 (69%)` 라벨, 범례에 유저별 일평균 %/일. 데이터 0개 유저는
    제외, None 구간은 선이 끊긴다. 전원 데이터 없으면 안내 문구만. 레벨업 마커 없음(연속값).
    모든 series 리스트는 길이가 같다고 가정한다(history_progress 가 동일 display_dates 로 생성).
    """
    bg, fg, grid, accent = _hex(_BG), _hex(_TEXT), _hex(_GRID_SUB), _hex(_HEADER_TEXT)
    axis = _hex(_GRID)

    fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    fig.patch.set_facecolor(bg)
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg)
    ax.set_title(
        "최근 7일 레벨 추이", fontproperties=_font(16), color=accent, loc="left", pad=12
    )

    # 데이터 0개 유저 제외(라인·범례 모두) + 공통 날짜축.
    drawn = {
        nick: pts for nick, pts in series.items() if any(v is not None for _, v in pts)
    }
    dates = [d for d, _ in next(iter(series.values()), [])]

    if not dates or not drawn:
        ax.text(
            0.5,
            0.5,
            "표시할 진행량 데이터가 아직 없어요.",
            ha="center",
            va="center",
            color=fg,
            fontproperties=_font(13),
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(axis)
        return _to_png(fig)

    n = len(dates)
    xs = list(range(n))
    for idx, (nick, pts) in enumerate(drawn.items()):
        color = _LINE_COLORS[idx % len(_LINE_COLORS)]
        ys = [v if v is not None else np.nan for _, v in pts]
        ax.plot(
            xs,
            ys,
            color=color,
            marker="o",
            markersize=5,
            linewidth=2.2,
            label=f"{nick} · 평균 {_daily_average(pts):.1f}%/일",
        )
        # 점 라벨은 라인별로 위/아래 번갈아 배치해 겹침을 줄인다.
        dy, va = (9, "bottom") if idx % 2 == 0 else (-17, "top")
        for x, (_, v) in zip(xs, pts):
            if v is None:
                continue
            ax.annotate(
                _progress_label(v),
                (x, v),
                textcoords="offset points",
                xytext=(0, dy),
                ha="center",
                va=va,
                color=color,
                fontproperties=_font(9),
            )

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{d:%m/%d}" for d in dates])
    # y눈금은 기본 AutoLocator(범위에 맞춰 정수~0.1 단위 자동). :g 로 'Lv.287'·'Lv.287.6' 처럼
    # 구분되게 — int 반올림은 같은 레벨 안(범위<1)에서 287.6·287.8 을 둘 다 'Lv.288'로 뭉갠다.
    ax.yaxis.set_major_formatter(lambda v, _pos: f"Lv.{v:g}")
    ax.margins(y=0.22)
    ax.grid(True, color=grid, linewidth=0.8, alpha=0.7)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(_font(10))
        label.set_color(fg)
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)
    for name in ("left", "bottom"):
        ax.spines[name].set_color(axis)

    legend = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=min(len(drawn), 3),
        prop=_font(11),
        facecolor=bg,
        edgecolor=axis,
        framealpha=0.0,
    )
    for text in legend.get_texts():
        text.set_color(fg)

    fig.subplots_adjust(left=0.1, right=0.97, top=0.86, bottom=0.2)
    return _to_png(fig)
