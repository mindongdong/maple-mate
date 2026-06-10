"""Discord 전달 계층 인프라 — 봇 게이트웨이 + 커맨드 트리 동기화 (빌드 단위 #7).

각 도메인의 `commands.py` 가 `setup(bot)` 으로 자기 슬래시 커맨드를 트리에 등록한다.
동기화: 개발=길드 스코프(DEV_GUILD_ID, 즉시 반영) / 운영=글로벌.
"""

from __future__ import annotations

import logging

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import app_commands

from ..dependencies import Deps
from ..notification.scheduler import shutdown as shutdown_scheduler
from ..notification.scheduler import start_scheduler

log = logging.getLogger(__name__)


class MapleMateBot(discord.Client):
    def __init__(self, *, deps: Deps, dev_guild_id: int | None):
        intents = discord.Intents.default()  # 슬래시 커맨드는 특권 인텐트 불필요
        # 비교 임베드의 유저 태그(@닉)는 '누가 어떤 캐릭 주인'인지 표시용 — 핑(알림)은 울리지
        # 않도록 전역 차단. (임베드 본문 멘션은 기본적으로 핑 안 하지만 명시적으로 무력화)
        super().__init__(
            intents=intents, allowed_mentions=discord.AllowedMentions.none()
        )
        self.deps = deps
        self._dev_guild_id = dev_guild_id
        self.tree = app_commands.CommandTree(self)
        self._scheduler: AsyncIOScheduler | None = (
            None  # 봇이 소유(setup_hook 시작 / close 종료)
        )

    async def setup_hook(self) -> None:
        self._register_commands()
        if self._dev_guild_id:
            guild = discord.Object(id=self._dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(
                "슬래시 커맨드 길드 동기화(dev guild=%s): %d개",
                self._dev_guild_id,
                len(synced),
            )
        else:
            synced = await self.tree.sync()
            log.info(
                "슬래시 커맨드 글로벌 동기화: %d개 (반영까지 최대 1시간)", len(synced)
            )
        # 알림 스케줄러를 1회 시작(setup_hook 은 재연결과 무관하게 한 번만 호출됨, Q7).
        if self._scheduler is None:
            self._scheduler = start_scheduler(self, self.deps)

    async def close(self) -> None:
        if self._scheduler is not None:
            shutdown_scheduler(self._scheduler)
            self._scheduler = None
        await super().close()

    def _register_commands(self) -> None:
        """도메인별 commands.setup 을 모아 트리에 등록. 새 명령은 도메인 commands.py 에 추가."""
        from ..character.commands import setup as setup_character
        from ..history.commands import setup as setup_history
        from ..history.potential_commands import setup as setup_potential
        from ..notification.commands import setup as setup_notification
        from ..registration.commands import setup as setup_registration
        from ..union.commands import setup as setup_union

        @self.tree.command(name="핑", description="봇 응답 확인")
        async def ping(interaction: discord.Interaction) -> None:
            await interaction.response.send_message("퐁! 🏓", ephemeral=True)

        setup_registration(self)
        setup_union(self)
        setup_character(self)  # /스펙 · /아이템
        setup_history(self)  # /스타포스
        setup_potential(self)  # /잠재
        setup_notification(self)  # /썬데이

    async def on_ready(self) -> None:
        user = self.user
        log.info("봇 온라인: %s (id=%s)", user, getattr(user, "id", "?"))
