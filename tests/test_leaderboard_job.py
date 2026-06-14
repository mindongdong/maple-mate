"""run_leaderboard_job 오케스트레이션 단위테스트 — 채널 0개 스킵 + 적재→발송 (작업지시서 #5).

모든 I/O(DB·넥슨·디스코드)를 페이크로 막고 제어흐름만 검증한다. 실제 발송·그래프 시각·10:00
readiness 는 라이브 1회 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from types import SimpleNamespace

from maple_mate.leaderboard import broadcast


def _deps():
    return SimpleNamespace(session_factory=object(), nexon=SimpleNamespace())


async def test_no_channels_skips_nexon_call(monkeypatch):
    calls: list[str] = []

    async def enabled_exp_channels(sf):
        calls.append("channels")
        return []

    async def get_targets(sf, guild_id):
        calls.append("get_targets")
        return []

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert calls == ["channels"]  # 넥슨/적재/발송 없음(Q10·#5)


async def test_first_run_backfills_then_fetches_and_sends(monkeypatch):
    calls: list[str] = []
    sent: list[tuple[int, int]] = []

    async def enabled_exp_channels(sf):
        return [(1, 100)]

    async def get_targets(sf, guild_id):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def has_snapshots(sf, guild_id):
        return False  # 첫 실행

    async def backfill(deps, guild_id, targets):
        calls.append("backfill")

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        calls.append("fetch")
        return 0

    async def build_payload(bot, deps, guild_id):
        calls.append("build")
        return SimpleNamespace(embed="e", to_files=lambda: ["f1", "f2"])

    class _Channel:
        async def send(self, **kwargs):
            sent.append((kwargs["embed"], kwargs["files"]))

    async def resolve_channel(bot, guild_id, channel_id):
        return _Channel()

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "has_snapshots", has_snapshots)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)
    monkeypatch.setattr(broadcast, "_resolve_channel", resolve_channel)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert calls == ["backfill", "fetch", "build"]
    assert len(sent) == 1


async def test_existing_snapshots_skip_backfill(monkeypatch):
    calls: list[str] = []

    async def enabled_exp_channels(sf):
        return [(1, 100)]

    async def get_targets(sf, guild_id):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def has_snapshots(sf, guild_id):
        return True  # 이미 적재됨 → 백필 안 함

    async def backfill(deps, guild_id, targets):
        calls.append("backfill")

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        calls.append("fetch")
        return 0

    async def build_payload(bot, deps, guild_id):
        return None  # 2명 미만 → 발송 생략

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "has_snapshots", has_snapshots)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert "backfill" not in calls  # 기존 스냅샷 있음 → 백필 스킵(Q11)
    assert "fetch" in calls


async def test_per_guild_payload_built_once_for_two_channels(monkeypatch):
    """같은 길드에 exp_alert 채널이 2개여도 build_payload(DB+렌더)는 1회만."""
    build_calls: list[int] = []
    sent_files: list[list] = []

    async def enabled_exp_channels(sf):
        # 길드 1의 채널 두 개
        return [(1, 100), (1, 101)]

    async def get_targets(sf, guild_id):
        return [SimpleNamespace(discord_user_id=10, nickname="손바", ocid="o1")]

    async def has_snapshots(sf, guild_id):
        return True

    async def backfill(deps, guild_id, targets):
        pass

    async def fetch_and_store(deps, guild_id, targets, date_iso):
        return 0

    async def build_payload(bot, deps, guild_id):
        build_calls.append(guild_id)
        return SimpleNamespace(embed="e", to_files=lambda: ["f1", "f2"])

    class _Channel:
        async def send(self, **kwargs):
            sent_files.append(kwargs["files"])

    async def resolve_channel(bot, guild_id, channel_id):
        return _Channel()

    monkeypatch.setattr(
        broadcast.channel_service, "enabled_exp_channels", enabled_exp_channels
    )
    monkeypatch.setattr(broadcast, "get_targets", get_targets)
    monkeypatch.setattr(broadcast.service, "has_snapshots", has_snapshots)
    monkeypatch.setattr(broadcast.service, "backfill", backfill)
    monkeypatch.setattr(broadcast.service, "fetch_and_store", fetch_and_store)
    monkeypatch.setattr(broadcast, "build_payload", build_payload)
    monkeypatch.setattr(broadcast, "_resolve_channel", resolve_channel)

    await broadcast.run_leaderboard_job(bot=object(), deps=_deps())
    assert build_calls == [1]  # 길드 1에 대해 단 1회만 호출됨(메모이제이션)
    assert len(sent_files) == 2  # 채널 100, 101 각각 발송됨
