"""registration 비즈니스 로직 (전달-무관). discord/http 타입에 의존하지 않는다.

`/등록` 흐름(handoff §5, ADR-0001): 닉 → ocid 검증 → (키 있으면) 개인 키 유효성 검증 +
Fernet 암호화 → (guild_id, discord_user_id) 1레코드 upsert. 서버 내 닉 중복 허용.
결과는 `RegistrationResult` 로 반환하고, 전달 계층(commands/views)이 렌더링한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..nexon.client import NexonClient
from ..nexon.errors import ErrorClass, NexonAPIError
from ..security.crypto import KeyCipher
from .models import Registration

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistrationResult:
    """등록 결과. ok=False 면 error(사용자 메시지)만 의미 있음."""

    ok: bool
    nickname: str | None = None
    has_key: bool = False
    error: str | None = None


async def resolve_ocid(nexon: NexonClient, nickname: str) -> tuple[str | None, str | None]:
    """닉 → ocid. 성공 시 (ocid, None), 실패 시 (None, 사용자메시지)."""
    try:
        ocid = await nexon.get_ocid(nickname)
        return ocid, None
    except NexonAPIError as exc:
        if exc.error_class in (ErrorClass.INVALID_PARAM, ErrorClass.INVALID_ID):
            return None, f"'{nickname}' 닉네임을 찾을 수 없어요. 닉네임을 확인해 주세요."
        log.warning("ocid 조회 실패: %s", exc)
        return None, "넥슨 API 오류로 등록하지 못했어요. 잠시 후 다시 시도해 주세요."


async def verify_and_encrypt_key(
    nexon: NexonClient, cipher: KeyCipher, api_key: str
) -> tuple[str | None, str | None]:
    """개인 키 검증 후 암호문. 성공 시 (암호문, None), 무효/오류 시 (None, 사용자메시지)."""
    try:
        valid = await nexon.verify_personal_key(api_key)
    except NexonAPIError as exc:
        log.warning("키 검증 중 API 오류: %s", exc)
        return None, "키 검증 중 넥슨 API 오류가 발생했어요. 잠시 후 다시 시도해 주세요."
    if not valid:
        return None, "API 키가 무효입니다. 키 없이 등록하려면 키 인자를 빼고 다시 시도해 주세요."
    return cipher.encrypt(api_key), None


async def upsert_registration(
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


async def register(
    *,
    nexon: NexonClient,
    cipher: KeyCipher,
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    nickname: str,
    api_key: str | None,
) -> RegistrationResult:
    """등록 오케스트레이션. ocid 검증 → (키) 유효성+암호화 → upsert."""
    ocid, err = await resolve_ocid(nexon, nickname)
    if ocid is None:
        return RegistrationResult(ok=False, error=err)

    api_key_encrypted: str | None = None
    if api_key:
        api_key_encrypted, err = await verify_and_encrypt_key(nexon, cipher, api_key)
        if api_key_encrypted is None:
            return RegistrationResult(ok=False, error=err)

    await upsert_registration(
        session_factory,
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        nickname=nickname,
        ocid=ocid,
        api_key_encrypted=api_key_encrypted,
    )
    return RegistrationResult(ok=True, nickname=nickname, has_key=api_key_encrypted is not None)
