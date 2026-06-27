"""run_scheduler_reminder_job 오케스트레이션 + build_homeworks 단위테스트 (작업지시서 #4·#5).

모든 I/O(DB·넥슨·디스코드 DM)를 페이크로 막고 제어흐름만 검증한다. 실제 DM 발송·임베드 시각은
라이브 1회 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from types import SimpleNamespace

from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from maple_mate.registration.realm import Realm
from maple_mate.scheduler import broadcast
from maple_mate.scheduler.service import Subscription


def _deps(**over):
    base = dict(
        session_factory=object(), nexon=SimpleNamespace(), cipher=SimpleNamespace()
    )
    base.update(over)
    return SimpleNamespace(**base)


# ── build_homeworks: resolve → 복호화 → 캐릭터별 페치 → 파싱 ───────────────────


async def test_build_homeworks_returns_error_when_resolve_fails(monkeypatch):
    async def resolve(sf, g, u, realm):
        return None, [], "개인 키 미등록"

    monkeypatch.setattr(broadcast.service, "resolve_self_characters", resolve)
    hws, error = await broadcast.build_homeworks(_deps(), 1, 10, Realm.MAIN)
    assert hws == [] and error == "개인 키 미등록"


async def test_build_homeworks_fetches_each_character(monkeypatch):
    async def resolve(sf, g, u, realm):
        return "enc", [("ocid1", "캐릭A"), ("ocid2", "캐릭B")], None

    async def scheduler_character_state(api_key, ocid, date_iso=None):
        assert api_key == "decrypted" and date_iso is None
        return {"character_name": {"ocid1": "캐릭A", "ocid2": "캐릭B"}[ocid]}

    deps = _deps(
        nexon=SimpleNamespace(scheduler_character_state=scheduler_character_state),
        cipher=SimpleNamespace(decrypt=lambda enc: "decrypted"),
    )
    monkeypatch.setattr(broadcast.service, "resolve_self_characters", resolve)
    hws, error = await broadcast.build_homeworks(deps, 1, 10, Realm.MAIN)
    assert error is None
    assert [hw.character_name for hw in hws] == ["캐릭A", "캐릭B"]  # 캐릭터 전부


async def test_build_homeworks_skips_4xx_character(monkeypatch):
    async def resolve(sf, g, u, realm):
        return "enc", [("bad", "저활동"), ("ok", "정상")], None

    async def scheduler_character_state(api_key, ocid, date_iso=None):
        if ocid == "bad":
            raise NexonAPIError(
                "OPENAPI00003",
                "invalid id",
                http_status=400,
                error_class=ErrorClass.INVALID_ID,
            )
        return {"character_name": "정상"}

    deps = _deps(
        nexon=SimpleNamespace(scheduler_character_state=scheduler_character_state),
        cipher=SimpleNamespace(decrypt=lambda enc: "k"),
    )
    monkeypatch.setattr(broadcast.service, "resolve_self_characters", resolve)
    hws, error = await broadcast.build_homeworks(deps, 1, 10, Realm.MAIN)
    assert error is None  # 캐릭터별 4xx 는 raise/error 아님(조용히 스킵)
    assert [hw.character_name for hw in hws] == ["정상"]  # bad 캐릭터만 빠짐


# ── run_scheduler_reminder_job: 시각 구독 → 구독별 캐릭터당 DM ─────────────────


async def test_job_skips_when_no_subscriptions(monkeypatch):
    calls: list[str] = []

    async def subscriptions_at_hour(sf, hour):
        calls.append("subs")
        return []

    async def build_homeworks(deps, g, u, realm):
        calls.append("build")
        return [], None

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homeworks", build_homeworks)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert calls == ["subs"]  # 구독 0 → 넥슨/발송 없음


async def test_job_dms_each_character(monkeypatch):
    subs = [Subscription(1, 10, Realm.MAIN, 21)]
    dmed: list[int] = []

    async def subscriptions_at_hour(sf, hour):
        return subs

    async def build_homeworks(deps, g, u, realm):
        return [SimpleNamespace(is_empty=False) for _ in range(3)], None  # 캐릭터 3개

    async def send_dm(bot, user_id, embed):
        dmed.append(user_id)
        return True

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homeworks", build_homeworks)
    monkeypatch.setattr(broadcast, "build_embed", lambda hw, realm, now: "e")
    monkeypatch.setattr(broadcast, "_send_dm", send_dm)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert dmed == [10, 10, 10]  # 캐릭터 3개 → 본인 DM 3개(캐릭터당 메시지 1개)


async def test_job_skips_empty_characters(monkeypatch):
    subs = [Subscription(1, 10, Realm.MAIN, 21)]
    sent: list = []

    async def subscriptions_at_hour(sf, hour):
        return subs

    async def build_homeworks(deps, g, u, realm):
        return [
            SimpleNamespace(is_empty=False),
            SimpleNamespace(is_empty=True),  # 빈 캐릭터 → 스킵
            SimpleNamespace(is_empty=False),
        ], None

    async def send_dm(bot, user_id, embed):
        sent.append(embed)
        return True

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homeworks", build_homeworks)
    monkeypatch.setattr(broadcast, "build_embed", lambda hw, realm, now: "e")
    monkeypatch.setattr(broadcast, "_send_dm", send_dm)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert len(sent) == 2  # 빈 캐릭터 1개 스킵(빈 DM 금지)


async def test_job_continues_when_dm_blocked(monkeypatch):
    subs = [Subscription(1, 10, Realm.MAIN, 21), Subscription(1, 11, Realm.MAIN, 21)]
    attempted: list[int] = []

    async def subscriptions_at_hour(sf, hour):
        return subs

    async def build_homeworks(deps, g, u, realm):
        return [SimpleNamespace(is_empty=False)], None

    async def send_dm(bot, user_id, embed):
        attempted.append(user_id)
        return user_id != 10  # 10 은 DM 차단(False) — raise 하지 않고 스킵

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homeworks", build_homeworks)
    monkeypatch.setattr(broadcast, "build_embed", lambda hw, realm, now: "e")
    monkeypatch.setattr(broadcast, "_send_dm", send_dm)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert attempted == [10, 11]  # 차단된 10 이후에도 11 시도(전체 계속)
