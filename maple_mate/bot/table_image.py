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

_RGB = tuple[int, int, int]

# 잠재 등급 → 색 (단일 출처). item_card._GRADE 가 이 표를 참조 — 두 모듈이 동일 시각 언어를
# 쓰도록 색은 여기 한 곳에만 둔다(table_image 는 item_card 를 import 하지 않음 → 순환 없음).
GRADE_COLORS: dict[str, _RGB] = {
    "레전드리": (121, 201, 64),
    "유니크": (240, 190, 52),
    "에픽": (159, 112, 216),
    "레어": (74, 165, 225),
}
_GRADE_BADGE_DEFAULT: _RGB = (128, 132, 140)  # 미상 등급은 회색

# (경로, regular index, bold index) — macOS 시스템 한글 폰트 우선, 실패 시 다음 후보.
_FONT_CANDIDATES: tuple[tuple[str, int, int], ...] = (
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0, 6),
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0, 0),
    ("/Library/Fonts/NanumGothic.ttf", 0, 0),
    # 리눅스(CI 러너·프로덕션 컨테이너): debian fonts-nanum 패키지 경로.
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0, 0),
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

_BADGE_SIZE = 26  # GradeBadges pill 글자 크기(행 높이 안에 들어가도록 본문보다 작게)
_BADGE_PAD_X = 13  # pill 좌우 안쪽 여백
_BADGE_GAP = 8  # pill 사이 간격


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


@dataclass(frozen=True)
class GradeBadges:
    """등업 from-등급 뱃지 셀. items=[(등급명, 횟수), ...] (0건 제외).

    각 등급을 GRADE_COLORS 색 라운드 pill('등급 ×횟수')로 가로 나열한다. 색만으로 어느
    등급에서 올랐는지 즉시 읽힌다. 빈 목록이면 호출부가 '—' 문자열을 대신 전달한다.
    """

    items: tuple[tuple[str, int], ...]


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
    badge_font, _ = _load_fonts(_BADGE_SIZE)

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def text_w(text: str, font: ImageFont.FreeTypeFont) -> float:
        return probe.textlength(text, font=font)

    def grid_in(c: int) -> NumGrid | None:
        return next((row[c] for row in rows if isinstance(row[c], NumGrid)), None)

    def badge_text(label: str, count: int) -> str:
        return f"{label} ×{count}"

    def badges_width(cell: GradeBadges) -> float:
        """GradeBadges pill 묶음의 가로 폭(pill 폭 합 + 간격)."""
        widths = [
            text_w(badge_text(lbl, cnt), badge_font) + 2 * _BADGE_PAD_X
            for lbl, cnt in cell.items
        ]
        return sum(widths) + _BADGE_GAP * max(0, len(widths) - 1)

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
                elif isinstance(cell, GradeBadges):
                    widest = max(widest, badges_width(cell) + 2 * _PAD_X)
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
                draw.line(
                    [(sx, header_bottom), (sx, table_bottom)], fill=_GRID_SUB, width=1
                )
        x += col_w[c]

    # 3) 가로 테두리(위/아래) + 헤더 밑줄(오렌지).
    draw.line(
        [(_MARGIN, table_top), (total_w - _MARGIN, table_top)], fill=_GRID, width=1
    )
    draw.line(
        [(_MARGIN, table_bottom), (total_w - _MARGIN, table_bottom)],
        fill=_GRID,
        width=1,
    )
    draw.line(
        [(_MARGIN, header_bottom), (total_w - _MARGIN, header_bottom)],
        fill=_UNDERLINE,
        width=2,
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
            font = (
                bold
                if (first and (cell.bold_first or cell.highlight_first))
                else regular
            )
            color = _BEST if (first and cell.highlight_first) else _TEXT
            tw = text_w(s, font)
            draw.text(
                (x_left + i * sub_w + (sub_w - tw) / 2, y + _PAD_Y),
                s,
                font=font,
                fill=color,
            )

    def draw_grade_badges(cell: GradeBadges, x_left, col, align, y) -> None:
        """등급 색 라운드 pill('등급 ×횟수')을 가로 나열. 행 높이 안에서 세로 중앙."""
        pills = [
            (badge_text(lbl, cnt), GRADE_COLORS.get(lbl, _GRADE_BADGE_DEFAULT))
            for lbl, cnt in cell.items
        ]
        widths = [text_w(t, badge_font) + 2 * _BADGE_PAD_X for t, _ in pills]
        group_w = sum(widths) + _BADGE_GAP * max(0, len(pills) - 1)
        if align == "right":
            sx = x_left + col - _PAD_X - group_w
        elif align == "center":
            sx = x_left + (col - group_w) / 2
        else:
            sx = x_left + _PAD_X
        pill_h = _BADGE_SIZE + 12
        py = y + (line_h - pill_h) / 2
        px = sx
        for (text, color), w in zip(pills, widths):
            fill = tuple(int(ch * 0.22 + bg * 0.78) for ch, bg in zip(color, _BG))
            draw.rounded_rectangle(
                [px, py, px + w, py + pill_h],
                radius=pill_h / 2,
                fill=fill,
                outline=color,
                width=2,
            )
            tw = text_w(text, badge_font)
            draw.text((px + (w - tw) / 2, py + 6), text, font=badge_font, fill=color)
            px += w + _BADGE_GAP

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
            elif isinstance(cell, GradeBadges):
                draw_grade_badges(cell, x, col_w[c], aligns[c], y)
            else:
                draw_text_cell(cell, regular, x, col_w[c], aligns[c], y, _TEXT)
            x += col_w[c]
        y += line_h

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()
