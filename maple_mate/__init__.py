"""maple-mate — 친구 그룹용 메이플스토리 디스코드 봇 (Phase 1 기반).

단일 프로세스: discord.py(봇 게이트웨이) + FastAPI(HTTP)를 한 asyncio 이벤트 루프에서 동시 기동.
이 패키지 __init__ 은 가벼워야 한다 (alembic env.py 가 models 만 임포트하므로 무거운 의존성 금지).
"""
