"""이력 캐시 이름표 = 계정 식별자(ADR-0024) 단위테스트.

스타포스·잠재 페치가 캐시를 **앵커 캐릭터 ocid 가 아니라 개인 키의 계정 식별자**로 읽고 쓰는지(키 교체·
앵커 변경에 흔들리지 않음), 그리고 1회 이전 스크립트의 계획(안전한 앵커만 이전)을 검증한다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from cryptography.fernet import Fernet

from maple_mate.history import potential_service
from maple_mate.history.service import HistoryTarget, fetch_starforce_records
from maple_mate.security.crypto import KeyCipher
from scripts.migrate_history_cache_keys import anchors_by_registration, plan_moves

_NOW = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)
_DAY = date(2026, 10, 1)


class _Recorder:
    """캐시 조회(get) 키와 upsert 값을 기록하는 가짜 세션(항상 미스)."""

    def __init__(self) -> None:
        self.gets: list[tuple] = []
        self.upserts: list[dict] = []

    def factory(self):
        recorder = self

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, model, pk):
                recorder.gets.append(pk)
                return None

            async def execute(self, stmt):
                recorder.upserts.append(stmt.compile().params)

            async def commit(self):
                return None

        return _Session()


class _Nexon:
    async def starforce_history(self, api_key, date_iso, count=1000):
        return []

    async def cube_history(self, api_key, date_iso, count=1000):
        return []

    async def potential_history(self, api_key, date_iso, count=1000):
        return []


def _deps(recorder: _Recorder, cipher: KeyCipher):
    return SimpleNamespace(
        session_factory=recorder.factory, nexon=_Nexon(), cipher=cipher
    )


def _target(cipher: KeyCipher, api_key: str, anchor: str) -> HistoryTarget:
    return HistoryTarget(
        guild_id=1,
        discord_user_id=10,
        nickname="본캐",
        ocid=anchor,
        api_key_encrypted=cipher.encrypt(api_key),
    )


async def test_starforce_cache_uses_account_key_not_anchor():
    cipher = KeyCipher(Fernet.generate_key())
    recorder = _Recorder()
    await fetch_starforce_records(
        _deps(recorder, cipher),
        _target(cipher, "key-a", "anchor-ocid"),
        [_DAY],
        now=_NOW,
    )
    expected = cipher.account_key("key-a")
    assert recorder.gets == [(expected, "starforce", _DAY)]
    assert recorder.upserts[0]["account_key"] == expected
    assert "anchor-ocid" not in str(recorder.gets)


async def test_same_key_shares_cache_across_anchors_and_new_key_does_not():
    cipher = KeyCipher(Fernet.generate_key())
    recorder = _Recorder()
    deps = _deps(recorder, cipher)
    # 앵커 캐릭터가 바뀌어도(삭제 등) 같은 키면 같은 이름표 → 기존 캐시 재사용
    await fetch_starforce_records(
        deps, _target(cipher, "key-a", "o1"), [_DAY], now=_NOW
    )
    await fetch_starforce_records(
        deps, _target(cipher, "key-a", "o2"), [_DAY], now=_NOW
    )
    # 다른 계정 키로 교체하면 앵커가 같아도 다른 이름표 → 이전 계정 캐시를 읽지 않음
    await fetch_starforce_records(
        deps, _target(cipher, "key-b", "o1"), [_DAY], now=_NOW
    )
    keys = [pk[0] for pk in recorder.gets]
    assert keys[0] == keys[1] != keys[2]


async def test_potential_cache_uses_account_key_for_both_types():
    cipher = KeyCipher(Fernet.generate_key())
    recorder = _Recorder()
    await potential_service.fetch_potential_records(
        _deps(recorder, cipher),
        _target(cipher, "key-a", "anchor-ocid"),
        [_DAY - timedelta(days=1)],
        now=_NOW,
    )
    expected = cipher.account_key("key-a")
    assert {pk[0] for pk in recorder.gets} == {expected}
    assert {pk[1] for pk in recorder.gets} == {
        potential_service.CUBE_TYPE,
        potential_service.RESET_TYPE,
    }


# ── 1회 이전 계획(scripts/migrate_history_cache_keys.py) ─────────────────────


def test_plan_moves_only_single_account_anchors():
    plan = plan_moves(
        [
            ("o1", "acct-a"),  # 단독 → 이전
            ("o2", "acct-b"),
            ("o2", "acct-b"),  # 같은 키로 두 서버 등록 → 여전히 단독
            ("o3", "acct-c"),
            ("o3", "acct-d"),  # 다른 계정이 같은 앵커 공유 → 혼입 의심
        ]
    )
    assert plan.moves == {"o1": "acct-a", "o2": "acct-b"}
    assert plan.shared == {"o3"}


def test_anchor_is_earliest_registered_character_per_registration():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def char(guild, user, ocid, days):
        return SimpleNamespace(
            guild_id=guild,
            discord_user_id=user,
            ocid=ocid,
            created_at=t0 + timedelta(days=days),
        )

    anchors = anchors_by_registration(
        [char(1, 10, "late", 5), char(1, 10, "early", 1), char(0, 10, "dm", 3)]
    )
    assert anchors == {(1, 10): "early", (0, 10): "dm"}  # 서버·DM 스코프 별도
