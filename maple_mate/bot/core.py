"""Discord 전달 계층 인프라 — 봇 게이트웨이 + 커맨드 트리 동기화 (빌드 단위 #7).

각 도메인의 `commands.py` 가 `setup(bot)` 으로 자기 슬래시 커맨드를 트리에 등록한다.
동기화: 개발=길드 스코프(DEV_GUILD_ID, 즉시 반영) / 운영=글로벌.
"""

from __future__ import annotations

import logging
import math

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import app_commands

from ..dependencies import Deps
from ..notification.scheduler import shutdown as shutdown_scheduler
from ..notification.scheduler import start_scheduler
from .embeds import make_embed

log = logging.getLogger(__name__)


async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    """트리 공통 에러 핸들러 (스케일 튜닝 3-3).

    CommandOnCooldown 은 ephemeral 로 남은 시간 안내(쿨다운은 callback 실행 전이라
    defer 미수행 → response 로 응답). 그 외는 앱로그만 — 명령별 에러 임베드 경로는
    각 핸들러가 이미 처리하므로 여기는 최종 안전망.
    """
    if isinstance(error, app_commands.CommandOnCooldown):
        seconds = max(1, math.ceil(error.retry_after))
        embed = make_embed(
            "잠시만요 ⏳",
            f"명령을 너무 자주 사용했어요. **{seconds}초** 후 다시 시도해 주세요.",
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    command = interaction.command.qualified_name if interaction.command else "?"
    log.error("슬래시 커맨드 오류 (/%s): %s", command, error, exc_info=error)


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
        self.tree.error(on_app_command_error)  # 쿨다운 ephemeral 안내 + 최종 안전망
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
        from ..bitik.commands import setup as setup_bitik
        from ..character.commands import setup as setup_character
        from ..history.commands import setup as setup_history
        from ..history.potential_commands import setup as setup_potential
        from ..leaderboard.commands import setup_leaderboard
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
        setup_bitik(self)  # /비틱 (스타포스·잠재·득템)
        setup_leaderboard(self)  # /경험치 · /경험치알림
        setup_notification(self)  # /썬데이

    async def on_ready(self) -> None:
        user = self.user
        log.info("봇 온라인: %s (id=%s)", user, getattr(user, "id", "?"))
