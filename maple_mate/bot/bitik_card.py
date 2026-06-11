"""`/비틱` 자랑 카드 PNG 렌더 (전달-무관 순수 렌더, `asyncio.to_thread` 호출 전제).

레이아웃 참고 스크린샷 구성의 다크 단일 카드: 가운데 정렬 세로 스택 —
[아이콘 / 아이템명 / ★시작→★끝 / 사용 메소 / 손익 줄(이득=금색·손해=빨강, Q6) /
강화·파괴 / ★도전 성공·실패 / 기간 footer]. 잠재는 [메소(+감정) / 큐브 텍스트 라벨
색상 코딩(Q8) / 종류별 시작 등급→끝 등급+옵션 풀표시(Q7)]. 아이콘 미매칭(None)이면
아이콘 칸 없이 텍스트 중심 레이아웃(Q5). 팔레트·폰트는 table_image/item_card 와 공유.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from ..bitik.service import ADDITIONAL_KIND, PotentialBitik, StarforceBitik
from ..character.service import format_eok
from .item_card import _scaled_icon
from .table_image import GRADE_COLORS, _load_fonts

_RGB = tuple[int, int, int]

# ── 팔레트 (item_card 와 동일 시각 언어) ─────────────────────────────────────
_IMG_BG = (30, 31, 34)
_PANEL = (43, 45, 49)
_ICON_BG = (24, 25, 28)
_NAME = (240, 242, 245)
_TEXT = (214, 217, 222)
_MUTED = (150, 154, 162)
_STAR = (255, 156, 56)  # 스타포스 오렌지
_GAIN = (250, 204, 21)  # 이득 = 금색(table_image._BEST 와 동일)
_LOSS = (240, 100, 100)  # 손해·실패 = 빨강
_SUCCESS = (120, 170, 250)  # 도전 성공 = 파랑(참고 스크린샷 톤)
_DIVIDER = (66, 69, 76)

# 큐브 종류 색상 코딩(Q8) — 라벨 앞쪽 키워드 매칭, 미상은 본문색.
_CUBE_COLORS: tuple[tuple[str, _RGB], ...] = (
    ("에디", (159, 112, 216)),
    ("레드", (235, 92, 92)),
    ("블랙", (190, 195, 205)),
    ("수상한", (120, 185, 120)),
    ("장인", (240, 190, 52)),
    ("명장", (255, 156, 56)),
)
_MESO_RESET_COLOR = (137, 180, 250)

# ── 치수 ──────────────────────────────────────────────────────────────
_NAME_SIZE = 40
_BODY_SIZE = 30
_SMALL_SIZE = 26
_ICON_BOX = 116
_PAD_X = 48
_PAD_Y = 36
_MIN_WIDTH = 560
_RADIUS = 16
_ICON_GAP = 18  # 아이콘 ↔ 첫 줄 간격
_FOOTER_GAP = 26  # 본문 ↔ footer 간격


@dataclass(frozen=True)
class _Seg:
    """한 줄 안의 색·폰트 구간."""

    text: str
    color: _RGB
    font: ImageFont.FreeTypeFont


@dataclass(frozen=True)
class _Line:
    """가운데 정렬 한 줄. segs 가 비면 가로 구분선(divider)."""

    segs: tuple[_Seg, ...]
    gap_after: int = 12


class _Fonts:
    def __init__(self) -> None:
        _, self.name_b = _load_fonts(_NAME_SIZE)  # 이름은 볼드만 사용
        self.body_r, self.body_b = _load_fonts(_BODY_SIZE)
        self.small_r, _ = _load_fonts(_SMALL_SIZE)  # 부가 정보는 레귤러만 사용


def _line_metrics(draw: ImageDraw.ImageDraw, line: _Line) -> tuple[float, int]:
    """(폭, 높이). divider 는 폭 0·높이 2."""
    if not line.segs:
        return 0.0, 2
    width = sum(draw.textlength(s.text, font=s.font) for s in line.segs)
    height = max(s.font.size for s in line.segs)
    return width, int(height)


def _grade_color(grade: str) -> _RGB:
    return GRADE_COLORS.get(grade, _MUTED)


def _cube_color(cube_type: str) -> _RGB:
    for keyword, color in _CUBE_COLORS:
        if keyword in cube_type:
            return color
    return _TEXT


def _profit_segs(net_meso: int, f: _Fonts) -> tuple[_Seg, ...]:
    """기댓값 대비 손익 한 줄(Q6). net = 기대 − 실제 (양수=이득)."""
    if net_meso > 0:
        return (
            _Seg("기댓값 대비 ", _MUTED, f.body_r),
            _Seg(f"+{format_eok(net_meso)} 이득", _GAIN, f.body_b),
        )
    if net_meso < 0:
        return (
            _Seg("기댓값 대비 ", _MUTED, f.body_r),
            _Seg(f"-{format_eok(-net_meso)} 손해", _LOSS, f.body_b),
        )
    return (_Seg("기댓값 대비 ±0", _MUTED, f.body_r),)


def _starforce_lines(b: StarforceBitik, f: _Fonts) -> list[_Line]:
    lines = [
        _Line((_Seg(b.item, _NAME, f.name_b),), gap_after=16),
        _Line(
            (
                _Seg(f"★{b.start_star}", _STAR, f.body_b),
                _Seg("  →  ", _MUTED, f.body_r),
                _Seg(f"★{b.end_star}", _STAR, f.body_b),
            ),
            gap_after=14,
        ),
        _Line(
            (_Seg(f"{format_eok(b.actual_meso)} 메소", _NAME, f.body_b),), gap_after=10
        ),
        _Line(_profit_segs(b.net_meso, f), gap_after=16),
        _Line(
            (
                _Seg("강화/파괴 ", _MUTED, f.body_r),
                _Seg(f"{b.attempt_count}번/{b.destroy_count}번", _TEXT, f.body_b),
            ),
            gap_after=10,
        ),
    ]
    challenge: list[_Seg] = [_Seg(f"★{b.challenge_star}도전 ", _STAR, f.body_b)]
    if b.challenge_success:
        challenge.append(_Seg(f"{b.challenge_success}성공", _SUCCESS, f.body_b))
    if b.challenge_fail:
        if b.challenge_success:
            challenge.append(_Seg(" ", _TEXT, f.body_r))
        challenge.append(_Seg(f"{b.challenge_fail}실패", _LOSS, f.body_b))
    lines.append(_Line(tuple(challenge)))
    return lines


def _section_kind_label(kind: str) -> str:
    return "에디셔널" if kind == ADDITIONAL_KIND else "잠재"


def _potential_lines(b: PotentialBitik, f: _Fonts) -> list[_Line]:
    lines = [
        _Line((_Seg(b.item, _NAME, f.name_b),), gap_after=8),
        _Line((_Seg(f"Lv.{b.item_level}", _MUTED, f.small_r),), gap_after=16),
        _Line(
            (_Seg(f"{format_eok(b.reset_meso)} 메소", _NAME, f.body_b),), gap_after=8
        ),
    ]
    if b.appraisal_meso:
        lines.append(
            _Line(
                (
                    _Seg(
                        f"+ 감정 {format_eok(b.appraisal_meso)} 메소", _MUTED, f.small_r
                    ),
                ),
                gap_after=16,
            )
        )

    # 큐브 사용량 — 텍스트 라벨+개수, 종류별 색상 코딩(Q8). 메소 재설정도 같은 줄 규약.
    usage: list[_Seg] = []
    for cube_type, count in b.cube_counts:
        if usage:
            usage.append(_Seg("  ·  ", _MUTED, f.body_r))
        usage.append(_Seg(f"{cube_type} ×{count}", _cube_color(cube_type), f.body_b))
    if b.meso_reset_count:
        if usage:
            usage.append(_Seg("  ·  ", _MUTED, f.body_r))
        usage.append(
            _Seg(f"메소 재설정 ×{b.meso_reset_count}", _MESO_RESET_COLOR, f.body_b)
        )
    if usage:
        lines.append(_Line((), gap_after=16))  # divider
        lines.append(_Line(tuple(usage), gap_after=16))

    # 종류별 시작→끝 섹션(Q7): 시작=등급만, 끝=등급+옵션 풀표시.
    for section in b.sections:
        lines.append(_Line((), gap_after=16))  # divider
        lines.append(
            _Line(
                (
                    _Seg(f"{_section_kind_label(section.kind)}  ", _NAME, f.body_b),
                    _Seg(
                        section.start_grade or "—",
                        _grade_color(section.start_grade),
                        f.body_b,
                    ),
                    _Seg("  →  ", _MUTED, f.body_r),
                    _Seg(
                        section.end_grade or "—",
                        _grade_color(section.end_grade),
                        f.body_b,
                    ),
                ),
                gap_after=10,
            )
        )
        for option in section.end_options:
            lines.append(_Line((_Seg(option, _TEXT, f.small_r),), gap_after=6))

    return lines


def _render_card(
    lines: list[_Line], icon_png: bytes | None, period_label: str, f: _Fonts
) -> bytes:
    """가운데 정렬 세로 스택 카드 → PNG bytes. icon_png None 이면 아이콘 칸 생략."""
    footer_line = _Line((_Seg(period_label, _MUTED, f.small_r),))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    metrics = [_line_metrics(probe, ln) for ln in lines]
    footer_w, footer_h = _line_metrics(probe, footer_line)

    icon = _scaled_icon(icon_png) if icon_png is not None else None
    icon_h = (_ICON_BOX + _ICON_GAP) if icon is not None else 0

    content_w = max([footer_w, *(w for w, _ in metrics)])
    card_w = max(_MIN_WIDTH, int(content_w) + 2 * _PAD_X)
    body_h = sum(h + ln.gap_after for (_, h), ln in zip(metrics, lines))
    card_h = _PAD_Y + icon_h + body_h + _FOOTER_GAP + footer_h + _PAD_Y

    img = Image.new("RGB", (card_w + 32, card_h + 32), _IMG_BG)
    draw = ImageDraw.Draw(img)
    x0, y0 = 16, 16
    draw.rounded_rectangle(
        [x0, y0, x0 + card_w, y0 + card_h], radius=_RADIUS, fill=_PANEL
    )

    y = y0 + _PAD_Y
    if icon is not None:
        bx = x0 + (card_w - _ICON_BOX) // 2
        draw.rounded_rectangle(
            [bx, y, bx + _ICON_BOX, y + _ICON_BOX], radius=12, fill=_ICON_BG
        )
        img.paste(
            icon,
            (bx + (_ICON_BOX - icon.width) // 2, y + (_ICON_BOX - icon.height) // 2),
            icon,
        )
        y += _ICON_BOX + _ICON_GAP

    def draw_line(line: _Line, width: float, height: int, ty: int) -> None:
        if not line.segs:  # divider
            draw.line(
                [(x0 + _PAD_X, ty), (x0 + card_w - _PAD_X, ty)], fill=_DIVIDER, width=2
            )
            return
        tx = x0 + (card_w - width) / 2
        for seg in line.segs:
            # 구간별 baseline 정렬: 같은 줄의 작은 폰트는 아래 기준선에 맞춘다.
            draw.text(
                (tx, ty + height - seg.font.size),
                seg.text,
                font=seg.font,
                fill=seg.color,
            )
            tx += draw.textlength(seg.text, font=seg.font)

    for line, (width, height) in zip(lines, metrics):
        draw_line(line, width, height, y)
        y += height + line.gap_after

    y += _FOOTER_GAP - 12
    draw_line(footer_line, footer_w, footer_h, y)

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()


def render_starforce_card(
    bitik: StarforceBitik, icon_png: bytes | None, period_label: str
) -> bytes:
    """스타포스 자랑 카드 1장 → PNG bytes (Q6 구성 + 손익 줄)."""
    f = _Fonts()
    return _render_card(_starforce_lines(bitik, f), icon_png, period_label, f)


def render_potential_card(
    bitik: PotentialBitik, icon_png: bytes | None, period_label: str
) -> bytes:
    """잠재 자랑 카드 1장 → PNG bytes (Q7 섹션 + Q8 큐브 텍스트 라벨)."""
    f = _Fonts()
    return _render_card(_potential_lines(bitik, f), icon_png, period_label, f)
