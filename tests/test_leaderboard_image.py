"""경험치 리더보드 그래프 렌더 테스트 (matplotlib — 예외 없이 PNG + 라벨·일평균 순수 로직)."""

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


# ── 점 라벨·일평균(순수) ──────────────────────────────────────────────────────


def test_progress_label_formats_level_and_pct():
    # 연속 progress(레벨+exp%/100) → 'Lv.287 (69%)'. 정수 레벨 + 정수 exp%.
    f = leaderboard_image._progress_label
    assert f(287.69) == "Lv.287 (69%)"
    assert f(288.0) == "Lv.288 (0%)"
    assert f(290.5) == "Lv.290 (50%)"
    assert f(287.999) == "Lv.287 (99%)"  # 99.5%↑ 는 99로 클램프('(100%)' 방지)


def test_daily_average_is_level_gain_over_days():
    # 첫 가용 287.0 ~ 끝 290.0(+3레벨), 간격 6일 → (3.0*100)/6 = 50%/일. 레벨업도 연속 합산.
    f = leaderboard_image._daily_average
    pts = [
        (date(2026, 6, 7), 287.0),
        (date(2026, 6, 10), 288.5),
        (date(2026, 6, 13), 290.0),
    ]
    assert f(pts) == 50.0


def test_daily_average_zero_for_single_or_no_point():
    f = leaderboard_image._daily_average
    assert f([(date(2026, 6, 13), 287.0)]) == 0.0  # 데이터 1개
    assert f([(date(2026, 6, 7), None), (date(2026, 6, 13), 287.0)]) == 0.0  # 가용 1개


# ── 7일 레벨 추이 그래프 ──────────────────────────────────────────────────────


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
