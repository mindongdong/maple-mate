"""`/스펙` · `/아이템` 디스코드 어댑터 (얇은 전달 계층). 로직은 service + 공유 머신.

- `/스펙`: 인자 필수(1~5명). 1명=상세, 2~5명=항목별 페이지 비교(전투력·어빌리티·심볼·HEXA코어·HEXA스탯).
- `/아이템`: build 5 에서 추가.
"""
from __future__ import annotations

import discord
from discord import app_commands

from ..bot import comparison
from ..bot.embeds import defer, make_embed
from ..dependencies import Deps
from ..registration import service as reg
from . import item, service
from .equipment_slots import SLOT_CHOICES
from .item import ItemResult
from .service import SpecInfo, format_eok

_SPEC_SECTIONS = ("전투력", "어빌리티", "장착 심볼", "HEXA 코어", "HEXA 스탯")


def _render_spec_section(section: str, info: SpecInfo) -> str:
    if section == "전투력":
        return f"Lv.**{info.level if info.level is not None else '—'}** {info.job or ''}\n전투력 **{format_eok(info.combat_power)}**"
    if section == "어빌리티":
        grade = info.ability_grade or "—"
        lines = "\n".join(f"· {value}" for value in info.abilities) or "—"
        return f"[{grade}]\n{lines}"
    if section == "장착 심볼":
        categories = " · ".join(f"{name} {count}" for name, count in info.symbols.counts) or "없음"
        return f"총 포스 **{info.symbols.total_force}**\n{categories}"
    if section == "HEXA 코어":
        if not info.hexa_cores:
            return "없음"
        return "\n".join(f"· {name} Lv.{level} ({core_type})" for name, level, core_type in info.hexa_cores)
    if section == "HEXA 스탯":
        return "\n".join(f"· {line}" for line in info.hexa_stats) or "없음"
    return "—"


def _single_detail_embed(nickname: str, info: SpecInfo, footer: str) -> discord.Embed:
    embed = make_embed(f"{nickname} 스펙", footer=footer)
    for section in _SPEC_SECTIONS:
        embed.add_field(name=section, value=_render_spec_section(section, info)[:1024], inline=False)
    return embed


