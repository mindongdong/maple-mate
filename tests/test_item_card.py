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
        potential=CardPotential(
            "레전드리", ("스킬 재사용 대기시간 -3초", "최대 HP +9%")
        ),
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
    assert (
        Image.open(io.BytesIO(png_two)).height > Image.open(io.BytesIO(png_one)).height
    )


def test_render_not_found_card_is_valid_png():
    assert _is_png(
        item_card.render_item_cards([ItemCard(label="점프 · 모자", found=False)])
    )


def test_render_empty_list_raises():
    import pytest

    with pytest.raises(ValueError):
        item_card.render_item_cards([])


# ── 2열 레이아웃 (6장부터 — 무인자 상한 10장 대비 세로 벽 방지) ──────────────


def test_column_split_examples():
    """5장 이하 1열, 6장부터 첫 열 ⌈n/2⌉ — 6→3·7→4·8→4·9→5·10→5."""
    assert [item_card._column_split(n) for n in (1, 5)] == [1, 5]
    assert [item_card._column_split(n) for n in (6, 7, 8, 9, 10)] == [3, 4, 4, 5, 5]


def _size(cards: list[ItemCard]) -> tuple[int, int]:
    img = Image.open(io.BytesIO(item_card.render_item_cards(cards)))
    return img.width, img.height


def test_five_cards_stay_single_column():
    w1, h1 = _size([_card()])
    w5, h5 = _size([_card(label=f"닉{i} · 모자") for i in range(5)])
    assert w5 == w1  # 1열 유지 — 폭 무변경
    assert h5 > 4 * h1  # 5장 세로 스택


def test_six_cards_fold_into_two_columns():
    w1, h1 = _size([_card()])
    w6, h6 = _size([_card(label=f"닉{i} · 모자") for i in range(6)])
    assert w6 > 1.8 * w1  # 2열 — 폭이 약 2배
    assert h6 < 4 * h1  # 열당 3장 — 세로가 절반 수준


def test_ten_cards_height_matches_five_stack():
    ws, hs = _size([_card(label=f"닉{i} · 모자") for i in range(5)])
    w10, h10 = _size([_card(label=f"닉{i} · 모자") for i in range(10)])
    assert h10 == hs  # 열당 5장 = 5장 1열과 같은 높이
    assert w10 > 1.8 * ws


def test_odd_count_first_column_gets_extra():
    """9장 = 5+4 — 전체 높이는 첫 열(5장) 기준."""
    h5 = _size([_card(label=f"닉{i} · 모자") for i in range(5)])[1]
    h9 = _size([_card(label=f"닉{i} · 모자") for i in range(9)])[1]
    assert h9 == h5


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
    result = item.ItemResult(
        found=True, slot="모자", item=item.parse_item(raw, "모자"), date=None
    )
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
