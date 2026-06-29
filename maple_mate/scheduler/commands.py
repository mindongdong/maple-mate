"""스케줄러 알리미 Discord 어댑터 (얇은 전달 계층, ADR-0017).

- `/스케줄러 [카테고리]`: 본인 등록 캐릭터 전체 숙제(캐릭터당 ephemeral 메시지 1개, 온디맨드).
- `/스케줄러알림 켜기 [시각] [카테고리]` / `끄기`: per-user DM 구독 토글(결정 2·4).
  켜기는 키·캐릭터 없으면 구독 거부(fail fast, 결정 7a). 발송은 매시 정각 cron(broadcast).
  realm 모드 인자 없음 — 한 구독이 등록 캐릭터 전부(본+챌)를 받는다(ADR-0017).
"""

from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import defer, make_embed
from ..dependencies import Deps
from ..nexon.client import KST
from . import service
from .broadcast import build_embed, build_homeworks
from .category_filter import (
    CATEGORY_ON_OFF,
    is_all_excluded,
    merge_excluded,
    parse_ondemand,
    summarize,
)
from .service import DEFAULT_HOUR

_TITLE_HOMEWORK = "스케줄러 숙제"
_TITLE_REMINDER = "스케줄러 알림"

_MSG_GUILD_ONLY = "서버(길드) 안에서만 쓸 수 있어요."
_MSG_NO_HOMEWORK = (
    "인게임 메이플 스케줄러에 등록된 숙제가 없어요."
    " 게임에서 콘텐츠를 스케줄러에 등록하면 여기 떠요."
)
_MSG_BAD_HOUR = "시각은 **0~23** 사이 정수로 입력해 주세요."
# 4묶음 전부 끄기 가드(ADR-0014 결정 5): 온디맨드는 빌드 전 안내, 알림은 저장 없이 거부.
_MSG_ALL_OFF = "표시할 카테고리를 최소 하나는 켜주세요. (일일·주간·보스·길드)"
_MSG_ALL_OFF_REMINDER = (
    "표시할 카테고리를 최소 하나는 남겨야 알림을 켤 수 있어요. (저장하지 않았어요)"
)

# 카테고리 파라미터 rename/choices 공유(`/스케줄러`·`/스케줄러알림 켜기`). 키 = 파라미터명.
_CATEGORY_RENAME = {"daily": "일일", "weekly": "주간", "boss": "보스", "guild": "길드"}
_CATEGORY_CHOICES = {name: CATEGORY_ON_OFF for name in _CATEGORY_RENAME}
# describe 는 표면별로 의미가 다르다 — 온디맨드=기본 켜기, 알림=미지정 시 기존 유지.
_ONDEMAND_DESCRIBE = {
    "daily": "일일 숙제(일일 퀘스트·콘텐츠) 표시 — 기본 켜기",
    "weekly": "주간 숙제(주간 퀘스트·콘텐츠) 표시 — 기본 켜기",
    "boss": "보스 숙제(일간·주간·월간) 표시 — 기본 켜기",
    "guild": "길드 콘텐츠 표시 — 기본 켜기",
}
_REMINDER_DESCRIBE = {
    "daily": "일일 숙제 표시 — 미지정 시 기존 설정 유지",
    "weekly": "주간 숙제 표시 — 미지정 시 기존 설정 유지",
    "boss": "보스 숙제 표시 — 미지정 시 기존 설정 유지",
    "guild": "길드 콘텐츠 표시 — 미지정 시 기존 설정 유지",
}


async def handle_scheduler(
    deps: Deps,
    interaction: discord.Interaction,
    excluded: frozenset[str] = frozenset(),
) -> None:
    """`/스케줄러` 본체: defer → (all-off 가드) → build_homeworks → 캐릭터당 임베드 1개씩 followup.

    등록 캐릭터 4개면 ephemeral 응답 4개(캐릭터당 메시지 1개). excluded(ADR-0014) 묶음은 가리고
    필터 후 빈 캐릭터는 생략한다. 무상태 — excluded 는 이번 호출에만 적용(저장 안 함).
    """
    await defer(interaction, ephemeral=True)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed(_TITLE_HOMEWORK, _MSG_GUILD_ONLY), ephemeral=True
        )
        return
    if is_all_excluded(excluded):  # 4묶음 전부 끄기 → 빌드(페치) 전 안내
        await interaction.followup.send(
            embed=make_embed(_TITLE_HOMEWORK, _MSG_ALL_OFF), ephemeral=True
        )
        return

    homeworks, error = await build_homeworks(
        deps, interaction.guild_id, interaction.user.id
    )
    if error is not None:  # 미등록·키없음·캐릭터 0 → 가드 메시지
        await interaction.followup.send(
            embed=make_embed(_TITLE_HOMEWORK, error), ephemeral=True
        )
        return

    non_empty = [hw for hw in homeworks if not service.is_empty_filtered(hw, excluded)]
    if not non_empty:  # 전 캐릭터 (필터 후) 빈 숙제(또는 전부 4xx 스킵)
        await interaction.followup.send(
            embed=make_embed(_TITLE_HOMEWORK, _MSG_NO_HOMEWORK), ephemeral=True
        )
        return

    now = datetime.now(KST)
    for homework in non_empty:  # 캐릭터당 메시지 1개(온디맨드 ephemeral)
        await interaction.followup.send(
            embed=build_embed(homework, now, excluded), ephemeral=True
        )


