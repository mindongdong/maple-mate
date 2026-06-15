"""경험치 리더보드 PNG 렌더 스모크 테스트 (예외 없이 PNG + 빈/단일 유저 분기)."""

from __future__ import annotations

import io
from datetime import date

from PIL import Image

from maple_mate.bot import leaderboard_image
from maple_mate.bot.leaderboard_image import render_progress_graph, render_table
from maple_mate.leaderboard.service import LeaderRow

_REF = date(2026, 6, 13)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _is_png(buf: io.BytesIO) -> bool:
    data = buf.getvalue()
    if data[:8] != _PNG_MAGIC:
        return False
    img = Image.open(io.BytesIO(data))
    img.verify()
    return img.format == "PNG"


def _row(rank: int, **kw) -> LeaderRow:
    base = dict(
        rank=rank,
        nickname=f"유저{rank}",
        level=287,
        exp_rate=None,
        delta=935_107_160_853,
        world_rank=129978,
    )
    base.update(kw)
    return LeaderRow(**base)


# ── 순위표 ───────────────────────────────────────────────────────────────────


def test_table_headers_are_four_columns_no_world_rank():
    # F1·F2: 4컬럼(순위·닉네임·레벨·하루 경험치), 전체 순위·어제 획득 컬럼 없음.
    headers = leaderboard_image._TABLE_HEADERS
    assert headers == ["순위", "닉네임", "레벨", "하루 경험치"]
    assert len(headers) == len(leaderboard_image._TABLE_ALIGNS) == 4
    assert "전체 순위" not in headers
    assert "어제 획득" not in headers


def test_render_table_produces_png():
    rows = [_row(1), _row(2, delta=None, world_rank=None)]
    assert _is_png(render_table(rows, _REF))


def test_render_table_with_exp_rate_label():
    # exp_rate 가 있으면 'Lv.287 (45.2%)' 라벨 경로, 없으면 'Lv.287'(분기 동시 검증).
    rows = [_row(1, exp_rate=45.2), _row(2)]
    assert _is_png(render_table(rows, _REF))


# ── 진행도 정규화·일평균(순수) ───────────────────────────────────────────────


def test_normalize_progress_starts_at_zero():
    # 창 내 첫 가용일 = 0%p, 이후는 (progress-baseline)*100. 287.5→0, 288.0→+50, 288.5→+100.
    f = leaderboard_image._normalize_progress
    pts = [
        (date(2026, 6, 7), 287.5),
        (date(2026, 6, 8), 288.0),
        (date(2026, 6, 9), 288.5),
    ]
    vals = [v for _, v in f(pts)]
    assert vals == [0.0, 50.0, 100.0]


def test_normalize_progress_none_segments_and_baseline_skip():
    f = leaderboard_image._normalize_progress
    pts = [
        (date(2026, 6, 7), None),  # 데이터 전 → None
        (date(2026, 6, 8), 287.0),  # 첫 가용일 → baseline(0%p)
        (date(2026, 6, 9), None),  # 중간 결손 → None(선 끊김)
        (date(2026, 6, 10), 287.25),  # +0.25레벨 → +25%p
    ]
    norm = dict(f(pts))
    assert norm[date(2026, 6, 7)] is None
    assert norm[date(2026, 6, 8)] == 0.0
    assert norm[date(2026, 6, 9)] is None
    assert norm[date(2026, 6, 10)] == 25.0


def test_normalize_progress_all_none():
    f = leaderboard_image._normalize_progress
    norm = f([(date(2026, 6, 7), None), (date(2026, 6, 8), None)])
    assert all(v is None for _, v in norm)


def test_daily_average_is_endpoint_over_gap_days():
    # 첫 가용일 06/07(0%p) ~ 끝 06/13(+90%p), 간격 6일 → 15%/일. 레벨업도 연속 합산.
    f = leaderboard_image._daily_average
    pts = [
        (date(2026, 6, 7), 0.0),
        (date(2026, 6, 10), 45.0),
        (date(2026, 6, 13), 90.0),
    ]
    assert f(pts) == 15.0


def test_daily_average_zero_for_single_or_no_point():
    f = leaderboard_image._daily_average
    assert f([(date(2026, 6, 13), 0.0)]) == 0.0  # 데이터 1개
    assert f([(date(2026, 6, 7), None), (date(2026, 6, 13), 0.0)]) == 0.0  # 가용 1개


# ── 7일 진행량 그래프 ────────────────────────────────────────────────────────


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
    # 첫날·전원 None → 안내 문구만 그리고 예외 없이 PNG.
    series = _series(손바=[None] * 7, 라딘라면=[None] * 7)
    assert _is_png(render_progress_graph(series, _REF))


def test_render_graph_no_series_guard():
    assert _is_png(render_progress_graph({}, _REF))


# ── y축 눈금(순수) ───────────────────────────────────────────────────────────


def test_nice_max_rounds_up_to_1_2_5():
    f = leaderboard_image._nice_max
    assert f(0) == 1
    assert f(3) == 5
    assert f(12) == 20
    assert f(60) == 100
    assert f(935_107_160_853) == 1_000_000_000_000
