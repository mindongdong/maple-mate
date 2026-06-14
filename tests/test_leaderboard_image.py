"""경험치 리더보드 PNG 렌더 스모크 테스트 (예외 없이 PNG + 빈/단일 유저 분기)."""

from __future__ import annotations

import io
from datetime import date

from PIL import Image

from maple_mate.bot import leaderboard_image
from maple_mate.bot.leaderboard_image import render_delta_graph, render_table
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


def test_render_table_produces_png():
    rows = [_row(1), _row(2, delta=None, world_rank=None)]
    assert _is_png(render_table(rows, _REF))


def test_render_table_with_exp_rate_label():
    # exp_rate 가 있으면 'Lv.287 (45.2%)' 라벨 경로, 없으면 'Lv.287'(분기 동시 검증).
    rows = [_row(1, exp_rate=45.2), _row(2)]
    assert _is_png(render_table(rows, _REF))


# ── 7일 Δ 그래프 ─────────────────────────────────────────────────────────────


def _series(**users) -> dict[str, list[tuple[date, int | None]]]:
    dates = [date(2026, 6, 7 + i) for i in range(7)]  # 06/07..06/13
    return {nick: list(zip(dates, vals)) for nick, vals in users.items()}


def test_render_graph_multi_user():
    series = _series(
        손바=[10_000_000, 0, 50_000_000, None, 30_000_000, 0, 12_000_000],
        라딘라면=[5_000_000, 8_000_000, 0, 0, 9_000_000, 1_000_000, 0],
    )
    assert _is_png(render_delta_graph(series, _REF))


def test_render_graph_single_user():
    series = _series(손바=[None, None, None, None, None, 5_000_000, 9_000_000])
    assert _is_png(render_delta_graph(series, _REF))


def test_render_graph_empty_data_guard():
    # 첫날·전원 None → 안내 문구만 그리고 예외 없이 PNG.
    series = _series(손바=[None] * 7, 라딘라면=[None] * 7)
    assert _is_png(render_delta_graph(series, _REF))


def test_render_graph_no_series_guard():
    assert _is_png(render_delta_graph({}, _REF))


# ── y축 눈금(순수) ───────────────────────────────────────────────────────────


def test_nice_max_rounds_up_to_1_2_5():
    f = leaderboard_image._nice_max
    assert f(0) == 1
    assert f(3) == 5
    assert f(12) == 20
    assert f(60) == 100
    assert f(935_107_160_853) == 1_000_000_000_000
