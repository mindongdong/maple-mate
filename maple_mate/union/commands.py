"""`/유니온` 디스코드 어댑터 (얇은 전달 계층). 로직은 service + 공유 머신이 담당.

인자 없으면 서버 등록자 전원, 지정 시 그 대상(최대 5명). 부분 성공 허용·페이지네이션.
"""
from __future__ import annotations

import discord
from discord import app_commands

from ..bot import comparison, table_image
from ..bot.embeds import defer, make_embed
from ..dependencies import Deps
from ..registration import service as reg
from . import service
from .service import UnionInfo


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

    # 단일 대상 = 카드 + 유저 태그(표는 비교 때만 의미 있음).
    if len(outcomes) == 1:
        target = successes[0].target
        embed = make_embed("유니온", footer=footer)
        embed.add_field(
            name=target.nickname,
            value=f"{comparison.mention(target)}\n{_format_union(successes[0].data)}",
            inline=False,
        )
        await interaction.followup.send(embed=embed)
        return

    # 비교 = PNG 정렬표(픽셀 고정) + 태그 범례. 유니온 레벨 내림차순 + 순위.
    # 단일 수치 컬럼(유니온·아티팩트)은 최고 행을 금색 강조(챔피언 분포는 단일값 아님 → 제외).
    ranked = sorted(successes, key=lambda o: o.data.union_level or -1, reverse=True)
    best_union = comparison.highest_indices([o.data.union_level for o in ranked])
    best_artifact = comparison.highest_indices([o.data.artifact_level for o in ranked])
    headers = ["순위", "캐릭터", "유니온", "아티팩트", "챔피언"]
    rows = []
    for i, o in enumerate(ranked):
        union_text = str(o.data.union_level) if o.data.union_level is not None else "—"
        artifact_text = f"{o.data.artifact_level} LV" if o.data.artifact_level is not None else "—"
        rows.append(
            [
                str(i + 1),
                comparison.truncate_display(o.target.nickname, 14),
                table_image.Highlight(union_text) if i in best_union else union_text,
                table_image.Highlight(artifact_text) if i in best_artifact else artifact_text,
                comparison.truncate_display(
                    " ".join(f"{g}({c})" for g, c in o.data.champion_grades) or "없음", 28
                ),
            ]
        )
    embed, file = comparison.table_image_message(
        "유니온 비교",
        headers,
        rows,
        [o.target for o in ranked],
        aligns=["center", "left", "center", "center", "left"],
        footer=footer,
        outcomes=outcomes,
        filename="union.png",
    )
    await interaction.followup.send(embed=embed, file=file)


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
