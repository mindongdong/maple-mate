"""GradeBadges 셀 렌더 단위테스트 (PNG bytes 생성·폭 계산·미상 등급)."""
from __future__ import annotations

import io

from PIL import Image

from maple_mate.bot.table_image import GradeBadges, render_table_image

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _png_width(png: bytes) -> int:
    return Image.open(io.BytesIO(png)).width


def test_render_badges_produces_png() -> None:
    png = render_table_image(
        ["순위", "캐릭터", "등업"],
        [["1", "손바", GradeBadges((("에픽", 2), ("유니크", 3)))]],
        aligns=["center", "left", "left"],
    )
    assert png[:8] == _PNG_MAGIC


def test_dash_string_when_no_tierup() -> None:
    # 0건은 호출부가 '—' 문자열을 전달(GradeBadges 아님) — 일반 텍스트 셀로 렌더.
    png = render_table_image(["등업"], [["—"]])
    assert png[:8] == _PNG_MAGIC


def test_more_badges_widen_column() -> None:
    one = render_table_image(["등업"], [[GradeBadges((("에픽", 1),))]])
    two = render_table_image(["등업"], [[GradeBadges((("에픽", 1), ("유니크", 2)))]])
    assert _png_width(two) > _png_width(one)


def test_unknown_grade_renders_without_error() -> None:
    # 미상 등급은 회색 기본 색으로 그려야지 예외가 나면 안 됨.
    png = render_table_image(["등업"], [[GradeBadges((("정체불명", 1),))]])
    assert png[:8] == _PNG_MAGIC
