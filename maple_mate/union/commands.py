"""`/유니온` 디스코드 어댑터 (얇은 전달 계층). 로직은 service + 공유 머신이 담당.

인자 없으면 서버 등록자 전원, 지정 시 그 대상(최대 5명). 부분 성공 허용·페이지네이션.
"""
from __future__ import annotations

import discord
from discord import app_commands

from ..bot import comparison
from ..bot.embeds import defer, make_embed
from ..dependencies import Deps
from ..registration import service as reg
from . import service
from .service import UnionInfo

_PER_PAGE = 10


def _format_union(info: UnionInfo) -> str:
    level = info.union_level if info.union_level is not None else "—"
    grade = info.union_grade or "—"
    artifact = info.artifact_level if info.artifact_level is not None else "—"
    champions = " / ".join(f"{g} {c}" for g, c in info.champion_grades) or "없음"
    return f"유니온 Lv.**{level}** ({grade})\n아티팩트 Lv.**{artifact}**\n챔피언 {champions}"


async def handle_union(
    deps: Deps, interaction: discord.Interaction, members: list[discord.Member]
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("유니온", "서버(길드) 안에서만 쓸 수 있어요.")
        )
        return

    targets, missing = await comparison.resolve_targets(
        deps.session_factory, interaction.guild_id, members
    )
    if not targets:
        if missing:
            await interaction.followup.send(
                embed=comparison.all_failed_embed("유니온 비교", missing)
            )
        else:
            await interaction.followup.send(
                embed=make_embed("유니온", "이 서버에 등록자가 없어요. `/등록` 먼저 해주세요.")
            )
        return

    outcomes = await reg.fetch_each(
        targets=targets,
        nexon=deps.nexon,
        session_factory=deps.session_factory,
        command="유니온",
        fetch=lambda ocid: service.fetch_union(deps.nexon, ocid),
    )
    outcomes = outcomes + missing

    successes = [o for o in outcomes if o.ok]
    if not successes:
        await interaction.followup.send(embed=comparison.all_failed_embed("유니온 비교", outcomes))
        return

    footer = comparison.data_footer(successes[0].data.date)
    title = "유니온" if len(outcomes) == 1 else "유니온 비교"
    fields = [(o.target.nickname, _format_union(o.data)) for o in successes]
    pages = comparison.field_pages(title, fields, per_page=_PER_PAGE, footer=footer)
    comparison.attach_failures(pages, outcomes)
    await comparison.respond_with_pages(interaction, pages, author_id=interaction.user.id)


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="유니온",
        description="유니온 레벨·아티팩트·챔피언 등급분포를 비교합니다 (대상 미지정 시 서버 전체).",
    )
    @app_commands.rename(
        member1="대상1", member2="대상2", member3="대상3", member4="대상4", member5="대상5"
    )
    @app_commands.describe(
        member1="비교할 유저 (미지정 시 이 서버 등록자 전원)",
        member2="추가 비교 대상",
        member3="추가 비교 대상",
        member4="추가 비교 대상",
        member5="추가 비교 대상",
    )
    async def union_command(
        interaction: discord.Interaction,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
    ) -> None:
        members = [m for m in (member1, member2, member3, member4, member5) if m is not None]
        await handle_union(deps, interaction, members)
