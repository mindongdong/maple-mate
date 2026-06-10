"""`/스펙` · `/아이템` 디스코드 어댑터 (얇은 전달 계층). 로직은 service + 공유 머신.

- `/스펙`: 인자 필수(1~5명). 1명=상세, 2~5명=항목별 페이지 비교(전투력·어빌리티·심볼·HEXA코어·HEXA스탯).
- `/아이템`: build 5 에서 추가.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import discord
from discord import app_commands

from ..bot import comparison, cooldowns, item_card, table_image
from ..bot.embeds import append_source, defer, make_embed
from ..dependencies import Deps
from ..nexon.client import KST, NexonClient
from ..nexon.errors import NexonAPIError
from ..registration import service as reg
from . import item, service
from .equipment_slots import SLOT_CHOICES
from .item import ItemResult
from .service import SpecInfo, format_eok

log = logging.getLogger(__name__)

_SPEC_SECTIONS = ("전투력", "어빌리티", "장착 심볼", "HEXA 코어", "HEXA 스탯")


def _render_spec_section(section: str, info: SpecInfo) -> str:
    if section == "전투력":
        return f"Lv.**{info.level if info.level is not None else '—'}** {info.job or ''}\n전투력 **{format_eok(info.combat_power)}**"
    if section == "어빌리티":
        grade = info.ability_grade or "—"
        lines = "\n".join(f"· {value}" for value in info.abilities) or "—"
        return f"[{grade}]\n{lines}"
    if section == "장착 심볼":
        categories = (
            " · ".join(f"{name} {count}" for name, count in info.symbols.counts)
            or "없음"
        )
        return f"총 포스 **{info.symbols.total_force}**\n{categories}"
    if section == "HEXA 코어":
        if not info.hexa_cores:
            return "없음"
        return "\n".join(
            f"· {name} Lv.{level} ({core_type})"
            for name, level, core_type in info.hexa_cores
        )
    if section == "HEXA 스탯":
        return "\n".join(f"· {line}" for line in info.hexa_stats) or "없음"
    return "—"


def _single_detail_embed(target, info: SpecInfo, footer: str) -> discord.Embed:
    # 설명에 유저 태그(누구 캐릭인지). 단일이라 표 대신 항목별 상세 필드.
    embed = make_embed(
        f"{target.nickname} 스펙", description=comparison.mention(target), footer=footer
    )
    for section in _SPEC_SECTIONS:
        embed.add_field(
            name=section, value=_render_spec_section(section, info)[:1024], inline=False
        )
    return embed


async def handle_spec(
    deps: Deps, interaction: discord.Interaction, members: list[discord.Member]
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("스펙", "서버(길드) 안에서만 쓸 수 있어요.")
        )
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
        await interaction.followup.send(
            embed=comparison.all_failed_embed("스펙 비교", missing)
        )
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
        await interaction.followup.send(
            embed=comparison.all_failed_embed("스펙 비교", outcomes)
        )
        return

    footer = append_source(comparison.data_footer(successes[0].data.date))

    # 단일 대상(실패/미등록 없이 1명) = 상세 전체 1임베드 + 유저 태그.
    if len(outcomes) == 1:
        await interaction.followup.send(
            embed=_single_detail_embed(successes[0].target, successes[0].data, footer)
        )
        return

    # 비교 = 한 장 PNG 표. 캐릭터를 세로(행)로 쌓아 전투력 내림차순 순위가 위→아래로 보이게.
    # 컬럼: 순위·캐릭터·전투력·HEXA 코어(타입별 묶음)·HEXA 스탯(숫자). 어빌리티·심볼 제외.
    def _latest_power(outcome) -> int:
        try:
            return int(outcome.data.combat_power)
        except (TypeError, ValueError):
            return -1

    # 전투력 = 지난 7일 중 최고치(A안): 표시·정렬·금색강조 모두 이 값 기준. (ocid,date) 인메모리
    # 캐시(과거 스냅샷 불변). 활성 프리셋 단일값 한계를 시간으로 우회 — 그 주 메인 프리셋 켠 날을 잡음.
    today = datetime.now(KST).date()
    weekly: dict[str, int | None] = {}
    for o in successes:
        latest = _latest_power(o)
        weekly[o.target.ocid] = await service.fetch_weekly_max_power(
            deps.nexon,
            o.target.ocid,
            today,
            cache=deps.combat_power_cache,
            latest=latest if latest >= 0 else None,
        )

    def _power(outcome) -> int:
        value = weekly.get(outcome.target.ocid)
        return value if value is not None else -1

    ranked = sorted(successes, key=_power, reverse=True)
    # 단일 수치 컬럼(전투력)만 최고 행 금색 강조. HEXA 코어·스탯은 다중값이라 제외.
    best_power = comparison.highest_indices(
        [p if (p := _power(o)) >= 0 else None for o in ranked]
    )
    # 코어 타입별 고정 칸 수(직업 무관, handoff §5). 부족분은 NumGrid 가 0으로 채움.
    core_cols = (("스킬", 2), ("마스터리", 4), ("강화", 4), ("공용", 3))
    # 스탯 코어 1·2·3을 로마숫자로 라벨링해 컬럼별로 분리(각 메인/서브/서브 3칸).
    stat_cols = ("스탯 코어 I", "스탯 코어 II", "스탯 코어 III")
    headers = ["순위", "캐릭터", "전투력", *(name for name, _ in core_cols), *stat_cols]

    # 스탯 코어별로 메인(첫 칸) 값을 유저끼리 비교해 최고 행을 금색 강조(각 코어 독립).
    # 코어 미보유(idx 초과)·메인 0은 후보 제외(0이 최고로 칠해지는 노이즈 방지).
    def _stat_main(o, idx: int) -> int | None:
        triples = o.data.hexa_stat_triples
        return triples[idx][0] if idx < len(triples) and triples[idx][0] > 0 else None

    best_stat_main = [
        comparison.highest_indices([_stat_main(o, idx) for o in ranked])
        for idx in range(len(stat_cols))
    ]

    rows: list[list] = []
    for rank, o in enumerate(ranked, start=1):
        info = o.data
        by_type = dict(info.hexa_core_by_type)
        triples = info.hexa_stat_triples
        power_text = format_eok(weekly.get(o.target.ocid))
        rows.append(
            [
                str(rank),
                comparison.truncate_display(o.target.nickname, 20),
                table_image.Highlight(power_text)
                if (rank - 1) in best_power
                else power_text,
                # 코어 = 칸 그리드(세로줄·가운데정렬·빈칸 0). 스탯 = 3칸 + 첫 칸(메인) 볼드,
                # 코어별 메인 최고 행은 첫 칸 금색.
                *(
                    table_image.NumGrid(by_type.get(name, ()), slots)
                    for name, slots in core_cols
                ),
                *(
                    table_image.NumGrid(
                        triples[i] if i < len(triples) else (),
                        3,
                        bold_first=True,
                        highlight_first=(rank - 1) in best_stat_main[i],
                    )
                    for i in range(len(stat_cols))
                ),
            ]
        )
    # 표 PNG 렌더(CPU)는 워커 스레드로 — 이벤트루프 비차단(D6).
    embed, file = await asyncio.to_thread(
        comparison.table_image_message,
        "스펙 비교",
        headers,
        rows,
        [o.target for o in ranked],
        aligns=["center", "left", "left", *(["center"] * (len(headers) - 3))],
        footer=footer,
        outcomes=outcomes,
        filename="spec.png",
    )
    await interaction.followup.send(embed=embed, file=file)


def _card_potential(p: item.PotentialView | None) -> item_card.CardPotential | None:
    """잠재 뷰 → 카드 잠재(같은 옵션 합산). 없으면 None."""
    if p is None:
        return None
    return item_card.CardPotential(p.grade, item.combine_options(p.options))


def _to_item_card(
    label: str, result: ItemResult, icon_png: bytes | None
) -> item_card.ItemCard:
    """ItemResult(+아이콘 bytes) → 렌더용 ItemCard (순수). 미착용이면 found=False."""
    if not result.found or result.item is None:
        return item_card.ItemCard(label=label, found=False)
    view = result.item
    return item_card.ItemCard(
        label=label,
        found=True,
        item_name=view.item_name,
        starforce=view.starforce,
        icon_png=icon_png,
        potential=_card_potential(view.potential),
        additional=_card_potential(view.additional_potential),
        add_option=view.add_option,
        upgrade=view.upgrade,
        upgrade_stats=view.upgrade_stats,
    )


async def _fetch_icon(nexon: NexonClient, result: ItemResult) -> bytes | None:
    """장비 아이콘 다운로드 — 실패해도 카드는 렌더되도록 None 반환(경고 로그)."""
    if not result.found or result.item is None or not result.item.icon_url:
        return None
    try:
        return await nexon.fetch_image(result.item.icon_url)
    except NexonAPIError as exc:
        log.warning("아이템 아이콘 다운로드 실패(%s): %s", result.item.item_name, exc)
        return None


async def handle_item(
    deps: Deps,
    interaction: discord.Interaction,
    slot: str,
    members: list[discord.Member],
) -> None:
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("아이템", "서버(길드) 안에서만 쓸 수 있어요.")
        )
        return

    targets, missing = await comparison.resolve_targets(
        deps.session_factory, interaction.guild_id, members
    )
    if not targets:
        if missing:
            await interaction.followup.send(
                embed=comparison.all_failed_embed(f"아이템 — {slot}", missing)
            )
        else:
            await interaction.followup.send(
                embed=make_embed(
                    "아이템", "이 서버에 등록자가 없어요. `/등록` 먼저 해주세요."
                )
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
        await interaction.followup.send(
            embed=comparison.all_failed_embed(f"아이템 — {slot}", outcomes)
        )
        return

    footer = append_source(comparison.data_footer(successes[0].data.date))
    # 아이콘 동시 다운로드(캐시) → 게임 툴팁풍 카드, 여러 명은 한 PNG 세로 스택.
    icons = await asyncio.gather(*(_fetch_icon(deps.nexon, o.data) for o in successes))
    cards = [
        _to_item_card(
            f"{comparison.truncate_display(o.target.nickname, 20)} · {slot}",
            o.data,
            icon,
        )
        for o, icon in zip(successes, icons)
    ]
    # 카드 PNG 렌더(CPU)는 워커 스레드로 — 이벤트루프 비차단(D6).
    png = await asyncio.to_thread(item_card.render_item_cards, cards)
    embed, file = comparison.image_message(
        f"아이템 — {slot}",
        png,
        [o.target for o in successes],
        footer=footer,
        outcomes=outcomes,
        filename="item.png",
    )
    await interaction.followup.send(embed=embed, file=file)


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="스펙",
        description="전투력·어빌리티·심볼·HEXA를 비교합니다 (1~5명 지정 필수).",
    )
    @app_commands.rename(
        member1="유저1",
        member2="유저2",
        member3="유저3",
        member4="유저4",
        member5="유저5",
    )
    @app_commands.describe(
        member1="조회할 유저 (1명이면 단일 상세)",
        member2="비교 대상",
        member3="비교 대상",
        member4="비교 대상",
        member5="비교 대상",
    )
    @cooldowns.spec_cooldown()
    async def spec_command(
        interaction: discord.Interaction,
        member1: discord.Member,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
    ) -> None:
        members = [
            m for m in (member1, member2, member3, member4, member5) if m is not None
        ]
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
    @cooldowns.spec_cooldown()
    async def item_command(
        interaction: discord.Interaction,
        part: app_commands.Choice[str],
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
    ) -> None:
        members = [
            m for m in (member1, member2, member3, member4, member5) if m is not None
        ]
        await handle_item(deps, interaction, part.value, members)
