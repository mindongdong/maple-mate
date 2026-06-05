"""현재 `notice-event` 제목 전체 덤프 + 썬데이 매칭 표시 (작업지시서 #6).

지금 진행 중 이벤트에 썬데이가 떠 있는지 즉시 확인 — "썬데이 메이플" 양성 매칭 미실측
(docs/api/notice.md 잔류) 보완용. 넥슨 앱 키만 필요(봇 로그인 불필요).

실행: uv run python -m scripts.dump_events
"""
from __future__ import annotations

import asyncio

from maple_mate.config import load_config
from maple_mate.nexon.client import NexonClient
from maple_mate.notification.service import (
    extract_content_image,
    format_period,
    match_sunday,
)


async def main() -> None:
    config = load_config()
    async with NexonClient(config.nexon_app_key) as nexon:
        events = await nexon.notice_event()

        print(f"진행 중 이벤트 {len(events)}건 (✅ = 썬데이 매칭):\n")
        matched: list[dict] = []
        for event in events:
            title = event.get("title") or ""
            is_sunday = match_sunday(title)
            if is_sunday:
                matched.append(event)
            print(f"  {'✅' if is_sunday else '  '} {title}")

        print(f"\n썬데이 매칭: {len(matched)}건")
        for event in matched:
            period = format_period(event.get("date_event_start"), event.get("date_event_end"))
            notice_id = event.get("notice_id")
            banner = None
            if isinstance(notice_id, int):
                detail = await nexon.notice_event_detail(notice_id)
                banner = extract_content_image(detail.get("contents"))
            print(f"  - {event.get('title')}")
            print(f"    링크   : {event.get('url')}")
            print(f"    기간   : {period}")
            print(f"    썸네일 : {event.get('thumbnail_url')}")
            print(f"    배너   : {banner or '(상세 본문에 이미지 없음)'}")


if __name__ == "__main__":
    asyncio.run(main())
