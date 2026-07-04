"""무인자 팬아웃 경계(ADR-0008 부분개정) 단위테스트.

select_with_self(본인 고정 + 나머지 랜덤·비복원)과 핸들러 배선을 검증한다:
무인자 = 상한 10(본인 포함) + 푸터 상시 안내 + 본인 부재 시 사유 안내 + (이력류) 키 미등록 숨김 /
대상 지정 = 기존 동작 유지. 랜덤은 시드 주입(comparison.random 치환)으로 결정적으로 검증한다.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from maple_mate.bot import comparison
from maple_mate.history import commands as sf_commands
from maple_mate.history.service import HistoryTarget
from maple_mate.registration.service import Target, TargetOutcome
from maple_mate.union import commands as union_commands


def _target(uid: int, level: int | None, nickname: str | None = None) -> Target:
    return Target(
        guild_id=1,
        discord_user_id=uid,
        nickname=nickname or f"닉{uid}",
        ocid=f"oc{uid}",
        level=level,
    )


def _history_target(
    uid: int, level: int | None, *, keyed: bool = True
) -> HistoryTarget:
    return HistoryTarget(
        guild_id=1,
        discord_user_id=uid,
        nickname=f"닉{uid}",
        ocid=f"oc{uid}",
        api_key_encrypted="enc" if keyed else None,
        level=level,
    )


# ── select_with_self ─────────────────────────────────────────────────────────


def test_select_noop_at_or_under_limit():
    targets = [_target(i, 200 + i) for i in range(10)]
    selected, total, self_in = comparison.select_with_self(targets, self_id=0)
    assert selected == targets and total == 10 and self_in  # 순서·구성 무변경


def test_select_under_limit_self_absent():
    targets = [_target(i, 200 + i) for i in range(5)]
    selected, total, self_in = comparison.select_with_self(targets, self_id=999)
    assert selected == targets and total == 5 and self_in is False


def test_select_self_first_and_random_rest():
    targets = [_target(i, 200) for i in range(20)]  # 본인 uid=3 포함
    rng = random.Random(42)
    selected, total, self_in = comparison.select_with_self(targets, self_id=3, rng=rng)
    assert total == 20 and len(selected) == 10 and self_in
    assert selected[0].discord_user_id == 3  # 본인 맨 앞 고정
    assert all(t.discord_user_id != 3 for t in selected[1:])  # 비복원(본인 중복 없음)
    assert len({t.discord_user_id for t in selected}) == 10  # 나머지도 중복 없음


def test_select_random_is_deterministic_with_seed():
    targets = [_target(i, 200) for i in range(20)]
    a = comparison.select_with_self(targets, self_id=3, rng=random.Random(7))[0]
    b = comparison.select_with_self(targets, self_id=3, rng=random.Random(7))[0]
    assert [t.discord_user_id for t in a] == [t.discord_user_id for t in b]


def test_select_self_absent_fills_full_cap():
    targets = [_target(i, 200) for i in range(20)]  # 본인 uid=999 없음
    rng = random.Random(1)
    selected, total, self_in = comparison.select_with_self(
        targets, self_id=999, rng=rng
    )
    assert total == 20 and len(selected) == 10 and self_in is False
    assert all(t.discord_user_id != 999 for t in selected)


def test_select_accepts_history_targets():
    targets = [_history_target(i, 200 + i) for i in range(20)]
    selected, total, self_in = comparison.select_with_self(
        targets, self_id=5, rng=random.Random(0)
    )
    assert total == 20 and len(selected) == 10 and self_in
    assert selected[0].discord_user_id == 5


def test_fanout_note_branches_on_count():
    under = comparison.fanout_note(4)
    assert "전원(4명)" in under and "랜덤" not in under
    over = comparison.fanout_note(14)
    assert "14명" in over and "랜덤 10명" in over and "대상 지정" in over
    keyed_note = comparison.fanout_note(12, noun="키 등록자")
    assert keyed_note.startswith("키 등록자 12명") and "랜덤 10명" in keyed_note
    keyed_under = comparison.fanout_note(3, noun="키 등록자")
    assert keyed_under == "키 등록자 전원(3명)을 비교했어요"


# ── 가짜 상호작용 ────────────────────────────────────────────────────────────


class _Response:
    def __init__(self) -> None:
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self._done = True


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


def _interaction(user_id: int = 1) -> SimpleNamespace:
    guild = SimpleNamespace(
        get_member=lambda uid: SimpleNamespace(display_name=f"유저{uid}")
    )
    return SimpleNamespace(
        guild_id=1,
        guild=guild,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        followup=_Followup(),
    )


# ── /스타포스 핸들러 배선 (잠재도 동일 패턴·동일 헬퍼) ───────────────────────


def _patch_starforce(monkeypatch, targets: list[HistoryTarget]) -> dict:
    """넥슨·DB 없이 handle_starforce 배선만 검증할 수 있게 경계를 페이크로 치환."""
    captured: dict = {"processed": [], "outcomes": None, "footer": None}

    async def fake_targets(session_factory, guild_id, user_ids=None):
        if user_ids is None:
            return list(targets)
        return [t for t in targets if t.discord_user_id in user_ids]

    async def fake_learned(session_factory):
        return {}

    async def fake_process(deps, target, dates, learned, display_name):
        captured["processed"].append(target)
        return (
            Target(
                guild_id=1,
                discord_user_id=target.discord_user_id,
                nickname=display_name,
                ocid=target.ocid,
            ),
            object(),
        )

    def fake_build(results, outcomes, footer):
        captured["outcomes"] = outcomes
        captured["footer"] = footer
        return SimpleNamespace(title="표"), object()

    monkeypatch.setattr(sf_commands, "get_history_targets", fake_targets)
    monkeypatch.setattr(sf_commands, "load_learned_levels", fake_learned)
    monkeypatch.setattr(sf_commands, "_process_target", fake_process)
    monkeypatch.setattr(sf_commands, "_build_table", fake_build)
    # 랜덤 선정 결정성 — 핸들러 내부 comparison.random 을 시드된 RNG 로 치환.
    monkeypatch.setattr(comparison, "random", random.Random(0))
    return captured


async def test_starforce_unspecified_selects_self_and_caps(monkeypatch):
    """무인자: 키 미등록 숨김 + 본인 포함 랜덤 10명 + 푸터 안내(ADR-0008 부분개정 결정 1·2·3)."""
    targets = [
        _history_target(i, 200 + i) for i in range(12)
    ]  # 키 등록 12명(본인 uid=1)
    targets.append(_history_target(99, 280, keyed=False))  # 키 미등록
    captured = _patch_starforce(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(
        deps, _interaction(user_id=1), [], "오늘", None, None
    )

    processed = captured["processed"]
    assert len(processed) == 10  # 상한
    assert all(t.api_key_encrypted for t in processed)  # 키 미등록은 선정 제외
    assert 1 in [t.discord_user_id for t in processed]  # 실행 본인 무조건 포함
    assert not any(
        o.error and "키 미등록" in o.error for o in captured["outcomes"]
    )  # 숨김 행 없음
    assert "키 등록자 12명 중" in captured["footer"]  # 상시 안내(잘림)
    assert "랜덤 10명" in captured["footer"]


async def test_starforce_unspecified_self_absent_notes_key(monkeypatch):
    """무인자 + 본인 키 미등록: 조용히 랜덤 10명 + '키 미등록' 사유 안내 한 줄."""
    targets = [_history_target(i, 200 + i) for i in range(2, 14)]  # 본인(uid=1) 없음
    captured = _patch_starforce(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(
        deps, _interaction(user_id=1), [], "오늘", None, None
    )

    assert len(captured["processed"]) == 10
    assert 1 not in [t.discord_user_id for t in captured["processed"]]
    assert "API 키 미등록이라 포함되지 않았어요" in captured["footer"]


async def test_starforce_unspecified_note_when_under_cap(monkeypatch):
    """상한 이하: 전원 비교 + 상시 푸터('전원')."""
    targets = [_history_target(i, 250 + i) for i in range(3)]  # 본인 uid=1 포함
    captured = _patch_starforce(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(
        deps, _interaction(user_id=1), [], "오늘", None, None
    )

    assert len(captured["processed"]) == 3
    assert "키 등록자 전원(3명)" in captured["footer"]  # 전원 비교 안내
    assert "랜덤" not in captured["footer"]


async def test_starforce_specified_keeps_no_key_row(monkeypatch):
    """대상 지정 시엔 '키 미등록' 안내 행 유지(부분 성공 철학 — 결정 3의 예외), 푸터 안내 없음."""
    targets = [_history_target(1, 260), _history_target(2, 255, keyed=False)]
    captured = _patch_starforce(monkeypatch, targets)

    members = [
        SimpleNamespace(id=1, display_name="유저1"),
        SimpleNamespace(id=2, display_name="유저2"),
    ]
    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(
        deps, _interaction(user_id=1), members, "오늘", None, None
    )

    assert [t.discord_user_id for t in captured["processed"]] == [1]
    assert any(o.error and "키 미등록" in o.error for o in captured["outcomes"])
    assert "전원" not in captured["footer"] and "랜덤" not in captured["footer"]


# ── /유니온 핸들러 배선 (아이템도 동일 패턴·동일 헬퍼) ───────────────────────


def _patch_union(monkeypatch, targets: list[Target]) -> dict:
    fetched: dict = {}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
        if members:
            ids = {m.id for m in members}
            return [t for t in targets if t.discord_user_id in ids], []
        return list(targets), []

    async def fake_fetch_each(*, targets, nexon, session_factory, command, fetch):
        fetched["targets"] = list(targets)
        return [
            TargetOutcome(
                target=t,
                data=SimpleNamespace(
                    date="2026-07-04",
                    union_level=9000,
                    union_grade="그랜드 마스터 유니온",
                    artifact_level=60,
                    champion_grades=[],
                ),
            )
            for t in targets
        ]

    monkeypatch.setattr(comparison, "resolve_targets", fake_resolve)
    monkeypatch.setattr(union_commands.reg, "fetch_each", fake_fetch_each)
    monkeypatch.setattr(comparison, "random", random.Random(0))
    return fetched


async def test_union_unspecified_selects_self_and_notes(monkeypatch):
    targets = [_target(i, 200 + i) for i in range(12)]  # 본인 uid=1 포함
    fetched = _patch_union(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    interaction = _interaction(user_id=1)
    await union_commands.handle_union(deps, interaction, [])

    assert len(fetched["targets"]) == 10  # 넥슨 팬아웃 자체가 10으로 경계
    assert 1 in [t.discord_user_id for t in fetched["targets"]]  # 본인 포함
    [sent] = interaction.followup.sent
    assert "등록자 12명 중" in sent["embed"].footer.text
    assert "랜덤 10명" in sent["embed"].footer.text


async def test_union_unspecified_self_absent_notes(monkeypatch):
    targets = [_target(i, 200 + i) for i in range(2, 14)]  # 본인 uid=1 없음
    fetched = _patch_union(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    interaction = _interaction(user_id=1)
    await union_commands.handle_union(deps, interaction, [])

    assert len(fetched["targets"]) == 10
    [sent] = interaction.followup.sent
    assert "미등록이라 포함되지 않았어요" in sent["embed"].footer.text


async def test_union_unspecified_under_cap_notes_all(monkeypatch):
    targets = [_target(i, 200 + i) for i in range(4)]  # 본인 uid=1 포함
    fetched = _patch_union(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    interaction = _interaction(user_id=1)
    await union_commands.handle_union(deps, interaction, [])

    assert len(fetched["targets"]) == 4
    [sent] = interaction.followup.sent
    assert "등록자 전원(4명)" in sent["embed"].footer.text  # 전원 비교 안내
    assert "랜덤" not in sent["embed"].footer.text


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
