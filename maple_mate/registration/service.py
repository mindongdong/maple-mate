"""registration 비즈니스 로직 (전달-무관). discord/http 타입에 의존하지 않는다.

`/등록` 흐름(handoff §5, ADR-0001): 닉 → ocid 검증 → (키 있으면) 개인 키 유효성 검증 +
Fernet 암호화 → (guild_id, discord_user_id) 1레코드 upsert. 서버 내 닉 중복 허용.
결과는 `RegistrationResult` 로 반환하고, 전달 계층(commands/views)이 렌더링한다.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..error_log import service as error_log
from ..nexon.client import NexonClient
from ..nexon.errors import ErrorClass, NexonAPIError, to_error_log_type
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


async def resolve_ocid(
    nexon: NexonClient, nickname: str
) -> tuple[str | None, str | None]:
    """닉 → ocid. 성공 시 (ocid, None), 실패 시 (None, 사용자메시지)."""
    try:
        ocid = await nexon.get_ocid(nickname)
        return ocid, None
    except NexonAPIError as exc:
        if exc.error_class in (ErrorClass.INVALID_PARAM, ErrorClass.INVALID_ID):
            return (
                None,
                f"'{nickname}' 닉네임을 찾을 수 없어요. 닉네임을 확인해 주세요.",
            )
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
        return (
            None,
            "키 검증 중 넥슨 API 오류가 발생했어요. 잠시 후 다시 시도해 주세요.",
        )
    if not valid:
        return (
            None,
            "API 키가 무효입니다. 키 없이 등록하려면 키 인자를 빼고 다시 시도해 주세요.",
        )
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
    return RegistrationResult(
        ok=True, nickname=nickname, has_key=api_key_encrypted is not None
    )


# ── Phase 2: 대상(target) 해석 + ocid lazy 갱신 + 부분 성공 수집 (handoff §2·§4) ──
#
# 스펙류 비교 명령(/유니온·/스펙·/아이템)이 공유하는 머신. registration 이 ocid 레코드를
# 소유하므로 여기 둔다. fetch 는 도메인별 조회 함수(전달-무관)이고, 이 모듈은 대상 해석·
# 캐싱 ocid 사용·실패 시 닉 재조회 1회·분류별 사용자 메시지·error_log 적재를 담당한다.


@dataclass(frozen=True)
class Target:
    """비교 대상 1명(등록 레코드의 비교용 스냅샷). ORM 분리 — 전달 계층이 자유롭게 쓴다."""

    guild_id: int
    discord_user_id: int
    nickname: str
    ocid: str


@dataclass(frozen=True)
class TargetOutcome:
    """대상 1명의 조회 결과. ok=True 면 data, 실패면 error(사용자 메시지)."""

    target: Target
    data: Any | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


async def get_targets(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    user_ids: Sequence[int] | None = None,
) -> list[Target]:
    """비교 대상 해석 (CONTEXT.md 용어 '대상').

    user_ids 없으면 현재 서버 등록자 전원, 지정 시 그 유저들 중 등록된 레코드만.
    user_ids 지정 시 입력 순서를 보존(비교 가독성). 미등록 유저는 제외(handoff §4).
    """
    async with session_factory() as session:
        stmt = select(Registration).where(Registration.guild_id == guild_id)
        if user_ids is not None:
            stmt = stmt.where(Registration.discord_user_id.in_(list(user_ids)))
        rows = (await session.execute(stmt)).scalars().all()

    targets = [
        Target(
            guild_id=r.guild_id,
            discord_user_id=r.discord_user_id,
            nickname=r.maple_nickname,
            ocid=r.ocid,
        )
        for r in rows
    ]
    if user_ids is not None:
        order = {uid: i for i, uid in enumerate(user_ids)}
        targets.sort(key=lambda t: order.get(t.discord_user_id, len(order)))
    return targets


async def refresh_ocid(
    session_factory: async_sessionmaker[AsyncSession],
    nexon: NexonClient,
    target: Target,
) -> str | None:
    """닉 → ocid 재조회 후 DB 갱신(handoff §4 lazy 갱신). 성공 시 새 ocid, 실패 시 None.

    닉 자체가 사라졌으면(닉 변경) get_ocid 가 NexonAPIError → None 반환.
    """
    try:
        new_ocid = await nexon.get_ocid(target.nickname)
    except NexonAPIError:
        return None
    if new_ocid and new_ocid != target.ocid:
        async with session_factory() as session:
            await session.execute(
                update(Registration)
                .where(
                    Registration.guild_id == target.guild_id,
                    Registration.discord_user_id == target.discord_user_id,
                )
                .values(ocid=new_ocid, updated_at=func.now())
            )
            await session.commit()
    return new_ocid


_STALE_OCID = (ErrorClass.INVALID_PARAM, ErrorClass.INVALID_ID)


def classify_target_error(exc: NexonAPIError) -> str:
    """넥슨 에러 → 대상별 사용자 메시지(부분 성공 행). 순수함수 — 단위테스트 대상."""
    cls = exc.error_class
    if cls is ErrorClass.DATA_NOT_READY:
        return "아직 데이터가 준비되지 않았어요(전일 미생성)."
    if cls is ErrorClass.AUTH_INVALID:
        return "조회 권한 오류가 발생했어요."
    if cls in (ErrorClass.RATE_LIMIT, ErrorClass.TIMEOUT, ErrorClass.NEXON_API):
        return "넥슨 API 오류로 조회하지 못했어요. 잠시 후 다시 시도해 주세요."
    # INVALID_PARAM/INVALID_ID(스테일 ocid 복구 실패 포함)·UNKNOWN
    return "조회에 실패했어요. 닉네임/등록 상태를 확인해 주세요."


async def _fetch_one(
    nexon: NexonClient,
    session_factory: async_sessionmaker[AsyncSession],
    target: Target,
    command: str,
    fetch: Callable[[str], Awaitable[Any]],
) -> TargetOutcome:
    """대상 1명 조회. 캐싱 ocid → 실패 시 닉 재조회 1회 → 재시도 → 분류/적재."""
    ocid = target.ocid
    refreshed = False
    while True:
        try:
            data = await fetch(ocid)
            return TargetOutcome(target=target, data=data)
        except NexonAPIError as exc:
            # 1) 스테일 ocid(없는 닉/잘못된 ocid=OPENAPI00004) → 닉 재조회 1회
            if exc.error_class in _STALE_OCID and not refreshed:
                refreshed = True
                new_ocid = await refresh_ocid(session_factory, nexon, target)
                if new_ocid is not None:
                    ocid = new_ocid
                    continue
                return TargetOutcome(
                    target=target,
                    error="닉 변경 가능성이 있어요. `/등록`으로 닉네임을 갱신해 주세요.",
                )
            # 2) 하드 실패 → (적재 대상이면) error_log + 사용자 메시지
            log_type = to_error_log_type(exc.error_class)
            if log_type is not None:
                await error_log.record(
                    session_factory,
                    error_type=log_type,
                    command=command,
                    guild_id=target.guild_id,
                    discord_user_id=target.discord_user_id,
                    target_ocid=ocid,
                    detail=f"{exc.code}: {exc.message}"[:500],
                )
            return TargetOutcome(target=target, error=classify_target_error(exc))


async def fetch_each(
    *,
    targets: Sequence[Target],
    nexon: NexonClient,
    session_factory: async_sessionmaker[AsyncSession],
    command: str,
    fetch: Callable[[str], Awaitable[Any]],
) -> list[TargetOutcome]:
    """대상 전원을 순차 조회(클라이언트 스로틀이 rate limit 보호). 부분 성공 허용.

    fetch(ocid) 는 도메인 조회 함수(성공 시 결과, 실패 시 NexonAPIError raise).
    """
    outcomes: list[TargetOutcome] = []
    for target in targets:
        outcomes.append(
            await _fetch_one(nexon, session_factory, target, command, fetch)
        )
    return outcomes
