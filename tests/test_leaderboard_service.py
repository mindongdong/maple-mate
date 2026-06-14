"""leaderboard service 단위테스트 — build_rows·history_deltas·prune·fetch_and_store.

순수 로직(정렬·순위·Δ·미등재 제외·시계열 변환·prune 경계)은 픽스처로 검증하고, DB/넥슨은
가짜 세션·페이크 nexon 으로 막는다(기존 history prune·bitik command 테스트와 동일 방침).
픽스처는 스파이크 실측치 재현(72.295조 − 71.360조 = 935,107,160,853 = "9351억 716만").
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from maple_mate.leaderboard import service
from maple_mate.leaderboard.service import (
    KST,
    build_rows,
    history_deltas,
    prune_old_snapshots,
    snapshot_cutoff,
    yesterday_kst,
)
from maple_mate.nexon.errors import ErrorClass, NexonAPIError

# 스파이크 실측 누적 경험치(손바 Lv287 D-1 / D-2).
_EXP_D1 = 72295476476158
_EXP_D2 = 71360369315305
_DELTA = _EXP_D1 - _EXP_D2  # 935,107,160,853 = "9351억 716만"

_NOW = datetime(2026, 6, 14, 10, 0, tzinfo=KST)
_REF = date(2026, 6, 13)  # D-1
_PREV = date(2026, 6, 12)  # D-2


def _snap(
    uid: int,
    total: int,
    *,
    level: int = 287,
    rank: int | None = 100,
    d=_REF,
    exp_rate: float | None = None,
):
    return SimpleNamespace(
        guild_id=1,
        discord_user_id=uid,
        snapshot_date=d,
        character_level=level,
        total_exp=total,
        world_rank=rank,
        exp_rate=exp_rate,
    )


# ── build_rows: 정렬·순위·Δ·미등재 제외 ──────────────────────────────────────


def test_build_rows_sorts_by_total_exp_desc_and_ranks():
    nicknames = {10: "손바", 20: "라딘라면"}
    today = [_snap(10, _EXP_D2), _snap(20, _EXP_D1)]  # 20 이 더 높음
    prev = [_snap(10, _EXP_D2, d=_PREV), _snap(20, _EXP_D2, d=_PREV)]
    rows, excluded = build_rows(today, prev, nicknames=nicknames)
    assert excluded == 0
    assert [r.rank for r in rows] == [1, 2]
    assert rows[0].nickname == "라딘라면"  # total_exp 최고가 1위
    assert rows[1].nickname == "손바"


def test_build_rows_delta_matches_spike_numbers():
    nicknames = {10: "손바"}
    today = [_snap(10, _EXP_D1)]
    prev = [_snap(10, _EXP_D2, d=_PREV)]
    [row], _ = build_rows(today, prev, nicknames=nicknames)
    assert row.delta == _DELTA  # 935,107,160,853


def test_build_rows_delta_none_when_no_prev_snapshot():
    nicknames = {10: "손바"}
    rows, _ = build_rows([_snap(10, _EXP_D1)], [], nicknames=nicknames)
    assert rows[0].delta is None  # 이전 스냅샷 없음 → '—'


def test_build_rows_negative_delta_clamped_to_none():
    # 음수 Δ(데이터 보정 등)는 None 클램프(작업지시서 파생 결정).
    nicknames = {10: "손바"}
    today = [_snap(10, _EXP_D2)]
    prev = [_snap(10, _EXP_D1, d=_PREV)]  # 어제가 더 큼 → 음수
    rows, _ = build_rows(today, prev, nicknames=nicknames)
    assert rows[0].delta is None


def test_build_rows_excludes_unranked_registrants():
    # 등록자 3명 중 오늘 스냅샷 있는 2명만 행, 미등재 1명은 excluded 카운트.
    nicknames = {10: "손바", 20: "라딘라면", 30: "미등재유저"}
    today = [_snap(10, _EXP_D1), _snap(20, _EXP_D2)]
    rows, excluded = build_rows(today, [], nicknames=nicknames)
    assert len(rows) == 2
    assert excluded == 1


def test_build_rows_carries_level_and_world_rank():
    nicknames = {10: "손바"}
    rows, _ = build_rows(
        [_snap(10, _EXP_D1, level=287, rank=129978)], [], nicknames=nicknames
    )
    assert rows[0].level == 287
    assert rows[0].world_rank == 129978
    assert rows[0].exp_rate is None  # 스냅샷에 보강값 없으면 None


def test_build_rows_passes_exp_rate_through():
    # character/basic 보강값(snap.exp_rate)이 LeaderRow 로 그대로 전달돼야 한다.
    nicknames = {10: "손바", 20: "라딘라면"}
    today = [_snap(10, _EXP_D1, exp_rate=45.23), _snap(20, _EXP_D2)]
    rows, _ = build_rows(today, [], nicknames=nicknames)
    by_nick = {r.nickname: r.exp_rate for r in rows}
    assert by_nick["손바"] == 45.23
    assert by_nick["라딘라면"] is None  # 보강 실패 행은 None 유지


# ── history_deltas: 유저별 7일 Δ 시계열 변환 ─────────────────────────────────


def _factory_for_rows(rows):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            return SimpleNamespace(all=lambda: rows)

    return lambda: _Session()


async def test_history_deltas_computes_daily_diffs_per_user():
    nicknames = {10: "손바"}
    today = date(2026, 6, 13)  # 기준일(어제) = 그래프 오른쪽 끝
    # 표시 구간 today-6..today = 06/07..06/13. Δ 계산 위해 06/06 도 읽음.
    rows = [
        (10, date(2026, 6, 11), 100),
        (10, date(2026, 6, 12), 130),  # Δ(6/12) = 30
        (10, date(2026, 6, 13), 130),  # Δ(6/13) = 0 (비활동)
    ]
    series = await history_deltas(_factory_for_rows(rows), 1, nicknames, today, days=7)
    points = dict(series["손바"])
    assert points[date(2026, 6, 12)] == 30
    assert points[date(2026, 6, 13)] == 0  # 비활동일 Δ=0(0 바닥선)
    assert points[date(2026, 6, 11)] is None  # 직전(6/10) 없음 → None


async def test_history_deltas_includes_all_registrants_even_without_data():
    nicknames = {10: "손바", 20: "라딘라면"}
    series = await history_deltas(
        _factory_for_rows([]), 1, nicknames, date(2026, 6, 13), days=7
    )
    assert set(series.keys()) == {"손바", "라딘라면"}
    # 데이터 없는 유저는 전 구간 None(빈 데이터 가드).
    assert all(v is None for _, v in series["손바"])


# ── prune 경계: snapshot_date < 오늘 KST − 90일 ─────────────────────────────


def test_snapshot_cutoff_is_90_days_before_today_kst():
    assert snapshot_cutoff(_NOW) == _NOW.date() - timedelta(days=90)


def test_row_older_than_90_days_is_pruned():
    cutoff = snapshot_cutoff(_NOW)
    assert (_NOW.date() - timedelta(days=91)) < cutoff  # 삭제 대상


def test_rows_within_90_days_are_preserved():
    cutoff = snapshot_cutoff(_NOW)
    assert not ((_NOW.date() - timedelta(days=90)) < cutoff)  # 경계 보존
    assert not ((_NOW.date() - timedelta(days=89)) < cutoff)


def _capture_factory(captured: list, rowcount: int = 4):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            captured.append(stmt)
            return SimpleNamespace(rowcount=rowcount)

        async def commit(self):
            return None

    return lambda: _Session()


async def test_prune_deletes_exp_snapshot_by_date_cutoff():
    captured: list = []
    deleted = await prune_old_snapshots(_capture_factory(captured), _NOW)
    assert deleted == 4
    [stmt] = captured
    assert stmt.table.name == "exp_snapshot"
    assert list(stmt.compile().params.values()) == [snapshot_cutoff(_NOW)]


# ── 기준일 헬퍼 ──────────────────────────────────────────────────────────────


def test_yesterday_kst_is_d_minus_1():
    assert yesterday_kst(_NOW) == date(2026, 6, 13)


# ── fetch_and_store: 미등재/미준비 스킵 카운트 ───────────────────────────────


class _FakeNexon:
    def __init__(
        self,
        by_ocid: dict[str, dict | None],
        basic: dict[str, dict | Exception] | None = None,
    ):
        self._by_ocid = by_ocid
        self._basic = basic or {}

    async def ranking_overall(self, ocid: str, date_iso: str) -> dict | None:
        return self._by_ocid.get(ocid)

    async def character_basic(self, ocid: str, date: str | None = None) -> dict:
        result = self._basic.get(ocid, {})
        if isinstance(result, Exception):
            raise result
        return result


def _target(uid: int, ocid: str):
    return SimpleNamespace(
        guild_id=1, discord_user_id=uid, nickname=f"u{uid}", ocid=ocid
    )


def _noop_factory():
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            return SimpleNamespace(rowcount=1)

        async def commit(self):
            return None

    return lambda: _Session()


def _capturing_insert_factory(params: list[dict]):
    """upsert INSERT 의 컴파일된 파라미터를 모아 exp_rate 적재값을 검증하게 해 주는 팩토리."""

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            params.append(stmt.compile().params)
            return SimpleNamespace(rowcount=1)

        async def commit(self):
            return None

    return lambda: _Session()


async def test_fetch_and_store_counts_unranked_skips(monkeypatch):
    # 2명 등재 + 1명 미등재(None) → 스킵 1.
    nexon = _FakeNexon(
        {
            "oc1": {"character_level": 287, "character_exp": _EXP_D1, "ranking": 1},
            "oc2": {"character_level": 280, "character_exp": _EXP_D2, "ranking": 2},
            "oc3": None,  # 미등재/미준비
        }
    )
    deps = SimpleNamespace(session_factory=_noop_factory(), nexon=nexon)
    targets = [_target(10, "oc1"), _target(20, "oc2"), _target(30, "oc3")]
    skipped = await service.fetch_and_store(deps, 1, targets, "2026-06-13")
    assert skipped == 1


# ── character/basic best-effort 보강(exp_rate) ───────────────────────────────


async def test_fetch_and_store_populates_exp_rate_from_basic(monkeypatch):
    # ranking 성공 + character/basic 의 character_exp_rate("45.23") → 스냅샷 exp_rate=45.23.
    nexon = _FakeNexon(
        {"oc1": {"character_level": 287, "character_exp": _EXP_D1, "ranking": 1}},
        basic={"oc1": {"character_exp_rate": "45.23"}},
    )
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 0
    [insert_params] = params
    assert insert_params["exp_rate"] == 45.23


async def test_fetch_and_store_basic_error_still_stores_with_none_and_no_error_log(
    monkeypatch,
):
    # character/basic 이 NexonAPIError(예: DATA_NOT_READY) → 캐릭은 여전히 적재(exp_rate=None),
    # basic 호출 실패로는 error_log 적재가 일어나지 않는다(주 소스 ranking 은 이미 성공).
    recorded: list = []

    async def _record(*args, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(service.error_log, "record", _record)

    nexon = _FakeNexon(
        {"oc1": {"character_level": 287, "character_exp": _EXP_D1, "ranking": 1}},
        basic={
            "oc1": NexonAPIError(
                "OPENAPI00009", "data not ready", error_class=ErrorClass.DATA_NOT_READY
            )
        },
    )
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 0  # 캐릭은 제외되지 않고 적재됨
    [insert_params] = params
    assert insert_params["exp_rate"] is None
    assert recorded == []  # basic 실패는 error_log 미적재


async def test_fetch_and_store_basic_timeout_still_stores_with_none(monkeypatch):
    # basic 호출이 타임아웃(다른 종류의 NexonAPIError)이어도 캐릭은 적재되고 exp_rate=None.
    recorded: list = []

    async def _record(*args, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(service.error_log, "record", _record)

    nexon = _FakeNexon(
        {"oc1": {"character_level": 287, "character_exp": _EXP_D1, "ranking": 1}},
        basic={"oc1": NexonAPIError(None, "timeout", error_class=ErrorClass.TIMEOUT)},
    )
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 0
    [insert_params] = params
    assert insert_params["exp_rate"] is None
    assert recorded == []
