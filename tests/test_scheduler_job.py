"""run_scheduler_reminder_job 오케스트레이션 + build_homework 단위테스트 (작업지시서 #4·#5).

모든 I/O(DB·넥슨·디스코드 DM)를 페이크로 막고 제어흐름만 검증한다. 실제 DM 발송·임베드 시각은
라이브 1회 확인(작업지시서 테스트 전략).
"""

from __future__ import annotations

from types import SimpleNamespace

from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from maple_mate.registration.realm import Realm
from maple_mate.scheduler import broadcast
from maple_mate.scheduler.service import Subscription


def _deps():
    return SimpleNamespace(
        session_factory=object(), nexon=SimpleNamespace(), cipher=SimpleNamespace()
    )


# ── build_homework: resolve → 복호화 → 페치 → 파싱 ───────────────────────────


async def test_build_homework_returns_error_when_resolve_fails(monkeypatch):
    async def resolve_self(sf, g, u, realm):
        return None, None, "개인 키 미등록"

    monkeypatch.setattr(broadcast.service, "resolve_self", resolve_self)
    hw, error = await broadcast.build_homework(_deps(), 1, 10, Realm.MAIN)
    assert hw is None and error == "개인 키 미등록"


async def test_build_homework_success_parses(monkeypatch):
    async def resolve_self(sf, g, u, realm):
        return "enc", "ocid1", None

    async def scheduler_character_state(api_key, ocid, date_iso=None):
        assert api_key == "decrypted" and ocid == "ocid1" and date_iso is None
        return {
            "character_name": "내캐릭",
            "daily_contents": [
                {
                    "content_name": "무릉도장",
                    "registration_flag": "true",
                    "now_count": 1,
                    "max_count": 1,
                }
            ],
        }

    deps = SimpleNamespace(
        session_factory=object(),
        nexon=SimpleNamespace(scheduler_character_state=scheduler_character_state),
        cipher=SimpleNamespace(decrypt=lambda enc: "decrypted"),
    )
    monkeypatch.setattr(broadcast.service, "resolve_self", resolve_self)
    hw, error = await broadcast.build_homework(deps, 1, 10, Realm.MAIN)
    assert error is None
    assert hw.daily[0].name == "무릉도장"


async def test_build_homework_absorbs_nexon_4xx(monkeypatch):
    async def resolve_self(sf, g, u, realm):
        return "enc", "ocid1", None

    async def scheduler_character_state(api_key, ocid, date_iso=None):
        raise NexonAPIError(
            "OPENAPI00003",
            "invalid id",
            http_status=400,
            error_class=ErrorClass.INVALID_ID,
        )

    deps = SimpleNamespace(
        session_factory=object(),
        nexon=SimpleNamespace(scheduler_character_state=scheduler_character_state),
        cipher=SimpleNamespace(decrypt=lambda enc: "k"),
    )
    monkeypatch.setattr(broadcast.service, "resolve_self", resolve_self)
    hw, error = await broadcast.build_homework(deps, 1, 10, Realm.MAIN)
    assert hw is None and error is not None  # 4xx → 조회 불가 메시지(에러 raise 안 함)


# ── run_scheduler_reminder_job: 시각 구독 조회 → 구독별 DM ─────────────────────


async def test_job_skips_when_no_subscriptions(monkeypatch):
    calls: list[str] = []

    async def subscriptions_at_hour(sf, hour):
        calls.append("subs")
        return []

    async def build_homework(deps, g, u, realm):
        calls.append("build")
        return None, None

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homework", build_homework)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert calls == ["subs"]  # 구독 0 → 넥슨/발송 없음


async def test_job_dms_each_subscription_with_homework(monkeypatch):
    subs = [
        Subscription(1, 10, Realm.MAIN, 21),
        Subscription(1, 11, Realm.CHALLENGERS, 21),
    ]
    dmed: list[int] = []

    async def subscriptions_at_hour(sf, hour):
        return subs

    async def build_homework(deps, g, u, realm):
        return SimpleNamespace(is_empty=False), None

    def build_embed(hw, realm, now):
        return "embed"

    async def send_dm(bot, user_id, embed):
        dmed.append(user_id)
        return True

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homework", build_homework)
    monkeypatch.setattr(broadcast, "build_embed", build_embed)
    monkeypatch.setattr(broadcast, "_send_dm", send_dm)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert dmed == [10, 11]  # 구독별 본인 DM


async def test_job_skips_empty_and_failed_homework(monkeypatch):
    subs = [
        Subscription(1, 10, Realm.MAIN, 21),  # 정상
        Subscription(1, 11, Realm.MAIN, 21),  # 등록 0개(is_empty)
        Subscription(1, 12, Realm.MAIN, 21),  # 키없음/4xx(None)
    ]
    dmed: list[int] = []

    async def subscriptions_at_hour(sf, hour):
        return subs

    async def build_homework(deps, g, u, realm):
        if u == 11:
            return SimpleNamespace(is_empty=True), None  # 빈 DM 금지
        if u == 12:
            return None, "키 미등록"  # 조용히 스킵
        return SimpleNamespace(is_empty=False), None

    async def send_dm(bot, user_id, embed):
        dmed.append(user_id)
        return True

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homework", build_homework)
    monkeypatch.setattr(broadcast, "build_embed", lambda hw, realm, now: "e")
    monkeypatch.setattr(broadcast, "_send_dm", send_dm)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert dmed == [10]  # 정상 1건만 발송, 나머지 조용히 스킵


async def test_job_continues_when_dm_blocked(monkeypatch):
    subs = [Subscription(1, 10, Realm.MAIN, 21), Subscription(1, 11, Realm.MAIN, 21)]
    attempted: list[int] = []

    async def subscriptions_at_hour(sf, hour):
        return subs

    async def build_homework(deps, g, u, realm):
        return SimpleNamespace(is_empty=False), None

    async def send_dm(bot, user_id, embed):
        attempted.append(user_id)
        return user_id != 10  # 10 은 DM 차단(False) — raise 하지 않고 스킵

    monkeypatch.setattr(
        broadcast.service, "subscriptions_at_hour", subscriptions_at_hour
    )
    monkeypatch.setattr(broadcast, "build_homework", build_homework)
    monkeypatch.setattr(broadcast, "build_embed", lambda hw, realm, now: "e")
    monkeypatch.setattr(broadcast, "_send_dm", send_dm)
    await broadcast.run_scheduler_reminder_job(bot=object(), deps=_deps())
    assert attempted == [10, 11]  # 차단된 10 이후에도 11 시도(전체 계속)
