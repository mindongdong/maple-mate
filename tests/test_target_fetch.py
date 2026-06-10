"""대상 해석·부분성공·ocid lazy 갱신 단위테스트 (Nexon/DB mock — handoff §6).

DB 쿼리(get_targets) 자체는 통합 영역이라 제외. 분기 로직(부분성공 취합, lazy 갱신,
에러 분류, error_log 적재 트리거)만 검증.
"""

from __future__ import annotations

from maple_mate.error_log.models import ErrorLog
from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration import service
from maple_mate.registration.service import Target, classify_target_error, fetch_each


class FakeNexon:
    def __init__(self, ocids=None):
        self._ocids = ocids or {}

    async def get_ocid(self, name):
        if name in self._ocids:
            return self._ocids[name]
        raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)


def make_factory():
    """add() 된 객체를 공유 리스트로 노출하는 가짜 async session factory."""
    added: list[object] = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *a, **k):
            return None

        async def commit(self):
            return None

        def add(self, obj):
            added.append(obj)

    return (lambda: _Session()), added


def _target(uid=1, nick="닉A", ocid="oc1"):
    return Target(guild_id=100, discord_user_id=uid, nickname=nick, ocid=ocid)


# ── classify_target_error (순수) ──────────────────────────────────────


def test_classify_data_not_ready():
    exc = NexonAPIError("OPENAPI00009", "wait", http_status=400)
    assert "준비되지" in classify_target_error(exc)


def test_classify_rate_limit_is_retry_message():
    exc = NexonAPIError("OPENAPI00007", "later", http_status=429)
    assert "잠시 후" in classify_target_error(exc)


def test_classify_unknown_param_error():
    exc = NexonAPIError("OPENAPI00004", "bad", http_status=400)
    assert "확인" in classify_target_error(exc)


# ── fetch_each 부분 성공 ──────────────────────────────────────────────


async def test_partial_success_collects_ok_and_failed():
    async def fetch(ocid):
        if ocid == "ok":
            return {"v": ocid}
        raise NexonAPIError("OPENAPI00009", "not ready", http_status=400)

    factory, _ = make_factory()
    targets = [_target(1, "닉A", "ok"), _target(2, "닉B", "notready")]
    outcomes = await fetch_each(
        targets=targets,
        nexon=FakeNexon(),
        session_factory=factory,
        command="유니온",
        fetch=fetch,
    )
    assert outcomes[0].ok and outcomes[0].data == {"v": "ok"}
    assert not outcomes[1].ok and "준비되지" in outcomes[1].error


# ── ocid lazy 갱신 ────────────────────────────────────────────────────


async def test_lazy_ocid_refresh_recovers_then_succeeds():
    calls: list[str] = []

    async def fetch(ocid):
        calls.append(ocid)
        if ocid == "stale":
            raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)
        return {"ok": ocid}

    factory, _ = make_factory()
    nexon = FakeNexon(ocids={"닉A": "fresh"})  # 닉 → 새 ocid
    outcomes = await fetch_each(
        targets=[_target(1, "닉A", "stale")],
        nexon=nexon,
        session_factory=factory,
        command="유니온",
        fetch=fetch,
    )
    assert outcomes[0].ok and outcomes[0].data == {"ok": "fresh"}
    assert calls == ["stale", "fresh"]  # 캐싱 ocid 실패 → 닉 재조회 → 재시도


async def test_lazy_ocid_refresh_exhausted_when_nick_gone():
    async def fetch(ocid):
        raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)

    factory, _ = make_factory()
    nexon = FakeNexon(ocids={})  # 닉 자체가 사라짐 → get_ocid 도 실패
    outcomes = await fetch_each(
        targets=[_target(1, "없는닉", "stale")],
        nexon=nexon,
        session_factory=factory,
        command="유니온",
        fetch=fetch,
    )
    assert not outcomes[0].ok and "닉 변경" in outcomes[0].error


async def test_only_refreshes_once():
    """스테일 ocid 가 재조회 후에도 또 스테일이면 무한루프 없이 1회만 갱신하고 실패."""
    calls: list[str] = []

    async def fetch(ocid):
        calls.append(ocid)
        raise NexonAPIError("OPENAPI00004", "invalid", http_status=400)

    factory, _ = make_factory()
    nexon = FakeNexon(ocids={"닉A": "fresh"})
    outcomes = await fetch_each(
        targets=[_target(1, "닉A", "stale")],
        nexon=nexon,
        session_factory=factory,
        command="유니온",
        fetch=fetch,
    )
    assert not outcomes[0].ok
    assert calls == ["stale", "fresh"]  # 최초 + 갱신 후 1회 재시도 → 멈춤


# ── error_log 적재 (재시도 발생 건) ──────────────────────────────────


async def test_hard_failure_records_error_log():
    async def fetch(ocid):
        raise NexonAPIError("OPENAPI00001", "internal", http_status=500)

    factory, added = make_factory()
    outcomes = await fetch_each(
        targets=[_target(1, "닉A", "oc1")],
        nexon=FakeNexon(),
        session_factory=factory,
        command="스펙",
        fetch=fetch,
    )
    assert not outcomes[0].ok
    logs = [o for o in added if isinstance(o, ErrorLog)]
    assert len(logs) == 1
    assert logs[0].error_type == "nexon_api"
    assert logs[0].command == "스펙"
    assert logs[0].target_ocid == "oc1"


async def test_data_not_ready_does_not_record_error_log():
    async def fetch(ocid):
        raise NexonAPIError("OPENAPI00009", "wait", http_status=400)

    factory, added = make_factory()
    await fetch_each(
        targets=[_target(1, "닉A", "oc1")],
        nexon=FakeNexon(),
        session_factory=factory,
        command="스펙",
        fetch=fetch,
    )
    assert [o for o in added if isinstance(o, ErrorLog)] == []


def test_target_outcome_ok_property():
    t = _target()
    assert service.TargetOutcome(target=t, data={"x": 1}).ok is True
    assert service.TargetOutcome(target=t, error="boom").ok is False
