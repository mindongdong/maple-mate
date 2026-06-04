"""단일 asyncio 진입점 (빌드 단위 #1).

discord.py 봇(게이트웨이)과 FastAPI(uvicorn)를 한 이벤트 루프에서 동시 기동.
실행: `uv run python -m maple_mate`
기동 순서: .env fail-fast 로딩 → 엔진/세션·넥슨·암호화 준비 → 봇 + uvicorn gather.
"""
from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn

from .bot.client import MapleMateBot
from .bot.deps import BotDeps
from .config import ConfigError, load_config
from .crypto import KeyCipher
from .db.engine import make_engine, make_session_factory
from .http.server import create_app
from .nexon.client import NexonClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("maple_mate")

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080


async def main(config) -> None:
    engine = make_engine(config.database_url)
    session_factory = make_session_factory(engine)
    nexon = NexonClient(config.nexon_app_key)
    cipher = KeyCipher(config.fernet_master_key)
    deps = BotDeps(config=config, session_factory=session_factory, nexon=nexon, cipher=cipher)

    bot = MapleMateBot(deps=deps, dev_guild_id=config.dev_guild_id)

    app = create_app()
    app.state.deps = deps  # Phase 4 HTTP 엔드포인트에서 사용
    server = uvicorn.Server(
        uvicorn.Config(app, host=HTTP_HOST, port=HTTP_PORT, log_level="info", loop="asyncio")
    )

    log.info("maple-mate 기동: discord 봇 + uvicorn(%s:%d) 동시 시작", HTTP_HOST, HTTP_PORT)
    server_task = asyncio.create_task(server.serve(), name="uvicorn")
    bot_task = asyncio.create_task(bot.start(config.discord_bot_token), name="discord-bot")
    tasks = {server_task, bot_task}
    try:
        # 둘 중 하나라도 끝나거나 실패하면 전체를 종료(한쪽만 살아남는 상태 방지).
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    finally:
        server.should_exit = True  # uvicorn graceful stop 신호
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await nexon.aclose()
        if not bot.is_closed():
            await bot.close()
        await engine.dispose()

    # 먼저 종료된 태스크의 예외를 전파 → 원인 로깅 + 프로세스 비정상 종료(exit!=0).
    for task in done:
        if not task.cancelled() and task.exception() is not None:
            raise task.exception()  # type: ignore[misc]


if __name__ == "__main__":
    try:
        config = load_config()  # fail-fast: 필수 키 누락 시 ConfigError
    except ConfigError as exc:
        print(f"[기동 거부] {exc}", file=sys.stderr)
        print("→ .env 의 필수 항목을 채운 뒤 다시 실행하세요 (.env.example 참고).", file=sys.stderr)
        sys.exit(1)
    try:
        asyncio.run(main(config))
    except KeyboardInterrupt:
        log.info("종료")
