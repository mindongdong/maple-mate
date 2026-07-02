"""`/내캐릭터` 디스코드 어댑터 — 본인 캐릭터끼리 비교 (솔로 모드, ADR-0018).

같은 서버에 비교할 친구가 없는 유저도 쓸 수 있게, 유저 간 비교(`/스펙`·`/아이템`)의
fetch·렌더 경로를 그대로 재사용하되 대상만 "내 등록 캐릭터들"(캐릭터당 Target 1개)로 바꾼다.
기존 명령은 한 줄도 바꾸지 않는다(회귀 0). realm 필터 없음 — 본인 캐릭끼리라 공정성 전제가
없어 본서버·챌린저스 혼합(결정 7), 챌린저스 캐릭터만 라벨에 월드 병기.

서브커맨드: `스펙`(캐릭터1~5 선택) · `아이템`(부위 필수 + 캐릭터1~5 선택) · `경험치`(무인자 =
등록 캐릭터 전체 — 상한 10 이 Top10 파이프라인과 정합이라 절단 없음, 결정 4). 출력은 채널
공개(기존 비교류와 동일).
"""

from __future__ import annotations

import discord
from discord import app_commands

from ..bot import comparison, cooldowns
from ..bot.embeds import append_source, defer, make_embed
from ..character import commands as character
from ..character.equipment_slots import SLOT_CHOICES
from ..dependencies import Deps
from ..leaderboard import broadcast as leaderboard
from ..leaderboard import service as exp_service
from ..registration import service as reg
from ..registration.commands import character_choices
from ..registration.realm import is_challengers
from ..registration.service import Target

_DM_ONLY = "서버(길드) 안에서만 쓸 수 있어요."
_NO_CHARACTERS = "등록된 캐릭터가 없어요. `/캐릭터등록`으로 추가해 주세요."
_EXP_NOT_READY = (
    "아직 종합 랭킹 데이터를 못 받았어요(전일 데이터 준비 전이거나 랭킹 미등재)."
    " 잠시 후 다시 시도해 주세요."
)

# 스펙·아이템 렌더 폭 + 팬아웃 비용 상한(기존 /스펙 5명 상한과 동일 근거).
MAX_COMPARE = 5


def char_label(target: Target) -> str:
    """표·카드 라벨 = 캐릭 닉(폭 20 절단). 챌린저스 캐릭터만 월드 병기(§3-2).

    전부 본인 캐릭이라 유저 멘션·표시명은 불필요 — 닉이 그대로 식별자.
    """
    nick = comparison.truncate_display(target.nickname, 20)
    return f"{nick} ({target.world})" if is_challengers(target.world) else nick


def _owner_line(target: Target) -> str:
    """임베드 설명 = 소유자 1명 태그. 전 행이 같은 유저라 닉별 범례 대신 한 줄로 대체."""
    return f"👤 {comparison.mention(target)}"


def _truncation_note(total: int) -> str:
    return (
        f"등록 캐릭터 {total}개 중 레벨 상위 {MAX_COMPARE}개만 표시했어요"
        " — 나머지는 캐릭터 파라미터로 지정해 주세요."
    )


async def _resolve_my_targets(
    deps: Deps, interaction: discord.Interaction, ocids: list[str]
) -> tuple[list[Target], str | None] | None:
    """내 캐릭터 Target 해석 + 상한 절단. None 이면 이미 에러 응답 완료.

    0캐릭·DM 에러는 본인에게만(ephemeral) — 공개 defer 뒤에는 ephemeral 전환이
    안 되므로 defer 전에 판정한다(단일 유저 SELECT 1회라 3초 창 안에 충분).
    """
    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed("내 캐릭터", _DM_ONLY), ephemeral=True
        )
        return None
    targets = await reg.get_my_character_targets(
        deps.session_factory,
        interaction.guild_id,
        interaction.user.id,
        ocids or None,
    )
    if not targets:
        await interaction.response.send_message(
            embed=make_embed("내 캐릭터", _NO_CHARACTERS), ephemeral=True
        )
        return None
    note = None
    if len(targets) > MAX_COMPARE:
        note = _truncation_note(len(targets))
        targets = targets[:MAX_COMPARE]
    return targets, note


