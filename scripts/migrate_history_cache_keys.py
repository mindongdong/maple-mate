"""이력 캐시 이름표 1회 이전 — ocid 앵커 → 계정 식별자(account_key) (ADR-0024).

마이그레이션 c8e2a4f6b1d9 는 `history_cache.ocid` 컬럼을 `account_key` 로 이름만 바꾼다. 기존 행의 값은
아직 "최초 등록 캐릭터 ocid"(옛 앵커)라 새 이름표(개인 키 HMAC)와 매칭되지 않는다. 이 스크립트가 옮긴다.

1. 키가 있는 등록(길드·DM 전부)마다 옛 앵커(= min(created_at, ocid) 캐릭터)와 새 이름표(복호화한 키의
   HMAC)를 짝짓는다. 키 원문은 메모리에서만 쓰고 출력·저장하지 않는다.
2. 한 앵커를 **한 계정(이름표 1개)만** 쓰면 그 앵커의 행을 새 이름표로 복사한다(이미 있으면 새 행 우선 —
   배포 후 새로 받은 데이터가 더 최신). 같은 사람이 같은 키로 여러 서버에 등록한 경우도 이름표가 같아 포함.
3. 한 앵커를 **서로 다른 계정이 함께** 쓰면(기록 혼입 의심) 옮기지 않는다 — 그 유저들은 다음 조회 때 새로 받는다.
4. 처리한 옛 앵커 행(옮긴 것·혼입 의심 모두)은 지운다. 어느 등록과도 안 이어진 옛 행은 400일 prune 에 맡긴다.

한계: 다른 계정 키로 **교체한 적이 있는** 유저의 옛 앵커 행에 이전 계정 데이터가 섞였는지는 구분할 수 없다
(키 교체 시각을 기록하지 않음). 해당 유저는 `/캐릭터목록` 키 삭제 후 재등록하면 새 이름표로 새로 받는다.

기본은 dry-run(계획만 출력). `--apply` 를 줘야 DB 에 반영한다. 재실행해도 안전하다(옮긴 앵커 행은 지워짐).

실행:
    uv run python -m scripts.migrate_history_cache_keys          # dry-run
    uv run python -m scripts.migrate_history_cache_keys --apply  # 반영
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from maple_mate.config import load_config
from maple_mate.database.core import make_engine, make_session_factory
from maple_mate.history.models import HistoryCache
from maple_mate.registration.models import Character, Registration
from maple_mate.security.crypto import InvalidToken, KeyCipher


@dataclass(frozen=True)
class Plan:
    moves: dict[str, str]  # 옛 앵커 ocid → 새 이름표(계정 1개만 쓰는 앵커)
    shared: set[str]  # 서로 다른 계정이 함께 쓰는 앵커(혼입 의심 — 옮기지 않음)


def plan_moves(pairs: Iterable[tuple[str, str]]) -> Plan:
    """(옛 앵커, 새 이름표) 쌍들 → 이전 계획(순수함수 — 단위테스트 대상)."""
    keys_by_anchor: dict[str, set[str]] = defaultdict(set)
    for anchor, account_key in pairs:
        keys_by_anchor[anchor].add(account_key)
    moves = {a: next(iter(ks)) for a, ks in keys_by_anchor.items() if len(ks) == 1}
    shared = {a for a, ks in keys_by_anchor.items() if len(ks) > 1}
    return Plan(moves=moves, shared=shared)


def anchors_by_registration(
    characters: Iterable[Character],
) -> dict[tuple[int, int], str]:
    """(guild, user) → 옛 앵커 ocid. 이력 대상 해석(get_history_targets)과 같은 규칙(순수)."""
    best: dict[tuple[int, int], Character] = {}
    for c in characters:
        k = (c.guild_id, c.discord_user_id)
        if k not in best or (c.created_at, c.ocid) < (
            best[k].created_at,
            best[k].ocid,
        ):
            best[k] = c
    return {k: c.ocid for k, c in best.items()}


async def main(apply: bool) -> None:
    config = load_config()
    cipher = KeyCipher(config.fernet_master_key)
    engine = make_engine(config.database_url)
    session_factory = make_session_factory(engine)
    try:
        async with session_factory() as session:
            regs = (
                await session.execute(
                    select(
                        Registration.guild_id,
                        Registration.discord_user_id,
                        Registration.api_key_encrypted,
                    ).where(Registration.api_key_encrypted.is_not(None))
                )
            ).all()
            anchors = anchors_by_registration(
                (await session.scalars(select(Character))).all()
            )
            row_counts = dict(
                (
                    await session.execute(
                        select(HistoryCache.account_key, func.count()).group_by(
                            HistoryCache.account_key
                        )
                    )
                ).all()
            )

        pairs: list[tuple[str, str]] = []
        undecryptable = 0
        for guild_id, user_id, encrypted in regs:
            anchor = anchors.get((guild_id, user_id))
            if anchor is None:  # 캐릭터 없는 등록 — 캐시된 적 없음
                continue
            try:
                pairs.append((anchor, cipher.account_key(cipher.decrypt(encrypted))))
            except InvalidToken:
                undecryptable += 1
        plan = plan_moves(pairs)

        moved_rows = sum(row_counts.get(a, 0) for a in plan.moves)
        shared_rows = sum(row_counts.get(a, 0) for a in plan.shared)
        print(
            f"키 등록 {len(regs)}건 · 앵커 연결 {len(pairs)}건 ({'반영' if apply else 'dry-run'})"
        )
        print(
            f"- 이전: 앵커 {len(plan.moves)}개 · 캐시 {moved_rows}행 → 계정 식별자로 복사"
        )
        print(
            f"- 혼입 의심(미이전·삭제): 앵커 {len(plan.shared)}개 · 캐시 {shared_rows}행"
        )
        if undecryptable:
            print(f"- 복호화 실패(건너뜀): {undecryptable}건 — 마스터 키 확인 필요")

        if apply:
            async with session_factory() as session:
                for anchor, account_key in plan.moves.items():
                    copy = select(
                        literal(account_key),
                        HistoryCache.type,
                        HistoryCache.date,
                        HistoryCache.payload,
                        HistoryCache.fetched_at,
                    ).where(HistoryCache.account_key == anchor)
                    await session.execute(
                        pg_insert(HistoryCache)
                        .from_select(
                            ["account_key", "type", "date", "payload", "fetched_at"],
                            copy,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["account_key", "type", "date"]
                        )
                    )
                done = set(plan.moves) | plan.shared
                if done:
                    await session.execute(
                        delete(HistoryCache).where(HistoryCache.account_key.in_(done))
                    )
                await session.commit()
            print("반영 완료.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv[1:]))
