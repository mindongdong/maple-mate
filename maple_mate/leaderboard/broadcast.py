"""경험치 리더보드 Discord 잡 어댑터 + 명령 본체 공유 (작업지시서 빌드 단위 #5).

전달-무관 service 위에 Discord 발송과 스케줄을 얹는 얇은 어댑터. `build_payload` 는 `/경험치`
명령과 매일 10시 잡이 공유하는 산출물 빌더(최근 7일 레벨 추이 그래프 PNG). `run_leaderboard_job` 은
exp_alert 채널 0개면 스킵(넥슨 콜 없음) → 길드별 (첫 실행)백필 → D-1 적재 → build_payload →
_resolve_channel 발송(부분실패 앱로그, 썬데이 패턴). prune 는 09:00 운영 잡에 편승.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import discord

from ..bot import leaderboard_image
from ..bot.embeds import DATA_SOURCE
from ..dependencies import Deps
from ..nexon.client import KST
from ..notification import service as channel_service
from ..notification.scheduler import _resolve_channel
from ..registration.realm import Realm
from ..registration.service import Target, get_targets
from . import service

log = logging.getLogger(__name__)

# 표시 임계(작업지시서 Q10): 랭킹 등재 2명 미만이면 발송/표시 생략.
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


def _footer_text(ref_date: date) -> str:
    """기준일 라벨(작업지시서 파생 결정) — 누적은 D-1 마감값임을 명시 + 넥슨 출처표시."""
    return f"기준: 어제({ref_date:%m/%d}) KST · {DATA_SOURCE}"


def _embed_title(realm: Realm) -> str:
    """리더보드 제목 — 본서버 '📈 경험치 리더보드', 챌린저스 '🏆 챌린저스 경험치 리더보드'(결정 9)."""
    prefix = "🏆 챌린저스" if realm is Realm.CHALLENGERS else "📈"
    return f"{prefix} 경험치 리더보드 — 최근 7일 레벨 추이"


def _build_embed(ref_date: date, realm: Realm = Realm.MAIN) -> discord.Embed:
    """7일 레벨 추이 그래프를 담을 임베드(그래프를 메인 이미지로). 챌린저스는 🏆 제목."""
    embed = discord.Embed(
        title=_embed_title(realm),
        description=(
            "등록 캐릭터들의 최근 7일 레벨 진행이에요. 각 점은 그날의 레벨(경험치%),"
            " 범례는 하루 평균 진행 속도예요."
        ),
        color=discord.Color.from_rgb(255, 140, 0),
    )
    embed.set_image(url=f"attachment://{_GRAPH_FILE}")
    embed.set_footer(text=_footer_text(ref_date))
    return embed


async def build_payload(
    bot: discord.Client, deps: Deps, guild_id: int, realm: Realm = Realm.MAIN
) -> LeaderboardPayload | None:
    """get_targets(realm) → realm D-1 스냅샷 → 등재 2명 미만이면 None → 7일 추이 그래프.

    `/경험치` 명령과 매일 10시 잡이 공유한다(작업지시서 #5). realm 별로 완전 분리(결정 8) —
    본서버/챌린저스 각각 독립 MIN_RANKED 게이트. 렌더는 to_thread(이벤트 루프 비차단).
    """
    targets = await get_targets(deps.session_factory, guild_id, realm=realm)
    nicknames = {t.discord_user_id: t.nickname for t in targets}

    now = datetime.now(KST)
    ref_date = service.yesterday_kst(now)  # D-1(누적 마감)
    prev_date = ref_date - timedelta(days=1)  # D-2(어제 Δ 계산용)

    today_snaps = await service.snapshots_on(
        deps.session_factory, guild_id, ref_date, realm
    )
    prev_snaps = await service.snapshots_on(
        deps.session_factory, guild_id, prev_date, realm
    )

    # rows 는 등재 카운트 게이트로만 쓴다(미렌더). build_rows = 등재 인원의 단일 출처(순위·미등재 제외).
    rows, _excluded = service.build_rows(today_snaps, prev_snaps, nicknames=nicknames)
    if len(rows) < MIN_RANKED:  # 등재 2명 미만 → 발송/표시 생략(Q10)
        return None

    series = await service.history_progress(
        deps.session_factory, guild_id, nicknames, ref_date, realm=realm
    )
    graph_buf = await asyncio.to_thread(
        leaderboard_image.render_progress_graph, series, ref_date
    )
    return LeaderboardPayload(
        graph_png=graph_buf.getvalue(),
        embed=_build_embed(ref_date, realm),
        ref_date=ref_date,
    )


async def refresh_guild(
    deps: Deps,
    guild_id: int,
    targets: Sequence[Target],
    ref_date: date,
) -> int:
    """길드 1개의 (첫 실행)백필 → D-1 적재 공통 블록. 스킵 카운트 반환.

    `run_leaderboard_job` 과 `ensure_guild_data` 가 함께 사용한다.
    """
    session_factory = deps.session_factory
    if not await service.has_snapshots(session_factory, guild_id):
        await service.backfill(deps, guild_id, targets)  # 첫 실행 1회 백필(Q11)
    return await service.fetch_and_store(deps, guild_id, targets, ref_date.isoformat())


async def _all_realm_targets(session_factory, guild_id: int) -> list[Target]:
    """본서버 + 챌린저스 대표 합집합(적재용). 각 대상은 자기 realm 으로 저장된다(결정 8).

    dual-realm 유저는 두 realm 대표 둘 다 포함된다(PK 에 realm 이 있어 충돌 없음, ADR-0009).
    """
    main = await get_targets(session_factory, guild_id, realm=Realm.MAIN)
    chal = await get_targets(session_factory, guild_id, realm=Realm.CHALLENGERS)
    return [*main, *chal]


async def ensure_guild_data(deps: Deps, guild_id: int) -> None:
    """`/경험치` 온디맨드 부트스트랩: D-1 스냅샷이 없으면 백필+적재해서 즉시 표시 가능하게 한다.

    D-1 이 이미 있으면 빠른 no-op. exp_alert 를 켜지 않아도 명령 한 번으로 데이터가 뜨도록
    `run_leaderboard_job` 의 첫 실행 경로를 /경험치 명령에서도 재현한다(두 realm 대상 모두 적재).
    """
    now = datetime.now(KST)
    ref_date = service.yesterday_kst(now)
    if await service.has_snapshot_on(deps.session_factory, guild_id, ref_date):
        return  # D-1 이미 있음 → 아무 것도 안 함
    targets = await _all_realm_targets(deps.session_factory, guild_id)
    if targets:
        await refresh_guild(deps, guild_id, targets, ref_date)


async def run_leaderboard_job(bot: discord.Client, deps: Deps) -> None:
    """매일 10시 잡: exp_alert 채널 0개면 스킵 / 길드별 (첫 실행)백필 → D-1 적재 → 발송."""
    session_factory = deps.session_factory
    channels = await channel_service.enabled_exp_channels(session_factory)
    if not channels:
        log.info("경험치 잡 스킵: 알림 켠 채널 없음(넥슨 호출 안 함)")
        return

    now = datetime.now(KST)
    ref_date = service.yesterday_kst(now)
    guild_ids = {guild_id for guild_id, _ in channels}

    for guild_id in guild_ids:
        targets = await _all_realm_targets(session_factory, guild_id)
        if not targets:
            continue
        skipped = await refresh_guild(deps, guild_id, targets, ref_date)
        if skipped:
            log.info("경험치 적재: 길드 %s 미등재/미준비 %d명 제외", guild_id, skipped)

    # (길드, realm)별 payload 를 메모이제이션: 같은 길드에 채널이 여러 개여도 DB 조회 + PNG
    # 렌더를 realm 당 한 번만 수행한다. 리더보드는 realm 별 2개 완전 분리(결정 8) — 한 채널에
    # 본서버·챌린저스 둘 다(각각 MIN_RANKED 게이트 통과 시) 발송한다.
    payloads: dict[tuple[int, Realm], LeaderboardPayload | None] = {}
    sent = 0
    for guild_id, channel_id in channels:
        ready: list[LeaderboardPayload] = []
        for realm in (Realm.MAIN, Realm.CHALLENGERS):
            key = (guild_id, realm)
            if key not in payloads:
                payloads[key] = await build_payload(bot, deps, guild_id, realm)
            if payloads[key] is not None:
                ready.append(payloads[key])
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
    log.info("경험치 발송: %d건 (채널 %d)", sent, len(channels))