async def handle_reminder_on(
    deps: Deps,
    interaction: discord.Interaction,
    hour: int,
    daily: app_commands.Choice[str] | None = None,
    weekly: app_commands.Choice[str] | None = None,
    boss: app_commands.Choice[str] | None = None,
    guild: app_commands.Choice[str] | None = None,
) -> None:
    """`/스케줄러알림 켜기` 본체: 시각 검증 → fail-fast 가드 → 제외집합 tri-state 병합 → upsert.

    카테고리 파라미터는 미지정=기존 유지(병합), 켜기/끄기=델타(ADR-0014 결정 2). 시각만 바꿔도
    꺼둔 묶음이 유지된다. 병합 결과가 4묶음 전부 끄기면 저장하지 않고 거부한다(결정 5).
    """
    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed(_TITLE_REMINDER, _MSG_GUILD_ONLY), ephemeral=True
        )
        return
    if not 0 <= hour <= 23:
        await interaction.response.send_message(
            embed=make_embed(_TITLE_REMINDER, _MSG_BAD_HOUR), ephemeral=True
        )
        return

    # fail fast: 키·캐릭터가 없으면 구독 자체를 거부한다(결정 7a — 죽은 구독 예방).
    _key, _chars, error = await service.resolve_self_characters(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    if error is not None:
        await interaction.response.send_message(
            embed=make_embed(_TITLE_REMINDER, error), ephemeral=True
        )
        return

    # 기존 제외집합 로드 → tri-state 병합 → all-off 거부(저장 안 함) → upsert.
    existing = await service.get_subscription(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    base = existing.excluded if existing is not None else frozenset()
    excluded = merge_excluded(base, daily=daily, weekly=weekly, boss=boss, guild=guild)
    if is_all_excluded(excluded):
        await interaction.response.send_message(
            embed=make_embed(_TITLE_REMINDER, _MSG_ALL_OFF_REMINDER), ephemeral=True
        )
        return

    await service.set_subscription(
        deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        hour=hour,
        excluded=excluded,
    )
    await interaction.response.send_message(
        embed=make_embed(
            "스케줄러 알림 켜짐 🔔",
            f"매일 **{hour:02d}:00**(KST)에 등록 캐릭터별 스케줄러 숙제를 DM으로 보낼게요."
            f"\n{summarize(excluded)}",
        ),
        ephemeral=True,
    )


async def handle_reminder_off(deps: Deps, interaction: discord.Interaction) -> None:
    """`/스케줄러알림 끄기` 본체: 구독 delete. 켜진 적 없으면 안내 분기."""
    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed(_TITLE_REMINDER, _MSG_GUILD_ONLY), ephemeral=True
        )
        return

    existed = await service.clear_subscription(
        deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
    )
    if existed:
        await interaction.response.send_message(
            embed=make_embed(
                "스케줄러 알림 꺼짐 🔕",
                "스케줄러 숙제 DM 알림을 껐어요.",
            ),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=make_embed(_TITLE_REMINDER, "켜져 있던 스케줄러 알림이 없어요."),
            ephemeral=True,
        )


# ── 트리 등록 ───────────────────────────────────────────────────────────────


def setup(bot: discord.Client) -> None:
    """봇 트리에 `/스케줄러`·`/스케줄러알림`(켜기·끄기) 등록. bot.deps(Deps) 사용."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="스케줄러",
        description="본인 등록 캐릭터 전체의 인게임 스케줄러 숙제 현황을 보여줍니다 (개인 키 필요).",
    )
    @app_commands.rename(**_CATEGORY_RENAME)
    @app_commands.describe(**_ONDEMAND_DESCRIBE)
    @app_commands.choices(**_CATEGORY_CHOICES)
    @cooldowns.spec_cooldown()  # 개인 키 1콜 — 스펙류와 동일 10초
    async def scheduler_command(
        interaction: discord.Interaction,
        daily: app_commands.Choice[str] | None = None,
        weekly: app_commands.Choice[str] | None = None,
        boss: app_commands.Choice[str] | None = None,
        guild: app_commands.Choice[str] | None = None,
    ) -> None:
        excluded = parse_ondemand(daily, weekly, boss, guild)
        await handle_scheduler(deps, interaction, excluded)

    group = app_commands.Group(
        name="스케줄러알림",
        description="매일 정해진 시각에 스케줄러 숙제를 DM으로 받는 구독을 켜거나 끕니다.",
    )

    @group.command(
        name="켜기",
        description="스케줄러 숙제 DM 구독을 켭니다 (개인 키 필요).",
    )
    @app_commands.rename(hour="시각", **_CATEGORY_RENAME)
    @app_commands.describe(
        hour=f"받을 시각 (KST 0~23시, 기본 {DEFAULT_HOUR}시)",
        **_REMINDER_DESCRIBE,
    )
    @app_commands.choices(**_CATEGORY_CHOICES)
    @cooldowns.settings_cooldown()
    async def reminder_on(
        interaction: discord.Interaction,
        hour: app_commands.Range[int, 0, 23] = DEFAULT_HOUR,
        daily: app_commands.Choice[str] | None = None,
        weekly: app_commands.Choice[str] | None = None,
        boss: app_commands.Choice[str] | None = None,
        guild: app_commands.Choice[str] | None = None,
    ) -> None:
        await handle_reminder_on(
            deps,
            interaction,
            hour,
            daily=daily,
            weekly=weekly,
            boss=boss,
            guild=guild,
        )

    @group.command(name="끄기", description="스케줄러 숙제 DM 구독을 끕니다.")
    @cooldowns.settings_cooldown()
    async def reminder_off(interaction: discord.Interaction) -> None:
        await handle_reminder_off(deps, interaction)

    bot.tree.add_command(group)  # type: ignore[attr-defined]
