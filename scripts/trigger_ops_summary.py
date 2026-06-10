"""운영 요약 임베드를 ADMIN_CHANNEL_ID 로 즉시 발송 (라이브 검증용, trigger_notice.py 패턴).

전날 error_log 를 fetch → aggregate → build → 발송하는 경로를 수동으로 실행한다.
`--no-prune` 옵션으로 prune 을 끌 수 있다(검증 중 데이터 보존).
봇 토큰으로 로그인, on_ready 에서 1회 실행 후 종료.

실행:
    uv run python -m scripts.trigger_ops_summary            # 발송 + prune
    uv run python -m scripts.trigger_ops_summary --no-prune # 발송만(prune 생략)
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta

import discord
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from maple_mate.config import load_config
from maple_mate.error_log import summary as ops_summary
from maple_mate.nexon.client import KST
from maple_mate.notification.scheduler import build_ops_summary_embed


async def main(no_prune: bool) -> None:
    config = load_config()
    engine = create_async_engine(config.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    client = discord.Client(
        intents=discord.Intents.default(),
        allowed_mentions=discord.AllowedMentions.none(),
    )

    @client.event
    async def on_ready() -> None:
        try:
            now = datetime.now(KST)
            rows = await ops_summary.fetch_yesterday_errors(session_factory, now)
            s = ops_summary.aggregate(rows)
            ref_date = (now - timedelta(days=1)).date()
            embed = build_ops_summary_embed(s, ref_date)

            channel_id = config.admin_channel_id
            channel = client.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await client.fetch_channel(channel_id)
                except discord.HTTPException as exc:
                    print(f"채널 해석 실패 (id={channel_id}): {exc}", file=sys.stderr)
                    return

            if embed is None:
                print("전날 요약 0건 — 발송 대상 없음.")
            else:
                await channel.send(embed=embed)  # type: ignore[union-attr]
                print(f"발송 완료 (채널 id={channel_id})")

            if no_prune:
                print("--no-prune: prune 생략.")
            else:
                pruned = await ops_summary.prune_old_errors(session_factory, now)
                print(f"prune 완료: {pruned}행 삭제.")
        finally:
            await engine.dispose()
            await client.close()

    await client.start(config.discord_bot_token)


if __name__ == "__main__":
    _no_prune = "--no-prune" in sys.argv
    asyncio.run(main(no_prune=_no_prune))
