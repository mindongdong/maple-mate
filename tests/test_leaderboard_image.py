"""경험치 리더보드 '성장 레이스' 그래프 렌더 테스트 (matplotlib — 예외 없이 PNG + 성장 라벨 순수 로직)."""

from __future__ import annotations

import io
from datetime import date

from PIL import Image

from maple_mate.bot import leaderboard_image
from maple_mate.bot.leaderboard_image import render_progress_graph

_REF = date(2026, 6, 13)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _is_png(buf: io.BytesIO) -> bool:
    data = buf.getvalue()
    if data[:8] != _PNG_MAGIC:
        return False
    img = Image.open(io.BytesIO(data))
    img.verify()
    return img.format == "PNG"


# ── 선 끝 라벨(순수) ──────────────────────────────────────────────────────────


def test_progress_label_formats_level_and_pct():
    # 연속 progress(레벨+exp%/100) → 'Lv.287 (79%)'. 정수 레벨 + 정수 exp%.
    f = leaderboard_image._progress_label
    assert f(287.69) == "Lv.287 (69%)"
    assert f(288.0) == "Lv.288 (0%)"
    assert f(290.5) == "Lv.290 (50%)"
    assert f(287.999) == "Lv.287 (99%)"  # 99.5%↑ 는 99로 클램프('(100%)' 방지)


def test_spread_labels_enforces_min_gap_preserving_order():
    # 붙은 끝-라벨을 최소 간격으로 위로 밀어 올리되 입력 인덱스 순서는 보존.
    out = leaderboard_image._spread_labels([0.0, 0.01, 0.02], 0.1)
    assert out[0] == 0.0
    assert out[1] >= out[0] + 0.1
    assert out[2] >= out[1] + 0.1


# ── 7일 절대 레벨 추이 그래프 ─────────────────────────────────────────────────


def _series(**users) -> dict[str, list[tuple[date, float | None]]]:
    dates = [date(2026, 6, 7 + i) for i in range(7)]  # 06/07..06/13
    return {nick: list(zip(dates, vals)) for nick, vals in users.items()}


def test_render_graph_multi_user():
    # progress = 레벨+exp%/100. None 구간 선 끊김, 레벨업(287→288) 연속.
    series = _series(
        손바=[287.0, 287.2, 287.5, None, 288.0, 288.3, 288.7],
        라딘라면=[290.0, 290.1, 290.3, 290.4, 290.6, 290.8, 291.0],
    )
    assert _is_png(render_progress_graph(series, _REF))


def test_render_graph_single_user():
    series = _series(손바=[None, None, None, None, None, 287.0, 287.9])
    assert _is_png(render_progress_graph(series, _REF))


def test_render_graph_empty_data_guard():
    # 전원 None → 안내 문구만 그리고 예외 없이 PNG.
    series = _series(손바=[None] * 7, 라딘라면=[None] * 7)
    assert _is_png(render_progress_graph(series, _REF))


def test_render_graph_no_series_guard():
    assert _is_png(render_progress_graph({}, _REF))


def test_palette_has_at_least_ten_distinct_colors():
    # Top10 라인 전원 고유색 — 9·10위가 1·2위와 색 충돌하지 않도록 10색 이상.
    colors = leaderboard_image._LINE_COLORS
    assert len(colors) >= 10
    assert len(set(colors)) >= 10  # 모두 서로 다른 색


def test_render_graph_ten_users():
    # 상위 10명 라인을 한 그래프에 — 예외 없이 PNG(10색 팔레트·끝라벨 분산 경로).
    series = _series(**{f"유저{i:02d}": [290.0 + i * 0.1] * 7 for i in range(1, 11)})
    assert _is_png(render_progress_graph(series, _REF))


def test_render_graph_dual_realm_crossing_lines():
    # 교차·급상승(정규화 outlier +72레벨)·동레벨 혼합 경로 예외 없이 PNG.
    series = _series(
        무기콤보=[None, None, 200.0, 200.5, 262.4, 272.5, 272.5],
        중망레테=[None, None, 262.2, 266.4, 272.1, 276.1, 276.1],
        힘찬하악질=[None, None, 260.6, 260.7, 262.2, 272.7, 272.7],
    )
    assert _is_png(render_progress_graph(series, _REF))
