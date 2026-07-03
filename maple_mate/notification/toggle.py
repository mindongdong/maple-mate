"""정기 알림 켜기/끄기 공통 처리 — 대상(채널/개인) 분기 (ADR-0017).

경험치·공지·썬데이가 공유하는 토글 본체. 대상에 따라 채널 토글(channel_settings)·개인 DM
구독(notification_subscription)을 한쪽 또는 둘 다 적용하고 확인 임베드를 낸다. **권한 체크
없음**(ADR-0017 결정 3) — 누구나 셀프 토글.

DM 워크스페이스(ADR-0019): 공용 채널 개념이 없어 채널 대상 명시는 거부하고, 대상 미지정은
개인 구독으로 라우팅한다(guild 0 채널행 생성 금지 — 크론이 DM 채널을 공용 채널로 오발송 방지).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import discord

from ..bot.embeds import make_embed
from ..bot.scope import DM_WORKSPACE_ID, MSG_UNAVAILABLE, resolve_scope
from ..dependencies import Deps
from . import service
from .target import targets_for

# 채널 토글 함수 시그니처(set_exp_alert / set_notice_alert / set_sunday_alert 공통).
SetChannel = Callable[..., Awaitable[None]]

_MSG_PERSONAL_NONE = "개인 DM 구독은 켜져 있지 않았어요."
_MSG_DM_PERSONAL_ONLY = "DM에서는 개인 알림만 설정할 수 있어요. (대상: 개인)"


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

    scope = resolve_scope(interaction)
    if scope is None:
        await interaction.response.send_message(
            embed=make_embed(spec.title, MSG_UNAVAILABLE), ephemeral=True
        )
        return
    if scope == DM_WORKSPACE_ID and do_channel:
        if target is not None:  # 대상=채널 명시 → 거부(ADR-0019 결정 3)
            await interaction.response.send_message(
                embed=make_embed(spec.title, _MSG_DM_PERSONAL_ONLY), ephemeral=True
            )
            return
        do_channel, do_personal = False, True  # 미지정 기본값은 DM 에선 개인

    lines: list[str] = []
    if do_channel:
        if interaction.channel_id is None:
            lines.append("채널: 이 채널을 알 수 없어 설정하지 못했어요.")
        else:
            await spec.set_channel(
                deps.session_factory,
                guild_id=scope,
                channel_id=interaction.channel_id,
                enabled=enabled,
            )
            lines.append(spec.channel_on if enabled else spec.channel_off)
    if do_personal:
        if enabled:
            await service.subscribe_dm(
                deps.session_factory,
                scope,
                interaction.user.id,
                spec.kind,
            )
            lines.append(spec.personal_on)
        else:
            existed = await service.unsubscribe_dm(
                deps.session_factory,
                scope,
                interaction.user.id,
                spec.kind,
            )
            lines.append(spec.personal_off if existed else _MSG_PERSONAL_NONE)

    state = "켜짐 🔔" if enabled else "꺼짐 🔕"
    await interaction.response.send_message(
        embed=make_embed(f"{spec.title} {state}", "\n".join(lines)), ephemeral=True
    )
