"""비교 렌더 헬퍼 단위테스트 (페이지 분할·실패필드·푸터·이미지 표)."""

from __future__ import annotations

import io

from PIL import Image

from maple_mate.bot import comparison, table_image
from maple_mate.registration.service import Target, TargetOutcome


def _outcome(nick="닉", *, ok=True, error=None):
    target = Target(guild_id=1, discord_user_id=2, nickname=nick, ocid="oc")
    return TargetOutcome(target=target, data={"x": 1} if ok else None, error=error)


def test_field_pages_single_page_when_small():
    pages = comparison.field_pages("T", [("a", "x"), ("b", "y")], per_page=10)
    assert len(pages) == 1
    assert pages[0].title == "T"
    assert len(pages[0].fields) == 2


def test_field_pages_splits_by_count():
    fields = [(f"n{i}", "v") for i in range(12)]
    pages = comparison.field_pages("T", fields, per_page=5)
    assert len(pages) == 3  # 5 + 5 + 2
    assert pages[0].title == "T (1/3)"


def test_field_pages_splits_by_char_budget_even_under_count_cap():
    big = "x" * 1000
    fields = [(f"n{i}", big) for i in range(10)]  # ~10000자 > 4500 예산
    pages = comparison.field_pages("T", fields, per_page=50)  # 개수론 1장이지만
    assert len(pages) >= 2  # 누적 문자수 예산이 강제 분할


def test_field_pages_empty_yields_one_empty_page():
    pages = comparison.field_pages("T", [])
    assert len(pages) == 1
    assert len(pages[0].fields) == 0


def test_field_pages_clips_oversized_value():
    pages = comparison.field_pages("T", [("a", "z" * 5000)])
    assert len(pages[0].fields[0].value) <= 1024


def test_attach_failures_adds_grouped_field_to_each_page():
    pages = comparison.field_pages("T", [("a", "x")])
    outcomes = [
        _outcome("성공", ok=True),
        _outcome("실패자", ok=False, error="닉 변경?"),
    ]
    comparison.attach_failures(pages, outcomes)
    failure_fields = [f for f in pages[0].fields if "조회 실패" in f.name]
    assert len(failure_fields) == 1
    assert "실패자" in failure_fields[0].value


def test_attach_failures_noop_when_all_ok():
    pages = comparison.field_pages("T", [("a", "x")])
    comparison.attach_failures(pages, [_outcome(ok=True)])
    assert all("조회 실패" not in f.name for f in pages[0].fields)


def test_data_footer_null_is_latest():
    assert comparison.data_footer(None) == "최신 기준"
    assert comparison.data_footer("") == "최신 기준"


def test_all_failed_embed_lists_reasons():
    embed = comparison.all_failed_embed(
        "유니온 비교", [_outcome("떡볶이", ok=False, error="미등록")]
    )
    assert "떡볶이" in embed.description and "미등록" in embed.description


# ── 유저 태그 + 정렬표 ────────────────────────────────────────────────


def test_mention_renders_tag_or_empty():
    assert (
        comparison.mention(
            Target(guild_id=1, discord_user_id=42, nickname="닉", ocid="oc")
        )
        == "<@42>"
    )
    # 미등록 합성 대상(id 0/빈 ocid)은 태그 없음
    assert (
        comparison.mention(
            Target(guild_id=1, discord_user_id=0, nickname="닉", ocid="")
        )
        == ""
    )


def test_display_width_counts_hangul_as_two():
    assert comparison._display_width("ab12") == 4
    assert comparison._display_width("손바") == 4  # 한글 2칸 × 2
    assert comparison._display_width("손바99") == 6


def test_truncate_display_by_width():
    assert comparison.truncate_display("손바", 12) == "손바"
    out = comparison.truncate_display("가나다라마바사아", 12)  # 16폭 → 자름
    assert comparison._display_width(out) <= 12
    assert out.endswith("…")


def test_highest_indices_picks_max_ignoring_none():
    assert comparison.highest_indices([10, 30, 20]) == {1}
    assert comparison.highest_indices([10, None, 20]) == {2}  # None 은 후보 제외


def test_highest_indices_includes_ties():
    assert comparison.highest_indices([30, 30, 10]) == {0, 1}


def test_highest_indices_empty_when_no_valid_value():
    assert comparison.highest_indices([None, None]) == set()
    assert comparison.highest_indices([]) == set()


