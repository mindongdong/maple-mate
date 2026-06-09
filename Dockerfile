# 공식 uv 이미지(Python 3.12, slim) — uv.lock 고정으로 재현 가능한 빌드.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# 1) 의존성만 먼저 설치 — 소스 변경이 의존성 레이어를 무효화하지 않도록 분리.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 2) 앱 소스 + alembic 설정/마이그레이션.
COPY . .

# 마이그레이션 적용 후 봇 기동(유료 preDeploy 회피, 단일 인스턴스라 동시성 충돌 없음).
# DATABASE_URL(postgresql://)은 코드/alembic 이 asyncpg 로 정규화한다.
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync python -m maple_mate"]
