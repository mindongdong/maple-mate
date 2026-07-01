"""정기 알림 켜기/끄기 공통 처리 — 대상(채널/개인) 분기 (ADR-0017).

경험치·공지·썬데이가 공유하는 토글 본체. 대상에 따라 채널 토글(channel_settings)·개인 DM
구독(notification_subscription)을 한쪽 또는 둘 다 적용하고 확인 임베드를 낸다. **권한 체크
없음**(ADR-0017 결정 3) — 누구나 셀프 토글. 개인 대상은 길드 컨텍스트만 확인한다.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import discord

from ..bot.embeds import make_embed
from ..dependencies import Deps
from . import service
from .target import targets_for

# 채널 토글 함수 시그니처(set_exp_alert / set_notice_alert / set_sunday_alert 공통).
SetChannel = Callable[..., Awaitable[None]]

_MSG_GUILD_ONLY = "서버(길드) 안에서만 설정할 수 있어요."
_MSG_PERSONAL_NONE = "개인 DM 구독은 켜져 있지 않았어요."


@dataclass(frozen=True)
class AlertSpec:
    """알림 1종의 토글 메타(경험치·공지·썬데이). 제목·확인 문구·채널 토글 함수·구독 kind."""

    kind: str  # notification_subscription.kind (service.KIND_*)
    title: str  # "경험치 알림"
    set_channel: SetChannel  # 채널 토글 함수
    channel_on: str
    channel_off: str
    personal_on: str
    personal_off: str


async def handle_toggle(
    deps: Deps,
    interaction: discord.Interaction,
    spec: AlertSpec,
    *,
    enabled: bool,
    target: discord.app_commands.Choice[str] | None,
) -> None:
    """대상(채널/개인) 분기 토글 + 확인 임베드. 권한 체크 없음(결정 3)."""
    do_channel, do_personal = targets_for(target, enabling=enabled)

    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed(spec.title, _MSG_GUILD_ONLY), ephemeral=True
        )
        return

    lines: list[str] = []
    if do_channel:
        if interaction.channel_id is None:
            lines.append("채널: 이 채널을 알 수 없어 설정하지 못했어요.")
        else:
            await spec.set_channel(
                deps.session_factory,
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                enabled=enabled,
            )
            lines.append(spec.channel_on if enabled else spec.channel_off)
    if do_personal:
        if enabled:
            await service.subscribe_dm(
                deps.session_factory,
                interaction.guild_id,
                interaction.user.id,
                spec.kind,
            )
            lines.append(spec.personal_on)
        else:
            existed = await service.unsubscribe_dm(
                deps.session_factory,
                interaction.guild_id,
                interaction.user.id,
                spec.kind,
            )
            lines.append(spec.personal_off if existed else _MSG_PERSONAL_NONE)

    state = "켜짐 🔔" if enabled else "꺼짐 🔕"
    await interaction.response.send_message(
        embed=make_embed(f"{spec.title} {state}", "\n".join(lines)), ephemeral=True
    )
