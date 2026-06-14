# maple-mate

친구 그룹용 메이플스토리 디스코드 봇 (discord.py + FastAPI 단일 프로세스).

## 한 줄 실행 (앱+DB 전체)

```bash
cp .env.example .env              # 최초 1회 — 시크릿 5종을 채운다(없으면 기동 거부)
docker compose up --build         # db + app(봇·FastAPI·스케줄러) 동시 기동
```

`app` 컨테이너가 `alembic upgrade head` → 봇 기동까지 자동 처리한다. `/health` 는 `localhost:8080`.

## 개발 루프 (호스트에서 직접 실행)

```bash
docker compose up -d db           # 로컬 Postgres만 (호스트 :5433)
uv run alembic upgrade head       # 스키마 마이그레이션
uv run pytest                     # 오프라인 테스트 (live 마커 기본 제외)
uv run ruff check . && uv run ruff format --check .   # 린트·포맷 (CI 와 동일)
```

로컬 봇 실행은 `.env` 에 `DEV_GUILD_ID` 를 채우면 길드 커맨드가 즉시 동기화된다.

배포: **PR → CI 그린 → main 머지 → Render 자동배포** (`render.yaml`, autoDeploy).
