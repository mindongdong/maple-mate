"""`/경험치` · `/경험치알림` 디스코드 어댑터 (얇은 전달 계층, 작업지시서 빌드 단위 #6, ADR-0017).

- `/경험치`: defer → build_payload(현재 길드) → 7일 레벨 추이 그래프 공개 응답(2명 미만/데이터 없음 안내).
- `/경험치알림 켜기·끄기`: `대상`(채널/개인) 인자로 채널 발송(channel_settings.exp_alert)·본인 DM
  구독(notification_subscription)을 토글. 권한 불필요(공지·썬데이와 통일, notification.toggle 공유).
"""

from __future__ import annotations

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import defer, make_embed
from ..bot.modes import MODE_CHOICES, MODE_DESCRIBE, parse_mode
from ..dependencies import Deps
from ..notification import service as channel_service
from ..notification.target import TARGET_CHOICES, TARGET_DESCRIBE
from ..notification.toggle import AlertSpec, handle_toggle
from ..registration.realm import Realm, realm_title
from ..registration.service import get_targets
from .broadcast import build_payload, ensure_guild_data

_EXP_SPEC = AlertSpec(
    kind=channel_service.KIND_EXP,
    title="경험치 알림",
    set_channel=channel_service.set_exp_alert,
    channel_on="이 채널에 매일 10:00(KST) 경험치 리더보드를 보낼게요.",
    channel_off="이 채널의 경험치 리더보드 알림을 더 이상 보내지 않아요.",
    personal_on="매일 10:00(KST) 경험치 리더보드를 DM으로 받을게요.",
    personal_off="경험치 리더보드 DM 구독을 껐어요.",
)

_MSG_NOT_ENOUGH = "경험치 리더보드는 **2명 이상 등록**해야 추이가 떠요. 친구들도 `/캐릭터등록` 하면 같이 나와요."
_MSG_NOT_READY = (
    "아직 종합 랭킹 데이터를 못 받았어요(전일 데이터 준비 전이거나 랭킹 미등재)."
    " 잠시 후 다시 시도해 주세요."
)
_MSG_CHAL_NOT_ENOUGH = (
    "챌린저스 경험치 리더보드는 **챌린저스 캐릭터 2명 이상**이 등록해야 떠요."
    " 챌린저스 캐릭터를 `/캐릭터등록` 하면 같이 나와요."
)
_MSG_CHAL_NOT_READY = (
    "아직 챌린저스 랭킹을 집계하기 전이에요(새 서버라 누적 랭킹 생성 대기 중)."
    " 넥슨이 생성하면 자동으로 표시돼요."
)


async def handle_leaderboard(
    deps: Deps, interaction: discord.Interaction, realm: Realm = Realm.MAIN
) -> None:
    """`/경험치` 본체: defer → 온디맨드 갱신(그 realm D-1 재적재) → build_payload(realm) → 공개 발송.

    주기 잡과 독립으로 명령 시점에 D-1 을 새로 받아 가장 신선한 어제 기준을 보여준다. payload 가
    None 이면 그 realm 등록자 수를 확인해 <2명 vs 데이터 미준비(챌린저스는 랭킹 집계 전)를 구분해 안내한다.
    """
    await defer(interaction)
    title = realm_title("경험치 리더보드", realm)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed(title, "서버(길드) 안에서만 쓸 수 있어요."),
            ephemeral=True,
        )
        return

    # 명령 시점 온디맨드 갱신: 그 realm D-1 을 넥슨에서 새로 받고(주기 잡과 독립) 빈 과거일 백필.
    await ensure_guild_data(deps, interaction.guild_id, realm)

    payload = await build_payload(interaction.client, deps, interaction.guild_id, realm)
    if payload is None:
        # 그 realm 등록자가 2명 미만인지, 데이터가 아직 미준비인지 구분해 안내한다.
        targets = await get_targets(
            deps.session_factory, interaction.guild_id, realm=realm
        )
        if realm is Realm.CHALLENGERS:
            msg = _MSG_CHAL_NOT_ENOUGH if len(targets) < 2 else _MSG_CHAL_NOT_READY
        else:
            msg = _MSG_NOT_ENOUGH if len(targets) < 2 else _MSG_NOT_READY
        await interaction.followup.send(embed=make_embed(title, msg), ephemeral=True)
        return

    await interaction.followup.send(
        embed=payload.embed, files=payload.to_files()
    )  # 공개


def setup_leaderboard(bot: discord.Client) -> None:
    """봇 트리에 `/경험치`·`/경험치알림`(켜기·끄기) 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="경험치",
        description="등록 캐릭터들의 최근 7일 레벨 추이 그래프를 보여줍니다.",
    )
    @app_commands.rename(mode="모드")
    @app_commands.describe(mode=MODE_DESCRIBE)
    @app_commands.choices(mode=MODE_CHOICES)
    @cooldowns.spec_cooldown()  # 10초 — 첫 호출은 넥슨 온디맨드 백필 가능; 이후는 DB 조회만
    async def leaderboard_command(
        interaction: discord.Interaction,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_leaderboard(deps, interaction, parse_mode(mode))

    group = app_commands.Group(
        name="경험치알림",
        description="매일 경험치 리더보드를 채널 또는 본인 DM으로 받을지 켜거나 끕니다.",
    )

    @group.command(
        name="켜기", description="경험치 리더보드 알림을 켭니다 (권한 불필요)."
    )
    @app_commands.rename(target="대상")
    @app_commands.describe(target=f"{TARGET_DESCRIBE} · 미지정 시 채널")
    @app_commands.choices(target=TARGET_CHOICES)
    @cooldowns.settings_cooldown()
    async def exp_alert_on(
        interaction: discord.Interaction,
        target: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_toggle(deps, interaction, _EXP_SPEC, enabled=True, target=target)

    @group.command(
        name="끄기", description="경험치 리더보드 알림을 끕니다 (권한 불필요)."
    )
    @app_commands.rename(target="대상")
    @app_commands.describe(target=f"{TARGET_DESCRIBE} · 미지정 시 둘 다 해제")
    @app_commands.choices(target=TARGET_CHOICES)
    @cooldowns.settings_cooldown()
    async def exp_alert_off(
        interaction: discord.Interaction,
        target: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_toggle(deps, interaction, _EXP_SPEC, enabled=False, target=target)

    bot.tree.add_command(group)  # type: ignore[attr-defined]
