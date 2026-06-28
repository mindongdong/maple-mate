"""`/잠재` 대상 처리·정렬·등업 셀 단위테스트 (Nexon/DB mock).

핵심 도메인 구분: 기록 없음(키 있으나 기간 내 큐브+재설정 0) vs 조회 실패(넥슨 에러) vs 성공.
키 미등록은 handle 단계 필터라 여기선 _process_target(키 있는 대상)만 검증.
"""

from __future__ import annotations

import inspect
from datetime import date
from types import SimpleNamespace

import discord

from maple_mate.bot import table_image
from maple_mate.dependencies import Deps
from maple_mate.error_log.models import ErrorLog
from maple_mate.history import potential_commands
from maple_mate.history.potential_commands import (
    _aux_fields,
    _build_table,
    _process_target,
    _upgrade_cell,
    handle_potential,
)
from maple_mate.history.potential_service import HistoryTarget, PotentialSummary
from maple_mate.nexon.errors import NexonAPIError
from maple_mate.registration.service import Target, TargetOutcome

DATES = [date(2026, 5, 31)]


def _raw(
    name: str, *, result: str = "성공", grades=("에픽",), cube: bool = True
) -> dict:
    base = {
        "character_name": name,
        "item_upgrade_result": result,
        "item_level": 200,
        "item_equipment_part": "모자",
        "target_item": "아케인셰이드 모자",
        "potential_option_grade": "유니크",
        "additional_potential_option_grade": "레어",
        "before_potential_option": [{"value": "x", "grade": g} for g in grades],
        "after_potential_option": [],
        "before_additional_potential_option": [],
        "after_additional_potential_option": [],
        "date_create": "2026-05-31T17:00:00+09:00",
    }
    base["cube_type" if cube else "potential_type"] = (
        "수상한 큐브" if cube else "잠재능력"
    )
    return base


class _FakeNexon:
    def __init__(self, *, cubes=None, resets=None, raise_exc=None) -> None:
        self._cubes = cubes or []
        self._resets = resets or []
        self._raise = raise_exc

    async def cube_history(self, api_key: str, date_iso: str, count: int = 1000):
        if self._raise is not None:
            raise self._raise
        return list(self._cubes)

    async def potential_history(self, api_key: str, date_iso: str, count: int = 1000):
        if self._raise is not None:
            raise self._raise
        return list(self._resets)


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


def _target(nickname: str = "손바") -> HistoryTarget:
    return HistoryTarget(
        guild_id=1,
        discord_user_id=2,
        nickname=nickname,
        ocid="oc1",
        api_key_encrypted="enc",
    )


# ── _process_target: 성공 / 기록없음 / 조회실패 ─────────────────────────────


async def test_success_returns_target_and_summary() -> None:
    nexon = _FakeNexon(cubes=[_raw("손바", result="성공", grades=("에픽",))])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, "표시명")
    assert isinstance(result, tuple)
    target, summary = result
    assert isinstance(target, Target)
    # 라벨 = 디스코드 서버 표시명(캐릭터 닉 아님, ADR-0015).
    assert target.nickname == "표시명"
    assert summary.cube_count == 1
    assert summary.tierups_pot == (("에픽", 1),)
    # 메소 단가표 주입됨 → 200제 큐브 1회 감정비 80만이 계산된다.
    assert summary.total_meso == 800_000
    assert summary.appraisal_meso == 800_000


async def test_other_character_records_counted_account_wide() -> None:
    # 계정 전체화: 대표와 다른 캐릭터(부캐) 기록도 계정 전체라 함께 집계된다(닉 필터 제거).
    nexon = _FakeNexon(cubes=[_raw("부캐")], resets=[_raw("부캐", cube=False)])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, "표시명")
    assert isinstance(result, tuple)
    _, summary = result
    assert summary.cube_count == 1 and summary.reset_count == 1


async def test_no_record_when_empty() -> None:
    # 키는 있으나 기간 내 기록이 전혀 없음 = 기록 없음(키 미등록과 구분).
    nexon = _FakeNexon(cubes=[], resets=[])
    deps, _ = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, "표시명")
    assert isinstance(result, TargetOutcome)
    assert "기록이 없어요" in result.error


async def test_fetch_failure_returns_outcome_and_logs_error() -> None:
    nexon = _FakeNexon(raise_exc=NexonAPIError("OPENAPI00001", "boom", http_status=500))
    deps, added = _make_deps(nexon)
    result = await _process_target(deps, _target(), DATES, "표시명")
    assert isinstance(result, TargetOutcome)
    assert not result.ok
    logs = [o for o in added if isinstance(o, ErrorLog)]
    assert len(logs) == 1 and logs[0].error_type == "nexon_api"


# ── _upgrade_cell: 뱃지 vs '—' ─────────────────────────────────────────────


