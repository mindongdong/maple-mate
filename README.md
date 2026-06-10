# maple-mate

친구 그룹용 메이플스토리 디스코드 봇 (discord.py + FastAPI 단일 프로세스).

## 개발 루프

```bash
docker compose up -d              # 로컬 Postgres (호스트 :5433)
uv run alembic upgrade head       # 스키마 마이그레이션
uv run pytest                     # 오프라인 테스트 (live 마커 기본 제외)
uv run ruff check . && uv run ruff format --check .   # 린트·포맷 (CI 와 동일)
```

로컬 봇 실행은 `.env` 에 `DEV_GUILD_ID` 를 채우면 길드 커맨드가 즉시 동기화된다.

배포: **PR → CI 그린 → main 머지 → Render 자동배포** (`render.yaml`, autoDeploy).
