"""경험치 리더보드 Discord 잡 어댑터 + 명령 본체 공유 (작업지시서 빌드 단위 #5).

전달-무관 service 위에 Discord 발송과 스케줄을 얹는 얇은 어댑터. `build_payload` 는 `/경험치`
명령과 매일 10시 잡이 공유하는 산출물 빌더(표 PNG + 7일 그래프 PNG). `run_leaderboard_job` 은
exp_alert 채널 0개면 스킵(넥슨 콜 없음) → 길드별 (첫 실행)백필 → D-1 적재 → build_payload →
_resolve_channel 발송(부분실패 앱로그, 썬데이 패턴). prune 는 09:00 운영 잡에 편승.
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import discord

from ..bot import leaderboard_image
from ..bot.embeds import DATA_SOURCE
from ..dependencies import Deps
from ..nexon.client import KST
from ..notification import service as channel_service
from ..notification.scheduler import _resolve_channel
from ..registration.service import get_targets
from . import service

log = logging.getLogger(__name__)

# 표시 임계(작업지시서 Q10): 랭킹 등재 2명 미만이면 발송/표시 생략.
MIN_RANKED = 2

# 첨부 파일명(임베드 image 매칭).
_TABLE_FILE = "leaderboard.png"
_GRAPH_FILE = "leaderboard_graph.png"


@dataclass(frozen=True)
class LeaderboardPayload:
    """발송 산출물(잡·명령 공유). 표·그래프 PNG 원시 바이트 + 임베드 + 기준일.

    `discord.File` 은 `BytesIO` 를 소비하므로 채널당 신규 파일 객체가 필요하다.
    `to_files()` 로 매 발송마다 fresh `discord.File` 쌍을 생성한다.
    """

    table_png: bytes
    graph_png: bytes
    embed: discord.Embed
    ref_date: date

    def to_files(self) -> list[discord.File]:
        """발송용 `discord.File` 쌍을 새로 만든다(BytesIO 소비 방지)."""
        return [
            discord.File(io.BytesIO(self.table_png), filename=_TABLE_FILE),
            discord.File(io.BytesIO(self.graph_png), filename=_GRAPH_FILE),
        ]


def _footer_text(ref_date: date) -> str:
    """기준일 라벨(작업지시서 파생 결정) — 누적은 D-1 마감값임을 명시 + 넥슨 출처표시."""
    return f"기준: 어제({ref_date:%m/%d}) KST · {DATA_SOURCE}"


def _build_embed(ref_date: date) -> discord.Embed:
    """순위표 + 그래프를 담을 임베드(표를 메인 이미지로, 그래프는 같은 메시지 추가 첨부)."""
    embed = discord.Embed(
        title="📊 경험치 리더보드",
        description="등록 캐릭터들의 누적 경험치 순위와 어제 하루 획득량이에요.",
        color=discord.Color.from_rgb(255, 140, 0),
    )
    embed.set_image(url=f"attachment://{_TABLE_FILE}")
    embed.set_footer(text=_footer_text(ref_date))
    return embed


async def build_payload(
    bot: discord.Client, deps: Deps, guild_id: int
) -> LeaderboardPayload | None:
    """get_targets → 오늘(D-1)/어제(D-2) 스냅샷 → build_rows → 2명 미만이면 None → 표·그래프 렌더.

    `/경험치` 명령과 매일 10시 잡이 공유한다(작업지시서 #5). 렌더는 to_thread(이벤트 루프 비차단).
    """
    targets = await get_targets(deps.session_factory, guild_id)
    nicknames = {t.discord_user_id: t.nickname for t in targets}

    now = datetime.now(KST)
    ref_date = service.yesterday_kst(now)  # D-1(누적 마감)
    prev_date = ref_date - timedelta(days=1)  # D-2(어제 Δ 계산용)

    today_snaps = await service.snapshots_on(deps.session_factory, guild_id, ref_date)
    prev_snaps = await service.snapshots_on(deps.session_factory, guild_id, prev_date)

    rows, _excluded = service.build_rows(today_snaps, prev_snaps, nicknames=nicknames)
    if len(rows) < MIN_RANKED:  # 등재 2명 미만 → 발송/표시 생략(Q10)
        return None

    series = await service.history_deltas(
        deps.session_factory, guild_id, nicknames, ref_date
    )

    table_buf = await asyncio.to_thread(leaderboard_image.render_table, rows, ref_date)
    graph_buf = await asyncio.to_thread(
        leaderboard_image.render_delta_graph, series, ref_date
    )
    return LeaderboardPayload(
        table_png=table_buf.getvalue(),
        graph_png=graph_buf.getvalue(),
        embed=_build_embed(ref_date),
        ref_date=ref_date,
    )


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
        targets = await get_targets(session_factory, guild_id)
        if not targets:
            continue
        if not await service.has_snapshots(session_factory, guild_id):
            await service.backfill(deps, guild_id, targets)  # 첫 실행 1회 백필(Q11)
        skipped = await service.fetch_and_store(
            deps, guild_id, targets, ref_date.isoformat()
        )
        if skipped:
            log.info("경험치 적재: 길드 %s 미등재/미준비 %d명 제외", guild_id, skipped)

    # 길드별 payload 를 메모이제이션: 같은 길드에 exp_alert 채널이 여러 개여도
    # DB 조회 + PNG 렌더를 한 번만 수행하고 결과를 재사용한다.
    payloads: dict[int, LeaderboardPayload | None] = {}
    sent = 0
    for guild_id, channel_id in channels:
        if guild_id not in payloads:
            payloads[guild_id] = await build_payload(bot, deps, guild_id)
        payload = payloads[guild_id]
        if payload is None:  # 등재 2명 미만 → 그 채널 생략(Q10)
            continue
        channel = await _resolve_channel(bot, guild_id, channel_id)
        if channel is None:
            continue
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
    log.info("경험치 발송: 채널 %d/%d", sent, len(channels))
