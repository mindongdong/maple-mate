"""경험치 리더보드 Discord 잡 어댑터 + 명령 본체 공유 (작업지시서 빌드 단위 #5).

전달-무관 service 위에 Discord 발송과 스케줄을 얹는 얇은 어댑터. `build_payload` 는 `/경험치`
명령과 매일 10시 잡이 공유하는 산출물 빌더(최근 7일 레벨 추이 그래프 PNG). `run_leaderboard_job` 은
채널·개인 구독자 0이면 스킵(넥슨 콜 없음) → 길드별 멱등 백필 → D-1 적재 → build_payload →
채널 발송 + 개인 DM(부분실패 앱로그, 썬데이 패턴, ADR-0017). prune 는 09:00 운영 잡에 편승.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import discord

from ..bot import leaderboard_image
from ..bot.dm import send_dm
from ..bot.embeds import DATA_SOURCE
from ..dependencies import Deps
from ..nexon.client import KST
from ..notification import service as channel_service
from ..notification.scheduler import _resolve_channel
from ..registration.realm import Realm
from ..registration.service import Target, get_all_character_targets, get_targets
from . import service

log = logging.getLogger(__name__)

# 표시 임계(작업지시서 Q10): D-1 스냅샷 보유 2명 미만이면 발송/표시 생략.
MIN_RANKED = 2

# 첨부 파일명(임베드 image 매칭).
_GRAPH_FILE = "leaderboard_graph.png"


@dataclass(frozen=True)
class LeaderboardPayload:
    """발송 산출물(잡·명령 공유). 7일 레벨 추이 그래프 PNG 원시 바이트 + 임베드 + 기준일.

    `discord.File` 은 `BytesIO` 를 소비하므로 채널당 신규 파일 객체가 필요하다.
    `to_files()` 로 매 발송마다 fresh `discord.File` 을 생성한다.
    """

    graph_png: bytes
    embed: discord.Embed
    ref_date: date

    def to_files(self) -> list[discord.File]:
        """발송용 `discord.File` 을 새로 만든다(BytesIO 소비 방지)."""
        return [discord.File(io.BytesIO(self.graph_png), filename=_GRAPH_FILE)]


def _footer_text(now_date: date) -> str:
    """기준일 라벨 — 표시 레벨이 character/basic 라이브(오늘 현재)임을 명시 + 넥슨 출처표시(ADR-0011)."""
    return f"기준: 오늘({now_date:%m/%d}) 현재 · {DATA_SOURCE}"


def _embed_title(realm: Realm) -> str:
    """리더보드 제목 — 본서버 '📈 경험치 리더보드', 챌린저스 '🏆 챌린저스 경험치 리더보드'(결정 9)."""
    prefix = "🏆 챌린저스" if realm is Realm.CHALLENGERS else "📈"
    return f"{prefix} 경험치 리더보드"


# 순위판 메달(Top3) + 임베드·그래프 공통 표기 상한(상위 10명 — 동일 순위 소스로 같은 10명).
_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_TOP_N = 10


def _level_label(level: int, exp_rate: float | None) -> str:
    """순위판 레벨 표기 — exp% 보강이 있으면 'Lv.287 (79%)', 없으면 'Lv.287'(ADR-0005 그레이스풀)."""
    if exp_rate is None:
        return f"Lv.{level}"
    return f"Lv.{level} ({min(round(exp_rate), 99)}%)"


def _rank_line(row: service.LeaderRow) -> str:
    """임베드 순위 1행(위치) — 메달 · **닉** · 레벨(exp%)만(ADR-0011)."""
    badge = _MEDALS.get(row.rank, f"`{row.rank}.`")
    return f"{badge} **{row.nickname}** — {_level_label(row.level, row.exp_rate)}"


def _build_embed(
    rows: Sequence[service.LeaderRow], now_date: date, title: str | None = None
) -> discord.Embed:
    """순위판(라이브 레벨 Top10) 텍스트 + 7일 추이 그래프 임베드. 제목 미지정 = 본서버 리더보드."""
    ranking = "\n".join(_rank_line(r) for r in rows[:_TOP_N])
    embed = discord.Embed(
        title=title if title is not None else _embed_title(Realm.MAIN),
        description=ranking,
        color=discord.Color.from_rgb(255, 140, 0),
    )
    embed.set_image(url=f"attachment://{_GRAPH_FILE}")
    embed.set_footer(text=_footer_text(now_date))
    return embed


async def build_targets_payload(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    *,
    labels: dict[str, str],
    title: str,
    min_ranked: int,
    realm: Realm | None = None,
) -> LeaderboardPayload | None:
    """Target 리스트 → D-1 스냅샷 게이트 → 라이브 레벨 덮어쓰기 → Top10 순위판+7일 추이 그래프.

    서버 리더보드(`build_payload`)와 `/내캐릭터 경험치`가 공유하는 코어(ADR-0018). labels =
    ocid → 표시 라벨. 수집이 등록 전 캐릭터로 확장돼도(결정 5) 스냅샷을 targets 의 (user, ocid)
    쌍으로 필터하므로 표시 대상은 호출측이 정한다. **표시 레벨은 character/basic 라이브(오늘
    현재)** 로 덮어쓰고, 그래프 끝에도 오늘 라이브 점을 붙여 임베드·그래프가 모두 '현재'로
    일치한다(ADR-0011). 정렬·게이트·이력은 스냅샷 기반 유지. 렌더는 to_thread(루프 비차단).
    """
    now = datetime.now(KST)
    ref_date = service.yesterday_kst(now)  # D-1(스냅샷 이력 끝)
    today = now.date()

    # 스냅샷은 캐릭터(ocid) 단위로 쌓인다 — 표시 대상 캐릭터의 행만 남긴다.
    pairs = {(t.discord_user_id, t.ocid) for t in targets}

    def _mine(snaps: Sequence) -> list:
        return [s for s in snaps if (s.discord_user_id, s.ocid) in pairs]

    today_snaps = _mine(
        await service.snapshots_on(deps.session_factory, guild_id, ref_date, realm)
    )

    # rows = D-1 스냅샷 보유 캐릭터의 단일 출처(순위·미준비 제외) — 게이트 + 임베드 순위판의 베이스.
    rows, _excluded = service.build_rows(today_snaps, labels=labels)
    if len(rows) < min_ranked:  # 스냅샷 수 미달 → 발송/표시 생략
        return None

    # 표시 레벨을 라이브로(character/basic 무지정=최신). 실패 대상은 D-1 스냅샷 폴백.
    ranked_ocids = {r.ocid for r in rows}
    live = await service.live_levels(
        deps, [t for t in targets if t.ocid in ranked_ocids]
    )
    display_rows = service.with_live_levels(rows, live)

    # 그래프: 7일 이력(스냅샷) + 오늘 라이브 점 → 끝점이 임베드 순위와 같은 '현재'.
    series = await service.history_progress(
        deps.session_factory, guild_id, labels, ref_date, realm=realm
    )
    series = service.append_live_point(series, labels, live, today)
    # 그래프도 임베드와 동일한 상위 _TOP_N 만 그 순위 순서로 그린다(단일 순위 소스 = display_rows).
    # dict 삽입 순서 = 순위 순서라 렌더러가 1위에 팔레트 선두색을 준다(구조적 일치, 렌더러는 재정렬 안 함).
    # 단, 7일 내내 exp% 결손이라 그릴 점이 0개인 상위권 캐릭은 순위판엔 뜨지만 그래프 라인은 없다(드묾).
    top_labels = [r.nickname for r in display_rows[:_TOP_N]]
    series = {label: series[label] for label in top_labels if label in series}
    graph_buf = await asyncio.to_thread(
        leaderboard_image.render_progress_graph, series, ref_date
    )
    return LeaderboardPayload(
        graph_png=graph_buf.getvalue(),
        embed=_build_embed(display_rows, today, title),
        ref_date=ref_date,
    )


async def build_payload(
    bot: discord.Client, deps: Deps, guild_id: int, realm: Realm = Realm.MAIN
) -> LeaderboardPayload | None:
    """서버 리더보드 payload — get_targets(realm) = **대표 캐릭터 행만** 표시(결과 불변, ADR-0018).

    `/경험치` 명령과 매일 10시 잡이 공유한다(작업지시서 #5). realm 별로 완전 분리(결정 8) — 각각
    독립 MIN_RANKED 게이트. 수집은 등록 전 캐릭터로 확장됐지만(결정 5) 표시는 유저당 대표 1캐릭
    유지 — 코어의 (user, ocid) 필터가 나머지 캐릭터 행을 걸러낸다.
    """
    targets = await get_targets(deps.session_factory, guild_id, realm=realm)
    return await build_targets_payload(
        deps,
        guild_id,
        targets,
        labels={t.ocid: t.nickname for t in targets},
        title=_embed_title(realm),
        min_ranked=MIN_RANKED,
        realm=realm,
    )


async def refresh_guild(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    ref_date: date,
) -> int:
    """길드 1개의 빈 과거일 백필 → D-1 적재 공통 블록. 스킵 카운트 반환.

    `backfill` 은 멱등(이미 있는 날만 건너뜀)이라 매 실행 호출한다 — 봇 미가동일이나 뒤늦게
    추가된 realm(챌린저스)의 공백이 매 잡마다 자가복구된다(정상 상태 넥슨 0콜). 이어 D-1 을
    무조건 재적재해 어제 마감값을 신선화한다. `run_leaderboard_job` 과 `ensure_guild_data` 공용.
    """
    await service.backfill(
        deps, guild_id, targets
    )  # 빈 과거일 채움(멱등 — 정상 상태 0콜)
    return await service.fetch_and_store(deps, guild_id, targets, ref_date.isoformat())


async def ensure_guild_data(
    deps: Deps, guild_id: int, realm: Realm = Realm.MAIN
) -> None:
    """`/경험치` 온디맨드: 그 realm **등록 전 캐릭터**의 빈 과거일 백필(그래프 이력 공백 메움).

    수집 대상 = 등록 전 캐릭터(ADR-0018 결정 5 — `/내캐릭터 경험치`의 캐릭별 추이 재료).
    표시 레벨은 build_payload 가 character/basic(무지정=최신)으로 **라이브** 조회하므로 명령 시점
    '현재 갱신'은 그쪽이 담당한다 — 여기선 `backfill`(멱등)로 7일 그래프 이력의 공백(봇 미가동일·
    뒤늦게 등록된 캐릭터)만 채운다(정상 상태 넥슨 0콜). 그 realm 캐릭터가 없으면 no-op.
    """
    targets = await get_all_character_targets(deps.session_factory, guild_id, realm)
    if targets:
        await service.backfill(deps, guild_id, targets)


async def _ready_payloads(
    bot: discord.Client,
    deps: Deps,
    guild_id: int,
    payloads: dict[tuple[int, Realm], LeaderboardPayload | None],
) -> list[LeaderboardPayload]:
    """그 길드의 발송 가능한 realm payload 목록(본서버 → 챌린저스). (길드, realm)별 메모이즈.

    같은 길드에 채널·구독자가 여럿이어도 DB 조회 + PNG 렌더를 realm 당 한 번만 수행한다.
    리더보드는 realm 별 2개 완전 분리(결정 8) — 각각 MIN_RANKED 게이트를 통과한 것만 담는다.
    """
    ready: list[LeaderboardPayload] = []
    for realm in (Realm.MAIN, Realm.CHALLENGERS):
        key = (guild_id, realm)
        if key not in payloads:
            payloads[key] = await build_payload(bot, deps, guild_id, realm)
        if payloads[key] is not None:
            ready.append(payloads[key])
    return ready


async def run_leaderboard_job(bot: discord.Client, deps: Deps) -> None:
    """매일 10시 잡: 채널·구독자 0이면 스킵 / 길드별 멱등 백필 → D-1 적재 → 채널 발송 + 개인 DM.

    채널 발송(channel_settings.exp_alert)과 병행해 개인 DM 구독자(notification_subscription
    kind=exp)에게도 같은 산출물을 DM 한다(ADR-0017). 경험치는 길드별 리더보드라 (guild, user)별로
    보낸다(공지·썬데이의 글로벌 디듀프와 달리 디듀프 없음). payload 는 채널과 공유(추가 페치 0).
    """
    session_factory = deps.session_factory
    channels = await channel_service.enabled_exp_channels(session_factory)
    dm_subs = await channel_service.dm_subscribers(
        session_factory, channel_service.KIND_EXP
    )
    if not channels and not dm_subs:
        log.info("경험치 잡 스킵: 알림 켠 채널·구독자 없음(넥슨 호출 안 함)")
        return

    now = datetime.now(KST)
    ref_date = service.yesterday_kst(now)
    # 적재 대상 길드 = 채널 길드 ∪ 개인 구독자 길드(구독자만 있는 길드도 신선화).
    guild_ids = {guild_id for guild_id, _ in channels} | {
        guild_id for guild_id, _ in dm_subs
    }

    for guild_id in guild_ids:
        # 수집 = 등록 전 캐릭터(realm 무관 — 각 캐릭터가 자기 realm 으로 저장됨, ADR-0018 결정 5).
        targets = await get_all_character_targets(session_factory, guild_id)
        if not targets:
            continue
        skipped = await refresh_guild(deps, guild_id, targets, ref_date)
        if skipped:
            log.info("경험치 적재: 길드 %s 미준비 %d명 제외", guild_id, skipped)

    payloads: dict[tuple[int, Realm], LeaderboardPayload | None] = {}

    # 채널 발송
    sent = 0
    for guild_id, channel_id in channels:
        ready = await _ready_payloads(bot, deps, guild_id, payloads)
        if not ready:  # 두 realm 모두 등재 2명 미만 → 그 채널 생략(Q10)
            continue
        channel = await _resolve_channel(bot, guild_id, channel_id)
        if channel is None:
            continue
        for payload in ready:  # 본서버 → 챌린저스 순(있는 것만)
            try:
                await channel.send(embed=payload.embed, files=payload.to_files())
                sent += 1
            except discord.HTTPException as exc:  # 발송 실패는 앱로그만(썬데이 패턴)
                log.warning(
                    "경험치 발송 실패 (guild=%s channel=%s): %s",
                    guild_id,
                    channel_id,
                    exc,
                )

    # 개인 DM 발송(길드별 — 다른 길드 = 다른 리더보드라 user 디듀프 없음).
    dm_sent = 0
    for guild_id, user_id in dm_subs:
        for payload in await _ready_payloads(bot, deps, guild_id, payloads):
            if await send_dm(
                bot, user_id, embed=payload.embed, files=payload.to_files()
            ):
                dm_sent += 1
    log.info(
        "경험치 발송: 채널 %d건 (채널 %d) · 개인 DM %d건 (구독 %d)",
        sent,
        len(channels),
        dm_sent,
        len(dm_subs),
    )
