"""`/등록` 디스코드 어댑터 (빌드 단위 #8). 얇은 전달 계층 — 로직은 service 가 담당.

입력 파싱 → service.register 호출 → 결과를 ephemeral 임베드로 렌더. 용어는 CONTEXT.md
("등록", "키 미등록") 사용. 개인 키 노출 최소화를 위해 응답은 항상 ephemeral.
"""
from __future__ import annotations

import discord
from discord import app_commands

from ..bot.embeds import defer, make_embed
from ..dependencies import Deps
from . import service


async def handle_register(
    deps: Deps,
    interaction: discord.Interaction,
    nickname: str,
    api_key: str | None,
) -> None:
    await defer(interaction, ephemeral=True)

    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("등록 실패", "서버(길드) 안에서만 등록할 수 있어요."), ephemeral=True
        )
        return

    result = await service.register(
        nexon=deps.nexon,
        cipher=deps.cipher,
        session_factory=deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        nickname=nickname.strip(),
        api_key=api_key.strip() if api_key else None,
    )

    if not result.ok:
        await interaction.followup.send(embed=make_embed("등록 실패", result.error), ephemeral=True)
        return

    if result.has_key:
        scope = "스타포스·잠재 등 **이력류**까지 조회 가능 (개인 키 등록됨)"
    else:
        scope = "**스펙류**만 조회 가능 (키 미등록)"
    await interaction.followup.send(
        embed=make_embed("등록 완료", f"**{result.nickname}** 등록이 완료됐어요.\n{scope}"),
        ephemeral=True,
    )


def setup(bot: discord.Client) -> None:
    """봇 트리에 `/등록` 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(name="등록", description="메이플 캐릭터를 이 서버에 등록합니다 (API 키는 선택).")  # type: ignore[attr-defined]
    @app_commands.rename(nickname="닉네임", api_key="api키")
    @app_commands.describe(
        nickname="메이플 캐릭터 닉네임",
        api_key="넥슨 개인 API 키 (선택). 입력하면 스타포스·잠재 등 이력류 조회가 열립니다.",
    )
    async def register_command(
        interaction: discord.Interaction,
        nickname: str,
        api_key: str | None = None,
    ) -> None:
        await handle_register(deps, interaction, nickname, api_key)
