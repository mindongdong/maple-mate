"""등록/관리 디스코드 어댑터 (얇은 전달 계층). 로직은 service 가 담당.

멀티 캐릭터 모델(작업지시서): `/등록`(닉+키 한 방)을 4개로 분리했다.
- `/캐릭터등록 닉네임` — 메이플 캐릭터를 등록(유저당 N개, 상한 10).
- `/키등록 api키` — 개인 API 키 등록(유저당 1개, 이력류 조회 개방).
- `/대표지정 캐릭터` — 공개 명령(스펙·경험치 등)에 쓸 대표 캐릭터 지정(본인 캐릭터 자동완성).
- `/캐릭터목록` — 등록 캐릭터·레벨·대표·키 등록 여부(ephemeral).

개인 키 노출 최소화를 위해 응답은 항상 ephemeral.
"""

from __future__ import annotations

import discord
from discord import app_commands

from ..bot import cooldowns
from ..bot.embeds import defer, make_embed
from ..dependencies import Deps
from . import service
from .realm import is_challengers

_DM_ONLY = "서버(길드) 안에서만 쓸 수 있어요."


def _char_label(nickname: str, level: int | None, world: str | None = None) -> str:
    """`닉 (Lv.260, 챌린저스3)`. 챌린저스만 realm 표기(본서버는 무표기 — 시각 회귀 0)."""
    parts: list[str] = []
    if level is not None:
        parts.append(f"Lv.{level}")
    if is_challengers(world):
        parts.append(world)  # 예: 챌린저스3
    return f"{nickname} ({', '.join(parts)})" if parts else nickname


def character_choices(
    characters: list[service.CharacterInfo], current: str
) -> list[app_commands.Choice[str]]:
    """본인 캐릭터 목록 → 자동완성 Choice(순수함수 — `/대표지정`·`/내캐릭터` 공유).

    닉 부분일치(대소문자 무시) 필터, 라벨 = `닉 (Lv, 챌린저스N)` + 대표 👑, 상한 25(디스코드).
    value = ocid.
    """
    needle = current.strip().lower()
    choices: list[app_commands.Choice[str]] = []
    for c in characters:
        if needle and needle not in c.nickname.lower():
            continue
        label = _char_label(c.nickname, c.level, c.world)
        if c.is_representative:
            label = f"{label} 👑"
        choices.append(app_commands.Choice(name=label[:100], value=c.ocid))
        if len(choices) >= 25:  # Discord 자동완성 옵션 상한
            break
    return choices


async def handle_character_register(
    deps: Deps, interaction: discord.Interaction, nickname: str
) -> None:
    await defer(interaction, ephemeral=True)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("캐릭터 등록 실패", _DM_ONLY), ephemeral=True
        )
        return

    result = await service.register_character(
        nexon=deps.nexon,
        session_factory=deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        nickname=nickname.strip(),
    )
    if not result.ok:
        await interaction.followup.send(
            embed=make_embed("캐릭터 등록 실패", result.error), ephemeral=True
        )
        return

    has_key = await service.has_personal_key(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    lines = [
        f"**{_char_label(result.nickname, result.level)}** 등록 완료 — 현재 {result.character_count}개.",
    ]
    if result.character_count == 1:
        lines.append("이 캐릭터가 대표예요. `/대표지정`으로 바꿀 수 있어요.")
    else:
        lines.append(
            "대표는 등록 캐릭터 중 최고 레벨이에요. `/대표지정`으로 바꿀 수 있어요."
        )
    if not has_key:
        lines.append(
            "스타포스·잠재 등 **이력류**를 보려면 `/키등록`으로 개인 키를 등록하세요."
        )
    await interaction.followup.send(
        embed=make_embed("캐릭터 등록 완료", "\n".join(lines)), ephemeral=True
    )


async def handle_key_register(
    deps: Deps, interaction: discord.Interaction, api_key: str
) -> None:
    await defer(interaction, ephemeral=True)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("키 등록 실패", _DM_ONLY), ephemeral=True
        )
        return

    result = await service.register_key(
        nexon=deps.nexon,
        cipher=deps.cipher,
        session_factory=deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        api_key=api_key.strip(),
    )
    if not result.ok:
        await interaction.followup.send(
            embed=make_embed("키 등록 실패", result.error), ephemeral=True
        )
        return
    await interaction.followup.send(
        embed=make_embed(
            "키 등록 완료",
            "개인 API 키를 등록했어요. 스타포스·잠재 등 **이력류**(계정 전체)를 조회할 수 있어요.",
        ),
        ephemeral=True,
    )


