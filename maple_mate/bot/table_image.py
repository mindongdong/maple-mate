"""비교 표를 PNG 이미지로 렌더 (handoff 후속 UX). 디스코드 텍스트표가 한글 폭·임베드 너비
때문에 정렬을 보장 못 해(깨짐) → 픽셀 고정 이미지로 보낸다. 어디서나 100% 동일.

전달-무관 순수 렌더: 입력은 헤더/행(셀=문자열 또는 NumGrid), 출력은 PNG bytes.
셀은 2종 — 문자열(그대로 텍스트), `NumGrid`(고정 칸 수의 수치 그리드; 세로줄로 칸을 나눠
각 칸 가운데 정렬, 빈 칸은 0, bold_first 면 첫 칸만 볼드). 한글 폰트(macOS 시스템) 필요.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

# (경로, regular index, bold index) — macOS 시스템 한글 폰트 우선, 실패 시 다음 후보.
_FONT_CANDIDATES: tuple[tuple[str, int, int], ...] = (
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0, 6),
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0, 0),
    ("/Library/Fonts/NanumGothic.ttf", 0, 0),
)

# 디스코드 다크 임베드에 어울리는 팔레트.
_BG = (43, 45, 49)  # #2b2d31 (임베드 배경과 근사)
_ROW_ALT = (49, 51, 56)  # 짝수 행 음영
_TEXT = (223, 225, 228)
_HEADER_TEXT = (255, 168, 76)  # 메이플 오렌지 톤
_UNDERLINE = (255, 140, 0)
_BEST = (250, 204, 21)  # 최고 수치 강조(금색) — 헤더 오렌지와 구분되는 밝은 골드
_GRID = (92, 96, 104)  # 주 컬럼 경계·바깥 테두리
_GRID_SUB = (66, 69, 76)  # 그리드 내부 칸 구분선(연하게)

_SIZE = 34
_PAD_X = 18
_PAD_Y = 11
_MARGIN = 20
_SUB_W = 62  # NumGrid 한 칸 폭(두 자릿수 + 여백)


@dataclass(frozen=True)
class NumGrid:
    """고정 칸 수의 수치 그리드 셀.

    values=실제 값들, slots=칸 수(부족분은 0으로 채움), bold_first=True면 첫 칸만 볼드,
    highlight_first=True면 첫 칸을 금색(_BEST)으로 강조(비교 대상 중 첫 값이 최고인 행 표시).
    세로줄로 칸을 나누고 각 칸 안에서 숫자를 가운데 정렬한다.
    """

    values: tuple[int, ...]
    slots: int
    bold_first: bool = False
    highlight_first: bool = False


@dataclass(frozen=True)
class Highlight:
    """최고 수치 강조 셀 — 같은 정렬을 유지하되 볼드 + 금색(_BEST)으로 그린다.

    비교 대상 중 해당 컬럼에서 가장 높은 수치를 가진 행을 한눈에 보이게 한다.
    """

    text: str


def _load_fonts(size: int) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """(본문 Regular, 헤더/강조 Bold) 폰트. 후보를 순회하고 모두 실패하면 기본 폰트."""
    for path, reg_idx, bold_idx in _FONT_CANDIDATES:
        try:
            regular = ImageFont.truetype(path, size, index=reg_idx)
            bold = ImageFont.truetype(path, size, index=bold_idx)
            return regular, bold
        except OSError:
            continue
    fallback = ImageFont.load_default()
    return fallback, fallback


def render_table_image(
    headers: list[str], rows: list, *, aligns: list[str] | None = None
) -> bytes:
    """헤더+행 → 세로줄 그리드 표 PNG bytes.

    셀은 문자열(텍스트, aligns 적용) 또는 `NumGrid`(칸별 가운데 정렬·세로 구분선).
    """
    cols = len(headers)
    aligns = aligns or ["left"] * cols
    regular, bold = _load_fonts(_SIZE)

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def text_w(text: str, font: ImageFont.FreeTypeFont) -> float:
        return probe.textlength(text, font=font)

    def grid_in(c: int) -> NumGrid | None:
        return next((row[c] for row in rows if isinstance(row[c], NumGrid)), None)

    col_w: list[float] = []
    for c in range(cols):
        header_w = text_w(headers[c], bold) + 2 * _PAD_X
        grid = grid_in(c)
        if grid is not None:
            slots = max(r[c].slots for r in rows if isinstance(r[c], NumGrid))
            col_w.append(max(header_w, slots * _SUB_W))
        else:
            widest = header_w
            for row in rows:
                cell = row[c]
                if isinstance(cell, Highlight):  # 볼드라 더 넓을 수 있어 bold 로 측정
                    widest = max(widest, text_w(cell.text, bold) + 2 * _PAD_X)
                else:
                    widest = max(widest, text_w(str(cell), regular) + 2 * _PAD_X)
            col_w.append(widest)

    line_h = _SIZE + 2 * _PAD_Y
    total_w = int(sum(col_w) + 2 * _MARGIN)
    total_h = int(2 * _MARGIN + line_h * (len(rows) + 1))

    img = Image.new("RGB", (total_w, total_h), _BG)
    draw = ImageDraw.Draw(img)

    table_top = _MARGIN
    header_bottom = _MARGIN + line_h
    table_bottom = _MARGIN + line_h * (len(rows) + 1)

    # 1) 행 음영(짝수 행).
    yb = header_bottom
    for idx in range(len(rows)):
        if idx % 2 == 1:
            draw.rectangle([_MARGIN, yb, total_w - _MARGIN, yb + line_h], fill=_ROW_ALT)
        yb += line_h

    # 2) 세로줄: 주 컬럼 경계(전체 높이) + NumGrid 내부 칸 구분선(본문만).
    x = _MARGIN
    xs = [x]
    for c in range(cols):
        x += col_w[c]
        xs.append(x)
    for vx in xs:
        draw.line([(vx, table_top), (vx, table_bottom)], fill=_GRID, width=1)
    x = _MARGIN
    for c in range(cols):
        grid = grid_in(c)
        if grid is not None:
            slots = grid.slots
            sub_w = col_w[c] / slots
            for i in range(1, slots):
                sx = x + i * sub_w
                draw.line([(sx, header_bottom), (sx, table_bottom)], fill=_GRID_SUB, width=1)
        x += col_w[c]

    # 3) 가로 테두리(위/아래) + 헤더 밑줄(오렌지).
    draw.line([(_MARGIN, table_top), (total_w - _MARGIN, table_top)], fill=_GRID, width=1)
    draw.line([(_MARGIN, table_bottom), (total_w - _MARGIN, table_bottom)], fill=_GRID, width=1)
    draw.line(
        [(_MARGIN, header_bottom), (total_w - _MARGIN, header_bottom)], fill=_UNDERLINE, width=2
    )

    def draw_text_cell(s, font, x_left, col, align, y, color) -> None:
        tw = text_w(s, font)
        if align == "right":
            tx = x_left + col - _PAD_X - tw
        elif align == "center":
            tx = x_left + (col - tw) / 2
        else:
            tx = x_left + _PAD_X
        draw.text((tx, y + _PAD_Y), s, font=font, fill=color)

    def draw_numgrid(cell: NumGrid, x_left, col, y) -> None:
        sub_w = col / cell.slots
        vals = list(cell.values[: cell.slots]) + [0] * (cell.slots - len(cell.values))
        for i, v in enumerate(vals):
            s = str(v)
            first = i == 0
            font = bold if (first and (cell.bold_first or cell.highlight_first)) else regular
            color = _BEST if (first and cell.highlight_first) else _TEXT
            tw = text_w(s, font)
            draw.text((x_left + i * sub_w + (sub_w - tw) / 2, y + _PAD_Y), s, font=font, fill=color)

    # 4) 헤더(그리드 컬럼은 가운데).
    x = _MARGIN
    for c in range(cols):
        align = "center" if grid_in(c) is not None else aligns[c]
        draw_text_cell(headers[c], bold, x, col_w[c], align, table_top, _HEADER_TEXT)
        x += col_w[c]

    # 5) 본문.
    y = header_bottom
    for row in rows:
        x = _MARGIN
        for c in range(cols):
            cell = row[c]
            if isinstance(cell, NumGrid):
                draw_numgrid(cell, x, col_w[c], y)
            elif isinstance(cell, Highlight):
                draw_text_cell(cell.text, bold, x, col_w[c], aligns[c], y, _BEST)
            else:
                draw_text_cell(cell, regular, x, col_w[c], aligns[c], y, _TEXT)
            x += col_w[c]
        y += line_h

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()
