"""FastAPI 앱 조립 (dispatch 의 main/api 격).

`api_router` 는 도메인별 `views.py` 의 라우터를 모으는 단일 지점이다. Phase 1 엔 도메인
HTTP 엔드포인트가 없어 비어 있고, 헬스체크만 노출한다.
Phase 4 추가 예: `from ..notification.views import router as sunday_router; api_router.include_router(sunday_router)`.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from ..dependencies import Deps
from ..notification.views import router as sunday_router

# 도메인 라우터 집합점. 도메인이 HTTP 를 노출하면 여기에 include_router 로 등록.
api_router = APIRouter()
api_router.include_router(sunday_router)  # 수동 썬데이 발송 POST /sunday/broadcast


def create_app(deps: Deps) -> FastAPI:
    app = FastAPI(title="maple-mate", docs_url=None, redoc_url=None)
    app.state.deps = deps  # 도메인 views 에서 request.app.state.deps 로 접근

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app