def _summary(
    *, tierups_pot=(), tierups_add=(), cube_count=0, reset_count=0, total_meso=None
) -> PotentialSummary:
    return PotentialSummary(
        cube_count=cube_count,
        reset_count=reset_count,
        tierups_pot=tierups_pot,
        tierups_add=tierups_add,
        total_meso=total_meso,
        appraisal_meso=None if total_meso is None else total_meso,
        reset_meso=None if total_meso is None else 0,
        by_cube_type=(),
        by_grade=(),
    )


def test_upgrade_cell_uses_to_grade_badges() -> None:
    # 입력은 from-등급(에픽)이지만 뱃지는 도달 등급(유니크)으로 표시.
    cell = _upgrade_cell((("에픽", 2),))
    assert isinstance(cell, table_image.GradeBadges)
    assert cell.items == (("유니크", 2),)


def test_upgrade_cell_unique_from_shows_legendary() -> None:
    # 유니크에서 올랐으면 → 레전드리 도달 뱃지.
    cell = _upgrade_cell((("유니크", 1),))
    assert cell.items == (("레전드리", 1),)


def test_upgrade_cell_dash_when_no_tierup() -> None:
    assert _upgrade_cell(()) == "—"


# ── _build_table: 사용 메소 내림차순(범례 순서로 확인) ──────────────────────


def test_build_table_ranks_by_meso_desc() -> None:
    low = (
        Target(guild_id=1, discord_user_id=10, nickname="적은애", ocid="o1"),
        _summary(total_meso=1_000_000),
    )
    high = (
        Target(guild_id=1, discord_user_id=11, nickname="많은애", ocid="o2"),
        _summary(total_meso=9_000_000),
    )
    embed, file = _build_table([low, high], [], "2026-05-31")
    # 범례(embed.description)는 ranked 순서대로 닉을 나열 → 메소 많은애가 앞.
    desc = embed.description or ""
    assert desc.index("많은애") < desc.index("적은애")
    assert file.filename == "potential.png"


# ── _build_table: 잠재/에디 2컬럼 + 디스코드 표시명 라벨(ADR-0015) ─────────────


def test_build_table_two_upgrade_columns_and_display_label(monkeypatch) -> None:
    captured: dict = {}

    def _fake_table_image_message(title, headers, rows, targets, **kw):
        captured["headers"] = headers
        captured["rows"] = rows
        captured["aligns"] = kw.get("aligns")
        return discord.Embed(), SimpleNamespace(filename="potential.png")

    monkeypatch.setattr(
        potential_commands.comparison,
        "table_image_message",
        _fake_table_image_message,
    )
    tgt = Target(guild_id=1, discord_user_id=2, nickname="표시명", ocid="o1")
    summary = _summary(tierups_pot=(("에픽", 1),), tierups_add=(), total_meso=1_000_000)
    _build_table([(tgt, summary)], [], "2026-05-31")

    assert captured["headers"] == [
        "순위",
        "대상",
        "잠재 재설정",
        "사용 큐브",
        "사용 메소",
        "잠재 등업",
        "에디 등업",
    ]
    assert len(captured["aligns"]) == len(captured["headers"])
    row = captured["rows"][0]
    assert row[1] == "표시명"  # 대상 = 디스코드 표시명(캐릭터 닉 부재)
    assert isinstance(row[5], table_image.GradeBadges)  # 잠재 등업 채워짐
    assert row[6] == "—"  # 에디 등업 0건 = '—'


# ── _aux_fields: ⬆️ 등업 진행 잠재/에디 2줄 ─────────────────────────────────


def test_aux_fields_splits_potential_and_additional_lines() -> None:
    embed = discord.Embed()
    summary = _summary(tierups_pot=(("유니크", 1),), tierups_add=(("에픽", 2),))
    _aux_fields(embed, summary)
    fields = {f.name: f.value for f in embed.fields}
    assert "⬆️ 등업 진행" in fields
    value = fields["⬆️ 등업 진행"]
    assert "잠재: 유니크 → 레전드리 ×1" in value
    assert "에디: 에픽 → 유니크 ×2" in value


def test_aux_fields_omits_empty_kind_line() -> None:
    embed = discord.Embed()
    summary = _summary(tierups_pot=(("유니크", 1),), tierups_add=())
    _aux_fields(embed, summary)
    value = {f.name: f.value for f in embed.fields}["⬆️ 등업 진행"]
    assert "잠재:" in value and "에디:" not in value  # 에디 0건 → 줄 생략


# ── 모드 파라미터 제거(ADR-0015) ───────────────────────────────────────────


def test_handle_potential_signature_has_no_mode() -> None:
    params = inspect.signature(handle_potential).parameters
    assert "realm" not in params and "mode" not in params
