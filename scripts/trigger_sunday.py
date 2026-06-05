"""테스트 채널에 썬데이 임베드를 직접 발송 (라이브 발송 눈으로 확인, 작업지시서 #6).

`broadcast_sunday` 를 지정 채널에 직접 호출(수동 HTTP 엔드포인트 대용). 현재 진행 중
썬데이가 없으면(`select_sunday_events` 0건) 합성 샘플 이벤트로 임베드 모양만 확인한다.
주차 dedup·마킹은 건드리지 않는다(발송 모양 점검용).

실행: uv run python -m scripts.trigger_sunday <채널ID>
"""
from __future__ import annotations

import asyncio
import sys

import discord

from maple_mate.config import load_config
from maple_mate.nexon.client import NexonClient
from maple_mate.notification import service
from maple_mate.notification.scheduler import broadcast_sunday
from maple_mate.notification.service import SundayEvent

_SAMPLE = SundayEvent(
    title="썬데이 메이플 (샘플)",
    url="https://maplestory.nexon.com/News/Event",
    thumbnail_url=None,
    period_text="샘플 기간 — 라이브 발송 모양 확인용",
)


async def main(channel_id: int) -> None:
    config = load_config()
    nexon = NexonClient(config.nexon_app_key)
    client = discord.Client(
        intents=discord.Intents.default(),
        allowed_mentions=discord.AllowedMentions.none(),
    )

    @client.event
    async def on_ready() -> None:
        try:
            events = await service.select_sunday_events(nexon)
            if not events:
                print("매칭 이벤트 0건 → 합성 샘플 임베드로 발송")
                events = [_SAMPLE]
            sent = await broadcast_sunday(client, [(0, channel_id)], events)
            print(f"발송 완료: {sent}개 채널, 이벤트 {len(events)}건")
        finally:
            await nexon.aclose()
            await client.close()

    await client.start(config.discord_bot_token)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: uv run python -m scripts.trigger_sunday <채널ID>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(main(int(sys.argv[1])))
