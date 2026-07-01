"""`/스케줄러`·`/스케줄러알림` 핸들러 단위테스트 — 결과 분기 + 구독 가드 (작업지시서 #5).

가짜 Interaction 으로 핸들러를 직접 호출하고, build_homeworks·service DB 함수는 monkeypatch
(test_guide·test_leaderboard_commands 패턴). 실제 발송은 라이브 1회 확인.
"""

from __future__ import annotations

from types import SimpleNamespace

from discord import app_commands

from maple_mate.scheduler import commands
from maple_mate.scheduler.category_filter import (
    BUCKET_BOSS,
    BUCKET_DAILY,
    BUCKET_GUILD,
    BUCKET_WEEKLY,
)
from maple_mate.scheduler.service import (
    BossItem,
    ContentItem,
    Homework,
    Subscription,
)


def _off() -> app_commands.Choice[str]:
    return app_commands.Choice(name="끄기", value="off")


class _Response:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, **kwargs) -> None:
        self._done = True

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)


class _Followup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


def _interaction(guild_id: int | None = 1, user_id: int = 10):
    return SimpleNamespace(
        guild_id=guild_id,
        channel_id=100,
        user=SimpleNamespace(id=user_id),
        response=_Response(),
        followup=_Followup(),
    )


def _deps():
    return SimpleNamespace(
        session_factory=object(), nexon=SimpleNamespace(), cipher=SimpleNamespace()
    )


def _homework(name: str = "내캐릭", empty: bool = False) -> Homework:
    if empty:
        return Homework(name, "스카니아", 200, [], [], [], 0, 0)
    return Homework(
        name,
        "스카니아",
        285,
        [ContentItem("무릉도장", 1, 1)],
        [],
        [BossItem("검은마법사", "하드", True)],
        8,
        14,
    )


# ── /스케줄러 온디맨드 분기 ──────────────────────────────────────────────────


async def test_scheduler_guild_only(monkeypatch):
    interaction = _interaction(guild_id=None)
    await commands.handle_scheduler(_deps(), interaction)
    [sent] = interaction.followup.sent
    assert "서버" in sent["embed"].description


async def test_scheduler_shows_error_when_build_fails(monkeypatch):
    async def build_homeworks(deps, g, u):
        return [], "개인 키 미등록이라 스케줄러를 볼 수 없어요."

    monkeypatch.setattr(commands, "build_homeworks", build_homeworks)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction)
    [sent] = interaction.followup.sent
    assert "개인 키 미등록" in sent["embed"].description
    assert sent["ephemeral"] is True


async def test_scheduler_empty_homework_message(monkeypatch):
    async def build_homeworks(deps, g, u):
        return [_homework(empty=True)], None  # 전 캐릭터 빈 숙제

    monkeypatch.setattr(commands, "build_homeworks", build_homeworks)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction)
    [sent] = interaction.followup.sent
    assert "등록된 숙제" in sent["embed"].description  # 빈 안내(체크리스트 아님)


async def test_scheduler_renders_one_message_per_character(monkeypatch):
    async def build_homeworks(deps, g, u):
        return [_homework(name="캐릭A"), _homework(name="캐릭B")], None

    monkeypatch.setattr(commands, "build_homeworks", build_homeworks)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction)
    titles = [s["embed"].title for s in interaction.followup.sent]
    assert titles == [
        "🗓 캐릭A 의 스케줄러 숙제",
        "🗓 캐릭B 의 스케줄러 숙제",
    ]  # 캐릭터당 1개
    assert all(s["ephemeral"] is True for s in interaction.followup.sent)


async def test_scheduler_skips_empty_characters_renders_rest(monkeypatch):
    async def build_homeworks(deps, g, u):
        return [_homework(name="캐릭A"), _homework(name="빈캐릭", empty=True)], None

    monkeypatch.setattr(commands, "build_homeworks", build_homeworks)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction)
    titles = [s["embed"].title for s in interaction.followup.sent]
    assert titles == ["🗓 캐릭A 의 스케줄러 숙제"]  # 빈 캐릭터 생략, 나머지 표시


# ── /스케줄러알림 켜기: fail fast 가드 + 시각 저장 ───────────────────────────


async def test_reminder_on_rejects_without_key_or_character(monkeypatch):
    set_calls: list = []

    async def resolve_self_characters(sf, g, u):
        return None, [], "개인 키 미등록이라 알림을 켤 수 없어요."

    async def set_subscription(sf, **kwargs):
        set_calls.append(kwargs)

    monkeypatch.setattr(
        commands.service, "resolve_self_characters", resolve_self_characters
    )
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    await commands.handle_reminder_on(_deps(), interaction, 21)
    [sent] = interaction.response.sent
    assert "개인 키 미등록" in sent["embed"].description
    assert set_calls == []  # 가드 실패 → 구독 안 함(fail fast)


async def test_reminder_on_stores_hour(monkeypatch):
    set_calls: list = []

    async def resolve_self_characters(sf, g, u):
        return "enc", [("ocid1", "캐릭A")], None

    async def get_subscription(sf, g, u):
        return None  # 신규 구독 → baseline 빈 제외

    async def set_subscription(sf, **kwargs):
        set_calls.append(kwargs)

    monkeypatch.setattr(
        commands.service, "resolve_self_characters", resolve_self_characters
    )
    monkeypatch.setattr(commands.service, "get_subscription", get_subscription)
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    await commands.handle_reminder_on(_deps(), interaction, 9)
    [kwargs] = set_calls
    assert kwargs["hour"] == 9
    assert kwargs["excluded"] == frozenset()  # 카테고리 미지정 → 전부 표시
    [sent] = interaction.response.sent
    assert "09:00" in sent["embed"].description


