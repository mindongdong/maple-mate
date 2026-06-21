"""comparison.resolve_targets realm 스코핑 — 부분성공 메시지 분기 (ADR-0009, 결정 5).

get_targets(DB)는 monkeypatch 로 막고, realm 전달 + 미보유 멤버의 realm 별 안내 문구만 검증한다.
본서버 모드 문구는 기존 그대로(시각 회귀 0), 챌린저스 모드는 '챌린저스 캐릭터 미등록' 안내.
"""

from __future__ import annotations

from types import SimpleNamespace

from maple_mate.bot import comparison
from maple_mate.registration.realm import CHALLENGERS_NO_TARGET, Realm
from maple_mate.registration.service import Target


def _member(uid: int):
    return SimpleNamespace(id=uid, display_name=f"유저{uid}")


async def test_resolve_targets_passes_main_realm_and_message(monkeypatch):
    captured: dict = {}

    async def fake_get_targets(sf, guild_id, user_ids, realm):
        captured["realm"] = realm
        captured["user_ids"] = list(user_ids)
        return [
            Target(guild_id=guild_id, discord_user_id=10, nickname="본닉", ocid="o10")
        ]

    monkeypatch.setattr(comparison, "get_targets", fake_get_targets)
    targets, missing = await comparison.resolve_targets(
        object(), 1, [_member(10), _member(20)], Realm.MAIN
    )
    assert captured["realm"] is Realm.MAIN  # 본서버 모드 명시(스펙/아이템)
    assert [t.discord_user_id for t in targets] == [10]
    assert len(missing) == 1
    assert missing[0].target.discord_user_id == 20
    assert (
        missing[0].error == "이 서버에 등록되지 않았어요. `/캐릭터등록` 먼저 해주세요."
    )


async def test_resolve_targets_default_realm_is_none_for_union(monkeypatch):
    # 무인자 기본 = None(realm 무필터) — /유니온 의 기존 동작 보존(realm 거름 '—', 코드 무변경).
    captured: dict = {}

    async def fake_get_targets(sf, guild_id, user_ids, realm):
        captured["realm"] = realm
        return []

    monkeypatch.setattr(comparison, "get_targets", fake_get_targets)
    await comparison.resolve_targets(object(), 1, [])
    assert captured["realm"] is None


async def test_resolve_targets_challengers_missing_message(monkeypatch):
    async def fake_get_targets(sf, guild_id, user_ids, realm):
        # 멤버 10만 챌린저스 대표 보유, 20은 챌린저스 캐릭터 미보유.
        return [
            Target(
                guild_id=guild_id,
                discord_user_id=10,
                nickname="챌닉",
                ocid="o10",
                world="챌린저스3",
            )
        ]

    monkeypatch.setattr(comparison, "get_targets", fake_get_targets)
    targets, missing = await comparison.resolve_targets(
        object(), 1, [_member(10), _member(20)], Realm.CHALLENGERS
    )
    assert [t.discord_user_id for t in targets] == [10]
    assert len(missing) == 1
    assert missing[0].error == CHALLENGERS_NO_TARGET  # '챌린저스 캐릭터 미등록' 안내
