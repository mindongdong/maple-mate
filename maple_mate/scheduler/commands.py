"""스케줄러 알리미 Discord 어댑터 (얇은 전달 계층, 작업지시서 #5).

- `/스케줄러 [모드]`: 본인 대표 캐릭터 숙제 체크리스트(ephemeral 온디맨드, 결정 1).
- `/스케줄러알림 켜기 [시각] [모드]` / `끄기 [모드]`: per-user DM 구독 토글(결정 2·4).
  켜기는 키·realm 대표 없으면 구독 거부(fail fast, 결정 7a). 발송은 매시 정각 cron(broadcast).
"""

from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import defer, make_embed
from ..bot.modes import MODE_CHOICES, MODE_DESCRIBE, parse_mode
from ..dependencies import Deps
from ..nexon.client import KST
from ..registration.realm import Realm, realm_title
from . import service
from .broadcast import build_embed, build_homework
from .service import DEFAULT_HOUR

_MSG_GUILD_ONLY = "서버(길드) 안에서만 쓸 수 있어요."
_MSG_NO_HOMEWORK = (
    "인게임 메이플 스케줄러에 등록된 숙제가 없어요."
    " 게임에서 콘텐츠를 스케줄러에 등록하면 여기 떠요."
)
_MSG_BAD_HOUR = "시각은 **0~23** 사이 정수로 입력해 주세요."


async def handle_scheduler(
    deps: Deps, interaction: discord.Interaction, realm: Realm = Realm.MAIN
) -> None:
    """`/스케줄러` 본체: defer(ephemeral) → build_homework → 결과 분기(에러·빈·체크리스트)."""
    await defer(interaction, ephemeral=True)
    title = realm_title("스케줄러 숙제", realm)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed(title, _MSG_GUILD_ONLY), ephemeral=True
        )
        return

    homework, error = await build_homework(
        deps, interaction.guild_id, interaction.user.id, realm
    )
    if homework is None:
        await interaction.followup.send(embed=make_embed(title, error), ephemeral=True)
        return
    if homework.is_empty:
        await interaction.followup.send(
            embed=make_embed(title, _MSG_NO_HOMEWORK), ephemeral=True
        )
        return

    embed = build_embed(homework, realm, datetime.now(KST))
    await interaction.followup.send(embed=embed, ephemeral=True)  # 온디맨드 ephemeral


async def handle_reminder_on(
    deps: Deps, interaction: discord.Interaction, hour: int, realm: Realm
) -> None:
    """`/스케줄러알림 켜기` 본체: 시각 검증 → fail-fast 가드(키·대표) → 구독 upsert."""
    title = realm_title("스케줄러 알림", realm)
    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed(title, _MSG_GUILD_ONLY), ephemeral=True
        )
        return
    if not 0 <= hour <= 23:
        await interaction.response.send_message(
            embed=make_embed(title, _MSG_BAD_HOUR), ephemeral=True
        )
        return

    # fail fast: 키·realm 대표가 없으면 구독 자체를 거부한다(결정 7a — 죽은 구독 예방).
    _key, _ocid, error = await service.resolve_self(
        deps.session_factory, interaction.guild_id, interaction.user.id, realm
    )
    if error is not None:
        await interaction.response.send_message(
            embed=make_embed(title, error), ephemeral=True
        )
        return

    await service.set_subscription(
        deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        realm=realm,
        hour=hour,
    )
    await interaction.response.send_message(
        embed=make_embed(
            realm_title("스케줄러 알림 켜짐 🔔", realm),
            f"매일 **{hour:02d}:00**(KST)에 스케줄러 숙제 체크리스트를 DM으로 보낼게요.",
        ),
        ephemeral=True,
    )


async def handle_reminder_off(
    deps: Deps, interaction: discord.Interaction, realm: Realm
) -> None:
    """`/스케줄러알림 끄기` 본체: 구독 delete. 켜진 적 없으면 안내 분기."""
    title = realm_title("스케줄러 알림", realm)
    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed(title, _MSG_GUILD_ONLY), ephemeral=True
        )
        return

    existed = await service.clear_subscription(
        deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        realm=realm,
    )
    if existed:
        await interaction.response.send_message(
            embed=make_embed(
                realm_title("스케줄러 알림 꺼짐 🔕", realm),
                "스케줄러 숙제 DM 알림을 껐어요.",
            ),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=make_embed(title, "켜져 있던 스케줄러 알림이 없어요."),
            ephemeral=True,
        )


# ── 트리 등록 ───────────────────────────────────────────────────────────────


def setup(bot: discord.Client) -> None:
    """봇 트리에 `/스케줄러`·`/스케줄러알림`(켜기·끄기) 등록. bot.deps(Deps) 사용."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="스케줄러",
        description="본인 대표 캐릭터의 인게임 스케줄러 숙제 현황을 보여줍니다 (개인 키 필요).",
    )
    @app_commands.rename(mode="모드")
    @app_commands.describe(mode=MODE_DESCRIBE)
    @app_commands.choices(mode=MODE_CHOICES)
    @cooldowns.spec_cooldown()  # 개인 키 1콜 — 스펙류와 동일 10초
    async def scheduler_command(
        interaction: discord.Interaction,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_scheduler(deps, interaction, parse_mode(mode))

    group = app_commands.Group(
        name="스케줄러알림",
        description="매일 정해진 시각에 스케줄러 숙제를 DM으로 받는 구독을 켜거나 끕니다.",
    )

    @group.command(
        name="켜기",
        description="스케줄러 숙제 DM 구독을 켭니다 (개인 키 필요).",
    )
    @app_commands.rename(hour="시각", mode="모드")
    @app_commands.describe(
        hour=f"받을 시각 (KST 0~23시, 기본 {DEFAULT_HOUR}시)",
        mode=MODE_DESCRIBE,
    )
    @app_commands.choices(mode=MODE_CHOICES)
    @cooldowns.settings_cooldown()
    async def reminder_on(
        interaction: discord.Interaction,
        hour: app_commands.Range[int, 0, 23] = DEFAULT_HOUR,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_reminder_on(deps, interaction, hour, parse_mode(mode))

    @group.command(name="끄기", description="스케줄러 숙제 DM 구독을 끕니다.")
    @app_commands.rename(mode="모드")
    @app_commands.describe(mode=MODE_DESCRIBE)
    @app_commands.choices(mode=MODE_CHOICES)
    @cooldowns.settings_cooldown()
    async def reminder_off(
        interaction: discord.Interaction,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_reminder_off(deps, interaction, parse_mode(mode))

    bot.tree.add_command(group)  # type: ignore[attr-defined]
