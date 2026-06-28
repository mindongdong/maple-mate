"""`/스타포스` 대상 처리 분기 단위테스트 (Nexon/DB mock).

핵심 도메인 구분: 기록 없음(키 있으나 기간 내 강화 0) vs 조회 실패(넥슨 에러) vs 성공.
키 미등록은 handle 단계 필터라 여기선 _process_target(키 있는 대상)만 검증.
"""

from __future__ import annotations

import inspect
from datetime import date
from types import SimpleNamespace

from maple_mate.dependencies import Deps
from maple_mate.error_log.models import ErrorLog
from maple_mate.history.commands import (
    _build_table,
    _format_count,
    _format_luck,
    _process_target,
    _rank_results,
    handle_starforce,
    resolve_member_displays,
)
from maple_mate.history.service import HistoryTarget, StarforceSummary
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


# ── 표시 (ADR-0016) — 운빨 클램프·단일 건수·동점 정렬·ℹ️ 필드 ─────────────────


def _summary(
    luck: float | None, *, matched: int = 5, total: int = 5, net: int = 0
) -> StarforceSummary:
    return StarforceSummary(
        luck_score=luck,
        total_meso=0,
        net_meso=net,
        expected=0.0,
        matched_count=matched,
        total_count=total,
        unmatched_items=(),
    )


def test_format_luck_clamps_extremes() -> None:
    # '상위 0%' 금지 → '상위 1% 미만', 대칭으로 극단 불운은 '상위 99% 초과'.
    assert _format_luck(_summary(99.7)) == "상위 1% 미만"  # top=0.3
    assert _format_luck(_summary(100.0)) == "상위 1% 미만"  # top=0
    assert _format_luck(_summary(0.5)) == "상위 99% 초과"  # top=99.5
    assert _format_luck(_summary(0.0)) == "상위 99% 초과"  # top=100
    assert _format_luck(_summary(70.0)) == "상위 30%"  # 일반 구간
    assert _format_luck(_summary(None)) == "—"


def test_format_count_is_single_number() -> None:
    # 11성 필터로 미상 소멸 → 분자=분모, 항상 단일 건수(M/N 분기 삭제).
    assert _format_count(_summary(50.0, matched=21, total=21)) == "21건"
    assert _format_count(_summary(50.0, matched=21, total=47)) == "21건"


def _t(uid: int) -> Target:
    return Target(guild_id=1, discord_user_id=uid, nickname=f"u{uid}", ocid="")


def test_rank_results_tiebreak_by_profit() -> None:
    # 운빨 동점(둘 다 클램프돼 같은 표시) → 손익(이득) 큰(net 작은) 쪽이 1위.
    less_gain = (_t(1), _summary(99.9, net=-1_000))  # 이득 1000
    more_gain = (_t(2), _summary(99.9, net=-5_000))  # 이득 5000 (더 큼)
    ranked = _rank_results([less_gain, more_gain])
    assert ranked[0][1].net_meso == -5_000  # 더 큰 이득이 위
    # None 운빨은 항상 맨 아래.
    ranked2 = _rank_results([(_t(3), _summary(None)), more_gain])
    assert ranked2[0][1].luck_score == 99.9 and ranked2[1][1].luck_score is None


def test_build_table_has_event_field_and_no_unmatched_field() -> None:
    results = [(_t(1), _summary(70.0, matched=21, total=21))]
    embed, _file = _build_table(results, [], "footer")
    names = [f.name for f in embed.fields]
    assert any("11성 이상" in n for n in names)  # 신규 ℹ️ 필드
    assert not any("레벨 미상" in n for n in names)  # 삭제된 필드
    assert any("계정 전체 합산" in n for n in names)  # 유지


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
        records=[_record("손바", 17, 18), _record("손바", 18, 19)],
        equipped={"하이네스 워리어헬름": 150},
    )
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {}, "표시명")
    assert isinstance(result, tuple)
    target, summary = result
    assert isinstance(target, Target)
    # 라벨 = 디스코드 서버 표시명(캐릭터 닉 아님, ADR-0015).
    assert target.nickname == "표시명"
    assert summary.matched_count == 2
    assert summary.total_count == 2
    assert summary.luck_score is not None