def test_owner_legend_maps_nick_to_mention():
    legend = comparison.owner_legend(
        [Target(1, 10, "손바", "oc"), Target(1, 20, "점프", "oc2")]
    )
    assert legend.startswith("👤")
    assert "손바 <@10>" in legend and "점프 <@20>" in legend


def test_render_table_image_returns_valid_png():
    png = table_image.render_table_image(
        ["캐릭터", "유니온", "챔피언"],
        [["손바", "9327", "SSS 1 / S 1"], ["점프투파이썬", "9205", "A 3"]],
        aligns=["left", "right", "left"],
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 시그니처
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.width > 0 and img.height > 0


def test_render_table_image_numgrid_returns_valid_png():
    # 칸 그리드(코어)·부족분 0채움(공용 2값/3칸)·빈 코어(스탯 III)·볼드 첫칸이 섞여도 렌더 OK.
    png = table_image.render_table_image(
        ["순위", "캐릭터", "공용", "스탯 코어 I", "스탯 코어 III"],
        [
            [
                "1",
                "손바",
                table_image.NumGrid((1, 1), 3),  # 3칸인데 2값 → 마지막 칸 0
                table_image.NumGrid((4, 10, 6), 3, bold_first=True),
                table_image.NumGrid((), 3, bold_first=True),  # 빈 코어 → 0 0 0
            ],
        ],
        aligns=["center", "left", "center", "center", "center"],
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.width > 0 and img.height > 0


def test_highlight_cell_renders_gold_only_when_wrapped():
    # Highlight 셀은 금색(_BEST) 픽셀을 남기고, 일반 문자열 셀은 남기지 않는다.
    def has_gold(png: bytes) -> bool:
        img = Image.open(io.BytesIO(png)).convert("RGB")
        colors = img.getcolors(maxcolors=img.width * img.height) or []
        return any(color == table_image._BEST for _, color in colors)

    with_highlight = table_image.render_table_image(
        ["유니온"], [[table_image.Highlight("9348")]], aligns=["center"]
    )
    without = table_image.render_table_image(["유니온"], [["9348"]], aligns=["center"])
    assert has_gold(with_highlight)
    assert not has_gold(without)


def test_numgrid_highlight_first_renders_gold_only_when_set():
    # highlight_first=True 면 첫 칸이 금색(_BEST)으로, 아니면 일반색으로 그려진다.
    def has_gold(png: bytes) -> bool:
        img = Image.open(io.BytesIO(png)).convert("RGB")
        colors = img.getcolors(maxcolors=img.width * img.height) or []
        return any(color == table_image._BEST for _, color in colors)

    highlighted = table_image.render_table_image(
        ["스탯"],
        [[table_image.NumGrid((4, 10, 6), 3, bold_first=True, highlight_first=True)]],
    )
    plain = table_image.render_table_image(
        ["스탯"], [[table_image.NumGrid((4, 10, 6), 3, bold_first=True)]]
    )
    assert has_gold(highlighted)
    assert not has_gold(plain)


def test_table_image_message_embed_has_legend_and_attachment():
    targets = [Target(1, 111, "손바", "oc"), Target(1, 222, "점프", "oc2")]
    rows = [["손바", "9327"], ["점프", "9205"]]
    outcomes = [
        _outcome("손바", ok=True),
        _outcome("실패자", ok=False, error="닉 변경?"),
    ]
    embed, file = comparison.table_image_message(
        "유니온 비교",
        ["캐릭터", "유니온"],
        rows,
        targets,
        aligns=["left", "right"],
        footer="최신 기준",
        outcomes=outcomes,
        filename="union.png",
    )
    assert file.filename == "union.png"
    assert embed.image.url == "attachment://union.png"
    assert "손바 <@111>" in embed.description and "점프 <@222>" in embed.description
    assert any("조회 실패" in f.name for f in embed.fields)  # 실패분은 필드로
    assert embed.footer.text == "최신 기준"


def test_image_message_wraps_prerendered_png_with_legend_and_failures():
    targets = [Target(1, 111, "손바", "oc")]
    outcomes = [
        _outcome("손바", ok=True),
        _outcome("실패자", ok=False, error="닉 변경?"),
    ]
    embed, file = comparison.image_message(
        "아이템 — 모자",
        b"\x89PNG\r\n\x1a\n fake png bytes",
        targets,
        footer="최신 기준",
        outcomes=outcomes,
        filename="item.png",
    )
    assert file.filename == "item.png"
    assert embed.image.url == "attachment://item.png"
    assert "손바 <@111>" in embed.description
    assert any("조회 실패" in f.name for f in embed.fields)
    assert embed.footer.text == "최신 기준"
