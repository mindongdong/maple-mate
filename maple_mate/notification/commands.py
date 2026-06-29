"""`/공지알림`·`/썬데이알림` 디스코드 어댑터 (얇은 전달 계층, ADR-0017).

두 알림을 `켜기`/`끄기` 서브커맨드 그룹으로 통일하고 **권한 없이** 토글한다. 각 서브커맨드는
`대상`(채널/개인) 인자를 받아 채널 발송(channel_settings)·본인 DM 구독(notification_subscription)을
고른다 — 켜기 기본=채널, 끄기 기본=둘 다. 토글 본체는 notification.toggle.handle_toggle 공유.
"""

from __future__ import annotations

import discord
from discord import app_commands

from ..bot import cooldowns
from ..dependencies import Deps
from . import notice_service, service
from .target import TARGET_CHOICES, TARGET_DESCRIBE
from .toggle import AlertSpec, handle_toggle

_NOTICE_SPEC = AlertSpec(
    kind=service.KIND_NOTICE,
    title="공지 알림",
    set_channel=notice_service.set_notice_alert,
    channel_on="이 채널에 메이플 공지사항·업데이트 소식을 보내드릴게요.",
    channel_off="이 채널의 공지 알림을 더 이상 보내지 않아요.",
    personal_on="메이플 공지사항·업데이트 소식을 DM으로 받을게요.",
    personal_off="공지 DM 구독을 껐어요.",
)

_SUNDAY_SPEC = AlertSpec(
    kind=service.KIND_SUNDAY,
    title="썬데이 알림",
    set_channel=service.set_sunday_alert,
    channel_on="이 채널에 금요일 10:10(KST) 썬데이 메이플 알림을 보낼게요.",
    channel_off="이 채널의 썬데이 알림을 더 이상 보내지 않아요.",
    personal_on="금요일 10:10(KST) 썬데이 메이플 알림을 DM으로 받을게요.",
    personal_off="썬데이 DM 구독을 껐어요.",
)


def _alert_group(
    spec: AlertSpec, deps: Deps, name: str, what: str
) -> app_commands.Group:
    """`켜기`/`끄기`(각 `대상` 인자) 서브커맨드를 가진 알림 그룹을 만든다(공지·썬데이 공유)."""
    group = app_commands.Group(
        name=name, description=f"{what}을 채널 또는 본인 DM으로 받을지 켜거나 끕니다."
    )

    @group.command(name="켜기", description=f"{what}을 켭니다 (권한 불필요).")
    @app_commands.rename(target="대상")
    @app_commands.describe(target=f"{TARGET_DESCRIBE} · 미지정 시 채널")
    @app_commands.choices(target=TARGET_CHOICES)
    @cooldowns.settings_cooldown()
    async def on(
        interaction: discord.Interaction,
        target: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_toggle(deps, interaction, spec, enabled=True, target=target)

    @group.command(name="끄기", description=f"{what}을 끕니다 (권한 불필요).")
    @app_commands.rename(target="대상")
    @app_commands.describe(target=f"{TARGET_DESCRIBE} · 미지정 시 둘 다 해제")
    @app_commands.choices(target=TARGET_CHOICES)
    @cooldowns.settings_cooldown()
    async def off(
        interaction: discord.Interaction,
        target: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_toggle(deps, interaction, spec, enabled=False, target=target)

    return group


def setup(bot: discord.Client) -> None:
    """봇 트리에 `/공지알림`·`/썬데이알림`(켜기·끄기) 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]
    bot.tree.add_command(  # type: ignore[attr-defined]
        _alert_group(_NOTICE_SPEC, deps, "공지알림", "메이플 공지·업데이트 알림")
    )
    bot.tree.add_command(  # type: ignore[attr-defined]
        _alert_group(_SUNDAY_SPEC, deps, "썬데이알림", "썬데이 메이플 알림")
    )