def _footer_with_note(footer: str, note: str | None) -> str:
    return f"{note}\n{footer}" if note else footer


async def handle_my_spec(
    deps: Deps, interaction: discord.Interaction, ocids: list[str]
) -> None:
    resolved = await _resolve_my_targets(deps, interaction, ocids)
    if resolved is None:
        return
    targets, note = resolved
    await defer(interaction)

    outcomes = await character.fetch_spec_outcomes(
        deps, targets, command="내캐릭터 스펙"
    )
    successes = [o for o in outcomes if o.ok]
    if not successes:
        await interaction.followup.send(
            embed=comparison.all_failed_embed("내 캐릭터 스펙", outcomes)
        )
        return

    footer = _footer_with_note(
        append_source(comparison.data_footer(successes[0].data.date)), note
    )
    # 1캐릭 = 기존 단일 상세 임베드 경로(graceful — 에러 아님).
    if len(outcomes) == 1:
        await interaction.followup.send(
            embed=character.single_detail_embed(
                successes[0].target, successes[0].data, footer
            )
        )
        return

    embed, file = await character.build_spec_comparison(
        deps,
        successes,
        outcomes,
        title="내 캐릭터 스펙 비교",
        footer=footer,
        label=char_label,
    )
    embed.description = _owner_line(targets[0])
    await interaction.followup.send(embed=embed, file=file)


async def handle_my_item(
    deps: Deps, interaction: discord.Interaction, slot: str, ocids: list[str]
) -> None:
    resolved = await _resolve_my_targets(deps, interaction, ocids)
    if resolved is None:
        return
    targets, note = resolved
    await defer(interaction)

    title = f"내 캐릭터 아이템 — {slot}"
    outcomes = await character.fetch_item_outcomes(
        deps, targets, slot, command="내캐릭터 아이템"
    )
    successes = [o for o in outcomes if o.ok]
    if not successes:
        await interaction.followup.send(
            embed=comparison.all_failed_embed(title, outcomes)
        )
        return

    footer = _footer_with_note(
        append_source(comparison.data_footer(successes[0].data.date)), note
    )
    embed, file = await character.build_item_cards(
        deps, successes, outcomes, slot, title=title, footer=footer, label=char_label
    )
    embed.description = _owner_line(targets[0])
    await interaction.followup.send(embed=embed, file=file)


