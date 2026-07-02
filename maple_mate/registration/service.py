"""registration 비즈니스 로직 (전달-무관). discord/http 타입에 의존하지 않는다.

멀티 캐릭터 모델(작업지시서): 유저당 캐릭터 N개(`character`) + 계정 레벨 1레코드(`registration`,
개인 키 + 대표 포인터). `/등록`(닉+키 한 방)은 `/캐릭터등록`·`/키등록`으로 분리됐다.

- register_character: 닉 → ocid 검증 → 레벨 스냅샷 → 상한 검사 → character upsert(+부모 자동 생성).
- register_key: 개인 키 검증/암호화 → registration upsert(키만, 부모 자동 생성).
- 대표 해석(pick_representative): 지정 우선 → 레벨 최고(타이브레이크 created_at·ocid) → 없으면 None.
- get_targets: 유저별 대표 1명을 비교용 Target(닉·ocid)으로 산출(스펙류·경험치의 단일 출처).

결과는 dataclass 로 반환하고, 전달 계층(commands/views)이 렌더링한다.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..error_log import service as error_log
from ..nexon.client import NexonClient
from ..nexon.errors import ErrorClass, NexonAPIError, to_error_log_type
from ..security.crypto import KeyCipher
from .models import Character, Registration
from .realm import Realm, in_realm

log = logging.getLogger(__name__)

# 유저당 캐릭터 등록 상한(그릴링 9). 환경 무관 고정 규칙이라 모듈 상수로 둔다.
MAX_CHARACTERS_PER_USER = 10


# ── 결과 DTO ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CharacterRegisterResult:
    """`/캐릭터등록` 결과. ok=False 면 error(사용자 메시지)만 의미 있음."""

    ok: bool
    nickname: str | None = None
    level: int | None = None
    character_count: int = 0  # 등록 후 이 유저의 총 캐릭터 수
    error: str | None = None


@dataclass(frozen=True)
class KeyRegisterResult:
    """`/키등록` 결과. ok=False 면 error 만 의미 있음."""

    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class CharacterInfo:
    """캐릭터 1개 표시용 스냅샷(/캐릭터목록·/대표지정 자동완성)."""

    ocid: str
    nickname: str
    level: int | None
    is_representative: bool
    world: str | None = (
        None  # realm 신호(ADR-0009). NULL=본서버. 목록에 챌린저스만 표기.
    )


# ── ocid / 키 검증 (재사용) ──────────────────────────────────────────────────


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
            "API 키가 무효입니다. 키만 다시 확인해서 `/키등록`으로 등록해 주세요.",
        )
    return cipher.encrypt(api_key), None


async def _fetch_level_and_world(
    nexon: NexonClient, ocid: str
) -> tuple[int | None, str | None]:
    """등록 시 레벨·월드 스냅샷(best-effort, 한 콜). 실패·파싱오류는 (None, None)(등록은 진행).

    world_name 은 realm 신호(ADR-0009) — `챌린저스N` 이면 챌린저스 캐릭터로 자동 판별된다.
    """
    try:
        basic = await nexon.character_basic(ocid)
    except NexonAPIError as exc:
        log.debug("레벨/월드 스냅샷 실패(무시) ocid=%s: %s", ocid, exc)
        return None, None
    world = basic.get("world_name")
    raw = basic.get("character_level")
    if raw is None:
        return None, world
    try:
        return int(raw), world
    except (TypeError, ValueError):
        return None, world


# ── 등록 (캐릭터 / 키) ────────────────────────────────────────────────────────


async def register_character(
    *,
    nexon: NexonClient,
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    nickname: str,
) -> CharacterRegisterResult:
    """캐릭터 등록. ocid 검증 → 레벨 스냅샷 → 상한 검사 → character upsert + 부모 자동 생성.

    같은 ocid 재등록은 닉/레벨 갱신(upsert)이라 상한에 안 걸린다. 새 ocid 가 상한(10) 초과면 거부.
    """
    ocid, err = await resolve_ocid(nexon, nickname)
    if ocid is None:
        return CharacterRegisterResult(ok=False, error=err)
    level, world = await _fetch_level_and_world(nexon, ocid)

    async with session_factory() as session:
        existing = set(
            (
                await session.execute(
                    select(Character.ocid).where(
                        Character.guild_id == guild_id,
                        Character.discord_user_id == discord_user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        is_new = ocid not in existing
        if is_new and len(existing) >= MAX_CHARACTERS_PER_USER:
            return CharacterRegisterResult(
                ok=False,
                error=(
                    f"캐릭터는 최대 {MAX_CHARACTERS_PER_USER}개까지 등록할 수 있어요."
                    " 같은 캐릭터를 다시 등록하면 닉/레벨만 갱신돼요."
                ),
            )

        # 부모 registration 자동 생성(키·대표는 건드리지 않음).
        await session.execute(
            pg_insert(Registration)
            .values(guild_id=guild_id, discord_user_id=discord_user_id)
            .on_conflict_do_nothing(index_elements=["guild_id", "discord_user_id"])
        )
        # 캐릭터 upsert — 같은 ocid 면 닉/레벨 갱신.
        await session.execute(
            pg_insert(Character)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                ocid=ocid,
                maple_nickname=nickname,
                level=level,
                world=world,
            )
            .on_conflict_do_update(
                index_elements=["guild_id", "discord_user_id", "ocid"],
                set_={
                    "maple_nickname": nickname,
                    "level": level,
                    "world": world,  # 재등록 시 realm 신호 lazy 갱신(레거시 NULL 백필)
                    "updated_at": func.now(),
                },
            )
        )
        await session.commit()

    count = len(existing) + 1 if is_new else len(existing)
    return CharacterRegisterResult(
        ok=True, nickname=nickname, level=level, character_count=count
    )


async def register_key(
    *,
    nexon: NexonClient,
    cipher: KeyCipher,
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    api_key: str,
) -> KeyRegisterResult:
    """개인 키 등록. 유효성 검증 + Fernet 암호화 → registration upsert(키만, 부모 자동 생성)."""
    api_key_encrypted, err = await verify_and_encrypt_key(nexon, cipher, api_key)
    if api_key_encrypted is None:
        return KeyRegisterResult(ok=False, error=err)

    async with session_factory() as session:
        await session.execute(
            pg_insert(Registration)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                api_key_encrypted=api_key_encrypted,
            )
            .on_conflict_do_update(
                index_elements=["guild_id", "discord_user_id"],
                set_={
                    "api_key_encrypted": api_key_encrypted,
                    "updated_at": func.now(),
                },
            )
        )
        await session.commit()
    return KeyRegisterResult(ok=True)


# ── 대표 해석 ─────────────────────────────────────────────────────────────────


class _CharacterLike(Protocol):
    ocid: str
    level: int | None
    created_at: Any  # datetime (정렬 가능하면 무엇이든 — 순수 단위테스트 용이)
    world: str | None  # realm 신호(ADR-0009). realm 인자 지정 시에만 접근.


def _auto_key(c: _CharacterLike) -> tuple:
    """자동 대표 정렬 키: 레벨 내림차순 → created_at 오름차순 → ocid. 첫 원소가 대표."""
    level = c.level if c.level is not None else -1
    return (-level, c.created_at, c.ocid)


def pick_representative(
    characters: Sequence[_CharacterLike],
    representative_ocid: str | None,
    realm: Realm | None = None,
) -> _CharacterLike | None:
    """대표 해석 규칙(작업지시서). 순수함수 — 단위테스트 대상.

    realm 지정 시 그 realm 캐릭터만 후보로 본다(결정 4 — realm 인지 해석). 수동 핀은 가리키는
    캐릭터가 그 realm 에 있을 때만 효력, 반대 realm 핀은 무시되고 그 realm 내 자동 대표가 된다.

    1. representative_ocid 가 set 이고 (realm) 후보에 존재 → 그 캐릭터(수동 지정).
    2. NULL 이거나 가리키는 캐릭터가 후보에 없음 → level 최고값(동률·NULL 은 created_at/ocid).
    3. (realm) 후보 0개 → None.
    """
    pool = (
        list(characters)
        if realm is None
        else [c for c in characters if in_realm(c.world, realm)]
    )
    if not pool:
        return None
    if representative_ocid is not None:
        match = next((c for c in pool if c.ocid == representative_ocid), None)
        if match is not None:
            return match
    return sorted(pool, key=_auto_key)[0]


async def _load_user_characters(
    session: AsyncSession, guild_id: int, discord_user_id: int
) -> list[Character]:
    rows = (
        await session.execute(
            select(Character).where(
                Character.guild_id == guild_id,
                Character.discord_user_id == discord_user_id,
            )
        )
    ).scalars()
    return list(rows.all())


async def get_characters(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
) -> list[CharacterInfo]:
    """본인 캐릭터 목록(레벨 내림차순). 대표 1명은 is_representative=True (대표 해석 반영)."""
    async with session_factory() as session:
        chars = await _load_user_characters(session, guild_id, discord_user_id)
        reg = await session.get(Registration, (guild_id, discord_user_id))
    rep_ocid = reg.representative_ocid if reg is not None else None
    rep = pick_representative(chars, rep_ocid)
    rep_id = rep.ocid if rep is not None else None
    return [
        CharacterInfo(
            ocid=c.ocid,
            nickname=c.maple_nickname,
            level=c.level,
            is_representative=c.ocid == rep_id,
            world=c.world,
        )
        for c in sorted(chars, key=_auto_key)
    ]


async def set_representative(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    ocid: str,
) -> str | None:
    """대표 캐릭터 수동 지정. ocid 가 본인 캐릭터면 그 닉네임 반환, 아니면 None(설정 안 함)."""
    async with session_factory() as session:
        char = await session.get(Character, (guild_id, discord_user_id, ocid))
        if char is None:
            return None
        await session.execute(
            pg_insert(Registration)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                representative_ocid=ocid,
            )
            .on_conflict_do_update(
                index_elements=["guild_id", "discord_user_id"],
                set_={"representative_ocid": ocid, "updated_at": func.now()},
            )
        )
        await session.commit()
        return char.maple_nickname


async def has_personal_key(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
) -> bool:
    """이 유저가 개인 키를 등록했는지(/캐릭터목록 표시용)."""
    async with session_factory() as session:
        reg = await session.get(Registration, (guild_id, discord_user_id))
    return reg is not None and reg.api_key_encrypted is not None


# ── 비교 대상(target) 해석 + ocid lazy 갱신 + 부분 성공 수집 (handoff §2·§4) ──
#
# 스펙류 비교 명령(/유니온·/스펙·/아이템)이 공유하는 머신. registration 이 대표 포인터를
# 소유하므로 여기 둔다. 유저별 대표 1명을 Target(닉·ocid)으로 산출한다.


@dataclass(frozen=True)
class Target:
    """비교 대상 1명(유저의 대표 캐릭터 스냅샷). ORM 분리 — 전달 계층이 자유롭게 쓴다."""

    guild_id: int
    discord_user_id: int
    nickname: str
    ocid: str
    world: str | None = None  # 대표의 realm 신호(ADR-0009) — 리더보드 적재·라벨용


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
    realm: Realm | None = None,
) -> list[Target]:
    """비교 대상 해석 — 유저별 대표 1명(CONTEXT.md 용어 '대상').

    user_ids 없으면 현재 서버 등록자 전원(각자 대표), 지정 시 그 유저들 중 캐릭터 보유자만.
    캐릭터 0개 유저(키만 등록 등)는 제외. user_ids 지정 시 입력 순서를 보존(비교 가독성).

    realm 지정 시 그 realm 캐릭터만으로 대표를 해석한다(결정 5 — 본서버 모드는 챌린저스 제외,
    챌린저스 모드는 챌린저스만). 그 realm 캐릭터가 없는 유저는 대상에서 빠진다(누수 0).
    """
    async with session_factory() as session:
        char_stmt = select(Character).where(Character.guild_id == guild_id)
        reg_stmt = select(
            Registration.discord_user_id, Registration.representative_ocid
        ).where(Registration.guild_id == guild_id)
        if user_ids is not None:
            ids = list(user_ids)
            char_stmt = char_stmt.where(Character.discord_user_id.in_(ids))
            reg_stmt = reg_stmt.where(Registration.discord_user_id.in_(ids))
        chars = (await session.execute(char_stmt)).scalars().all()
        rep_rows = (await session.execute(reg_stmt)).all()

    rep_by_user = {uid: rep_ocid for uid, rep_ocid in rep_rows}
    by_user: dict[int, list[Character]] = {}
    for c in chars:
        by_user.setdefault(c.discord_user_id, []).append(c)

    targets: list[Target] = []
    for uid, clist in by_user.items():
        rep = pick_representative(clist, rep_by_user.get(uid), realm)
        if rep is None:
            continue
        targets.append(
            Target(
                guild_id=guild_id,
                discord_user_id=uid,
                nickname=rep.maple_nickname,
                ocid=rep.ocid,
                world=rep.world,
            )
        )
    if user_ids is not None:
        order = {uid: i for i, uid in enumerate(user_ids)}
        targets.sort(key=lambda t: order.get(t.discord_user_id, len(order)))
    return targets


def _my_character_targets(
    characters: Sequence[Character],
    guild_id: int,
    discord_user_id: int,
    ocids: Sequence[str] | None = None,
) -> list[Target]:
    """캐릭터 목록 → 캐릭터당 Target 1개(순수함수 — 단위테스트 대상).

    무지정 = 등록 레벨 내림차순(동률 시 닉 오름차순). ocids 지정 시 그 캐릭터만,
    입력 순서 보존(get_targets 의 user_ids 순서 보존 관행) + 중복 제거.
    본인 것이 아닌 ocid 는 무시.
    """
    if ocids is not None:
        by_ocid = {c.ocid: c for c in characters}
        picked = []
        seen: set[str] = set()
        for o in ocids:
            if o in by_ocid and o not in seen:
                seen.add(o)
                picked.append(by_ocid[o])
    else:
        picked = sorted(
            characters,
            key=lambda c: (-(c.level if c.level is not None else -1), c.maple_nickname),
        )
    return [
        Target(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            nickname=c.maple_nickname,
            ocid=c.ocid,
            world=c.world,
        )
        for c in picked
    ]


async def get_my_character_targets(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    ocids: Sequence[str] | None = None,
) -> list[Target]:
    """솔로 비교(`/내캐릭터`) 대상 해석 — 이 유저의 등록 캐릭터를 캐릭터당 Target 1개로.

    realm 필터 없음(본인 캐릭끼리라 공정성 전제가 없음 — ADR-0018 결정 7, 챌린저스 혼합).
    기존 Target 을 그대로 재사용하므로 비교 렌더 경로가 무수정으로 받는다.
    """
    async with session_factory() as session:
        chars = await _load_user_characters(session, guild_id, discord_user_id)
    return _my_character_targets(chars, guild_id, discord_user_id, ocids)


async def refresh_ocid(
    session_factory: async_sessionmaker[AsyncSession],
    nexon: NexonClient,
    target: Target,
) -> str | None:
    """닉 → ocid 재조회 후 DB 갱신(handoff §4 lazy 갱신). 성공 시 새 ocid, 실패 시 None.

    대표 캐릭터의 ocid(character PK) 를 갱신하고, 대표 포인터가 옛 ocid 를 가리켰다면 함께 정합한다.
    닉 자체가 사라졌으면(닉 변경) get_ocid 가 NexonAPIError → None 반환.
    """
    try:
        new_ocid = await nexon.get_ocid(target.nickname)
    except NexonAPIError:
        return None
    if new_ocid and new_ocid != target.ocid:
        async with session_factory() as session:
            await session.execute(
                update(Character)
                .where(
                    Character.guild_id == target.guild_id,
                    Character.discord_user_id == target.discord_user_id,
                    Character.ocid == target.ocid,
                )
                .values(ocid=new_ocid, updated_at=func.now())
            )
            await session.execute(
                update(Registration)
                .where(
                    Registration.guild_id == target.guild_id,
                    Registration.discord_user_id == target.discord_user_id,
                    Registration.representative_ocid == target.ocid,
                )
                .values(representative_ocid=new_ocid, updated_at=func.now())
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
                    error="닉 변경 가능성이 있어요. `/캐릭터등록`으로 닉네임을 갱신해 주세요.",
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
