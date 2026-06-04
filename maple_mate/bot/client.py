"""discord.py 봇 클라이언트 + 커맨드 트리 등록 (빌드 단위 #7).

슬래시 커맨드 동기화: 개발=길드 스코프(DEV_GUILD_ID, 즉시 반영) / 운영=글로벌.
빈 명령(`/핑`)으로 등록·응답을 확인하고, `/등록`(빌드 단위 #8)을 트리에 추가한다.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from .deps import BotDeps

log = logging.getLogger(__name__)


class MapleMateBot(discord.Client):
    def __init__(self, *, deps: BotDeps, dev_guild_id: int | None):
        intents = discord.Intents.default()  # 슬래시 커맨드는 특권 인텐트 불필요
        super().__init__(intents=intents)
        self.deps = deps
        self._dev_guild_id = dev_guild_id
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        # 명령 등록
        self._register_commands()
        # 동기화: 개발=길드 스코프(즉시) / 운영=글로벌
        if self._dev_guild_id:
            guild = discord.Object(id=self._dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("슬래시 커맨드 길드 동기화 완료(dev guild=%s): %d개", self._dev_guild_id, len(synced))
        else:
            synced = await self.tree.sync()
            log.info("슬래시 커맨드 글로벌 동기화 완료: %d개 (반영까지 최대 1시간)", len(synced))

    def _register_commands(self) -> None:
        from .commands.register import setup as setup_register

        @self.tree.command(name="핑", description="봇 응답 확인")
        async def ping(interaction: discord.Interaction) -> None:
            await interaction.response.send_message("퐁! 🏓", ephemeral=True)

        setup_register(self)

    async def on_ready(self) -> None:
        user = self.user
        log.info("봇 온라인: %s (id=%s)", user, getattr(user, "id", "?"))