async def handle_set_representative(
    deps: Deps, interaction: discord.Interaction, ocid: str
) -> None:
    await defer(interaction, ephemeral=True)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("대표 지정 실패", _DM_ONLY), ephemeral=True
        )
        return

    nickname = await service.set_representative(
        deps.session_factory, interaction.guild_id, interaction.user.id, ocid
    )
    if nickname is None:
        await interaction.followup.send(
            embed=make_embed(
                "대표 지정 실패",
                "본인 등록 캐릭터가 아니에요. `/캐릭터목록`에서 확인해 주세요.",
            ),
            ephemeral=True,
        )
        return
    await interaction.followup.send(
        embed=make_embed(
            "대표 지정 완료",
            f"대표 캐릭터를 **{nickname}** 으로 지정했어요. 스펙·경험치 등 공개 명령에 반영돼요.",
        ),
        ephemeral=True,
    )


async def handle_character_list(deps: Deps, interaction: discord.Interaction) -> None:
    await defer(interaction, ephemeral=True)
    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("캐릭터 목록", _DM_ONLY), ephemeral=True
        )
        return

    characters = await service.get_characters(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    if not characters:
        await interaction.followup.send(
            embed=make_embed(
                "캐릭터 목록",
                "등록된 캐릭터가 없어요. `/캐릭터등록`으로 먼저 등록해 주세요.",
            ),
            ephemeral=True,
        )
        return

    has_key = await service.has_personal_key(
        deps.session_factory, interaction.guild_id, interaction.user.id
    )
    lines = []
    for c in characters:
        mark = " 👑 대표" if c.is_representative else ""
        lines.append(f"• {_char_label(c.nickname, c.level, c.world)}{mark}")
    key_line = (
        "개인 키: 등록됨 (이력류 조회 가능)"
        if has_key
        else "개인 키: 미등록 (`/키등록`으로 이력류 조회 개방)"
    )
    lines.append("")
    lines.append(key_line)
    await interaction.followup.send(
        embed=make_embed(
            f"캐릭터 목록 ({len(characters)}/{service.MAX_CHARACTERS_PER_USER})",
            "\n".join(lines),
        ),
        ephemeral=True,
    )


def setup(bot: discord.Client) -> None:
    """봇 트리에 등록/관리 명령 4개를 등록. bot.deps(Deps) 를 사용한다."""
    deps: Deps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(  # type: ignore[attr-defined]
        name="캐릭터등록",
        description="메이플 캐릭터를 이 서버에 등록합니다 (유저당 여러 개 가능).",
    )
    @app_commands.rename(nickname="닉네임")
    @app_commands.describe(nickname="메이플 캐릭터 닉네임")
    @cooldowns.settings_cooldown()
    async def character_register_command(
        interaction: discord.Interaction, nickname: str
    ) -> None:
        await handle_character_register(deps, interaction, nickname)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="키등록",
        description="넥슨 개인 API 키를 등록합니다 (스타포스·잠재 등 이력류 조회 개방).",
    )
    @app_commands.rename(api_key="api키")
    @app_commands.describe(api_key="넥슨 개인 API 키")
    @cooldowns.settings_cooldown()
    async def key_register_command(
        interaction: discord.Interaction, api_key: str
    ) -> None:
        await handle_key_register(deps, interaction, api_key)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="대표지정",
        description="공개 명령(스펙·경험치 등)에 쓸 대표 캐릭터를 지정합니다.",
    )
    @app_commands.rename(ocid="캐릭터")
    @app_commands.describe(ocid="대표로 지정할 본인 등록 캐릭터")
    @cooldowns.settings_cooldown()
    async def set_representative_command(
        interaction: discord.Interaction, ocid: str
    ) -> None:
        await handle_set_representative(deps, interaction, ocid)

    @set_representative_command.autocomplete("ocid")
    async def _representative_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        characters = await service.get_characters(
            deps.session_factory, interaction.guild_id, interaction.user.id
        )
        return character_choices(characters, current)

    @bot.tree.command(  # type: ignore[attr-defined]
        name="캐릭터목록",
        description="등록한 캐릭터·레벨·대표·키 등록 여부를 봅니다 (본인만 보임).",
    )
    @cooldowns.spec_cooldown()
    async def character_list_command(interaction: discord.Interaction) -> None:
        await handle_character_list(deps, interaction)
