"""`/썬데이` 디스코드 어댑터 (얇은 전달 계층, 작업지시서 빌드 단위 #4, Q5).

단일 `/썬데이` + 필수 `상태`(켜기/끄기) 평면 구조. 서버 관리(`manage_guild`) 권한을
인라인 체크하고 거부는 ephemeral. DM 가드. 토글은 명령이 실행된 채널 단위(design §2).
"""

from __future__ import annotations

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import make_embed
from ..dependencies import Deps
from . import notice_service, service


async def handle_sunday(
    deps: Deps, interaction: discord.Interaction, enabled: bool
) -> None:
    if interaction.guild_id is None or interaction.channel_id is None:
        await interaction.response.send_message(
            embed=make_embed(
                "썬데이 알림", "서버(길드) 채널 안에서만 설정할 수 있어요."
            ),
            ephemeral=True,
        )
        return

    perms = getattr(interaction.user, "guild_permissions", None)
    if perms is None or not perms.manage_guild:
        await interaction.response.send_message(
            embed=make_embed("권한 없음", "이 설정은 **서버 관리** 권한이 필요해요."),
            ephemeral=True,
        )
        return

    await service.set_sunday_alert(
        deps.session_factory,
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        enabled=enabled,
    )
    state = "켜짐 🔔" if enabled else "꺼짐 🔕"
    description = (
        "이 채널에 금요일 10:10(KST) 썬데이 메이플 알림을 보낼게요."
        if enabled
        else "이 채널의 썬데이 알림을 더 이상 보내지 않아요."
    )
    await interaction.response.send_message(
        embed=make_embed(f"썬데이 알림 {state}", description), ephemeral=True
    )


async def handle_notice(
    deps: Deps, interaction: discord.Interaction, enabled: bool
) -> None:
    if interaction.guild_id is None or interaction.channel_id is None:
        await interaction.response.send_message(
            embed=make_embed("공지 알림", "서버(길드) 채널 안에서만 설정할 수 있어요."),
            ephemeral=True,
        )
        return

    perms = getattr(interaction.user, "guild_permissions", None)
    if perms is None or not perms.manage_guild:
        await interaction.response.send_message(
            embed=make_embed("권한 없음", "이 설정은 **서버 관리** 권한이 필요해요."),
            ephemeral=True,
        )
        return

    await notice_service.set_notice_alert(
        deps.session_factory,
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        enabled=enabled,
    )
    state = "켜짐 🔔" if enabled else "꺼짐 🔕"
    description = (
        "이 채널에 메이플 공지사항·업데이트 소식을 보내드릴게요."
        if enabled
        else "이 채널의 공지 알림을 더 이상 보내지 않아요."
    )
    await interaction.response.send_message(
        embed=make_embed(f"공지 알림 {state}", description), ephemeral=True
    )


def setup(bot: discord.Client) -> None:
    """봇 트리에 `/썬데이`·`/공지알림` 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="썬데이",
        description="이 채널의 썬데이 메이플 알림을 켜거나 끕니다 (서버 관리 권한 필요).",
    )
    @app_commands.rename(status="상태")
    @app_commands.describe(status="썬데이 알림을 켤지 끌지 선택")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="켜기", value="on"),
            app_commands.Choice(name="끄기", value="off"),
        ]
    )
    @cooldowns.settings_cooldown()
    async def sunday_command(
        interaction: discord.Interaction, status: app_commands.Choice[str]
    ) -> None:
        await handle_sunday(deps, interaction, status.value == "on")

    @bot.tree.command(  # type: ignore[attr-defined]
        name="공지알림",
        description="이 채널의 메이플 공지·업데이트 알림을 켜거나 끕니다 (서버 관리 권한 필요).",
    )
    @app_commands.rename(status="상태")
    @app_commands.describe(status="공지 알림을 켤지 끌지 선택")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="켜기", value="on"),
            app_commands.Choice(name="끄기", value="off"),
        ]
    )
    @cooldowns.settings_cooldown()
    async def notice_command(
        interaction: discord.Interaction, status: app_commands.Choice[str]
    ) -> None:
        await handle_notice(deps, interaction, status.value == "on")