async def handle_spec(
    deps: Deps, interaction: discord.Interaction, members: list[discord.Member]
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(embed=make_embed("스펙", "서버(길드) 안에서만 쓸 수 있어요."))
        return
    if not members:  # 인자 필수(보통 Discord 가 강제하지만 방어적으로)
        await interaction.followup.send(
            embed=make_embed("스펙", "비교할 유저를 1~5명 지정해 주세요.")
        )
        return

    targets, missing = await comparison.resolve_targets(
        deps.session_factory, interaction.guild_id, members
    )
    if not targets:
        await interaction.followup.send(embed=comparison.all_failed_embed("스펙 비교", missing))
        return

    outcomes = await reg.fetch_each(
        targets=targets,
        nexon=deps.nexon,
        session_factory=deps.session_factory,
        command="스펙",
        fetch=lambda ocid: service.fetch_spec(deps.nexon, ocid),
    )
    outcomes = outcomes + missing

    successes = [o for o in outcomes if o.ok]
    if not successes:
        await interaction.followup.send(embed=comparison.all_failed_embed("스펙 비교", outcomes))
        return

    footer = comparison.data_footer(successes[0].data.date)

    # 단일 대상(실패/미등록 없이 1명) = 상세 전체 1임베드.
    if len(outcomes) == 1:
        nickname = successes[0].target.nickname
        await interaction.followup.send(embed=_single_detail_embed(nickname, successes[0].data, footer))
        return

    # 비교 = 항목별 페이지(같은 항목끼리 가로 비교). /스펙은 최대 5명이라 항목당 1페이지.
    pages: list[discord.Embed] = []
    for section in _SPEC_SECTIONS:
        fields = [(o.target.nickname, _render_spec_section(section, o.data)) for o in successes]
        pages.extend(comparison.field_pages(f"스펙 비교 — {section}", fields, per_page=5, footer=footer))
    comparison.attach_failures(pages, outcomes)
    await comparison.respond_with_pages(interaction, pages, author_id=interaction.user.id)


def _render_item(result: ItemResult) -> str:
    if not result.found or result.item is None:
        return "_미착용_"
    view = result.item
    lines = [f"**{view.item_name}**"]
    if view.starforce is not None:
        lines.append(f"⭐ {view.starforce}성")
    if view.potential is not None:
        options = " / ".join(view.potential.options) or "—"
        lines.append(f"잠재 [{view.potential.grade}] {options}")
    if view.additional_potential is not None:
        options = " / ".join(view.additional_potential.options) or "—"
        lines.append(f"에디 [{view.additional_potential.grade}] {options}")
    if view.add_option:
        lines.append(f"추옵 {view.add_option}")
    if view.upgrade:
        lines.append(f"작 {view.upgrade}")
    return "\n".join(lines)


async def handle_item(
    deps: Deps, interaction: discord.Interaction, slot: str, members: list[discord.Member]
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(embed=make_embed("아이템", "서버(길드) 안에서만 쓸 수 있어요."))
        return

    targets, missing = await comparison.resolve_targets(
        deps.session_factory, interaction.guild_id, members
    )
    if not targets:
        if missing:
            await interaction.followup.send(embed=comparison.all_failed_embed(f"아이템 — {slot}", missing))
        else:
            await interaction.followup.send(
                embed=make_embed("아이템", "이 서버에 등록자가 없어요. `/등록` 먼저 해주세요.")
            )
        return

    outcomes = await reg.fetch_each(
        targets=targets,
        nexon=deps.nexon,
        session_factory=deps.session_factory,
        command="아이템",
        fetch=lambda ocid: item.fetch_item(deps.nexon, ocid, slot),
    )
    outcomes = outcomes + missing

    successes = [o for o in outcomes if o.ok]
    if not successes:
        await interaction.followup.send(embed=comparison.all_failed_embed(f"아이템 — {slot}", outcomes))
        return

    footer = comparison.data_footer(successes[0].data.date)
    fields = [(o.target.nickname, _render_item(o.data)) for o in successes]
    pages = comparison.field_pages(f"아이템 — {slot}", fields, per_page=8, footer=footer)
    comparison.attach_failures(pages, outcomes)
    await comparison.respond_with_pages(interaction, pages, author_id=interaction.user.id)


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="스펙",
        description="전투력·어빌리티·심볼·HEXA를 비교합니다 (1~5명 지정 필수).",
    )
    @app_commands.rename(
        member1="유저1", member2="유저2", member3="유저3", member4="유저4", member5="유저5"
    )
    @app_commands.describe(
        member1="조회할 유저 (1명이면 단일 상세)",
        member2="비교 대상",
        member3="비교 대상",
        member4="비교 대상",
        member5="비교 대상",
    )
    async def spec_command(
        interaction: discord.Interaction,
        member1: discord.Member,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
    ) -> None:
        members = [m for m in (member1, member2, member3, member4, member5) if m is not None]
        await handle_spec(deps, interaction, members)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="아이템",
        description="부위별 스타포스·잠재·옵션을 비교합니다 (대상 미지정 시 서버 전체).",
    )
    @app_commands.rename(
        part="부위",
        member1="대상1",
        member2="대상2",
        member3="대상3",
        member4="대상4",
        member5="대상5",
    )
    @app_commands.describe(
        part="조회할 장비 부위",
        member1="비교 대상 (미지정 시 이 서버 등록자 전원)",
        member2="추가 비교 대상",
        member3="추가 비교 대상",
        member4="추가 비교 대상",
        member5="추가 비교 대상",
    )
    @app_commands.choices(
        part=[app_commands.Choice(name=slot, value=slot) for slot in SLOT_CHOICES]
    )
    async def item_command(
        interaction: discord.Interaction,
        part: app_commands.Choice[str],
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
    ) -> None:
        members = [m for m in (member1, member2, member3, member4, member5) if m is not None]
        await handle_item(deps, interaction, part.value, members)
