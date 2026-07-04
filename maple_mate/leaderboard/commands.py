"""`/경험치` · `/경험치알림` 디스코드 어댑터 (얇은 전달 계층, 작업지시서 빌드 단위 #6, ADR-0017).

- `/경험치`: defer → build_payload(현재 길드) → 7일 레벨 추이 그래프 공개 응답(미등록/데이터 없음 안내).
- `/경험치알림 켜기·끄기`: `대상`(채널/개인) 인자로 채널 발송(channel_settings.exp_alert)·본인 DM
  구독(notification_subscription)을 토글. 권한 불필요(공지·썬데이와 통일, notification.toggle 공유).
"""

from __future__ import annotations

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import defer, make_embed
from ..bot.modes import MODE_CHOICES, MODE_DESCRIBE, parse_mode
from ..bot.scope import GUILD_CONTEXTS, GUILD_INSTALLS
from ..dependencies import Deps
from ..notification import service as channel_service
from ..notification.target import TARGET_CHOICES, TARGET_DESCRIBE
from ..notification.toggle import AlertSpec, handle_toggle
from ..registration.realm import Realm, realm_title
from ..registration.service import get_targets
from .broadcast import build_payload, build_specified_payload, ensure_guild_data

_EXP_SPEC = AlertSpec(
    kind=channel_service.KIND_EXP,
    title="경험치 알림",
    set_channel=channel_service.set_exp_alert,
    channel_on="이 채널에 매일 10:00(KST) 경험치 리더보드를 보낼게요.",
    channel_off="이 채널의 경험치 리더보드 알림을 더 이상 보내지 않아요.",
    personal_on="매일 10:00(KST) 경험치 리더보드를 DM으로 받을게요.",
    personal_off="경험치 리더보드 DM 구독을 껐어요.",
)

_MSG_NO_TARGETS = (
    "경험치 리더보드는 **캐릭터를 등록**해야 떠요."
    " `/캐릭터등록` 하면 나와요 — 친구들도 등록하면 같이 순위가 떠요."
)
_MSG_NOT_READY = (
    "아직 표시할 경험치 데이터가 없어요(넥슨 전일 데이터 준비 전)."
    " 잠시 후 다시 시도해 주세요."
)
_MSG_CHAL_NO_TARGETS = (
    "챌린저스 경험치 리더보드는 **챌린저스 캐릭터를 등록**해야 떠요."
    " 챌린저스 캐릭터를 `/캐릭터등록` 하면 나와요."
)
_MSG_CHAL_NOT_READY = (
    "아직 표시할 챌린저스 경험치 데이터가 없어요(넥슨 전일 데이터 준비 전)."
    " 잠시 후 다시 시도해 주세요."
)
_MSG_TARGETS_NONE = (
    "지정한 유저는 모두 미등록이거나 표시할 데이터가 없어요."
    " `/캐릭터등록` 이 필요할 수 있어요."
)


async def handle_leaderboard(
    deps: Deps,
    interaction: discord.Interaction,
    members: list[discord.Member] | None = None,
    realm: Realm = Realm.MAIN,
) -> None:
    """`/경험치` 본체: defer → 온디맨드 갱신(그 realm D-1 재적재) → payload → 공개 발송.

    주기 잡과 독립으로 명령 시점에 빈 과거일을 백필해 가장 신선한 기준을 보여준다. 무인자면
    서버 리더보드(레벨 Top-10 기조 유지), 대상 지정 시엔 그 유저들의 대표 캐릭터만 비교한다.
    payload 가 None 이면 등록자·지정 유무를 확인해 미등록 vs 데이터 미준비를 구분해 안내한다.
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

    if members:  # 대상 지정 = 그 유저들의 대표 캐릭터만(Top-10 상한 무의미, ≤5명).
        payload = await build_specified_payload(
            deps, interaction.guild_id, [m.id for m in members], realm
        )
        if payload is None:
            await interaction.followup.send(
                embed=make_embed(title, _MSG_TARGETS_NONE), ephemeral=True
            )
            return
        await interaction.followup.send(embed=payload.embed, files=payload.to_files())
        return

    payload = await build_payload(interaction.client, deps, interaction.guild_id, realm)
    if payload is None:
        # 그 realm 에 등록자가 없는지, 데이터가 아직 미준비인지 구분해 안내한다.
        targets = await get_targets(
            deps.session_factory, interaction.guild_id, realm=realm
        )
        if realm is Realm.CHALLENGERS:
            msg = _MSG_CHAL_NO_TARGETS if not targets else _MSG_CHAL_NOT_READY
        else:
            msg = _MSG_NO_TARGETS if not targets else _MSG_NOT_READY
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
        description="등록 캐릭터들의 최근 7일 레벨 추이 그래프를 보여줍니다 (대상 지정 시 최대 5명만 비교).",
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.rename(
        member1="유저1",
        member2="유저2",
        member3="유저3",
        member4="유저4",
        member5="유저5",
        mode="모드",
    )
    @app_commands.describe(
        member1="비교할 유저 (미지정 시 서버 레벨 Top 10 리더보드)",
        member2="추가 비교 대상",
        member3="추가 비교 대상",
        member4="추가 비교 대상",
        member5="추가 비교 대상",
        mode=MODE_DESCRIBE,
    )
    @app_commands.choices(mode=MODE_CHOICES)
    @cooldowns.spec_cooldown()  # 10초 — 첫 호출은 넥슨 온디맨드 백필 가능; 이후는 DB 조회만
    async def leaderboard_command(
        interaction: discord.Interaction,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        members = [
            m for m in (member1, member2, member3, member4, member5) if m is not None
        ]
        await handle_leaderboard(deps, interaction, members, parse_mode(mode))

    # 미개방(ADR-0019 결정 3 — 리더보드는 서버 개념 전제): 알림도 서버 리더보드 산출물이라
    # 함께 길드 전용으로 명시(기본값 드리프트 방지).
    group = app_commands.Group(
        name="경험치알림",
        description="매일 경험치 리더보드를 채널 또는 본인 DM으로 받을지 켜거나 끕니다.",
        allowed_installs=GUILD_INSTALLS,
        allowed_contexts=GUILD_CONTEXTS,
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
