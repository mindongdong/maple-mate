"""테스트 채널에 최근 공지 N개를 직접 발송 (라이브 발송 눈으로 확인).

`/공지알림` 잡과 동일한 렌더링 경로(`parse_notices` → `build_notice_embeds` →
`broadcast_notices` 10개 청킹)를 그대로 태워, 임베드 모양·등록일 포맷·발송을 실데이터로 점검한다.
넥슨은 최신순(date 내림차순)으로 주므로 앞에서 N개를 떼어 "가장 최근 N개"로 발송한다.
**notice_state 마커는 건드리지 않는다**(폴링 신규판정과 무관 — 발송 모양 점검용, trigger_sunday 와 동일).

실행:
    uv run python -m scripts.trigger_notice <채널ID> [notice|update] [개수]
    예) uv run python -m scripts.trigger_notice 123456789012345678          # 공지 최근 3개
        uv run python -m scripts.trigger_notice 123456789012345678 update 5  # 업데이트 최근 5개
"""
from __future__ import annotations

import asyncio
import sys

import discord

from maple_mate.config import load_config
from maple_mate.nexon.client import NexonClient
from maple_mate.notification import notice_service
from maple_mate.notification.scheduler import broadcast_notices


async def main(channel_id: int, category: str, count: int) -> None:
    config = load_config()
    nexon = NexonClient(config.nexon_app_key)
    client = discord.Client(
        intents=discord.Intents.default(),
        allowed_mentions=discord.AllowedMentions.none(),
    )

    @client.event
    async def on_ready() -> None:
        try:
            fetch = nexon.notice_update if category == "update" else nexon.notice
            label = "업데이트" if category == "update" else "공지"
            raw = await fetch()
            # 최신순 응답에서 앞 N개(가장 최근) → parse 가 오름차순으로 정렬(발송도 오래된→최신).
            items = notice_service.parse_notices(raw[:count])
            if not items:
                print(f"{label} 0건 — 발송할 항목이 없습니다.")
                return
            print(f"{label} 최근 {len(items)}건 발송:")
            for item in items:
                print(f"  [{item.notice_id}] {item.date_text} — {item.title}")
            sent = await broadcast_notices(client, [(0, channel_id)], items)
            print(f"발송 완료: {sent}개 채널")
        finally:
            await nexon.aclose()
            await client.close()

    await client.start(config.discord_bot_token)


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 4:
        print(
            "usage: uv run python -m scripts.trigger_notice <채널ID> [notice|update] [개수]",
            file=sys.stderr,
        )
        raise SystemExit(2)
    cid = int(sys.argv[1])
    cat = sys.argv[2] if len(sys.argv) >= 3 else "notice"
    if cat not in ("notice", "update"):
        print("두 번째 인자는 notice 또는 update 여야 합니다.", file=sys.stderr)
        raise SystemExit(2)
    cnt = int(sys.argv[3]) if len(sys.argv) == 4 else 3
    asyncio.run(main(cid, cat, cnt))
