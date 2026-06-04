"""`/등록` — 메이플 캐릭터를 서버에 등록 (빌드 단위 #8, design §3·§5①, ADR-0001).

레코드 단위 = (guild_id, discord_user_id) 1레코드 upsert. 서버 내 닉네임 중복 허용.
- 키 없음: 닉 → ocid 조회·검증 후 등록(스펙류만).
- 키 있음: history/starforce count=10 로 키 유효성 검증 → 유효하면 Fernet 암호화 저장, 무효면 거부.
응답은 ephemeral(개인 키 노출 최소화). 용어는 CONTEXT.md("등록", "키 미등록") 사용.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...db.models import Registration
from ...nexon.client import NexonClient
from ...nexon.errors import ErrorClass, NexonAPIError
from ..deps import BotDeps
from ..embeds import defer, make_embed

log = logging.getLogger(__name__)


async def _upsert_registration(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    discord_user_id: int,
    nickname: str,
    ocid: str,
    api_key_encrypted: str | None,
) -> None:
    """(guild_id, discord_user_id) 1레코드 upsert. 재등록 시 닉/ocid/키를 최신값으로 덮어쓴다."""
    async with session_factory() as session:
        stmt = (
            pg_insert(Registration)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                maple_nickname=nickname,
                ocid=ocid,
                api_key_encrypted=api_key_encrypted,
            )
            .on_conflict_do_update(
                index_elements=["guild_id", "discord_user_id"],
                set_={
                    "maple_nickname": nickname,
                    "ocid": ocid,
                    "api_key_encrypted": api_key_encrypted,
                    "updated_at": func.now(),
                },
            )
        )
        await session.execute(stmt)
        await session.commit()


async def _resolve_ocid(nexon: NexonClient, nickname: str) -> tuple[str | None, str | None]:
    """닉 → ocid. 성공 시 (ocid, None), 실패 시 (None, 사용자메시지)."""
    try:
        ocid = await nexon.get_ocid(nickname)
        return ocid, None
    except NexonAPIError as exc:
        if exc.error_class in (ErrorClass.INVALID_PARAM, ErrorClass.INVALID_ID):
            return None, f"'{nickname}' 닉네임을 찾을 수 없어요. 닉네임을 확인해 주세요."
        log.warning("ocid 조회 실패: %s", exc)
        return None, "넥슨 API 오류로 등록하지 못했어요. 잠시 후 다시 시도해 주세요."


async def _encrypt_if_valid(
    deps: BotDeps, api_key: str
) -> tuple[str | None, str | None]:
    """개인 키 검증 후 암호문. 성공 시 (암호문, None), 무효/오류 시 (None, 사용자메시지)."""
    try:
        valid = await deps.nexon.verify_personal_key(api_key)
    except NexonAPIError as exc:
        log.warning("키 검증 중 API 오류: %s", exc)
        return None, "키 검증 중 넥슨 API 오류가 발생했어요. 잠시 후 다시 시도해 주세요."
    if not valid:
        return None, (
            "API 키가 무효입니다. 키 없이 등록하려면 키 인자를 빼고 다시 시도해 주세요."
        )
    return deps.cipher.encrypt(api_key), None


async def handle_register(
    deps: BotDeps,
    interaction: discord.Interaction,
    nickname: str,
    api_key: str | None,
) -> None:
    await defer(interaction, ephemeral=True)
    nickname = nickname.strip()

    if interaction.guild_id is None:
        await interaction.followup.send(
            embed=make_embed("등록 실패", "서버(길드) 안에서만 등록할 수 있어요."), ephemeral=True
        )
        return

    # 1) ocid 조회·검증
    ocid, err = await _resolve_ocid(deps.nexon, nickname)
    if ocid is None:
        await interaction.followup.send(embed=make_embed("등록 실패", err), ephemeral=True)
        return

    # 2) 키가 있으면 유효성 검증 + 암호화
    api_key_encrypted: str | None = None
    if api_key:
        api_key_encrypted, err = await _encrypt_if_valid(deps, api_key.strip())
        if api_key_encrypted is None:
            await interaction.followup.send(embed=make_embed("등록 실패", err), ephemeral=True)
            return

    # 3) upsert
    await _upsert_registration(
        deps.session_factory,
        guild_id=interaction.guild_id,
        discord_user_id=interaction.user.id,
        nickname=nickname,
        ocid=ocid,
        api_key_encrypted=api_key_encrypted,
    )

    # 4) 결과 안내(CONTEXT 용어)
    if api_key_encrypted:
        scope = "스타포스·잠재 등 **이력류**까지 조회 가능 (개인 키 등록됨)"
    else:
        scope = "**스펙류**만 조회 가능 (키 미등록)"
    await interaction.followup.send(
        embed=make_embed("등록 완료", f"**{nickname}** 등록이 완료됐어요.\n{scope}"),
        ephemeral=True,
    )


def setup(bot: discord.Client) -> None:
    """봇 트리에 `/등록` 등록. bot.deps(BotDeps) 를 사용한다."""
    deps: BotDeps = bot.deps  # type: ignore[attr-defined]

    @bot.tree.command(name="등록", description="메이플 캐릭터를 이 서버에 등록합니다 (API 키는 선택).")  # type: ignore[attr-defined]
    @app_commands.rename(nickname="닉네임", api_key="api키")
    @app_commands.describe(
        nickname="메이플 캐릭터 닉네임",
        api_key="넥슨 개인 API 키 (선택). 입력하면 스타포스·잠재 등 이력류 조회가 열립니다.",
    )
    async def register_command(
        interaction: discord.Interaction,
        nickname: str,
        api_key: str | None = None,
    ) -> None:
        await handle_register(deps, interaction, nickname, api_key)
