"""챌린저스 캐릭터 1회 갱신 — 시즌 종료로 일반 서버로 이전된 캐릭터의 world/level(·ocid) 재조회.

대상 = character.world 가 `챌린저스` 로 시작하는 행(등록 시 스냅샷이 남은 것). 행마다:
1. character/basic(기존 ocid) 성공 → world·level 갱신.
2. 기존 ocid 가 무효(INVALID_ID/INVALID_PARAM)면 닉네임 → ocid 재조회 → basic → ocid·world·level
   갱신 + 그 ocid 참조(registration.representative_ocid, exp_snapshot.ocid) 이관.
   history_cache 는 ocid 키 캐시라 손대지 않는다(새 ocid 로 재조회됨).
3. 그 외 실패는 건드리지 않고 목록만 출력(해당 유저는 `/캐릭터등록` 재등록 필요).

갱신된 행은 world 가 일반 서버명이 되어 대상에서 빠지므로 재실행해도 안전하다(멱등).
기본은 dry-run(계획만 출력). `--apply` 를 줘야 DB 에 반영한다.

실행:
    uv run python -m scripts.refresh_challengers          # dry-run
    uv run python -m scripts.refresh_challengers --apply  # 반영
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from maple_mate.config import load_config
from maple_mate.database.core import make_engine, make_session_factory
from maple_mate.leaderboard.models import ExpSnapshot
from maple_mate.nexon.client import NexonClient
from maple_mate.nexon.errors import ErrorClass, NexonAPIError
from maple_mate.registration.models import Character, Registration
from maple_mate.registration.realm import CHALLENGERS_PREFIX

# 기존 ocid 가 더는 유효하지 않다는 신호 — 이때만 닉네임 재조회로 넘어간다(장애·429 는 제외).
_STALE_OCID = {ErrorClass.INVALID_ID, ErrorClass.INVALID_PARAM}


@dataclass(frozen=True)
class Refreshed:
    ocid: str
    world: str | None
    level: int | None


def _parse_basic(ocid: str, basic: dict) -> Refreshed:
    raw = basic.get("character_level")
    try:
        level = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        level = None
    return Refreshed(ocid=ocid, world=basic.get("world_name"), level=level)


async def resolve(nexon: NexonClient, ocid: str, nickname: str) -> Refreshed:
    """기존 ocid 로 조회, 무효면 닉네임으로 새 ocid 조회. 실패는 NexonAPIError 그대로 전파."""
    try:
        return _parse_basic(ocid, await nexon.character_basic(ocid))
    except NexonAPIError as exc:
        if exc.error_class not in _STALE_OCID:
            raise
    new_ocid = await nexon.get_ocid(nickname)
    return _parse_basic(new_ocid, await nexon.character_basic(new_ocid))


async def _apply(session: AsyncSession, row: Character, new: Refreshed) -> None:
    """한 캐릭터 행 갱신. ocid 가 바뀌면 PK 이관 + 참조 이관(충돌 시 기존 새 ocid 행 우선)."""
    key = (
        Character.guild_id == row.guild_id,
        Character.discord_user_id == row.discord_user_id,
    )
    values = {"world": new.world, "level": new.level}
    if new.ocid == row.ocid:
        await session.execute(
            update(Character).where(*key, Character.ocid == row.ocid).values(**values)
        )
        return

    # 새 ocid 로 이미 재등록돼 있으면 옛 행만 지우고, 아니면 옛 행의 ocid 를 바꾼다.
    already = await session.scalar(
        select(Character.ocid).where(*key, Character.ocid == new.ocid)
    )
    if already is not None:
        await session.execute(delete(Character).where(*key, Character.ocid == row.ocid))
        await session.execute(
            update(Character).where(*key, Character.ocid == new.ocid).values(**values)
        )
    else:
        await session.execute(
            update(Character)
            .where(*key, Character.ocid == row.ocid)
            .values(ocid=new.ocid, **values)
        )

    await session.execute(
        update(Registration)
        .where(
            Registration.guild_id == row.guild_id,
            Registration.discord_user_id == row.discord_user_id,
            Registration.representative_ocid == row.ocid,
        )
        .values(representative_ocid=new.ocid)
    )

    # exp_snapshot PK = (guild, user, ocid, date): 새 ocid 행과 날짜가 겹치는 옛 행은 버리고 이관.
    snap_key = (
        ExpSnapshot.guild_id == row.guild_id,
        ExpSnapshot.discord_user_id == row.discord_user_id,
    )
    taken = select(ExpSnapshot.snapshot_date).where(
        *snap_key, ExpSnapshot.ocid == new.ocid
    )
    await session.execute(
        delete(ExpSnapshot).where(
            *snap_key,
            ExpSnapshot.ocid == row.ocid,
            ExpSnapshot.snapshot_date.in_(taken),
        )
    )
    await session.execute(
        update(ExpSnapshot)
        .where(*snap_key, ExpSnapshot.ocid == row.ocid)
        .values(ocid=new.ocid)
    )


async def main(apply: bool) -> None:
    config = load_config()
    engine = make_engine(config.database_url)
    session_factory = make_session_factory(engine)
    failed: list[str] = []
    try:
        async with NexonClient(
            config.nexon_app_key, throttle=config.nexon_throttle
        ) as nexon:
            async with session_factory() as session:
                rows = (
                    await session.scalars(
                        select(Character).where(
                            Character.world.startswith(CHALLENGERS_PREFIX)
                        )
                    )
                ).all()
            print(f"대상 {len(rows)}건 ({'반영' if apply else 'dry-run'})")

            for row in rows:
                label = (
                    f"guild={row.guild_id} user={row.discord_user_id}"
                    f" {row.maple_nickname} ({row.world})"
                )
                try:
                    new = await resolve(nexon, row.ocid, row.maple_nickname)
                except NexonAPIError as exc:
                    failed.append(f"{label}: {exc.error_class.value} {exc}")
                    continue
                changed = " [ocid 변경]" if new.ocid != row.ocid else ""
                print(f"- {label} → {new.world} Lv.{new.level}{changed}")
                if apply:
                    async with session_factory() as session:
                        await _apply(session, row, new)
                        await session.commit()
    finally:
        await engine.dispose()

    if failed:
        print(f"\n실패 {len(failed)}건 (미변경 — /캐릭터등록 재등록 필요):")
        for line in failed:
            print(f"- {line}")


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv[1:]))
