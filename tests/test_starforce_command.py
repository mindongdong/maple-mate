"""`/스타포스` 대상 처리 분기 단위테스트 (Nexon/DB mock).

핵심 도메인 구분: 기록 없음(키 있으나 기간 내 강화 0) vs 조회 실패(넥슨 에러) vs 성공.
키 미등록은 handle 단계 필터라 여기선 _process_target(키 있는 대상)만 검증.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from maple_mate.dependencies import Deps
from maple_mate.error_log.models import ErrorLog
from maple_mate.history.commands import _format_profit, _process_target
from maple_mate.history.service import HistoryTarget
from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration.service import Target, TargetOutcome

DATES = [date(2026, 5, 31)]


def _record(name: str, before: int, after: int) -> dict:
    return {
        "character_name": name,
        "before_starforce_count": before,
        "after_starforce_count": after,
        "item_upgrade_result": "성공",
        "target_item": "하이네스 워리어헬름",  # 시드 150
        "date_create": "2026-05-31T17:00:00+09:00",
    }


class _FakeNexon:
    def __init__(self, *, records=None, raise_exc=None, equipped=None) -> None:
        self._records = records or []
        self._raise = raise_exc
        self._equipped = equipped or {}

    async def starforce_history(self, api_key: str, date_iso: str, count: int = 1000):
        if self._raise is not None:
            raise self._raise
        return list(self._records)

    async def character_item_equipment(self, ocid: str) -> dict:
        items = [
            {"item_name": n, "item_base_option": {"base_equipment_level": lv}}
            for n, lv in self._equipped.items()
        ]
        return {"item_equipment": items}


def _make_deps(nexon: _FakeNexon) -> tuple[Deps, list[object]]:
    added: list[object] = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, model, pk):
            return None  # 캐시 미스

        async def execute(self, *a, **k):
            return None

        async def commit(self):
            return None

        def add(self, obj):
            added.append(obj)

    deps = Deps(
        config=SimpleNamespace(),  # type: ignore[arg-type]
        session_factory=lambda: _Session(),
        nexon=nexon,  # type: ignore[arg-type]
        cipher=SimpleNamespace(decrypt=lambda token: "decrypted"),  # type: ignore[arg-type]
    )
    return deps, added


def test_format_profit_intuitive_sign() -> None:
    # 이득(기댓값보다 덜 씀, net<0) → +, 손해(더 씀, net>0) → −, 정확히 기댓값 → 0.
    assert _format_profit(-45_970_000) == "+4597만"
    assert _format_profit(1_221_270_000) == "-12억 2127만"
    assert _format_profit(0) == "0"


def _target() -> HistoryTarget:
    return HistoryTarget(
        guild_id=1,
        discord_user_id=2,
        nickname="손바",
        ocid="oc1",
        api_key_encrypted="enc",
    )


async def test_success_returns_target_and_summary() -> None:
    nexon = _FakeNexon(
        records=[_record("손바", 0, 1), _record("손바", 1, 2)],
        equipped={"하이네스 워리어헬름": 150},
    )
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {})
    assert isinstance(result, tuple)
    target, summary = result
    assert isinstance(target, Target)
    assert summary.matched_count == 2
    assert summary.total_count == 2
    assert summary.luck_score is not None


async def test_no_record_when_only_other_characters() -> None:
    # 키는 있으나 등록 캐릭터의 기록이 없음 = 기록 없음(키 미등록과 구분).
    nexon = _FakeNexon(records=[_record("부캐", 0, 1)])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {})
    assert isinstance(result, TargetOutcome)
    assert "기록이 없어요" in result.error


async def test_fetch_failure_returns_outcome_and_logs_error() -> None:
    nexon = _FakeNexon(raise_exc=NexonAPIError("OPENAPI00001", "boom", http_status=500))
    deps, added = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {})
    assert isinstance(result, TargetOutcome)
    assert not result.ok
    logs = [o for o in added if isinstance(o, ErrorLog)]
    assert len(logs) == 1 and logs[0].error_type == "nexon_api"


async def test_unmatched_equipment_is_reported_to_error_log() -> None:
    # 시드·장착 어디에도 없는 장비 → unmatched → error_log(unmatched_equipment) 적재.
    rec = _record("손바", 0, 1)
    rec["target_item"] = "정체불명 장비"
    nexon = _FakeNexon(records=[rec], equipped={})
    deps, added = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {})
    assert isinstance(result, tuple)
    logs = [o for o in added if isinstance(o, ErrorLog)]
    assert any(
        o.error_type == "unmatched_equipment" and o.detail == "정체불명 장비"
        for o in logs
    )
