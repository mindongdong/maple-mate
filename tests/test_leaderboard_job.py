"""run_leaderboard_job 오케스트레이션 단위테스트 — 채널 0개 스킵 + 적재→발송 (작업지시서 #5).

모든 I/O(DB·넥슨·디스코드)를 페이크로 막고 제어흐름만 검증한다. 실제 발송·그래프 시각·10:00
readiness 는 라이브 1회 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from maple_mate.leaderboard import broadcast
from maple_mate.registration.realm import Realm


def _deps():
    return SimpleNamespace(session_factory=object(), nexon=SimpleNamespace())


def _no_dm_subs(monkeypatch):
    """개인 DM 구독 0명으로 패치(채널 경로만 검증하는 기존 테스트 공통)."""

    async def dm_subscribers(sf, kind):
        return []

    monkeypatch.setattr(broadcast.channel_service, "dm_subscribers", dm_subscribers)


async def test_no_channels_no_subs_skips_nexon_call(monkeypatch):
    calls: list[str] = []

    async def enabled_exp_channels(sf):
        calls.append("channels")
        return []

    async def dm_subscribers(sf, kind):
        calls.append("dm_subs")
        return []

    async def get_targets(sf, guild_id, realm=None):
        calls.append("get_targets")
        return []

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast.channel_service, "dm_subscribers", dm_subscribers)
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert calls == ["channels", "dm_subs"]  # 채널·구독자 0 → 넥슨/적재/발송 없음


async def test_job_backfills_then_fetches_and_sends(monkeypatch):
    calls: list[str] = []
    sent: list[tuple[int, int]] = []

    async def enabled_exp_channels(sf):
        return [(1, 100)]

    async def get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def backfill(deps, guild_id, targets):
        calls.append("backfill")

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        calls.append("fetch")
        return 0

    async def build_payload(bot, deps, guild_id, realm):
        calls.append("build")
        # 본서버만 등재(챌린저스는 빈 랭킹 → None) — 리더보드 2개 독립 게이트.
        if realm is Realm.MAIN:
            return SimpleNamespace(embed="e", to_files=lambda: ["f1"])
        return None

    class _Channel:
        async def send(self, **kwargs):
            sent.append((kwargs["embed"], kwargs["files"]))

    async def resolve_channel(bot, guild_id, channel_id):
        return _Channel()

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    _no_dm_subs(monkeypatch)
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)
    monkeypatch.setattr(broadcast, "_resolve_channel", resolve_channel)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    # 적재 1회(union 대상) 후 realm 2개 각각 build → 본서버만 발송.
    assert calls == ["backfill", "fetch", "build", "build"]
    assert len(sent) == 1


async def test_job_always_backfills_even_with_existing_data(monkeypatch):
    # 게이트 폐기 후: 기존 스냅샷이 있어도 매 실행 backfill 을 호출한다(멱등 — 빈 날만 채움).
    calls: list[str] = []

    async def enabled_exp_channels(sf):
        return [(1, 100)]

    async def get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def backfill(deps, guild_id, targets):
        calls.append("backfill")

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        calls.append("fetch")
        return 0

    async def build_payload(bot, deps, guild_id, realm):
        return None  # 2명 미만 → 발송 생략(양 realm 모두)

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    _no_dm_subs(monkeypatch)
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert "backfill" in calls  # 항상 백필(공백 자가복구)
    assert "fetch" in calls


async def test_per_guild_payload_built_once_per_realm_for_two_channels(monkeypatch):
    """같은 길드에 exp_alert 채널이 2개여도 build_payload(DB+렌더)는 (길드,realm)당 1회만."""
    build_calls: list[tuple[int, Realm]] = []
    sent_files: list[list] = []

    async def enabled_exp_channels(sf):
        # 길드 1의 채널 두 개
        return [(1, 100), (1, 101)]

    async def get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def backfill(deps, guild_id, targets):
        pass

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        return 0

    async def build_payload(bot, deps, guild_id, realm):
        build_calls.append((guild_id, realm))
        # 본서버만 등재(챌린저스 None) — 두 채널 모두 본서버 1장씩 받는다.
        if realm is Realm.MAIN:
            return SimpleNamespace(embed="e", to_files=lambda: ["f1"])
        return None

    class _Channel:
        async def send(self, **kwargs):
            sent_files.append(kwargs["files"])

    async def resolve_channel(bot, guild_id, channel_id):
        return _Channel()

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    _no_dm_subs(monkeypatch)
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)
    monkeypatch.setattr(broadcast, "_resolve_channel", resolve_channel)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    # (길드1, 본서버)·(길드1, 챌린저스) 각 1회만 — 채널 2개에 걸쳐 메모이제이션.
    assert build_calls == [(1, Realm.MAIN), (1, Realm.CHALLENGERS)]
    assert len(sent_files) == 2  # 채널 100, 101 각각 본서버 1장씩 발송


# ── 개인 DM 팬아웃(ADR-0017): 구독자 0/N · 길드별 · 메모이즈 공유 ──────────────


async def test_dm_fanout_to_subscribers(monkeypatch):
    """채널 0개라도 개인 구독자가 있으면 적재 후 그 길드 payload 를 DM 한다(길드별, 디듀프 없음)."""
    dmed: list[int] = []

    async def enabled_exp_channels(sf):
        return []

    async def dm_subscribers(sf, kind):
        assert kind == broadcast.channel_service.KIND_EXP
        return [(1, 10), (1, 11)]  # 같은 길드 두 구독자

    async def get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def backfill(deps, guild_id, targets):
        pass

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        return 0

    build_calls: list = []

    async def build_payload(bot, deps, guild_id, realm):
        build_calls.append((guild_id, realm))
        if realm is Realm.MAIN:
            return SimpleNamespace(embed="e", to_files=lambda: ["f1"])
        return None

    async def fake_send_dm(bot, user_id, **kwargs):
        dmed.append(user_id)
        return True

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast.channel_service, "dm_subscribers", dm_subscribers)
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)
    monkeypatch.setattr(broadcast, "send_dm", fake_send_dm)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert dmed == [10, 11]  # 구독자 2명 각각 본서버 1장 DM(길드별, user 디듀프 없음)
    # payload 는 (길드,realm)당 1회만 — 두 구독자가 메모이즈 공유.
    assert build_calls == [(1, Realm.MAIN), (1, Realm.CHALLENGERS)]


async def test_dm_fanout_skips_blocked_dm(monkeypatch):
    """DM 차단(False) 구독자가 있어도 다음 구독자는 계속 시도한다."""
    attempted: list[int] = []

    async def enabled_exp_channels(sf):
        return []

    async def dm_subscribers(sf, kind):
        return [(1, 10), (1, 11)]

    async def get_targets(sf, guild_id, realm=None):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def backfill(deps, guild_id, targets):
        pass

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        return 0

    async def build_payload(bot, deps, guild_id, realm):
        if realm is Realm.MAIN:
            return SimpleNamespace(embed="e", to_files=lambda: ["f1"])
        return None

    async def fake_send_dm(bot, user_id, **kwargs):
        attempted.append(user_id)
        return user_id != 10  # 10 은 DM 차단

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast.channel_service, "dm_subscribers", dm_subscribers)
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)
    monkeypatch.setattr(broadcast, "send_dm", fake_send_dm)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert attempted == [10, 11]  # 차단된 10 이후에도 11 시도


# ── refresh_guild: 매 실행 멱등 백필 → D-1 적재 ──────────────────────────────


async def test_refresh_guild_always_backfills_then_fetches(monkeypatch):
    calls: list[str] = []

    async def backfill(deps, guild_id, targets):
        calls.append("backfill")

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        calls.append("fetch")
        return 2

    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    skipped = await broadcast.refresh_guild(_deps(), 1, [object()], date(2026, 6, 13))
    assert calls == ["backfill", "fetch"]  # 게이트 없이 항상 백필 → 적재
    assert skipped == 2


# ── ensure_guild_data: 온디맨드(그 realm 빈 과거일 백필 — 표시는 build_payload 라이브) ──


async def test_ensure_guild_data_backfills_realm_gaps(monkeypatch):
    seen = {}

    async def get_targets(sf, guild_id, realm=None):
        seen["realm"] = realm
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    backfilled: list[int] = []

    async def backfill(deps, guild_id, targets):
        backfilled.append(len(targets))

    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    await broadcast.ensure_guild_data(_deps(), 1, Realm.CHALLENGERS)
    assert seen["realm"] is Realm.CHALLENGERS  # 그 realm 대표만(realm 혼합 없음)
    assert backfilled == [1]  # 7일 그래프 이력 공백만 메움(현재값은 라이브)


async def test_ensure_guild_data_noop_when_no_targets(monkeypatch):
    backfilled: list[int] = []

    async def get_targets(sf, guild_id, realm=None):
        return []  # 등록자 없음

    async def backfill(deps, guild_id, targets):
        backfilled.append(len(targets))

    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    await broadcast.ensure_guild_data(_deps(), 1)
    assert backfilled == []  # 대상 0 → 백필 안 함
