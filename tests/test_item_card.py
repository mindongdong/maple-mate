"""아이템 카드 PNG 렌더 단위테스트 (전달-무관 순수 렌더 — PNG 유효성 + 뱃지/줄 구성)."""
from __future__ import annotations

import io

from PIL import Image

from maple_mate.bot import item_card
from maple_mate.bot.item_card import CardPotential, ItemCard


def _card(**kw) -> ItemCard:
    base = dict(
        label="손바 · 모자",
        found=True,
        item_name="하이네스 워리어헬름",
        starforce="19",
        potential=CardPotential("레전드리", ("스킬 재사용 대기시간 -3초", "최대 HP +9%")),
        additional=CardPotential("에픽", ("공격력 +21",)),
        add_option="STR +76",
        upgrade="주문서 12회",
        upgrade_stats="STR +29, 공격력 +25",
    )
    base.update(kw)
    return ItemCard(**base)


def _is_png(data: bytes) -> bool:
    img = Image.open(io.BytesIO(data))
    img.verify()
    return img.format == "PNG"


def test_render_single_card_returns_valid_png():
    assert _is_png(item_card.render_item_cards([_card()]))


def test_render_stacks_multiple_cards():
    png_one = item_card.render_item_cards([_card()])
    png_two = item_card.render_item_cards([_card(), _card(label="점프 · 모자")])
    assert _is_png(png_two)
    # 세로 스택이므로 2장이 1장보다 키가 크다.
    assert Image.open(io.BytesIO(png_two)).height > Image.open(io.BytesIO(png_one)).height


def test_render_not_found_card_is_valid_png():
    assert _is_png(item_card.render_item_cards([ItemCard(label="점프 · 모자", found=False)]))


def test_render_empty_list_raises():
    import pytest

    with pytest.raises(ValueError):
        item_card.render_item_cards([])


def test_additional_grade_pill_has_no_plus_prefix():
    pills = item_card._pills(_card())
    labels = [text for text, _ in pills]
    assert "★ 19" in labels
    assert "레전드리" in labels
    assert "에픽" in labels  # '+에픽' 아님(피드백 #1)
    assert not any(label.startswith("+") for label in labels)


def test_jak_row_merges_upgrade_and_scroll_stats():
    rows = item_card._detail_rows(_card())
    jak = next(value for label, _, value in rows if label == "작")
    assert jak == "주문서 12회 · STR +29, 공격력 +25"


def test_starforce_none_hides_star_pill():
    pills = item_card._pills(_card(starforce=None))
    assert not any(text.startswith("★") for text, _ in pills)


# ── ItemResult → ItemCard 브리지(commands._to_item_card) ───────────────


def test_to_item_card_combines_options_from_result():
    from maple_mate.character import item
    from maple_mate.character.commands import _to_item_card

    raw = {
        "item_name": "테스트헬름",
        "item_icon": "https://x/icon",
        "starforce": "19",
        "potential_option_grade": "레전드리",
        "potential_option_1": "스킬 재사용 대기시간 -2초",
        "potential_option_2": "스킬 재사용 대기시간 -1초",
        "additional_potential_option_grade": "에픽",
        "additional_potential_option_1": "공격력 +11",
        "additional_potential_option_2": "공격력 +10",
        "item_etc_option": {"str": "29"},
    }
    result = item.ItemResult(found=True, slot="모자", item=item.parse_item(raw, "모자"), date=None)
    card = _to_item_card("손바 · 모자", result, icon_png=b"icon")

    assert card.found is True
    assert card.icon_png == b"icon"
    assert card.potential.options == ("스킬 재사용 대기시간 -3초",)  # 합산
    assert card.additional.options == ("공격력 +21",)  # 합산
    assert card.upgrade_stats == "STR +29"


def test_to_item_card_not_found():
    from maple_mate.character import item
    from maple_mate.character.commands import _to_item_card

    result = item.ItemResult(found=False, slot="모자", item=None, date=None)
    card = _to_item_card("점프 · 모자", result, icon_png=None)
    assert card.found is False and card.item_name is None