async def test_other_character_records_counted_account_wide() -> None:
    # 계정 전체화: 대표와 다른 캐릭터(부캐) 기록도 계정 전체라 함께 집계된다(닉 필터 제거).
    nexon = _FakeNexon(records=[_record("부캐", 17, 18)])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {}, "표시명")
    assert isinstance(result, tuple)
    _, summary = result
    assert summary.total_count == 1


async def test_no_record_when_empty() -> None:
    # 키는 있으나 기간 내 강화 기록이 전혀 없음 = 기록 없음(키 미등록과 구분).
    nexon = _FakeNexon(records=[])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {}, "표시명")
    assert isinstance(result, TargetOutcome)
    assert "기록이 없어요" in result.error


async def test_no_record_when_only_low_stars() -> None:
    # 강화는 했으나 전부 10성 이하 → 11성 이상 기록 없음(no-record 분기, ADR-0016).
    nexon = _FakeNexon(records=[_record("손바", 0, 1), _record("손바", 5, 6)])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {}, "표시명")
    assert isinstance(result, TargetOutcome)
    assert "11성 이상" in result.error


async def test_fetch_failure_returns_outcome_and_logs_error() -> None:
    nexon = _FakeNexon(raise_exc=NexonAPIError("OPENAPI00001", "boom", http_status=500))
    deps, added = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {}, "표시명")
    assert isinstance(result, TargetOutcome)
    assert not result.ok
    logs = [o for o in added if isinstance(o, ErrorLog)]
    assert len(logs) == 1 and logs[0].error_type == "nexon_api"


async def test_unmatched_equipment_is_reported_to_error_log() -> None:
    # 11성+ 미상 장비 → unmatched → error_log(unmatched_equipment) 적재. 매칭 장비가 함께
    # 있어야 결과가 표(tuple)로 나온다(미상만이면 no-record 분기).
    matched = _record("손바", 17, 18)  # 하이네스(세트 150) → 매칭
    unknown = _record("손바", 17, 18)
    unknown["target_item"] = "정체불명 장비"
    nexon = _FakeNexon(records=[matched, unknown], equipped={})
    deps, added = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, {}, "표시명")
    assert isinstance(result, tuple)
    logs = [o for o in added if isinstance(o, ErrorLog)]
    assert any(
        o.error_type == "unmatched_equipment" and o.detail == "정체불명 장비"
        for o in logs
    )


# ── resolve_member_displays: 표시명 매핑 + 서버 이탈 제외(ADR-0015 결정 3) ─────


def _keyed_target(uid: int, nickname: str = "메이플닉") -> HistoryTarget:
    return HistoryTarget(
        guild_id=1,
        discord_user_id=uid,
        nickname=nickname,
        ocid=f"oc{uid}",
        api_key_encrypted="enc",
    )


def test_resolve_member_displays_maps_present_and_excludes_left() -> None:
    targets = [_keyed_target(2, "본캐닉"), _keyed_target(3, "떠난이닉")]
    guild = SimpleNamespace(
        get_member=lambda uid: (
            SimpleNamespace(display_name="표시명") if uid == 2 else None
        )  # uid 3 = 서버 이탈(get_member None)
    )
    display_by_uid, present = resolve_member_displays(guild, targets)
    assert display_by_uid == {2: "표시명"}
    assert [t.discord_user_id for t in present] == [2]  # 이탈 유저 제외


def test_resolve_member_displays_none_guild_excludes_all() -> None:
    display_by_uid, present = resolve_member_displays(None, [_keyed_target(2)])
    assert display_by_uid == {} and present == []


# ── 모드 파라미터 제거(ADR-0015) ───────────────────────────────────────────


def test_handle_starforce_signature_has_no_mode() -> None:
    params = inspect.signature(handle_starforce).parameters
    assert "realm" not in params and "mode" not in params
