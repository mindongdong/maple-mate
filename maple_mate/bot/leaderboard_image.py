"""경험치 리더보드 PNG 렌더 — 절대 레벨 추이 그래프(matplotlib, `asyncio.to_thread` 전제).

render_progress_graph: 등록 캐릭터들의 최근 7일 진행도(= character_level + exp%/100)를 **절대값
그대로** multi-user 라인으로 그린다 — 선 높이 = 총 레벨이라 그래프 순위가 곧 레벨 순위(임베드
순위판과 일치). 선 끝에 `닉네임 Lv.287 (79%)`를 붙여 범례를 내장하고(끝점이 붙으면 세로 분산),
중간 점별 라벨은 두지 않는다. 순위(현재 레벨)는 임베드 텍스트가 Top10으로 함께 보여준다(ADR-0011).
입력 series 는 호출측(broadcast)이 이미 상위 10명으로 캡해 넘긴다 — 이 모듈은 받은 만큼 그린다.
시리즈별 색+마커로 선을 식별한다. 입력은 service.history_progress 시계열(닉 → [(date,
progress|None)]), 출력은 PNG BytesIO. 다크 팔레트·한글 폰트는 table_image 와 공유한다. None
구간은 선이 끊기고, 데이터 0개 유저는 제외.
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
from matplotlib.ticker import MaxNLocator

from .table_image import _BG, _FONT_CANDIDATES, _GRID, _GRID_SUB, _TEXT

log = logging.getLogger(__name__)

_RGB = tuple[int, int, int]

# 라인 색 팔레트(순환) — 다크 배경 대비 좋은 톤(표 그래프와 동일 계열). 10색 모두 고유라 상위 10개
# 라인은 **색만으로** 구별된다(마커는 색약·교차 대비 보조). 11번째부터만 색이 순환한다.
_LINE_COLORS: tuple[str, ...] = (
    "#ffa84c",  # 메이플 오렌지
    "#4aa5e1",  # 블루
    "#79c940",  # 그린
    "#f06eaa",  # 핑크
    "#9f70d8",  # 퍼플
    "#facc15",  # 골드
    "#60d6c8",  # 틸
    "#e16060",  # 레드
    "#b8d44a",  # 라임
    "#7a8cff",  # 인디고
)

# 라인 마커(순환) — 색과 함께 시리즈 식별(선 교차·유사색·색약 대비).
_LINE_MARKERS: tuple[str, ...] = ("o", "s", "^", "D", "v", "P", "X", "*")

# 한글 폰트 파일(matplotlib FontProperties 용) — 표와 동일 후보 중 첫 존재 경로(없으면 기본).
_FONT_FILE = next((p for p, *_ in _FONT_CANDIDATES if os.path.exists(p)), None)
if (
    _FONT_FILE is None
):  # 슬림 컨테이너에 fonts-nanum 누락 시 한글이 깨짐(tofu) → 로그로 가시화
    log.warning(
        "한글 폰트 후보를 찾지 못했어요 — 그래프 한글이 깨질 수 있어요(fonts-nanum 설치 필요)"
    )

_FIG_W, _FIG_H, _DPI = 11.0, 5.0, 150


def _hex(rgb: _RGB) -> str:
    """(r,g,b) 0-255 → matplotlib 용 '#rrggbb'."""
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _font(size: float) -> FontProperties:
    """한글 폰트 FontProperties(파일 미발견 시 기본 폰트)."""
    return FontProperties(fname=_FONT_FILE, size=size)


def _progress_label(progress: float) -> str:
    """연속 progress(레벨+exp%/100) → 'Lv.287 (79%)'. 정수 레벨 + 정수 exp%(99 클램프)."""
    level = int(progress)
    pct = min(round((progress - level) * 100), 99)  # 99.5%↑ 가 '(100%)'로 보이지 않게
    return f"Lv.{level} ({pct}%)"


def _to_png(fig: Figure) -> io.BytesIO:
    """Figure → PNG BytesIO(Agg 캔버스, pyplot 전역상태 비사용 → 워커스레드 안전)."""
    buffer = io.BytesIO()
    FigureCanvasAgg(fig).print_png(buffer)
    buffer.seek(0)
    return buffer


def _spread_labels(values: list[float], min_gap: float) -> list[float]:
    """끝-라벨 세로 위치를 겹치지 않게 — 값 오름차순으로 최소 간격(min_gap)을 강제(위로 밀어 올림).

    순서(인덱스)는 보존하고, 인접 두 라벨이 min_gap 보다 가까우면 아래 것을 기준으로 위 것을
    밀어 최소 간격을 확보한다. 반환은 입력과 같은 길이의 조정된 y 리스트.
    """
    adjusted = list(values)
    prev: float | None = None
    for i in sorted(range(len(values)), key=lambda j: values[j]):
        v = values[i] if prev is None else max(values[i], prev + min_gap)
        adjusted[i] = v
        prev = v
    return adjusted


def render_progress_graph(
    series: dict[str, list[tuple[date, float | None]]], ref_date: date
) -> io.BytesIO:
    """유저별 최근 7일 절대 레벨(= 레벨 + exp%/100) 추이 라인 그래프 PNG.

    series=닉 → [(날짜, progress|None)]. Y축은 절대 레벨(선 높이 = 총 레벨 → 그래프 순위가 곧
    레벨 순위). 선 끝엔 `닉 Lv.287 (79%)`(겹치면 세로 분산), 중간 라벨은 없음. 순위(현재 레벨)는
    임베드 텍스트가 Top10으로 함께 보여준다(ADR-0011). 데이터 0개 유저는 제외, None 구간은 선이
    끊긴다. 전원 데이터 없으면 안내 문구만. 모든 series 리스트는 길이가 같다고 가정.
    """
    bg, fg, grid = _hex(_BG), _hex(_TEXT), _hex(_GRID_SUB)
    axis = _hex(_GRID)

    fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=_DPI)
    fig.patch.set_facecolor(bg)
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg)
    # 그래프 제목 없음 — 임베드 제목·순위판이 맥락을 전달한다.

    # 데이터 0개 유저 제외 + 공통 날짜축.
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
            fontproperties=_font(14),
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(axis)
        return _to_png(fig)

    n = len(dates)
    xs = list(range(n))
    # 색·마커는 입력 순서대로 배정한다 — 호출측(broadcast)이 이미 임베드 순위(display_rows) 순서로
    # series 를 넘기므로 1위가 팔레트 선두 = 임베드 순위판과 **구조적으로** 동일하다. (이전엔 끝점값
    # 으로 재정렬했는데, 라이브 exp% 결손 시 순위 키와 어긋날 수 있었다 — 순위 소스 단일화.)
    ordered = list(drawn.items())

    end_points: list[tuple[int, float, str, str]] = []  # (x, 절대 progress, 닉, 색)
    all_values: list[float] = []
    for idx, (nick, pts) in enumerate(ordered):
        color = _LINE_COLORS[idx % len(_LINE_COLORS)]
        marker = _LINE_MARKERS[idx % len(_LINE_MARKERS)]
        ys = [v if v is not None else np.nan for _, v in pts]
        ax.plot(xs, ys, color=color, marker=marker, markersize=7, linewidth=2.6)
        last_i = max(i for i, (_, v) in enumerate(pts) if v is not None)
        end_points.append((last_i, pts[last_i][1], nick, color))
        all_values.extend(v for _, v in pts if v is not None)

    # 축 범위 — 데이터 실범위에 맞춰 줌(작은 레벨차도 보이게) + 위아래 여백.
    ymin, ymax = min(all_values), max(all_values)
    yspan = (ymax - ymin) or 1.0
    ax.set_xlim(-0.3, (n - 1) + 0.3)
    ax.set_ylim(ymin - yspan * 0.12, ymax + yspan * 0.18)

    # 선 끝 라벨(범례 내장) — 우측 라벨 칸에 정렬, 끝점이 붙으면 세로로 분산해 점과 가는 가이드 연결.
    lo, hi = ax.get_ylim()
    min_gap = (hi - lo) * 0.075
    x_text = (n - 1) + 0.18
    label_ys = _spread_labels([v for _, v, _, _ in end_points], min_gap)
    for (x, value, nick, color), ly in zip(end_points, label_ys):
        if abs(ly - value) > min_gap * 0.15:  # 분산으로 멀어지면 가는 가이드 라인.
            ax.plot(
                [x, x_text - 0.04],
                [value, ly],
                color=color,
                linewidth=0.8,
                alpha=0.5,
                clip_on=False,
            )
        ax.text(
            x_text,
            ly,
            f"{nick} {_progress_label(value)}",
            ha="left",
            va="center",
            color=color,
            fontproperties=_font(14),
            clip_on=False,
        )

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{d:%m/%d}" for d in dates])
    # y눈금 = 절대 레벨('Lv.287'). 정수 눈금만(287.3 같은 소수 눈금 방지 — 정확값은 끝-라벨이 준다).
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(lambda v, _pos: f"Lv.{v:g}")
    ax.grid(True, color=grid, linewidth=0.8, alpha=0.7)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(_font(13))
        label.set_color(fg)
    for name in ("top", "right"):
        ax.spines[name].set_visible(False)
    for name in ("left", "bottom"):
        ax.spines[name].set_color(axis)

    # 그래프가 폭을 전부 차지(표 패널 폐기) — 우측은 선 끝 라벨 칸으로 비워둔다(ADR-0011).
    fig.subplots_adjust(left=0.07, right=0.80, top=0.93, bottom=0.13)
    return _to_png(fig)
