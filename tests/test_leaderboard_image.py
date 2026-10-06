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


# ── 기간 확장: 날짜 비례 X축·증가량 라벨 (docs/exp-period-work-order.md) ───────


def test_gain_label_signed_percent_or_empty():
    f = leaderboard_image._gain_label
    assert f(132) == " +132%"
    assert f(0) == " +0%"
    assert f(-3) == " -3%"
    assert f(None) == ""  # 유효점 부족 → 생략


def test_x_positions_are_day_offsets_from_first_date():
    # 불균등 샘플 간격(달력 앵커 + 기준일 + 오늘 라이브)이 실제 날짜 비례로 놓인다.
    dates = [
        date(2026, 9, 28),
        date(2026, 10, 1),
        date(2026, 10, 4),
        date(2026, 10, 5),
        date(2026, 10, 7),
    ]
    assert leaderboard_image._x_positions(dates) == [0, 3, 6, 7, 9]


def test_render_graph_30_day_uneven_samples_with_gains():
    dates = [
        date(2026, 9, 7) + (date(2026, 9, 10) - date(2026, 9, 7)) * i for i in range(10)
    ]
    dates += [date(2026, 10, 5), date(2026, 10, 7)]
    series = {
        f"유저{i:02d}": [(d, 280.0 + i + k * 0.2) for k, d in enumerate(dates)]
        for i in range(1, 11)
    }
    gains = {label: 220 for label in series}
    assert _is_png(render_progress_graph(series, date(2026, 10, 5), gains))


def test_tick_labels_thin_crowded_dates_keeping_last():
    # 앵커 끝(10/04)·기준일(10/05)·오늘(10/07)이 붙으면 오늘 라벨은 유지하고 붙은 라벨만 비운다.
    dates = [date(2026, 10, 1), date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 7)]
    xs = leaderboard_image._x_positions(dates)
    labels = leaderboard_image._tick_labels(dates, xs, min_gap=2.5)
    assert labels == ["10/01", "10/04", "", "10/07"]


def test_tick_labels_daily_keeps_all():
    dates = [date(2026, 10, d) for d in range(1, 8)]
    xs = leaderboard_image._x_positions(dates)
    assert all(leaderboard_image._tick_labels(dates, xs, min_gap=0.9))


def test_label_gap_is_median_spacing_so_daily_with_late_today_keeps_all():
    # 7일 매일 + 오늘이 이틀 뒤(D-1 미준비 폴백)여도 날짜 라벨이 하나씩 빠지지 않는다(평균 간격 회귀 가드).
    dates = [
        date(2026, 9, 29 + i) if i < 2 else date(2026, 10, i - 1) for i in range(7)
    ]
    dates.append(date(2026, 10, 7))
    xs = leaderboard_image._x_positions(dates)
    gap = leaderboard_image._label_gap(xs)
    assert gap == 0.9  # 중앙 간격 1일 × 0.9
    assert all(leaderboard_image._tick_labels(dates, xs, min_gap=gap))
