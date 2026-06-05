"""`/아이템` 장비를 PNG 카드로 렌더 (전달-무관 순수 렌더).

텍스트 나열 대신 게임 툴팁풍 카드로 보여준다: 아이콘 + 이름 + 스타포스/잠재등급 뱃지 +
실제 잠재·에디·추옵·작 수치. 비교(여러 명)는 카드를 한 PNG에 세로로 스택한다.

스코프: 우열 판정/환산 점수 없음(설계 §10) — API 실제 값만 표기. 닉↔주인 태그는 이미지에
못 넣으므로(멘션 불가) 호출부가 임베드 범례로 분리한다. 한글 폰트는 table_image 와 공유.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .table_image import _load_fonts

_RGB = tuple[int, int, int]
_Pill = tuple[str, _RGB]  # (뱃지 텍스트, 색)
_DetailRow = tuple[str, _RGB, str]  # (라벨, 라벨색, 값)

# ── 팔레트 ────────────────────────────────────────────────────────────
_IMG_BG = (30, 31, 34)  # 카드 사이 배경(패널보다 어둡게)
_PANEL = (43, 45, 49)  # 카드 패널(임베드 톤)
_ICON_BG = (24, 25, 28)  # 아이콘 칸 배경
_NAME = (240, 242, 245)
_TEXT = (214, 217, 222)
_MUTED = (150, 154, 162)
_STAR = (255, 156, 56)  # 스타포스 오렌지(참조 카드 톤)

# 잠재 등급 → (색, 표시 라벨). 미상 등급은 회색.
_GRADE: dict[str, tuple[tuple[int, int, int], str]] = {
    "레전드리": ((121, 201, 64), "레전드리"),
    "유니크": ((240, 190, 52), "유니크"),
    "에픽": ((159, 112, 216), "에픽"),
    "레어": ((74, 165, 225), "레어"),
}
_GRADE_DEFAULT = ((128, 132, 140), "")

# ── 치수 ──────────────────────────────────────────────────────────────
_NAME_SIZE = 38
_BODY_SIZE = 28
_PILL_SIZE = 26
_LABEL_SIZE = 26

_ICON_BOX = 116  # 아이콘 칸(정사각)
_PAD = 24  # 카드 내부 여백
_GAP = 22  # 아이콘↔텍스트 간격
_ROW_GAP = 10  # 텍스트 줄 간격
_PILL_GAP = 10  # 뱃지 사이 간격
_CARD_GAP = 16  # 카드 사이 간격
_MARGIN = 20  # 이미지 바깥 여백
_RADIUS = 14  # 패널 라운드


@dataclass(frozen=True)
class CardPotential:
    grade: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class ItemCard:
    """카드 1장 렌더 입력(전달-무관). 미착용이면 found=False."""

    label: str  # 카드 헤더(예: "손바 · 모자")
    found: bool
    item_name: str | None = None
    starforce: str | None = None  # None=스타포스 불가 부위(뱃지 숨김)
    icon_png: bytes | None = None
    potential: CardPotential | None = None
    additional: CardPotential | None = None
    add_option: str | None = None
    upgrade: str | None = None
    upgrade_stats: str | None = None  # 작(주문서)으로 오른 스탯


def _grade(name: str) -> tuple[_RGB, str]:
    return _GRADE.get(name, (_GRADE_DEFAULT[0], name))


def _scaled_icon(png: bytes) -> Image.Image | None:
    """아이콘 PNG → 정수배 NEAREST 확대(픽셀아트 보존), _ICON_BOX 안에 맞춤."""
    try:
        icon = Image.open(io.BytesIO(png)).convert("RGBA")
    except (OSError, ValueError):
        return None
    w, h = icon.size
    if w == 0 or h == 0:
        return None
    factor = max(1, min(_ICON_BOX // w, _ICON_BOX // h))
    return icon.resize((w * factor, h * factor), Image.NEAREST)


def _detail_rows(card: ItemCard) -> list[_DetailRow]:
    """(라벨, 라벨색, 값) 줄 목록. 잠재/에디/추옵/작 중 있는 것만."""
    rows: list[_DetailRow] = []
    if card.potential is not None:
        color, _ = _grade(card.potential.grade)
        rows.append(("잠재", color, " · ".join(card.potential.options) or "—"))
    if card.additional is not None:
        color, _ = _grade(card.additional.grade)
        rows.append(("에디", color, " · ".join(card.additional.options) or "—"))
    if card.add_option:
        rows.append(("추옵", _MUTED, card.add_option))
    if card.upgrade or card.upgrade_stats:
        parts = [p for p in (card.upgrade, card.upgrade_stats) if p]
        rows.append(("작", _MUTED, " · ".join(parts)))
    return rows


def _pills(card: ItemCard) -> list[_Pill]:
    """뱃지(텍스트, 색) 목록: 스타포스 + 잠재등급 + 에디등급."""
    pills: list[_Pill] = []
    if card.starforce is not None:
        pills.append((f"★ {card.starforce}", _STAR))
    if card.potential is not None:
        color, label = _grade(card.potential.grade)
        if label:
            pills.append((label, color))
    if card.additional is not None:
        color, label = _grade(card.additional.grade)
        if label:
            pills.append((label, color))
    return pills


class _Fonts:
    def __init__(self) -> None:
        self.name_r, self.name_b = _load_fonts(_NAME_SIZE)
        self.body_r, self.body_b = _load_fonts(_BODY_SIZE)
        self.pill_r, self.pill_b = _load_fonts(_PILL_SIZE)
        self.label_r, self.label_b = _load_fonts(_LABEL_SIZE)


def _text_w(draw: ImageDraw.ImageDraw, s: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(s, font=font)


def _card_size(
    draw: ImageDraw.ImageDraw, f: _Fonts, card: ItemCard
) -> tuple[int, int, list[_Pill], list[_DetailRow]]:
    """카드 1장의 (필요폭, 높이, pills, detail_rows) 계산."""
    pills = _pills(card)
    rows = _detail_rows(card)

    # 텍스트 블록 폭: 이름 / 뱃지줄 / 디테일줄 중 최대.
    name = card.item_name or ("미착용" if not card.found else "?")
    text_w = _text_w(draw, name, f.name_b)
    pill_w = sum(_text_w(draw, t, f.pill_b) + 2 * 14 for t, _ in pills)
    pill_w += _PILL_GAP * max(0, len(pills) - 1)
    text_w = max(text_w, pill_w)
    label_col = max((_text_w(draw, lbl, f.label_b) for lbl, _, _ in rows), default=0) + 16
    for lbl, _, val in rows:
        text_w = max(text_w, label_col + _text_w(draw, val, f.body_r))

    # 텍스트 블록 높이.
    line = _BODY_SIZE + _ROW_GAP
    text_h = _NAME_SIZE + _ROW_GAP + (_PILL_SIZE + 8) + _ROW_GAP + line * len(rows)
    if not card.found:
        text_h = _NAME_SIZE  # 미착용은 한 줄

    inner_h = max(_ICON_BOX, int(text_h))
    width = int(_PAD + _ICON_BOX + _GAP + text_w + _PAD)
    width = max(width, int(_PAD + _text_w(draw, card.label, f.label_b) + _PAD))  # 긴 라벨도 안 잘리게
    height = int(_PAD + 28 + 6 + inner_h + _PAD)  # 헤더줄(라벨) 포함
    return width, height, pills, rows


def _draw_pill(
    draw: ImageDraw.ImageDraw, x: float, y: float, text: str, font, color: _RGB
) -> float:
    """라운드 뱃지 그리고 오른쪽 x 좌표 반환. 색=테두리/글자, 내부는 옅은 채움."""
    tw = _text_w(draw, text, font)
    h = _PILL_SIZE + 12
    w = tw + 2 * 14
    fill = tuple(int(c * 0.22 + 30 * 0.78) for c in color)  # 색조 옅게
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=fill, outline=color, width=2)
    draw.text((x + 14, y + 6), text, font=font, fill=color)
    return x + w


def _draw_card(
    img: Image.Image, draw: ImageDraw.ImageDraw, f: _Fonts, card: ItemCard,
    x0: int, y0: int, w: int, h: int, pills: list[_Pill], rows: list[_DetailRow],
) -> None:
    accent = _grade(card.potential.grade)[0] if card.potential else _STAR
    # 패널 + 좌측 등급 액센트 스트라이프.
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=_RADIUS, fill=_PANEL)
    draw.rounded_rectangle([x0, y0, x0 + 6, y0 + h], radius=3, fill=accent)

    # 헤더 라벨(닉 · 부위).
    draw.text((x0 + _PAD, y0 + _PAD - 6), card.label, font=f.label_r, fill=_MUTED)
    top = y0 + _PAD + 28 + 6

    # 아이콘 칸.
    ix, iy = x0 + _PAD, top
    draw.rounded_rectangle([ix, iy, ix + _ICON_BOX, iy + _ICON_BOX], radius=10, fill=_ICON_BG,
                           outline=accent, width=2)
    if card.icon_png is not None:
        icon = _scaled_icon(card.icon_png)
        if icon is not None:
            ox = ix + (_ICON_BOX - icon.width) // 2
            oy = iy + (_ICON_BOX - icon.height) // 2
            img.paste(icon, (ox, oy), icon)

    tx = ix + _ICON_BOX + _GAP
    if not card.found:
        draw.text((tx, top + (_ICON_BOX - _NAME_SIZE) // 2), "미착용", font=f.name_r, fill=_MUTED)
        return

    # 이름.
    y = top
    draw.text((tx, y), card.item_name or "?", font=f.name_b, fill=_NAME)
    y += _NAME_SIZE + _ROW_GAP

    # 뱃지줄.
    px = tx
    for text, color in pills:
        px = _draw_pill(draw, px, y, text, f.pill_b, color) + _PILL_GAP
    y += _PILL_SIZE + 12 + _ROW_GAP

    # 디테일줄(라벨 + 값).
    label_col = max((_text_w(draw, lbl, f.label_b) for lbl, _, _ in rows), default=0) + 16
    for lbl, lbl_color, val in rows:
        draw.text((tx, y), lbl, font=f.label_b, fill=lbl_color)
        draw.text((tx + label_col, y), val, font=f.body_r, fill=_TEXT)
        y += _BODY_SIZE + _ROW_GAP


def render_item_cards(cards: list[ItemCard]) -> bytes:
    """아이템 카드(1장 이상)를 세로 스택 PNG 로 렌더 → bytes."""
    if not cards:
        raise ValueError("render_item_cards: 카드가 최소 1장 필요합니다")
    f = _Fonts()
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    sizes = [_card_size(probe, f, c) for c in cards]
    card_w = max(w for w, _, _, _ in sizes)
    total_w = card_w + 2 * _MARGIN
    total_h = _MARGIN + sum(h for _, h, _, _ in sizes) + _CARD_GAP * (len(cards) - 1) + _MARGIN

    img = Image.new("RGB", (total_w, total_h), _IMG_BG)
    draw = ImageDraw.Draw(img)

    y = _MARGIN
    for card, (_, h, pills, rows) in zip(cards, sizes):
        _draw_card(img, draw, f, card, _MARGIN, y, card_w, h, pills, rows)
        y += h + _CARD_GAP

    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()