async def test_reminder_on_rejects_invalid_hour(monkeypatch):
    set_calls: list = []

    async def resolve_self_characters(sf, g, u):  # 도달하면 안 됨
        set_calls.append("resolve")
        return "enc", [("ocid1", "캐릭A")], None

    async def set_subscription(sf, **kwargs):
        set_calls.append("set")

    monkeypatch.setattr(
        commands.service, "resolve_self_characters", resolve_self_characters
    )
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    await commands.handle_reminder_on(_deps(), interaction, 25)
    [sent] = interaction.response.sent
    assert "0" in sent["embed"].description and "23" in sent["embed"].description
    assert set_calls == []  # 범위 밖 → 해석·구독 모두 안 함


# ── /스케줄러알림 끄기 ───────────────────────────────────────────────────────


async def test_reminder_off_existing(monkeypatch):
    async def clear_subscription(sf, **kwargs):
        return True

    monkeypatch.setattr(commands.service, "clear_subscription", clear_subscription)
    interaction = _interaction()
    await commands.handle_reminder_off(_deps(), interaction)
    [sent] = interaction.response.sent
    assert "껐어요" in sent["embed"].description


async def test_reminder_off_when_not_subscribed(monkeypatch):
    async def clear_subscription(sf, **kwargs):
        return False

    monkeypatch.setattr(commands.service, "clear_subscription", clear_subscription)
    interaction = _interaction()
    await commands.handle_reminder_off(_deps(), interaction)
    [sent] = interaction.response.sent
    assert "없어요" in sent["embed"].description


# ── 카테고리 필터(ADR-0014) ──────────────────────────────────────────────────


async def test_scheduler_excludes_bucket_from_embed(monkeypatch):
    async def build_homeworks(deps, g, u):
        return [_homework(name="캐릭A")], None  # daily 무릉도장 + boss 검은마법사

    monkeypatch.setattr(commands, "build_homeworks", build_homeworks)
    interaction = _interaction()
    await commands.handle_scheduler(_deps(), interaction, frozenset({BUCKET_BOSS}))
    [sent] = interaction.followup.sent
    names = [f.name for f in sent["embed"].fields]
    assert all("보스" not in n for n in names)  # 보스 묶음 가림
    assert any("일일" in n for n in names)  # 나머지는 유지


async def test_scheduler_all_off_guard_before_build(monkeypatch):
    calls: list[str] = []

    async def build_homeworks(deps, g, u):
        calls.append("build")
        return [_homework()], None

    monkeypatch.setattr(commands, "build_homeworks", build_homeworks)
    interaction = _interaction()
    excluded = frozenset({BUCKET_DAILY, BUCKET_WEEKLY, BUCKET_BOSS, BUCKET_GUILD})
    await commands.handle_scheduler(_deps(), interaction, excluded)
    [sent] = interaction.followup.sent
    assert "최소 하나" in sent["embed"].description
    assert calls == []  # 빌드(페치) 전에 거부


async def test_reminder_on_merges_with_stored_excluded(monkeypatch):
    set_calls: list = []

    async def resolve_self_characters(sf, g, u):
        return "enc", [("ocid1", "캐릭A")], None

    async def get_subscription(sf, g, u):
        return Subscription(1, 10, 21, frozenset({BUCKET_GUILD}))

    async def set_subscription(sf, **kwargs):
        set_calls.append(kwargs)

    monkeypatch.setattr(
        commands.service, "resolve_self_characters", resolve_self_characters
    )
    monkeypatch.setattr(commands.service, "get_subscription", get_subscription)
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    # 기존 {길드} + 이번에 보스 끄기 → {길드, 보스}(시각 21 유지, 미지정 묶음 보존)
    await commands.handle_reminder_on(_deps(), interaction, 21, boss=_off())
    [kwargs] = set_calls
    assert kwargs["excluded"] == frozenset({BUCKET_GUILD, BUCKET_BOSS})
    [sent] = interaction.response.sent
    assert "숨김" in sent["embed"].description  # 확인 메시지에 필터 요약


async def test_reminder_on_rejects_merged_all_off(monkeypatch):
    set_calls: list = []

    async def resolve_self_characters(sf, g, u):
        return "enc", [("ocid1", "캐릭A")], None

    async def get_subscription(sf, g, u):
        return Subscription(
            1, 10, 21, frozenset({BUCKET_DAILY, BUCKET_WEEKLY, BUCKET_BOSS})
        )

    async def set_subscription(sf, **kwargs):
        set_calls.append(kwargs)

    monkeypatch.setattr(
        commands.service, "resolve_self_characters", resolve_self_characters
    )
    monkeypatch.setattr(commands.service, "get_subscription", get_subscription)
    monkeypatch.setattr(commands.service, "set_subscription", set_subscription)
    interaction = _interaction()
    # 기존 {일일,주간,보스} + 길드 끄기 → 4묶음 전부 → 거부(저장 안 함)
    await commands.handle_reminder_on(_deps(), interaction, 21, guild=_off())
    [sent] = interaction.response.sent
    assert "최소 하나" in sent["embed"].description
    assert set_calls == []
