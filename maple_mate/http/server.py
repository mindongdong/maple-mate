"""FastAPI 앱 (골격). Phase 1 은 헬스체크만. 수동 썬데이 발송 엔드포인트는 Phase 4(design §4)."""
from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="maple-mate", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # TODO(Phase 4): POST /sunday — Bearer(OPERATOR_TOKEN) 인증, sunday_alert 채널 즉시 발송.
    return app
