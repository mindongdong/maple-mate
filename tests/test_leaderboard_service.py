"""leaderboard service 단위테스트 — build_rows·history_progress·prune·fetch_and_store.

순수 로직(정렬·순위·미준비 제외·진행도 시계열·prune 경계)은 픽스처로 검증하고, DB/넥슨은
가짜 세션·페이크 nexon 으로 막는다(기존 history prune·bitik command 테스트와 동일 방침).
스냅샷 소스는 character/basic 단일(ADR-0020) — 레벨·exp% 가 같은 응답의 같은 시점 값이다.
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

_NOW = datetime(2026, 6, 14, 10, 0, tzinfo=KST)
_REF = date(2026, 6, 13)  # D-1


def _snap(
    uid: int,
    *,
    level: int = 287,
    d=_REF,
    exp_rate: float | None = None,
    ocid: str | None = None,
):
    return SimpleNamespace(
        guild_id=1,
        discord_user_id=uid,
        ocid=ocid if ocid is not None else f"oc{uid}",  # 캐릭터 차원(ADR-0018)
        snapshot_date=d,
        character_level=level,
        exp_rate=exp_rate,
    )


# ── build_rows: 정렬·순위·미준비 제외 ────────────────────────────────────────


def test_build_rows_same_level_same_exp_rate_keeps_input_order():
    # 통일 키 = (레벨, 레벨내 exp%)뿐 — 동레벨·exp% 동일(None)이면 입력 순서 유지(안정 정렬).
    labels = {"oc10": "손바", "oc20": "라딘라면"}
    today = [_snap(10), _snap(20)]  # 둘 다 Lv.287, exp_rate None
    rows, excluded = build_rows(today, labels=labels)
    assert excluded == 0
    assert [r.rank for r in rows] == [1, 2]
    assert rows[0].nickname == "손바"
    assert rows[1].nickname == "라딘라면"


def test_build_rows_ranks_by_level_first():
    # 레벨이 1차 키 — 챌린저스 버닝(레벨 부스트)에서도 레벨 높은 쪽이 1위(ADR-0011).
    labels = {"oc10": "중망레테", "oc20": "힘찬하악질"}
    today = [
        _snap(10, level=276, exp_rate=41.1),
        _snap(20, level=272, exp_rate=71.5),
    ]
    rows, _ = build_rows(today, labels=labels)
    assert [r.nickname for r in rows] == ["중망레테", "힘찬하악질"]  # 레벨 우선
    assert [r.rank for r in rows] == [1, 2]


def test_build_rows_same_level_ranks_by_exp_rate():
    # 같은 레벨이면 exp%(레벨 내 진행)가 2차 키(그래프 progress 와 일치).
    labels = {"oc10": "무기콤보", "oc20": "힘찬하악질"}
    today = [
        _snap(10, level=272, exp_rate=9.4),
        _snap(20, level=272, exp_rate=71.5),
    ]
    rows, _ = build_rows(today, labels=labels)
    assert [r.nickname for r in rows] == ["힘찬하악질", "무기콤보"]


def test_build_rows_excludes_missing_snapshots():
    # 캐릭터 3개 중 오늘 스냅샷 있는 2개만 행, 미준비 1개는 excluded 카운트.
    labels = {"oc10": "손바", "oc20": "라딘라면", "oc30": "미준비유저"}
    today = [_snap(10), _snap(20)]
    rows, excluded = build_rows(today, labels=labels)
    assert len(rows) == 2
    assert excluded == 1


def test_build_rows_carries_level():
    labels = {"oc10": "손바"}
    rows, _ = build_rows([_snap(10, level=287)], labels=labels)
    assert rows[0].level == 287
    assert rows[0].exp_rate is None  # 스냅샷에 exp% 없으면 None


def test_build_rows_passes_exp_rate_through():
    # 스냅샷 exp_rate 가 LeaderRow 로 그대로 전달돼야 한다.
    labels = {"oc10": "손바", "oc20": "라딘라면"}
    today = [_snap(10, exp_rate=45.23), _snap(20)]
    rows, _ = build_rows(today, labels=labels)
    by_nick = {r.nickname: r.exp_rate for r in rows}
    assert by_nick["손바"] == 45.23
    assert by_nick["라딘라면"] is None  # 결손 행은 None 유지


def test_build_rows_same_user_two_characters_coexist():
    # 캐릭터 차원(ADR-0018): 같은 유저의 두 캐릭터가 같은 날 각각 행으로 공존한다(/내캐릭터).
    labels = {"ocA": "본캐", "ocB": "부캐"}
    today = [
        _snap(10, level=287, exp_rate=50.0, ocid="ocA"),
        _snap(10, level=260, exp_rate=10.0, ocid="ocB"),
    ]
    rows, excluded = build_rows(today, labels=labels)
    assert [(r.nickname, r.rank) for r in rows] == [("본캐", 1), ("부캐", 2)]
    assert excluded == 0


# ── 라이브 레벨(표시 전용 — character/basic 무지정=최신) ─────────────────────


def _lrow(uid, level, exp_rate, *, rank=1):
    return service.LeaderRow(
        ocid=f"oc{uid}",
        rank=rank,
        nickname=f"u{uid}",
        level=level,
        exp_rate=exp_rate,
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
    assert out == {"ok": (274, 14.24)}  # ocid 키 — 실패한 "bad" 는 빠짐


def test_with_live_levels_overrides_and_reranks():
    # D-1 순위(레벨 272 > 271)를 라이브(oc20 이 274 로 추월)가 뒤집어 재순위·재부여.
    rows = [_lrow(10, 272, 9.0, rank=1), _lrow(20, 271, 50.0, rank=2)]
    out = service.with_live_levels(rows, {"oc10": (272, 10.0), "oc20": (274, 14.2)})
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
    out = service.append_live_point(
        series, {"oc10": "손바"}, {"oc10": (287, 80.0)}, today
    )
    assert out["손바"][-1] == (today, 287.8)  # 287 + 80/100


def test_append_live_point_none_when_live_missing():
    today = date(2026, 6, 24)
    series = {"손바": [(date(2026, 6, 23), 287.7)]}
    out = service.append_live_point(series, {"oc10": "손바"}, {}, today)
    assert out["손바"][-1] == (today, None)  # 라이브 없으면 선 끊김


# ── history_progress: 캐릭터별 7일 진행도(레벨+exp%) 시계열 ───────────────────


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
    labels = {"oc10": "손바"}
    today = date(2026, 6, 13)  # 기준일(어제) = 그래프 오른쪽 끝, 표시 구간 06/07..06/13
    # rows = (ocid, date, character_level, exp_rate). 스파이크 Lv287 재현, exp% 는 float-정확값.
    rows = [
        ("oc10", date(2026, 6, 11), 287, 50.0),  # progress = 287.5
        ("oc10", date(2026, 6, 12), 287, 75.0),  # progress = 287.75
        ("oc10", date(2026, 6, 13), 288, 25.0),  # progress = 288.25 (레벨업 후)
    ]
    series = await history_progress(_factory_for_rows(rows), 1, labels, today, days=7)
    points = dict(series["손바"])
    assert points[date(2026, 6, 11)] == 287.5
    assert points[date(2026, 6, 12)] == 287.75
    assert points[date(2026, 6, 13)] == 288.25
    assert points[date(2026, 6, 7)] is None  # 스냅샷 없는 날 → None(선 끊김)


async def test_history_progress_none_when_exp_rate_missing():
    # exp_rate 결손이면 그날 progress 미산출(None) — 백필 결손·basic 실패 케이스.
    labels = {"oc10": "손바"}
    rows = [
        ("oc10", date(2026, 6, 12), 287, None),  # exp_rate 없음 → None
        ("oc10", date(2026, 6, 13), 287, 50.0),  # 정상 → 287.5
    ]
    series = await history_progress(
        _factory_for_rows(rows), 1, labels, date(2026, 6, 13), days=7
    )
    points = dict(series["손바"])
    assert points[date(2026, 6, 12)] is None
    assert points[date(2026, 6, 13)] == 287.5


async def test_history_progress_includes_all_characters_even_without_data():
    labels = {"oc10": "손바", "oc20": "라딘라면"}
    series = await history_progress(
        _factory_for_rows([]), 1, labels, date(2026, 6, 13), days=7
    )
    assert set(series.keys()) == {"손바", "라딘라면"}
    # 데이터 없는 캐릭터는 전 구간 None(빈 데이터 가드).
    assert all(v is None for _, v in series["손바"])


async def test_history_progress_same_user_two_characters_separate_series():
    # 같은 유저의 두 캐릭터가 각자 라인을 가진다(/내캐릭터 — 유저 키였다면 한 라인으로 뭉개짐).
    labels = {"ocA": "본캐", "ocB": "부캐"}
    d = date(2026, 6, 13)
    rows = [
        ("ocA", d, 287, 50.0),  # progress = 287.5
        ("ocB", d, 260, 10.0),  # progress = 260.1
    ]
    series = await history_progress(_factory_for_rows(rows), 1, labels, d, days=7)
    assert dict(series["본캐"])[d] == 287.5
    assert dict(series["부캐"])[d] == 260.1


# ── latest_snapshot_date: 게이트·표시 기준일(가장 최근 스냅샷 일자, ≤ D-1) ────


def _scalar_factory(value, captured: list | None = None):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            if captured is not None:
                captured.append(stmt)
            return SimpleNamespace(scalar=lambda: value)

    return lambda: _Session()


async def test_latest_snapshot_date_returns_max_date():
    # D-1 미준비(자정~넥슨 생성 사이)면 max(snapshot_date)=D-2 가 기준일로 내려온다.
    d2 = date(2026, 7, 2)
    out = await service.latest_snapshot_date(
        _scalar_factory(d2), 1, ["oc1"], date(2026, 7, 3)
    )
    assert out == d2


async def test_latest_snapshot_date_none_when_empty():
    # 스냅샷 0건(신규 길드 + 넥슨 미준비) → None(호출측이 표시 불가 처리).
    out = await service.latest_snapshot_date(
        _scalar_factory(None), 1, ["oc1"], date(2026, 7, 3)
    )
    assert out is None


async def test_latest_snapshot_date_bounds_query_by_date_and_ocids():
    # 쿼리가 on_or_before 상한과 ocid 목록으로 제한되는지(컴파일 파라미터로 검증).
    captured: list = []
    await service.latest_snapshot_date(
        _scalar_factory(None, captured), 7, ["ocA", "ocB"], date(2026, 7, 3)
    )
    [stmt] = captured
    params = stmt.compile().params
    assert date(2026, 7, 3) in params.values()
    # IN 절은 확장 파라미터(리스트 1개)로 컴파일된다 — ocid 목록이 통째로 바인딩되는지 확인.
    assert ["ocA", "ocB"] in params.values()


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


# ── fetch_and_store: 미준비 스킵 카운트 ──────────────────────────────────────


class _FakeNexon:
    """character/basic(단일 소스, ADR-0020) 페이크 — ocid 별 응답 dict 또는 예외."""

    def __init__(self, basic: dict[str, dict | Exception]):
        self._basic = basic
        self.calls: list[tuple[str, str | None]] = []

    async def character_basic(self, ocid: str, date: str | None = None) -> dict:
        self.calls.append((ocid, date))
        result = self._basic.get(ocid, {})
        if isinstance(result, Exception):
            raise result
        return result


def _target(uid: int, ocid: str, world: str | None = None):
    return SimpleNamespace(
        guild_id=1, discord_user_id=uid, nickname=f"u{uid}", ocid=ocid, world=world
    )


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
            "ocM": {"character_level": 287, "character_exp_rate": "45.23"},
            "ocC": {"character_level": 260, "character_exp_rate": "10.0"},
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
    assert [p["ocid"] for p in params] == ["ocM", "ocC"]  # 캐릭터 차원 적재(ADR-0018)
    assert nexon.calls == [("ocM", "2026-06-13"), ("ocC", "2026-06-13")]  # date 명시


async def test_upsert_conflict_target_is_ocid_key(monkeypatch):
    # upsert 충돌 키 = (guild, user, ocid, date) — 같은 유저의 캐릭터 N개가 같은 날 공존하는 근거.
    nexon = _FakeNexon({"ocA": {"character_level": 287, "character_exp_rate": "1.0"}})
    captured: list = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, stmt):
            captured.append(stmt)
            return SimpleNamespace(rowcount=1)

        async def commit(self):
            return None

    deps = SimpleNamespace(session_factory=lambda: _Session(), nexon=nexon)
    await service.fetch_and_store(deps, 1, [_target(10, "ocA")], "2026-06-13")
    [stmt] = captured
    sql = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "ON CONFLICT (guild_id, discord_user_id, ocid, snapshot_date)" in sql


async def test_fetch_and_store_stores_level_and_exp_rate_from_basic(monkeypatch):
    # 단일 소스 = character/basic — 같은 응답의 character_level + character_exp_rate("45.23") 를
    # 함께 적재한다(레벨·exp% 동일 시점, ADR-0020 — 종전 랭킹 레벨은 하루 뒤처져 가짜 하락 유발).
    nexon = _FakeNexon({"oc1": {"character_level": 287, "character_exp_rate": "45.23"}})
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 0
    [insert_params] = params
    assert insert_params["character_level"] == 287
    assert insert_params["exp_rate"] == 45.23


async def test_fetch_and_store_not_ready_skips_without_row_or_error_log(monkeypatch):
    # basic 이 DATA_NOT_READY → 행을 만들지 않고 스킵(빈 날로 남아 다음 backfill 이 재시도),
    # error_log 미적재(미준비는 에러 아님).
    recorded: list = []

    async def _record(*args, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(service.error_log, "record", _record)

    nexon = _FakeNexon(
        {
            "oc1": {"character_level": 287, "character_exp_rate": "1.0"},
            "oc2": NexonAPIError(
                "OPENAPI00009", "data not ready", error_class=ErrorClass.DATA_NOT_READY
            ),
        }
    )
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    targets = [_target(10, "oc1"), _target(20, "oc2")]
    skipped = await service.fetch_and_store(deps, 1, targets, "2026-06-13")
    assert skipped == 1  # oc2 만 스킵
    assert [p["ocid"] for p in params] == ["oc1"]  # oc2 행 미생성
    assert recorded == []  # 미준비는 error_log 미적재


async def test_fetch_and_store_timeout_skips_row_and_records_error_log(monkeypatch):
    # basic 타임아웃(가용성 장애) → 행 미생성 + error_log 적재. 빈 날은 다음 backfill 이 재시도.
    recorded: list = []

    async def _record(*args, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(service.error_log, "record", _record)

    nexon = _FakeNexon(
        {"oc1": NexonAPIError(None, "timeout", error_class=ErrorClass.TIMEOUT)}
    )
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 1
    assert params == []  # 행 미생성(exp_rate=None 영구 결손 행을 남기지 않는다)
    [record] = recorded
    assert record["error_type"] == "timeout"


async def test_fetch_and_store_missing_level_skips_row(monkeypatch):
    # 응답에 character_level 이 없으면(응답형 이상) 행 미생성 스킵.
    nexon = _FakeNexon({"oc1": {"character_exp_rate": "45.23"}})
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 1
    assert params == []


async def test_fetch_and_store_unparseable_exp_rate_stores_none(monkeypatch):
    # exp_rate 파싱 실패는 행 제외 사유가 아니다 — 레벨은 적재하고 exp_rate=None(그날 선 끊김).
    nexon = _FakeNexon({"oc1": {"character_level": 287, "character_exp_rate": "n/a"}})
    params: list[dict] = []
    deps = SimpleNamespace(
        session_factory=_capturing_insert_factory(params), nexon=nexon
    )
    skipped = await service.fetch_and_store(deps, 1, [_target(10, "oc1")], "2026-06-13")
    assert skipped == 0
    [insert_params] = params
    assert insert_params["character_level"] == 287
    assert insert_params["exp_rate"] is None


# ── backfill: 과거일도 character/basic(date) 수집(일별 진행도 그래프용) ────────


class _RecordingNexon:
    """character_basic 호출을 기록하는 페이크(백필 콜 검증용)."""

    def __init__(self):
        self.basic_calls: list[str | None] = []

    async def character_basic(self, ocid: str, date: str | None = None) -> dict:
        self.basic_calls.append(date)
        return {"character_level": 287, "character_exp_rate": "10.0"}


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


async def test_backfill_fetches_basic_per_empty_day():
    # 과거 8일 백필은 character/basic(date) 를 날짜별 1콜씩 — 레벨·exp% 를 함께 적재한다.
    upserts: list[dict] = []
    nexon = _RecordingNexon()
    deps = SimpleNamespace(session_factory=_backfill_factory(upserts), nexon=nexon)
    await service.backfill(deps, 1, [_target(10, "oc1")], days=8)
    assert (
        len(nexon.basic_calls) == 8
    )  # D-1~D-8, 날짜별 단일 콜(종전 ranking+basic 2콜)
    assert all(d is not None for d in nexon.basic_calls)  # 과거일은 date 명시
    assert len(upserts) == 8
    assert all(p["character_level"] == 287 for p in upserts)  # basic 의 레벨 적재됨
    assert all(p["exp_rate"] == 10.0 for p in upserts)  # basic 의 exp_rate 적재됨


# ── backfill: 캐릭터(ocid)별 빈 날 판정(캐릭터 간 가림 회귀 가드) ──────────────


async def test_backfill_checks_existing_dates_per_target_ocid(monkeypatch):
    # 같은 유저의 캐릭터 N개(ADR-0018 — dual-realm 대표 포함)를 백필할 때, 빈 날 판정은
    # 캐릭터(ocid)별이어야 한다 — ocid 무관 조회는 한 캐릭터의 스냅샷이 다른 캐릭터의 빈 날을
    # 가려 그날을 건너뛰는 구멍을 만든다(종전 realm 별 판정을 포섭하는 더 정밀한 키).
    seen_ocids: list[str] = []

    async def fake_existing(session_factory, guild_id, discord_user_id, ocid, dates):
        seen_ocids.append(ocid)
        return set()  # 전부 빈 날 → 전부 페치(가림 없음을 검증)

    fetched: list[str] = []

    async def fake_fetch_one_day(deps, target, snapshot_date):
        fetched.append(target.ocid)
        return True

    monkeypatch.setattr(service, "_existing_dates", fake_existing)
    monkeypatch.setattr(service, "_fetch_one_day", fake_fetch_one_day)
    deps = SimpleNamespace(session_factory=object(), nexon=object())
    targets = [
        _target(10, "ocM", world="스카니아"),  # 본서버
        _target(10, "ocC", world="챌린저스3"),  # 같은 유저의 챌린저스 캐릭터
    ]
    await service.backfill(deps, 1, targets, days=8)
    assert seen_ocids == ["ocM", "ocC"]  # 캐릭터별로 빈 날 조회
    assert (
        len(fetched) == 16
    )  # 캐릭터 2개 × 8일 전부 페치(다른 캐릭터가 빈 날을 가리지 않음)
