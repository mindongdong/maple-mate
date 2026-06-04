# 아키텍처 — 도메인 주도(DDD) 폴더 구조

> [Netflix/dispatch](https://github.com/Netflix/dispatch)의 구조 철학을 차용. **레이어가 아니라 도메인으로**
> 나누고, 각 도메인은 일관된 역할의 파일들을 가진 **수직 슬라이스**다. 단, dispatch가 HTTP 단일 전달인 데 비해
> maple-mate는 **전달 표면이 둘**(Discord 슬래시 = 주력, FastAPI HTTP = 보조)이라 도메인 로직을
> 전달-무관(`service.py`)으로 두고 그 위에 얇은 어댑터(`commands.py`/`views.py`)를 얹는다.

## 핵심 원칙

1. **도메인 = 패키지.** 한 비즈니스 도메인(`registration`, `history`, `notification`, `error_log`)이 한 폴더.
2. **`service.py`는 전달-무관.** discord/FastAPI 타입을 임포트하지 않는다. 입력은 평범한 값(+`Deps` 구성요소),
   출력은 결과 객체(`@dataclass`). 그래서 Discord 명령과 HTTP 엔드포인트가 같은 로직을 공유한다.
3. **전달 어댑터는 얇게.** `commands.py`(Discord)·`views.py`(FastAPI)는 입력 파싱 → `service` 호출 → 렌더링만.
4. **FastAPI는 1급.** `api/core.py`의 `create_app` + `api_router`가 HTTP 앱을 조립한다(곁다리 아님).
5. **단일 프로세스.** `main.py`가 봇과 uvicorn을 한 asyncio 루프에서 동시 기동(한쪽 실패 시 양쪽 정리).

## 폴더 구조

```
maple_mate/
  main.py            # composition root: .env→Deps 조립 + 봇/uvicorn 동시 기동
  __main__.py        # `python -m maple_mate` → main.main 위임
  config.py          # .env fail-fast 로딩(Config.from_env 순수함수)
  dependencies.py    # Deps 컨테이너(config, session_factory, nexon, cipher) — 두 전달 계층이 공유

  database/core.py   # 선언적 Base + async engine/session factory
  security/crypto.py # Fernet 개인 키 암복호
  nexon/             # 외부 API 통합: client.py(httpx+스로틀+재시도) · errors.py(코드→분류)

  api/core.py        # FastAPI 앱 조립 + api_router(도메인 views 집합점) + /health
  bot/               # Discord 전달 인프라: core.py(게이트웨이/트리/동기화) · embeds.py(출력 헬퍼)

  registration/      # ★ 도메인 (Phase 1, full slice)
    models.py        #   ORM (Base 상속)
    service.py       #   전달-무관 로직 (resolve_ocid·verify_and_encrypt_key·upsert·register)
    commands.py      #   /등록 Discord 어댑터 (service 호출)
  history/           # 이력류 (Phase 3) — 현재 models.py + cache.py(TTL 순수함수)
  notification/      # 공지/썬데이 (Phase 4) — 현재 models.py
  error_log/         # 운영 관측 (Phase 5) — 현재 models.py

  alembic/           # env.py가 각 도메인 models 임포트 → Base.metadata 등록
```

도메인 파일 역할(dispatch 관례, 필요할 때만 추가): `models.py`(ORM/스키마) · `service.py`(로직/데이터 접근) ·
`commands.py`(Discord) · `views.py`(FastAPI 라우터) · `flows.py`(다단계 오케스트레이션) · `scheduled.py`(스케줄 작업) ·
`enums.py`.

## 확장 방법 (다음 Phase가 따를 패턴)

- **새 도메인 추가:** `maple_mate/<domain>/` 폴더 생성 → `models.py`(있으면) → `service.py`(로직) →
  필요한 전달 어댑터. ORM이 새로 생기면 `alembic/env.py`에 `import maple_mate.<domain>.models` 한 줄 추가 후
  `uv run alembic revision --autogenerate -m "..."`.
- **새 슬래시 명령:** 도메인의 `commands.py`에 `setup(bot)`에서 `@bot.tree.command` 추가 →
  `bot/core.py._register_commands`에서 그 `setup` 호출. 로직은 반드시 `service.py`에.
- **새 HTTP 엔드포인트:** 도메인의 `views.py`에 `APIRouter` 정의 →
  `api/core.py`의 `api_router.include_router(...)`로 등록. (예: Phase 4 수동 썬데이 `POST`)
- **공유 로직:** discord/http 양쪽이 쓰면 `service.py`에 두고 두 어댑터가 호출.

## 실행 / 검증

```bash
docker compose up -d db                 # 로컬 Postgres(5433)
uv sync                                 # 의존성(py3.12)
uv run alembic upgrade head             # 5테이블
uv run python -m maple_mate             # 봇 + uvicorn(:8080) 동시 기동
uv run pytest                           # 순수 단위테스트(Nexon/Discord mock)
```
