"""명령군별 쿨다운 + 트리 에러 핸들러 단위테스트 (스케일 튜닝 3-3, D3).

discord 게이트웨이 없이: 봇을 오프라인 생성해 트리에 등록된 실제 명령의 체크를
가짜 Interaction 으로 직접 호출한다. 시간은 interaction.created_at 으로 주입
(discord.py 쿨다운이 created_at.timestamp() 를 현재 시각으로 쓴다).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from discord import app_commands

from maple_mate.bot import cooldowns
from maple_mate.bot.core import MapleMateBot, on_app_command_error

# 0 epoch 은 discord.py Cooldown 의 `current or time.time()` 폴백에 걸린다 → 0 아닌 기준점.
_BASE = 1_000_000.0


def _interaction(guild_id: int = 1, user_id: int = 10, at: float = 0.0):
    return SimpleNamespace(
        created_at=datetime.fromtimestamp(_BASE + at, tz=timezone.utc),
        guild_id=guild_id,
        user=SimpleNamespace(id=user_id),
    )


@pytest.fixture(scope="module")
def bot() -> MapleMateBot:
    # deps 는 setup 클로저에 잡히기만 하므로 더미면 충분. 게이트웨이 미접속.
    bot = MapleMateBot(deps=object(), dev_guild_id=None)
    bot._register_commands()
    return bot


def _check(bot: MapleMateBot, name: str):
    command = bot.tree.get_command(name)
    assert command is not None, f"/{name} 미등록"
    assert len(command.checks) == 1, f"/{name} 쿨다운 체크 1개여야 함"
    return command.checks[0]


# ── 명령군별 부착 + 간격 (D3 표) ──────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "per"),
    [
        ("스타포스", 30.0),
        ("잠재", 30.0),
        ("스펙", 10.0),
        ("아이템", 10.0),
        ("유니온", 10.0),
        ("등록", 5.0),
        ("썬데이", 5.0),
        ("공지알림", 5.0),
    ],
)
async def test_command_group_cooldown_attached(bot, name, per):
    check = _check(bot, name)
    assert await check(_interaction(at=0.0)) is True
    with pytest.raises(app_commands.CommandOnCooldown) as exc:
        await check(_interaction(at=0.0))
    assert exc.value.retry_after == pytest.approx(per, abs=0.01)
    # 경과 후 정상 실행.
    assert await check(_interaction(at=per + 0.1)) is True


async def test_ping_has_no_cooldown(bot):
    ping = bot.tree.get_command("핑")
    assert ping is not None
    assert not ping.checks


async def test_cooldown_is_per_user_and_per_guild(bot):
    check = _check(bot, "스타포스")
    assert await check(_interaction(guild_id=1, user_id=10, at=100.0)) is True
    # 다른 유저·다른 서버는 독립 버킷 — 즉시 통과.
    assert await check(_interaction(guild_id=1, user_id=11, at=100.0)) is True
    assert await check(_interaction(guild_id=2, user_id=10, at=100.0)) is True


def test_factories_create_independent_buckets():
    # 같은 팩토리로 만든 두 데코레이터는 매핑을 공유하지 않는다(명령 간 쿨다운 격리).
    deco_a, deco_b = cooldowns.history_cooldown(), cooldowns.history_cooldown()
    assert deco_a is not deco_b


# ── 트리 에러 핸들러: CommandOnCooldown → ephemeral 안내 ─────────────


class _Response:
    def __init__(self, done: bool = False):
        self._done = done
        self.sent: list[dict] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)


class _Followup:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


def _error_interaction(done: bool = False):
    return SimpleNamespace(response=_Response(done), followup=_Followup(), command=None)


def _cooldown_error(retry_after: float) -> app_commands.CommandOnCooldown:
    return app_commands.CommandOnCooldown(app_commands.Cooldown(1, 30.0), retry_after)


async def test_cooldown_error_sends_ephemeral_with_remaining_seconds():
    interaction = _error_interaction()
    await on_app_command_error(interaction, _cooldown_error(11.2))
    [sent] = interaction.response.sent
    assert sent["ephemeral"] is True
    assert "12초" in sent["embed"].description  # ceil(11.2)


async def test_cooldown_error_uses_followup_when_already_responded():
    interaction = _error_interaction(done=True)
    await on_app_command_error(interaction, _cooldown_error(3.0))
    assert not interaction.response.sent
    [sent] = interaction.followup.sent
    assert sent["ephemeral"] is True


async def test_other_errors_do_not_message_user(caplog):
    interaction = _error_interaction()
    error = app_commands.AppCommandError("boom")
    with caplog.at_level("ERROR"):
        await on_app_command_error(interaction, error)
    assert not interaction.response.sent
    assert not interaction.followup.sent
    assert any("슬래시 커맨드 오류" in r.message for r in caplog.records)
