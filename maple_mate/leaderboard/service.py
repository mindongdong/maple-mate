"""경험치 리더보드 페치·집계·prune·백필 (전달-무관). discord/apscheduler 비의존.

- fetch_and_store: 대상별 character/basic(ocid, D-1) → 스냅샷 upsert(미준비는 스킵, ADR-0020).
- backfill: 과거 ~8일 중 빈 날만 멱등 적재(매 실행 호출 — 캐릭터(ocid)별 공백 자가복구).
- build_rows: 순수 — (레벨, 레벨내 exp%) 내림차순 정렬·순위 부여·미준비 제외 카운트(_rank_key).
- live_levels/with_live_levels/append_live_point: 표시 레벨을 character/basic 라이브(최신)로 덮어쓰기.
- history_progress: 그래프용 캐릭터별 7일 진행도(레벨+exp%) 시계열(전달-무관).
- prune_old_snapshots: snapshot_date 가 90일 경과한 행 삭제(09:00 운영 잡 편승).

스냅샷 키 = (guild_id, discord_user_id, ocid, snapshot_date) — 캐릭터(ocid) 차원 포함(ADR-0018).
집계·매칭 키도 전부 ocid 다(labels = ocid → 표시 라벨) — 같은 유저의 캐릭터 N개가 한 판에 공존하는
`/내캐릭터 경험치`와 유저당 대표 1캐릭인 서버 리더보드가 같은 파이프라인을 쓴다.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..dependencies import Deps
from ..error_log import service as error_log
from ..nexon.errors import NexonAPIError, to_error_log_type
from ..registration.realm import Realm, realm_of
from ..registration.service import Target
from .models import ExpSnapshot

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 백필 일수(작업지시서 Q11) — 과거 ~8일 창. 매 실행 빈 날만 멱등 적재(realm 별 공백 자가복구).
BACKFILL_DAYS = 8
# 그래프 시계열 일수 — 최근 7일 진행도(레벨+exp%), 7일 전 대비 정규화.
HISTORY_DAYS = 7
# 스냅샷 보존 일수(작업지시서 Q12) — 09:00 운영 잡에 편승해 prune.
RETENTION_DAYS = 90


@dataclass(frozen=True)
class LeaderRow:
    """순위표 1행(전달 계층이 표로 렌더).

    ocid 는 라이브 레벨 덮어쓰기(with_live_levels)의 매칭 키(캐릭터 차원, ADR-0018 —
    `/내캐릭터`는 한 유저의 캐릭터 N행이라 유저 키로는 구분 불가). nickname 은 표시 라벨
    (서버=대표 닉, 내캐릭터=char_label). exp_rate 는 레벨 내 경험치 백분율(있을 때만
    'Lv.287 (45.2%)'). level·exp_rate 는 표시 시 character/basic 라이브 값으로 덮어써진다.
    """

    ocid: str
    rank: int
    nickname: str
    level: int
    exp_rate: float | None


def yesterday_kst(now: datetime) -> date:
    """발송 기준일 D-1(KST). 누적은 D-1 마감값(작업지시서 기준일 라벨)."""
    return now.astimezone(KST).date() - timedelta(days=1)


def snapshot_cutoff(now: datetime) -> date:
    """prune 기준일(오늘 KST − 90일). snapshot_date 가 이 값 **미만**인 행이 삭제 대상(순수)."""
    return now.astimezone(KST).date() - timedelta(days=RETENTION_DAYS)


# ── 페치·적재 (전달-무관) ───────────────────────────────────────────────────


async def _upsert_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    guild_id: int,
    discord_user_id: int,
    ocid: str,
    snapshot_date: date,
    realm: str,
    character_level: int,
    exp_rate: float | None,
) -> None:
    """character/basic 응답 1건 → (guild, user, ocid, date) 스냅샷 upsert(재실행 시 최신값 덮어씀).

    realm 은 캐릭터 world 에서 파생된 디스크리미넌트(본서버/챌린저스) — PK 에서 강등된 일반
    컬럼이라 set_ 에도 포함해 최신 판정을 따라간다(ADR-0018).
    """
    async with session_factory() as session:
        stmt = (
            pg_insert(ExpSnapshot)
            .values(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                ocid=ocid,
                snapshot_date=snapshot_date,
                realm=realm,
                character_level=character_level,
                exp_rate=exp_rate,
            )
            .on_conflict_do_update(
                index_elements=[
                    "guild_id",
                    "discord_user_id",
                    "ocid",
                    "snapshot_date",
                ],
                set_={
                    "realm": realm,
                    "character_level": character_level,
                    "exp_rate": exp_rate,
                },
            )
        )
        await session.execute(stmt)
        await session.commit()


async def _fetch_one_day(
    deps: Deps,
    target: Target,
    snapshot_date: date,
) -> bool:
    """대상 1명의 1일치 character/basic(date) 조회→upsert. 미준비는 False(스킵), 성공은 True.

    단일 소스 = character/basic — 레벨과 레벨 내 exp% 가 **같은 시점**(그날 마감) 값이라 그래프
    progress(레벨+exp%/100)의 두 성분이 정합한다(ADR-0020). 종전 주 소스 ranking/overall 의
    레벨은 하루 뒤처진 값(그날 아침 발표 = 전날 마감 집계)이라, 레벨업 날 exp% 리셋과 짝지어져
    가짜 하락점을 만들었다. 실패한 날은 행을 만들지 않는다 — 멱등 backfill 이 다음 실행에서 그
    빈 날을 재시도해 자가복구한다(exp_rate=None 행을 남기던 종전 구조는 결손이 영구였다).
    넥슨 장애(타임아웃·429·5xx)·앱키 실패만 error_log.record, 미준비(00009)는 조용히 스킵.
    """
    date_iso = snapshot_date.isoformat()
    try:
        basic = await deps.nexon.character_basic(target.ocid, date_iso)
    except NexonAPIError as exc:
        log_type = to_error_log_type(exc.error_class)
        if (
            log_type is not None
        ):  # 넥슨 가용성·앱키 실패만 적재(미준비/잘못된 파라미터는 제외)
            await error_log.record(
                deps.session_factory,
                error_type=log_type,
                command="경험치",
                guild_id=target.guild_id,
                discord_user_id=target.discord_user_id,
                target_ocid=target.ocid,
                detail=f"{date_iso} {exc.code}: {exc.message}"[:500],
            )
        return False
    raw_level = basic.get("character_level")
    if raw_level is None:  # 응답형 이상 → 그날 그 캐릭 제외(에러 아님)
        return False
    raw_rate = basic.get("character_exp_rate")
    try:
        exp_rate = float(raw_rate) if raw_rate is not None else None
    except (TypeError, ValueError):
        log.debug(
            "character_exp_rate 파싱 실패(exp_rate 생략) ocid=%s raw=%r",
            target.ocid,
            raw_rate,
        )
        exp_rate = None
    await _upsert_snapshot(
        deps.session_factory,
        guild_id=target.guild_id,
        discord_user_id=target.discord_user_id,
        ocid=target.ocid,
        snapshot_date=snapshot_date,
        realm=realm_of(
            target.world
        ).value,  # 캐릭터 world → realm 디스크리미넌트(ADR-0009)
        character_level=int(raw_level),
        exp_rate=exp_rate,
    )
    return True


async def fetch_and_store(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    date_iso: str,
) -> int:
    """대상 전원의 date 스냅샷 조회→upsert. 미준비로 건너뛴 대상 수(스킵 카운트) 반환."""
    snapshot_date = date.fromisoformat(date_iso)
    skipped = 0
    for target in targets:
        stored = await _fetch_one_day(deps, target, snapshot_date)
        if not stored:
            skipped += 1
    return skipped


async def _existing_dates(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    discord_user_id: int,
    ocid: str,
    dates: Sequence[date],
) -> set[date]:
    """캐릭터 1개(ocid)에 이미 적재된 snapshot_date 집합(백필 중복 콜 방지).

    멱등 판정 키 = 날짜×ocid(ADR-0018). ocid 가 캐릭터를 유일하게 집으므로 종전의 realm
    필터(dual-realm 대표가 서로의 빈 날을 가리는 구멍 방지)는 자연히 포섭된다.
    """
    async with session_factory() as session:
        stmt = select(ExpSnapshot.snapshot_date).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.discord_user_id == discord_user_id,
            ExpSnapshot.ocid == ocid,
            ExpSnapshot.snapshot_date.in_(list(dates)),
        )
        rows = (await session.execute(stmt)).scalars().all()
    return set(rows)


async def backfill(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    days: int = BACKFILL_DAYS,
) -> None:
    """과거 D-1~D-`days` 중 **빈 날만** 대상별로 적재(멱등 — 이미 있으면 건너뜀).

    매 실행 호출해도 안전하다(작업지시서 Q11 의 '첫 실행 1회' 게이트 폐기) — _existing_dates 가
    캐릭터(ocid)별로 이미 있는 날을 빼므로 정상 상태(8일 다 참)엔 넥슨 콜 0건이고, 빈 날(봇
    미가동·뒤늦게 추가된 캐릭터·일시 실패로 못 만든 행)만 채워 공백이 자가복구된다. 과거일도
    character/basic(date) 로 그날 마감 (레벨, exp%) 를 수집한다(_fetch_one_day 단일 경로,
    ADR-0020). 미준비·넥슨 장애는 _fetch_one_day 가 처리.
    """
    today = datetime.now(KST).date()
    dates = [today - timedelta(days=d) for d in range(1, days + 1)]
    for target in targets:
        existing = await _existing_dates(
            deps.session_factory,
            target.guild_id,
            target.discord_user_id,
            target.ocid,  # 멱등 판정 = 날짜×캐릭터(ADR-0018)
            dates,
        )
        for snapshot_date in dates:
            if snapshot_date in existing:
                continue
            await _fetch_one_day(deps, target, snapshot_date)


# ── 조회 + 순수 집계 ────────────────────────────────────────────────────────


async def latest_snapshot_date(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    ocids: Sequence[str],
    on_or_before: date,
    realm: Realm | None = None,
) -> date | None:
    """대상 캐릭터들의 가장 최근 스냅샷 일자(≤ on_or_before). 스냅샷 0건이면 None.

    넥슨 전일 데이터는 "다음날 오전 1시 이후" 생성이지만 경계가 soft 라(01:10 에도 미준비
    실측 — docs/api/README.md) 자정~생성 사이엔 D-1 행이 없다. 유니온의 D-2 폴백과 같은
    취지로, 게이트·표시 기준일을 특정 시각 가정 없이 '가장 최근 있는 날'로 낮춰 어떤
    시각에도 리더보드가 뜨게 한다(표시 레벨은 어차피 라이브 덮어쓰기라 신선도 무손실).
    """
    async with session_factory() as session:
        stmt = select(func.max(ExpSnapshot.snapshot_date)).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.ocid.in_(list(ocids)),
            ExpSnapshot.snapshot_date <= on_or_before,
        )
        if realm is not None:
            stmt = stmt.where(ExpSnapshot.realm == realm.value)
        return (await session.execute(stmt)).scalar()


async def snapshots_on(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    snapshot_date: date,
    realm: Realm | None = None,
) -> list[ExpSnapshot]:
    """길드의 특정 일자 스냅샷(순서 무관 — build_rows 가 정렬). realm 지정 시 그 realm 만(누수 0)."""
    async with session_factory() as session:
        stmt = select(ExpSnapshot).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.snapshot_date == snapshot_date,
        )
        if realm is not None:
            stmt = stmt.where(ExpSnapshot.realm == realm.value)
        return list((await session.execute(stmt)).scalars().all())


def _rank_key(level: int, exp_rate: float | None) -> tuple[int, float]:
    """통일 순위 키 — (레벨, 레벨 내 exp%). 임베드 순위판·그래프가 **한 공식**을 공유한다.

    레벨 1차, 같은 레벨이면 exp%(레벨 내 진행) 2차(exp_rate None 은 레벨 내 최하 -1.0). total_exp 는
    쓰지 않는다 — 그래프(progress=레벨+exp%/100)가 볼 수 없는 키라, 두 표시면을 한 공식으로 맞춘다.
    챌린저스 **버닝**(레벨 부스트)은 누적과 무관하게 레벨을 올려 total_exp 순위를 뒤집으므로, 레벨
    우선 키가 본서버(누적=레벨 단조)·챌린저스 모두 올바르고 그래프 순위와 일치한다(ADR-0011).
    """
    return (level, exp_rate if exp_rate is not None else -1.0)


def build_rows(
    today_snaps: Sequence[ExpSnapshot],
    *,
    labels: dict[str, str],
) -> tuple[list[LeaderRow], int]:
    """순수: 오늘 스냅샷을 (레벨, 레벨 내 exp%) 내림차순 정렬·순위 부여. (행, 미준비수) 반환.

    labels = ocid → 표시 라벨(서버=대표 닉, 내캐릭터=char_label) — 매칭 키가 캐릭터(ocid)라
    같은 유저의 캐릭터 N행이 공존한다(ADR-0018). 정렬 키 = `_rank_key`(레벨, exp%) — 임베드·그래프
    통일 공식. 같은 (레벨, exp%)면 안정 정렬로 입력 순서를 유지한다. 미준비 제외 카운트 =
    labels 중 today_snaps 에 없는 캐릭터 수.
    """
    ordered = sorted(
        today_snaps,
        key=lambda s: _rank_key(s.character_level, s.exp_rate),
        reverse=True,
    )
    rows = [
        LeaderRow(
            ocid=snap.ocid,
            rank=rank,
            nickname=labels.get(snap.ocid, "?"),
            level=snap.character_level,
            exp_rate=snap.exp_rate,  # character/basic 의 그날 마감 exp%(없으면 None)
        )
        for rank, snap in enumerate(ordered, start=1)
    ]
    ranked_ocids = {s.ocid for s in today_snaps}
    excluded = sum(1 for ocid in labels if ocid not in ranked_ocids)
    return rows, excluded


# ── 라이브 레벨(표시 전용 — character/basic 무지정=최신) ─────────────────────


async def live_levels(
    deps: Deps, targets: Sequence[Target]
) -> dict[str, tuple[int, float | None]]:
    """대상별 character/basic(date 무지정=최신) → {ocid: (레벨, exp%)}. 표시용 라이브 레벨.

    스냅샷(전일 D-1 마감)과 달리 character/basic 무지정은 **최신** 캐릭터 상태(현재 레벨·레벨 내 exp%)를
    준다 — 리더보드 표시값을 '오늘 현재'로 만든다(정렬·게이트·그래프 이력은 여전히 스냅샷 기반).
    best-effort: 호출/파싱 실패한 대상은 결과에서 빠져 호출측이 D-1 스냅샷으로 폴백한다.
    """
    out: dict[str, tuple[int, float | None]] = {}
    for target in targets:
        try:
            basic = await deps.nexon.character_basic(target.ocid)  # 무지정=최신
        except NexonAPIError as exc:
            log.debug(
                "character/basic 라이브 실패(D-1 폴백) ocid=%s: %s", target.ocid, exc
            )
            continue
        raw_level = basic.get("character_level")
        if raw_level is None:
            continue
        raw_rate = basic.get("character_exp_rate")
        try:
            rate = float(raw_rate) if raw_rate is not None else None
        except (TypeError, ValueError):
            rate = None
        out[target.ocid] = (int(raw_level), rate)
    return out


def with_live_levels(
    rows: Sequence[LeaderRow], live: dict[str, tuple[int, float | None]]
) -> list[LeaderRow]:
    """rows 의 레벨·exp% 를 live(ocid 키)로 덮어쓰고 (레벨, exp%) 재정렬·재순위(순수).

    live 에 없는 행(라이브 조회 실패)은 D-1 스냅샷 값을 유지한다. 순위(rank)는 덮어쓴 값 기준으로
    1부터 재부여 — 임베드 표시 순위가 라이브 레벨과 일치한다(`_rank_key` 통일 공식, 그래프와 동일).
    """
    updated = [
        replace(r, level=live[r.ocid][0], exp_rate=live[r.ocid][1])
        if r.ocid in live
        else r
        for r in rows
    ]
    updated.sort(key=lambda r: _rank_key(r.level, r.exp_rate), reverse=True)
    return [replace(r, rank=i) for i, r in enumerate(updated, start=1)]


def append_live_point(
    series: dict[str, list[tuple[date, float | None]]],
    labels: dict[str, str],
    live: dict[str, tuple[int, float | None]],
    today: date,
) -> dict[str, list[tuple[date, float | None]]]:
    """7일 이력 시계열 끝에 오늘(today) 라이브 점을 붙인다(표시 전용, 미저장).

    labels = ocid → 표시 라벨(series 의 키), live = ocid → (레벨, exp%). progress =
    레벨 + exp%/100(스냅샷 이력과 동일 지표). 라이브 조회 실패거나 exp% None 이면
    (today, None) 으로 선이 끊긴다(이력과 동일 규칙). 라벨로 ocid 를 못 찾으면 None.
    """
    label_to_ocid = {label: ocid for ocid, label in labels.items()}
    out: dict[str, list[tuple[date, float | None]]] = {}
    for label, pts in series.items():
        lv = live.get(label_to_ocid.get(label, ""))
        point = lv[0] + lv[1] / 100 if lv is not None and lv[1] is not None else None
        out[label] = [*pts, (today, point)]
    return out


async def history_progress(
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    labels: dict[str, str],
    today: date,
    *,
    days: int = HISTORY_DAYS,
    realm: Realm | None = None,
) -> dict[str, list[tuple[date, float | None]]]:
    """그래프용 캐릭터별 최근 `days`일 연속 진행도 시계열(라벨 → [(날짜, progress|None), ...]).

    labels = ocid → 표시 라벨. 조회도 그 ocid 들만(수집이 전 캐릭터로 확장돼도 표시 대상은
    호출측이 정한다 — 서버 리더보드는 대표 ocid, `/내캐릭터`는 내 캐릭 전부. ADR-0018).
    `today` = 기준일(D-1, '어제')이고 그래프 오른쪽 끝. 표시 구간은 `today-(days-1)..today`
    (어제를 포함한 최근 7일, baseline 은 보통 D-7). 각 표시일 d 의 progress =
    character_level + exp_rate/100(예: Lv.287 45.2% → 287.452) — 레벨업을 넘어 연속이라 렌더러가
    이를 7일 전 대비로 정규화한다. exp_rate 가 없거나 그날 스냅샷이 없으면 None(선 끊김).
    절대 progress 만 반환한다(정규화·일평균은 render_progress_graph 가 한다). labels 의
    캐릭터 전원을 키로 낸다.
    """
    display_dates = [today - timedelta(days=d) for d in range(days - 1, -1, -1)]
    async with session_factory() as session:
        stmt = select(
            ExpSnapshot.ocid,
            ExpSnapshot.snapshot_date,
            ExpSnapshot.character_level,
            ExpSnapshot.exp_rate,
        ).where(
            ExpSnapshot.guild_id == guild_id,
            ExpSnapshot.ocid.in_(list(labels)),
            ExpSnapshot.snapshot_date >= display_dates[0],
            ExpSnapshot.snapshot_date <= display_dates[-1],
        )
        if realm is not None:
            stmt = stmt.where(ExpSnapshot.realm == realm.value)
        rows = (await session.execute(stmt)).all()

    by_ocid: dict[str, dict[date, float]] = {}
    for ocid, snap_date, level, exp_rate in rows:
        if exp_rate is None:  # exp_rate 결손이면 진행도 미산출(그날 선 끊김)
            continue
        by_ocid.setdefault(ocid, {})[snap_date] = level + exp_rate / 100

    series: dict[str, list[tuple[date, float | None]]] = {}
    for ocid, label in labels.items():
        progress_by_date = by_ocid.get(ocid, {})
        series[label] = [(d, progress_by_date.get(d)) for d in display_dates]
    return series


# ── prune (09:00 운영 잡 편승) ───────────────────────────────────────────────


async def prune_old_snapshots(
    session_factory: async_sessionmaker[AsyncSession],
    now: datetime,
    days: int = RETENTION_DAYS,
) -> int:
    """snapshot_date 가 90일 경과한 exp_snapshot 행 단일 DELETE. 삭제 행수 반환(작업지시서 Q12)."""
    cutoff = now.astimezone(KST).date() - timedelta(days=days)
    async with session_factory() as session:
        result = await session.execute(
            delete(ExpSnapshot).where(ExpSnapshot.snapshot_date < cutoff)
        )
        await session.commit()
        return result.rowcount or 0
