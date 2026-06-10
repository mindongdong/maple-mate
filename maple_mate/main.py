"""Composition root + 단일 asyncio 진입점 (빌드 단위 #1).

.env fail-fast 로딩 → 엔진/세션·넥슨·암호화를 `Deps` 로 조립 → discord 봇 + FastAPI(uvicorn)를
한 이벤트 루프에서 동시 기동. 실행: `uv run python -m maple_mate`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import uvicorn

from .api.core import create_app
from .bot.core import MapleMateBot
from .config import Config, ConfigError, load_config
from .database.core import make_engine, make_session_factory
from .dependencies import Deps
from .nexon.client import NexonClient
from .security.crypto import KeyCipher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("maple_mate")

HTTP_HOST = "0.0.0.0"
# 운영(Render 등)은 $PORT 를 주입한다. 없으면 로컬 기본 8080.
HTTP_PORT = int(os.environ.get("PORT", "8080"))


def build_deps(config: Config) -> tuple[Deps, object]:
    """Config → Deps + engine(정리용). 봇/HTTP 가 공유할 의존성 컨테이너 구성."""
    engine = make_engine(config.database_url)
    session_factory = make_session_factory(engine)
    nexon = NexonClient(config.nexon_app_key, throttle=config.nexon_throttle)
    cipher = KeyCipher(config.fernet_master_key)
    deps = Deps(
        config=config, session_factory=session_factory, nexon=nexon, cipher=cipher
    )
    return deps, engine


async def serve(config: Config) -> None:
    deps, engine = build_deps(config)
    bot = MapleMateBot(deps=deps, dev_guild_id=config.dev_guild_id)
    app = create_app(deps)
    app.state.bot = bot  # 수동 썬데이 HTTP 핸들러가 broadcast 에 쓸 봇 레퍼런스(#1)
    server = uvicorn.Server(
        uvicorn.Config(
            app, host=HTTP_HOST, port=HTTP_PORT, log_level="info", loop="asyncio"
        )
    )

    log.info(
        "maple-mate 기동: discord 봇 + uvicorn(%s:%d) 동시 시작", HTTP_HOST, HTTP_PORT
    )
    server_task = asyncio.create_task(server.serve(), name="uvicorn")
    bot_task = asyncio.create_task(
        bot.start(config.discord_bot_token), name="discord-bot"
    )
    tasks = {server_task, bot_task}
    try:
        # 둘 중 하나라도 끝나거나 실패하면 전체를 종료(한쪽만 살아남는 상태 방지).
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    finally:
        server.should_exit = True  # uvicorn graceful stop 신호
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await deps.nexon.aclose()
        if not bot.is_closed():
            await bot.close()
        await engine.dispose()

    for task in done:
        if not task.cancelled() and task.exception() is not None:
            raise task.exception()  # type: ignore[misc]


def main() -> None:
    try:
        config = load_config()  # fail-fast: 필수 키 누락 시 ConfigError
    except ConfigError as exc:
        print(f"[기동 거부] {exc}", file=sys.stderr)
        print(
            "→ .env 의 필수 항목을 채운 뒤 다시 실행하세요 (.env.example 참고).",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        asyncio.run(serve(config))
    except KeyboardInterrupt:
        log.info("종료")
