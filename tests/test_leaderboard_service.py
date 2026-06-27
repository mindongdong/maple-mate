"""leaderboard service 단위테스트 — build_rows·history_progress·prune·fetch_and_store.

순수 로직(정렬·순위·Δ·미등재 제외·진행도 시계열·prune 경계)은 픽스처로 검증하고, DB/넥슨은
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
    history_progress,
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


def test_build_rows_same_level_same_exp_rate_ignores_total_exp():
    # 통일 키 = (레벨, 레벨내 exp%)뿐 — total_exp 는 타이브레이크에서 제외(그래프와 동일 공식).
    # 동레벨·exp% 동일(None)이면 누적이 달라도 순서를 뒤집지 않고 입력 순서를 유지(안정 정렬).
    nicknames = {10: "손바", 20: "라딘라면"}
    today = [_snap(10, _EXP_D2), _snap(20, _EXP_D1)]  # 둘 다 Lv.287, 20 이 누적 큼
    prev = [_snap(10, _EXP_D2, d=_PREV), _snap(20, _EXP_D2, d=_PREV)]
    rows, excluded = build_rows(today, prev, nicknames=nicknames)
    assert excluded == 0
    assert [r.rank for r in rows] == [1, 2]
    assert rows[0].nickname == "손바"  # 누적이 작아도 입력 순서 유지(total_exp 미사용)
    assert rows[1].nickname == "라딘라면"


def test_build_rows_ranks_by_level_over_total_exp():
    # 챌린저스 버닝: Lv.276 의 누적이 Lv.272 보다 적어도 레벨이 높아 1위(total_exp 단독 정렬 회귀 방지).
    nicknames = {10: "중망레테", 20: "힘찬하악질"}
    today = [
        _snap(10, 2_777_501_192_234, level=276, exp_rate=41.1),  # 레벨 높고 누적 적음
        _snap(20, 3_949_632_842_569, level=272, exp_rate=71.5),  # 레벨 낮고 누적 많음
    ]
    rows, _ = build_rows(today, [], nicknames=nicknames)
    assert [r.nickname for r in rows] == ["중망레테", "힘찬하악질"]  # 레벨 우선
    assert [r.rank for r in rows] == [1, 2]


def test_build_rows_same_level_ranks_by_exp_rate_over_total_exp():
    # 같은 레벨이면 exp%(레벨 내 진행)가 2차 키 — 누적이 낮아도 exp% 높으면 먼저(그래프와 일치).
    nicknames = {10: "무기콤보", 20: "힘찬하악질"}
    today = [
        _snap(10, 9_000_000, level=272, exp_rate=9.4),  # 누적 큼, exp% 낮음
        _snap(20, 5_000_000, level=272, exp_rate=71.5),  # 누적 작음, exp% 높음
    ]
    rows, _ = build_rows(today, [], nicknames=nicknames)
    assert [r.nickname for r in rows] == ["힘찬하악질", "무기콤보"]


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


# ── 라이브 레벨(표시 전용 — character/basic 무지정=최신) ─────────────────────


def _lrow(uid, level, exp_rate, *, rank=1):
    return service.LeaderRow(
        discord_user_id=uid,
        rank=rank,
        nickname=f"u{uid}",
        level=level,
        exp_rate=exp_rate,
        delta=None,
        world_rank=None,
    )


async def test_live_levels_fetches_latest_and_skips_failures():
    # character/basic 을 date 무지정(최신)으로 호출, 실패 대상은 결과에서 제외(폴백은 호출측).
    class FakeNexon:
        async def character_basic(self, ocid, date=None):
            assert date is None  # 무지정=최신
            if ocid == "bad":
                raise NexonAPIError("OPENAPI00009", "not ready")
            return {"character_level": 274, "character_exp_rate": "14.24"}

    deps = SimpleNamespace(nexon=FakeNexon())
    targets = [
        SimpleNamespace(discord_user_id=10, ocid="ok"),
        SimpleNamespace(discord_user_id=20, ocid="bad"),
    ]
    out = await service.live_levels(deps, targets)
    assert out == {10: (274, 14.24)}  # 실패한 20 은 빠짐


def test_with_live_levels_overrides_and_reranks():
    # D-1 순위(레벨 272 > 271)를 라이브(20 이 274 로 추월)가 뒤집어 재순위·재부여.
    rows = [_lrow(10, 272, 9.0, rank=1), _lrow(20, 271, 50.0, rank=2)]
    out = service.with_live_levels(rows, {10: (272, 10.0), 20: (274, 14.2)})
    assert [(r.nickname, r.level, r.rank) for r in out] == [
        ("u20", 274, 1),
        ("u10", 272, 2),
    ]


def test_with_live_levels_keeps_d1_when_live_missing():
    # 라이브 조회 실패 대상은 D-1 값 유지(폴백).
    [out] = service.with_live_levels([_lrow(10, 287, 79.0)], {})
    assert out.level == 287 and out.exp_rate == 79.0


def test_append_live_point_adds_today_progress():
    today = date(2026, 6, 24)
    series = {"손바": [(date(2026, 6, 23), 287.7)]}
    out = service.append_live_point(series, {10: "손바"}, {10: (287, 80.0)}, today)
    assert out["손바"][-1] == (today, 287.8)  # 287 + 80/100


def test_append_live_point_none_when_live_missing():
    today = date(2026, 6, 24)
    series = {"손바": [(date(2026, 6, 23), 287.7)]}
    out = service.append_live_point(series, {10: "손바"}, {}, today)
    assert out["손바"][-1] == (today, None)  # 라이브 없으면 선 끊김


# ── history_progress: 유저별 7일 진행도(레벨+exp%) 시계열 ─────────────────────


def _factory_for_rows(rows):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            return SimpleNamespace(all=lambda: rows)

    return lambda: _Session()


async def test_history_progress_computes_level_plus_exp_rate():
    nicknames = {10: "손바"}
    today = date(2026, 6, 13)  # 기준일(어제) = 그래프 오른쪽 끝, 표시 구간 06/07..06/13
    # rows = (uid, date, character_level, exp_rate). 스파이크 Lv287 재현, exp% 는 float-정확값.
    rows = [
        (10, date(2026, 6, 11), 287, 50.0),  # progress = 287.5
        (10, date(2026, 6, 12), 287, 75.0),  # progress = 287.75
        (10, date(2026, 6, 13), 288, 25.0),  # progress = 288.25 (레벨업 후)
    ]
    series = await history_progress(
        _factory_for_rows(rows), 1, nicknames, today, days=7
    )
    points = dict(series["손바"])
    assert points[date(2026, 6, 11)] == 287.5
    assert points[date(2026, 6, 12)] == 287.75
    assert points[date(2026, 6, 13)] == 288.25
    assert points[date(2026, 6, 7)] is None  # 스냅샷 없는 날 → None(선 끊김)


async def test_history_progress_none_when_exp_rate_missing():
    # exp_rate 결손이면 그날 progress 미산출(None) — 백필 결손·basic 실패 케이스.
    nicknames = {10: "손바"}
    rows = [
        (10, date(2026, 6, 12), 287, None),  # exp_rate 없음 → None
        (10, date(2026, 6, 13), 287, 50.0),  # 정상 → 287.5
    ]
    series = await history_progress(
        _factory_for_rows(rows), 1, nicknames, date(2026, 6, 13), days=7
    )
    points = dict(series["손바"])
    assert points[date(2026, 6, 12)] is None
    assert points[date(2026, 6, 13)] == 287.5


async def test_history_progress_includes_all_registrants_even_without_data():
    nicknames = {10: "손바", 20: "라딘라면"}
    series = await history_progress(
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


def _target(uid: int, ocid: str, world: str | None = None):
    return SimpleNamespace(
        guild_id=1, discord_user_id=uid, nickname=f"u{uid}", ocid=ocid, world=world
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


async def test_fetch_and_store_records_realm_from_world(monkeypatch):
    # 대표 world → realm 디스크리미넌트로 적재(본서버/챌린저스 분리, ADR-0009).
    nexon = _FakeNexon(
        {
            "ocM": {"character_level": 287, "character_exp": _EXP_D1, "ranking": 1},
            "ocC": {"character_level": 260, "character_exp": _EXP_D2, "ranking": 2},
        }
    )
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    targets = [
        _target(10, "ocM", world="스카니아"),
        _target(20, "ocC", world="챌린저스3"),
    ]
    await service.fetch_and_store(deps, 1, targets, "2026-06-13")
    assert [p["realm"] for p in params] == ["본서버", "챌린저스"]


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


# ── backfill: 과거일도 ranking+basic 수집(일별 진행도 그래프용) ───────────────


class _RecordingNexon:
    """ranking_overall·character_basic 호출을 기록하는 페이크(백필 콜 검증용)."""

    def __init__(self, entry: dict | None):
        self._entry = entry
        self.ranking_calls: list[str] = []
        self.basic_calls: list[str | None] = []

    async def ranking_overall(self, ocid: str, date_iso: str) -> dict | None:
        self.ranking_calls.append(date_iso)
        return self._entry

    async def character_basic(self, ocid: str, date: str | None = None) -> dict:
        self.basic_calls.append(date)
        return {"character_exp_rate": "10.0"}


def _backfill_factory(upserts: list[dict] | None = None):
    """_existing_dates(select.scalars().all()→[])와 _upsert_snapshot(execute/commit)를 함께 받는 세션.

    upserts 가 주어지면 'exp_rate' 키를 가진 INSERT 파라미터만 모은다(백필 적재값 검증용).
    """

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            if upserts is not None:
                params = stmt.compile().params
                if "exp_rate" in params:  # _upsert_snapshot 의 INSERT 만(select 제외)
                    upserts.append(params)
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: []),  # 기존 적재 없음
                rowcount=1,
            )

        async def commit(self):
            return None

    return lambda: _Session()


async def test_backfill_fetches_ranking_and_basic():
    # 과거 8일 백필은 ranking_overall + character/basic 둘 다 호출해 일별 exp_rate 를 채운다
    # (진행도 그래프는 baseline 부터 exp_rate 가 있어야 정규화됨 — #19 지연 최적화의 의도적 되돌림).
    upserts: list[dict] = []
    nexon = _RecordingNexon(
        {"character_level": 287, "character_exp": _EXP_D1, "ranking": 1}
    )
    deps = SimpleNamespace(session_factory=_backfill_factory(upserts), nexon=nexon)
    await service.backfill(deps, 1, [_target(10, "oc1")], days=8)
    assert len(nexon.ranking_calls) == 8  # D-1~D-8
    assert len(nexon.basic_calls) == 8  # 과거일도 character/basic 수집
    assert len(upserts) == 8
    assert all(p["exp_rate"] == 10.0 for p in upserts)  # basic 의 exp_rate 적재됨


# ── backfill: realm 별 빈 날 판정(dual-realm 구멍 회귀 가드) ───────────────────


async def test_backfill_checks_existing_dates_per_target_realm(monkeypatch):
    # 같은 디스코드 유저가 본서버·챌린저스 대표를 둘 다 가질 때(ADR-0009), 백필은 대상의 realm
    # 으로 기존일을 조회해야 한다 — realm 무관 조회는 한 realm 의 스냅샷이 다른 realm 의 빈 날을
    # 가려 그날을 건너뛰는 구멍을 만든다(챌린저스 추이가 일부 끊기는 버그).
    seen_realms: list[str] = []

    async def fake_existing(session_factory, guild_id, discord_user_id, realm, dates):
        seen_realms.append(realm)
        return set()  # 전부 빈 날 → 전부 페치(가림 없음을 검증)

    fetched: list[str | None] = []

    async def fake_fetch_one_day(deps, target, snapshot_date):
        fetched.append(target.world)
        return True

    monkeypatch.setattr(service, "_existing_dates", fake_existing)
    monkeypatch.setattr(service, "_fetch_one_day", fake_fetch_one_day)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    targets = [
        _target(10, "ocM", world="스카니아"),  # 본서버
        _target(20, "ocC", world="챌린저스3"),  # 챌린저스
    ]
    await service.backfill(deps, 1, targets, days=8)
    assert seen_realms == ["본서버", "챌린저스"]  # 대표 world → realm 으로 빈 날 조회
    assert (
        len(fetched) == 16
    )  # 대상 2명 × 8일 전부 페치(다른 realm 이 빈 날을 가리지 않음)
