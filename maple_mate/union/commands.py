"""`/유니온` 디스코드 어댑터 (얇은 전달 계층). 로직은 service + 공유 머신이 담당.

인자 없으면 등록자 중 본인 포함 랜덤 최대 10명(ADR-0008 부분개정), 지정 시 그 대상(유저 슬롯 + `닉네임` 합쳐 최대 5명, ADR-0021). 부분 성공 허용.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import discord
from discord import app_commands

from ..bot import comparison, cooldowns, table_image
from ..bot.embeds import defer, make_embed
from ..character.commands import send_with_tabs
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
    deps: Deps,
    interaction: discord.Interaction,
    members: list[discord.Member],
    *,
    nicknames: Sequence[str] = (),
) -> None:
    nicknames = list(nicknames)
    await defer(interaction)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("유니온", "서버(길드) 안에서만 쓸 수 있어요.")
        )
        return

    targets, missing = await comparison.resolve_mixed_targets(
        deps.session_factory,
        deps.nexon,
        interaction.guild_id,
        members,
        nicknames,
        command="유니온",
    )
    if not targets:
        if missing:
            await interaction.followup.send(
                embed=comparison.all_failed_embed("유니온 비교", missing)
            )
        else:
            await interaction.followup.send(
                embed=make_embed(
                    "유니온", "이 서버에 등록자가 없어요. `/캐릭터등록` 먼저 해주세요."
                )
            )
        return

    # 무인자 = 본인 포함 랜덤 K명 경계(ADR-0008 부분개정). 지정 시엔 파라미터 5개가 이미 상한.
    notes: list[str] = []  # 푸터 안내 줄(위→아래): 팬아웃 안내 → 본인 미포함
    if not members and not nicknames:
        targets, total, self_included = comparison.select_with_self(
            targets, interaction.user.id
        )
        notes.append(comparison.fanout_note(total))
        if not self_included:
            notes.append(
                "본인은 미등록이라 포함되지 않았어요. `/캐릭터등록` 부터 해주세요!"
            )

    message = await build_union_message(deps, targets, missing, notes=notes)
    await send_with_tabs(
        deps,
        interaction,
        message,
        targets=targets,
        missing=missing,
        notes=notes,
        current="union",
    )


async def build_union_message(
    deps: Deps,
    targets: list[reg.Target],
    missing: list[reg.TargetOutcome],
    *,
    notes: Sequence[str] = (),
) -> comparison.ComparisonMessage:
    """유니온 조회 + 렌더(단일 카드 / 비교표 / 전원 실패) — `/유니온`·탭 전환 공유(ADR-0022)."""
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
        return comparison.ComparisonMessage(
            comparison.all_failed_embed("유니온 비교", outcomes)
        )

    footer = comparison.footer_with_notes(successes[0].data.date, notes)

    # 단일 대상 = 카드 + 유저 태그(표는 비교 때만 의미 있음).
    if len(outcomes) == 1:
        target = successes[0].target
        embed = make_embed("유니온", footer=footer)
        embed.add_field(
            name=target.nickname,
            # 게스트(태그 없음)는 빈 첫 줄 없이 본문부터.
            value="\n".join(
                p
                for p in (comparison.mention(target), _format_union(successes[0].data))
                if p
            ),
            inline=False,
        )
        return comparison.ComparisonMessage(embed)

    # 비교 = PNG 정렬표(픽셀 고정) + 태그 범례. 유니온 레벨 내림차순 + 순위.
    # 단일 수치 컬럼(유니온·아티팩트)은 최고 행을 금색 강조(챔피언 분포는 단일값 아님 → 제외).
    ranked = sorted(successes, key=lambda o: o.data.union_level or -1, reverse=True)
    best_union = comparison.highest_indices([o.data.union_level for o in ranked])
    best_artifact = comparison.highest_indices([o.data.artifact_level for o in ranked])
    headers = ["순위", "캐릭터", "유니온", "아티팩트", "챔피언"]
    rows = []
    for i, o in enumerate(ranked):
        union_text = str(o.data.union_level) if o.data.union_level is not None else "—"
        artifact_text = (
            f"{o.data.artifact_level} LV" if o.data.artifact_level is not None else "—"
        )
        rows.append(
            [
                str(i + 1),
                comparison.truncate_display(o.target.nickname, 14),
                table_image.Highlight(union_text) if i in best_union else union_text,
                table_image.Highlight(artifact_text)
                if i in best_artifact
                else artifact_text,
                comparison.truncate_display(
                    " ".join(f"{g}({c})" for g, c in o.data.champion_grades) or "없음",
                    28,
                ),
            ]
        )
    # 표 PNG 렌더(CPU)는 워커 스레드로 — 이벤트루프 비차단(D6).
    embed, file = await asyncio.to_thread(
        comparison.table_image_message,
        "유니온 비교",
        headers,
        rows,
        [o.target for o in ranked],
        aligns=["center", "left", "center", "center", "left"],
        footer=footer,
        outcomes=outcomes,
        filename="union.png",
    )
    return comparison.ComparisonMessage(embed, file)


def setup(bot: discord.Client) -> None:
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="유니온",
        description="유니온 레벨·아티팩트·챔피언 등급분포를 비교합니다 (미지정 시 본인 포함 랜덤 최대 10명).",
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.rename(
        member1="대상1",
        member2="대상2",
        member3="대상3",
        member4="대상4",
        member5="대상5",
        nicknames="닉네임",
    )
    @app_commands.describe(
        member1="비교할 유저 (미지정 시 이 서버 등록자 중 본인 포함 랜덤 최대 10명)",
        member2="추가 비교 대상",
        member3="추가 비교 대상",
        member4="추가 비교 대상",
        member5="추가 비교 대상",
        nicknames=comparison.NICKNAMES_DESCRIBE,
    )
    @cooldowns.spec_cooldown()
    @comparison.target_limit_check()  # 쿨다운보다 먼저 실행 — 거부가 쿨다운을 소모하지 않음
    async def union_command(
        interaction: discord.Interaction,
        member1: discord.Member | None = None,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
        nicknames: str | None = None,
    ) -> None:
        members = [
            m for m in (member1, member2, member3, member4, member5) if m is not None
        ]
        await handle_union(
            deps, interaction, members, nicknames=comparison.parse_nicknames(nicknames)
        )