async def handle_my_exp(deps: Deps, interaction: discord.Interaction) -> None:
    """`/내캐릭터 경험치`: defer 전 0캐릭/DM 판정 → 멱등 백필 → 캐릭별 Top10 순위판+7일 그래프.

    `_resolve_my_targets` 를 쓰지 않는다 — 상위 5 절단은 스펙·아이템 전용이고 경험치는
    무인자 = 등록 전체(상한 10 = Top10 파이프라인과 정합, 결정 4). realm 혼합 한 그래프
    (절대 레벨 그대로 — ADR-0011 원칙과 정합), 1캐릭 = 1라인 허용(2명 게이트는 서버
    리더보드 전용). 백필은 멱등이라 스케줄러가 웜이면 넥슨 0콜, 콜드면 캐릭당 ≤8콜.
    """
    if interaction.guild_id is None:
        await interaction.response.send_message(
            embed=make_embed("내 캐릭터 경험치", _DM_ONLY), ephemeral=True
        )
        return
    targets = await reg.get_my_character_targets(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    if not targets:
        await interaction.response.send_message(
            embed=make_embed("내 캐릭터 경험치", _NO_CHARACTERS), ephemeral=True
        )
        return
    await defer(interaction)

    await exp_service.backfill(deps, interaction.guild_id, targets)

    payload = await leaderboard.build_targets_payload(
        deps,
        interaction.guild_id,
        targets,
        labels={t.ocid: char_label(t) for t in targets},
        title="📈 내 캐릭터 경험치",
        min_ranked=1,  # 1캐릭 = 1라인 그래프 허용(graceful)
        realm=None,  # 본서버·챌린저스 혼합(결정 7)
    )
    if payload is None:
        await interaction.followup.send(
            embed=make_embed("내 캐릭터 경험치", _EXP_NOT_READY), ephemeral=True
        )
        return
    embed = payload.embed
    embed.description = f"{_owner_line(targets[0])}\n\n{embed.description}"
    await interaction.followup.send(embed=embed, files=payload.to_files())


def setup(bot: discord.Client) -> None:
    """`/내캐릭터` 그룹(스펙·아이템·경험치)을 트리에 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    group = app_commands.Group(
        name="내캐릭터",
        description="내가 등록한 캐릭터끼리 비교합니다 (친구 없이도 사용 가능).",
    )

    async def _char_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        characters = await reg.get_characters(
            deps.session_factory, interaction.guild_id, interaction.user.id
        )
        return character_choices(characters, current)

    @group.command(
        name="스펙",
        description="내 등록 캐릭터끼리 전투력·HEXA 스펙을 비교합니다 (미지정 시 전체, 최대 5개).",
    )
    @app_commands.rename(
        char1="캐릭터1",
        char2="캐릭터2",
        char3="캐릭터3",
        char4="캐릭터4",
        char5="캐릭터5",
    )
    @app_commands.describe(
        char1="비교할 내 캐릭터 (미지정 시 레벨 상위 5개)",
        char2="추가 비교 캐릭터",
        char3="추가 비교 캐릭터",
        char4="추가 비교 캐릭터",
        char5="추가 비교 캐릭터",
    )
    @app_commands.autocomplete(
        char1=_char_autocomplete,
        char2=_char_autocomplete,
        char3=_char_autocomplete,
        char4=_char_autocomplete,
        char5=_char_autocomplete,
    )
    @cooldowns.spec_cooldown()
    async def my_spec_command(
        interaction: discord.Interaction,
        char1: str | None = None,
        char2: str | None = None,
        char3: str | None = None,
        char4: str | None = None,
        char5: str | None = None,
    ) -> None:
        ocids = [c for c in (char1, char2, char3, char4, char5) if c]
        await handle_my_spec(deps, interaction, ocids)

    @group.command(
        name="아이템",
        description="내 등록 캐릭터끼리 부위별 장비를 비교합니다 (미지정 시 전체, 최대 5개).",
    )
    @app_commands.rename(
        part="부위",
        char1="캐릭터1",
        char2="캐릭터2",
        char3="캐릭터3",
        char4="캐릭터4",
        char5="캐릭터5",
    )
    @app_commands.describe(
        part="조회할 장비 부위",
        char1="비교할 내 캐릭터 (미지정 시 레벨 상위 5개)",
        char2="추가 비교 캐릭터",
        char3="추가 비교 캐릭터",
        char4="추가 비교 캐릭터",
        char5="추가 비교 캐릭터",
    )
    @app_commands.choices(
        part=[app_commands.Choice(name=slot, value=slot) for slot in SLOT_CHOICES]
    )
    @app_commands.autocomplete(
        char1=_char_autocomplete,
        char2=_char_autocomplete,
        char3=_char_autocomplete,
        char4=_char_autocomplete,
        char5=_char_autocomplete,
    )
    @cooldowns.spec_cooldown()
    async def my_item_command(
        interaction: discord.Interaction,
        part: app_commands.Choice[str],
        char1: str | None = None,
        char2: str | None = None,
        char3: str | None = None,
        char4: str | None = None,
        char5: str | None = None,
    ) -> None:
        ocids = [c for c in (char1, char2, char3, char4, char5) if c]
        await handle_my_item(deps, interaction, part.value, ocids)

    @group.command(
        name="경험치",
        description="내 등록 캐릭터들의 최근 7일 레벨 추이를 그래프와 순위로 보여줍니다.",
    )
    @cooldowns.spec_cooldown()  # 10초 — 첫 호출은 넥슨 콜드 백필 가능; 이후는 DB 조회만
    async def my_exp_command(interaction: discord.Interaction) -> None:
        await handle_my_exp(deps, interaction)

    bot.tree.add_command(group)
