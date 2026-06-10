"""봇 가동 중인 서버의 수동 썬데이 HTTP 엔드포인트를 호출 (라이브 검증, 작업지시서 #5).

POST http://localhost:8080/sunday/broadcast 에 Bearer 토큰 + JSON 바디(제목·링크·기간)를
보내고 응답 {sent,total} 을 출력한다. trigger_notice.py 패턴. 봇 + uvicorn 이 떠 있어야
실제 발송이 일어난다(sunday_alert 켠 테스트 채널로 1회 눈 확인). 잘못된 토큰/빈 제목으로
401·422 도 이 도구로 확인할 수 있다.

실행:
    uv run python -m scripts.trigger_sunday "<제목>" ["<링크>"] ["<기간>"] ["<이미지URL>"]
    예) uv run python -m scripts.trigger_sunday "썬데이 메이플 (테스트)" \\
            "https://maplestory.nexon.com/News/Event" "6/9 ~ 6/15" \\
            "https://ssl.nexon.com/.../banner.jpg"
"""

from __future__ import annotations

import sys

import httpx

from maple_mate.config import load_config

URL = "http://localhost:8080/sunday/broadcast"


def main(title: str, link: str | None, period: str | None, image: str | None) -> None:
    config = load_config()
    body: dict[str, str] = {"title": title}
    if link:
        body["link"] = link
    if period:
        body["period"] = period
    if image:
        body["image"] = image
    resp = httpx.post(
        URL, json=body, headers={"Authorization": f"Bearer {config.operator_token}"}
    )
    print(f"HTTP {resp.status_code}: {resp.text}")


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 5:
        print(
            'usage: uv run python -m scripts.trigger_sunday "<제목>" ["<링크>"] ["<기간>"] ["<이미지URL>"]',
            file=sys.stderr,
        )
        raise SystemExit(2)
    arg_title = sys.argv[1]
    arg_link = sys.argv[2] if len(sys.argv) >= 3 else None
    arg_period = sys.argv[3] if len(sys.argv) >= 4 else None
    arg_image = sys.argv[4] if len(sys.argv) == 5 else None
    main(arg_title, arg_link, arg_period, arg_image)
