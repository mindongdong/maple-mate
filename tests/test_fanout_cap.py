"""무인자 팬아웃 경계(ADR-0008) 단위테스트.

cap_by_level(레벨 내림차순 상위 K·타이브레이크)과 핸들러 배선을 검증한다:
무인자 = 상한 10 + 푸터 안내 + (이력류) 키 미등록 숨김 / 대상 지정 = 기존 동작 유지.
"""

from __future__ import annotations

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


# ── cap_by_level ─────────────────────────────────────────────────────────────


def test_cap_noop_at_or_under_limit():
    targets = [_target(i, 200 + i) for i in range(10)]
    capped, total = comparison.cap_by_level(targets)
    assert capped == targets and total == 10  # 순서·구성 무변경


def test_cap_selects_top_levels_when_over_limit():
    targets = [_target(i, 200 + i) for i in range(13)]  # 레벨 200~212
    capped, total = comparison.cap_by_level(targets)
    assert total == 13 and len(capped) == 10
    assert [t.level for t in capped] == list(range(212, 202, -1))  # 상위 10 내림차순


def test_cap_tiebreak_same_level_by_nickname():
    targets = [
        _target(i, 260, nickname=n) for i, n in enumerate("하파타카차자아사바마다"[:11])
    ]
    capped, _ = comparison.cap_by_level(targets)
    names = [t.nickname for t in capped]
    assert names == sorted(names)  # 동레벨은 가나다순
    assert "하" not in names  # 가나다 마지막 1명 탈락


def test_cap_none_level_ranks_last():
    targets = [_target(i, 250) for i in range(10)] + [_target(99, None)]
    capped, total = comparison.cap_by_level(targets)
    assert total == 11
    assert all(t.level is not None for t in capped)  # 레벨 미상이 밀려남


def test_cap_accepts_history_targets():
    targets = [_history_target(i, 200 + i) for i in range(12)]
    capped, total = comparison.cap_by_level(targets)
    assert total == 12 and len(capped) == 10
    assert capped[0].level == 211


def test_fanout_note_mentions_total_and_cap():
    note = comparison.fanout_note(14)
    assert "14명" in note and "10명" in note and "대상 지정" in note
    keyed_note = comparison.fanout_note(12, noun="키 등록자")
    assert keyed_note.startswith("키 등록자 12명")


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


def _interaction() -> SimpleNamespace:
    guild = SimpleNamespace(
        get_member=lambda uid: SimpleNamespace(display_name=f"유저{uid}")
    )
    return SimpleNamespace(
        guild_id=1, guild=guild, response=_Response(), followup=_Followup()
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
    return captured


async def test_starforce_unspecified_caps_and_hides_keyless(monkeypatch):
    """무인자: 키 미등록 숨김 + 레벨 상위 10명만 + 푸터 안내(ADR-0008 결정 1·2·3)."""
    targets = [_history_target(i, 200 + i) for i in range(12)]  # 키 등록 12명
    targets.append(_history_target(99, 280, keyed=False))  # 최고레벨 키 미등록
    captured = _patch_starforce(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(deps, _interaction(), [], "오늘", None, None)

    processed = captured["processed"]
    assert len(processed) == 10  # 상한
    assert all(t.api_key_encrypted for t in processed)  # 키 미등록은 선정 제외
    assert min(t.level for t in processed) == 202  # 키 등록자 중 레벨 상위 10명
    assert not any(
        o.error and "키 미등록" in o.error for o in captured["outcomes"]
    )  # 숨김 행 없음
    assert "키 등록자 12명 중" in captured["footer"]  # 잘림 안내


async def test_starforce_unspecified_no_note_when_under_cap(monkeypatch):
    targets = [_history_target(i, 250 + i) for i in range(3)]
    captured = _patch_starforce(monkeypatch, targets)

    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(deps, _interaction(), [], "오늘", None, None)

    assert len(captured["processed"]) == 3
    assert "레벨 상위" not in captured["footer"]  # 안 잘리면 평소 화면 그대로


async def test_starforce_specified_keeps_no_key_row(monkeypatch):
    """대상 지정 시엔 '키 미등록' 안내 행 유지(부분 성공 철학 — 결정 3의 예외)."""
    targets = [_history_target(1, 260), _history_target(2, 255, keyed=False)]
    captured = _patch_starforce(monkeypatch, targets)

    members = [
        SimpleNamespace(id=1, display_name="유저1"),
        SimpleNamespace(id=2, display_name="유저2"),
    ]
    deps = SimpleNamespace(session_factory=object())
    await sf_commands.handle_starforce(
        deps, _interaction(), members, "오늘", None, None
    )

    assert [t.discord_user_id for t in captured["processed"]] == [1]
    assert any(o.error and "키 미등록" in o.error for o in captured["outcomes"])
    assert "레벨 상위" not in captured["footer"]


# ── /유니온 핸들러 배선 (아이템도 동일 패턴·동일 헬퍼) ───────────────────────


async def test_union_unspecified_caps_and_notes(monkeypatch):
    targets = [_target(i, 200 + i) for i in range(12)]
    fetched: dict = {}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
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

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    interaction = _interaction()
    await union_commands.handle_union(deps, interaction, [])

    assert len(fetched["targets"]) == 10  # 넥슨 팬아웃 자체가 10으로 경계
    [sent] = interaction.followup.sent
    assert "등록자 12명 중" in sent["embed"].footer.text


async def test_union_unspecified_under_cap_unchanged(monkeypatch):
    targets = [_target(i, 200 + i) for i in range(4)]
    fetched: dict = {}

    async def fake_resolve(session_factory, guild_id, members, realm=None):
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

    deps = SimpleNamespace(session_factory=object(), nexon=object())
    interaction = _interaction()
    await union_commands.handle_union(deps, interaction, [])

    assert len(fetched["targets"]) == 4
    [sent] = interaction.followup.sent
    assert "레벨 상위" not in sent["embed"].footer.text


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
