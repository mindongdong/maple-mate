# 핸드오프 — 단계 0+1 배포 작업 (Render, 다음 세션 인계)

> [deploy-plan.md](deploy-plan.md)의 **단계 0(약관 출처표시) + 단계 1(Render 배포)** 만 실행하는 콜드스타트 인계서.
> 로드맵·근거·수용량은 deploy-plan.md가 SSOT이고, **이 문서는 "어디서 시작해 무엇을 어떻게 만들고
> 무엇이 완료인가"** 에 집중한다. 복잡도 낮음 → `executor`(표준)로 충분. 단계 2/3·라이브 검증·
> Render 대시보드 설정은 **이 작업 밖**(§6·§8).

## 0. 먼저 읽을 것 (SSOT — 중복 금지, 경로로 참조)

- [deploy-plan.md](deploy-plan.md) §1·§3 — 배포 아키텍처·작업 근거(파일:라인). **본 핸드오프의 상위 문서.**
- [work-plan.md](work-plan.md) — 구현 완료 현황(Spike 0~Phase 5).
- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §7 — 출력/임베드 규칙(SSOT).
- 넥슨 약관 제6조④(출처표시 의무): [이용약관](https://openapi.nexon.com/ko/support/terms/).

## 1. 시작점 (git · 실행 · 환경)

- **현재 브랜치**: `phase-5-ops-summary` (main보다 3커밋 앞, **Phase 5 미머지**). 배포 작업은 Phase 5 코드(`error_log/summary.py`·운영요약 잡)에 의존.
- **새 브랜치**: `phase-5-ops-summary`가 main에 머지됐으면 **main에서**, 아직이면 **`phase-5-ops-summary`에서** 분기 → 권장명 `phase-6-deploy`.
- **로컬 실행**: `docker compose up -d`(Postgres :5433) → `uv run alembic upgrade head` → `uv run python -m maple_mate`.
- **테스트**: `uv run pytest` (실용 테스트 합의 — 순수 로직만 단위테스트, API mock).
- **환경변수**: [.env.example](../.env.example) 참조. 로컬은 `.env`, 운영은 Render 환경변수(§6).

## 2. 범위

**포함**: 단계 0(출처표시 1건) + 단계 1 필수 코드수정 5건(1-1~1-5). **에이전트가 코드로 완결 가능한 것만.**
**불포함**(§8): 단계 2 튜닝·단계 3 분산 / Render 대시보드·Discord 포털 설정 / 라이브 검증(봇 실가동 필요).

## 3. 확정 결정 (이 세션)

| 항목 | 결정 |
|---|---|
| 출처표시 위치 | **모든 데이터 임베드 푸터** (전 출력이 `embed=embed, file=file`라 PNG 표도 임베드 푸터 사용 — 이미지에 글자 안 새김) |
| 출처 문구 | 기존 푸터에 **` · NEXON Open API` 덧붙임**, 푸터 없으면 `NEXON Open API`. 예: `2026-06-08 · NEXON Open API` |
| DB URL 정규화 | **코드 자동 정규화** (`postgresql://`→`postgresql+asyncpg://`). Render 기본 URL 그대로 사용 |
| 빌드 방식 | **Dockerfile** (공식 uv 이미지 + uv.lock frozen) |
| 인프라 정의 | **render.yaml Blueprint** (서비스+DB+env 코드화) |
| DEV_GUILD_ID | **선택값화** (없으면 글로벌 동기화) — 테스트 갱신 동반 |

## 4. 작업 항목 (에이전트 실행)

### 0-1 출처표시 (제6조④)

- **무엇**: 넥슨 **결과 데이터를 표시하는** 임베드 푸터에 ` · NEXON Open API` 일괄 적용.
- **구현**: [embeds.py](../maple_mate/bot/embeds.py)에 상수 + 헬퍼 추가(예: `DATA_SOURCE = "NEXON Open API"`, `append_source(footer: str | None) -> str`). `make_embed`의 footer 합성에 반영 + **직접 `discord.Embed()` 만드는 발신처에도 동일 헬퍼 적용**.
- **적용 지점**(데이터 임베드): `/스펙`·`/아이템`([character/commands.py:184·276](../maple_mate/character/commands.py#L184)) · `/유니온`([union/commands.py:75·109](../maple_mate/union/commands.py#L109)) · `/스타포스`([history/commands.py:268](../maple_mate/history/commands.py#L268)) · `/잠재`([potential_commands.py:248](../maple_mate/history/potential_commands.py#L248)) · 썬데이·공지(`build_event_embeds`·`build_notice_embeds` [scheduler.py](../maple_mate/notification/scheduler.py)).
- **제외**(결과 데이터 아님): 운영요약(내부 error_log)·에러/검증/등록결과·`all_failed_embed`.
- **verify**: 각 명령 실제 임베드 푸터에 문구 노출. `uv run pytest` 그린(아래 테스트 갱신 포함).
- **테스트 영향**: [test_footer.py](../tests/test_footer.py)(헬퍼 추가 시) · [test_sunday_embed.py](../tests/test_sunday_embed.py)(썬데이 푸터 변경) — 단정문 갱신.

### 1-1 DEV_GUILD_ID 선택값화 🔴 (멀티서버 블로커)

- **무엇**: 운영 글로벌 명령 동기화가 막혀 있음 — 현재 `DEV_GUILD_ID` 필수라 빈 값이면 기동 거부. 선택값으로.
- **구현**: [config.py:22-25](../maple_mate/config.py#L22-L25) `_REQUIRED_INT_KEYS`에서 `DEV_GUILD_ID` 제거 → `Config.dev_guild_id: int | None`로 선택 파싱(값이 있으면 정수여야 하고, 잘못된 정수는 여전히 오류). [bot/core.py:34-41](../maple_mate/bot/core.py#L34-L41)은 `if self._dev_guild_id:`라 **None이면 글로벌** — 추가 변경 불필요.
- **verify**: `DEV_GUILD_ID` 미설정으로 `load_config` 성공 + 기동 시 "글로벌 동기화" 로그.
- **테스트 영향**: [test_config.py](../tests/test_config.py)(5개) — "DEV_GUILD_ID 없으면 성공·dev_guild_id=None" 케이스로 갱신.

### 1-2 PORT 환경변수

- **구현**: [main.py:29](../maple_mate/main.py#L29) `HTTP_PORT = int(os.environ.get("PORT", "8080"))` (`import os` 추가). HOST는 `0.0.0.0` 유지.
- **verify**: `PORT=10000` 환경에서 그 포트로 uvicorn 바인딩.

### 1-3 DATABASE_URL 정규화 (코드)

- **구현**: 순수함수 `normalize_db_url(url) -> str` 추가(`postgres://`·`postgresql://` → `postgresql+asyncpg://`, 이미 `+asyncpg`면 그대로). [database/core.py:21-23](../maple_mate/database/core.py#L21-L23) `make_engine`에서 적용(또는 config 로드 시).
- **verify**: `postgresql://u:p@h/db` 입력 → 엔진이 asyncpg 사용.
- **테스트 영향**: 순수함수라 단위테스트 추가(test_config.py 또는 신규 test_database.py).

### 1-4 tzdata 의존성

- **구현**: [pyproject.toml](../pyproject.toml) dependencies에 `"tzdata"` 추가 → `uv lock`. (슬림 컨테이너에서 `ZoneInfo("Asia/Seoul")` 크래시 방지.)
- **verify**: `uv.lock`에 tzdata 반영 · 컨테이너 빌드 후 스케줄러 기동 무오류.

### 1-5 Dockerfile + render.yaml

- **Dockerfile**: 공식 uv 이미지(`python3.12`) 기반, `uv sync --frozen`, 시작 = `uv run alembic upgrade head && uv run python -m maple_mate`(마이그레이션 후 기동; 유료 preDeploy 의존 회피).
- **render.yaml**: `web` 서비스(`env: docker`, `plan: starter`, `numInstances: 1`, `healthCheckPath: /health`) + `databases:` Postgres 1개. envVars: 시크릿 5종 `sync: false` + `DATABASE_URL`은 `fromDatabase`. `DEV_GUILD_ID`는 비움(글로벌).
- **verify**: `docker build` 로컬 성공 · render.yaml 스키마 유효 · 1-3 정규화와 조합되어 `fromDatabase`의 `postgresql://` 동작.

## 5. 테스트 방침

"실용 테스트"(순수 로직 단위테스트, API mock). 이 작업으로 **갱신/추가**할 것: `test_config.py`(1-1·1-3), `test_footer.py`·`test_sunday_embed.py`(0-1), 신규 `normalize_db_url` 테스트. 완료 기준 = `uv run pytest` 전부 그린.

## 6. 사람(운영자) 작업 — 에이전트 불가, 코드 PR 후

- **시크릿 생성**: `FERNET_MASTER_KEY` = `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- **Discord 포털**: 앱+봇 생성 → 토큰 확보 → **Public Bot** 켜기 → 초대 URL(스코프 `bot`+`applications.commands`, 권한 Send Messages·Embed Links) → 서버에 추가.
- **Render**: 레포 연결 → render.yaml Blueprint 적용 → 시크릿 5종 입력(`DISCORD_BOT_TOKEN`·`NEXON_APP_KEY`·`FERNET_MASTER_KEY`·`OPERATOR_TOKEN`·`ADMIN_CHANNEL_ID`) → `DEV_GUILD_ID` 비움.
- **라이브 검증**(봇 가동 후): `/잠재` G1 등업(`scripts/spike_potential.py`) · `/공지알림` baseline 1주기 · 운영요약 임베드(`scripts/trigger_ops_summary.py`).

## 7. 산출물 체크리스트 (완료 정의)

- [ ] 새 브랜치 `phase-6-deploy`에서 작업
- [ ] 0-1 출처표시 6개 명령 임베드 반영
- [ ] 1-1~1-4 코드 수정 + 테스트 갱신
- [ ] Dockerfile + render.yaml 추가
- [ ] `uv run pytest` 전부 그린
- [ ] 로컬 기동 확인: `DEV_GUILD_ID` 빈 값 → "글로벌 동기화" 로그 + docker Postgres 연결
- [ ] `docker build .` 성공
- [ ] 커밋(`feat:`/`chore:`) + main 대상 PR

## 8. 스코프 밖 / 주의

- **하지 말 것**: 단계 2 튜닝(스로틀·`to_thread`·쿨다운·prune·캐시)·단계 3 분산 — 별도 작업.
- **인접 리팩터 금지**(CLAUDE.md 외과적 변경) — 변경 라인은 0+1 작업에 직접 연결될 것.
- **커밋 금지 파일**: 루트 `기댓값/`(로컬 전용 검증 이미지)·`starforce-simulator-system.md` 등 untracked 로컬 파일.
- 운영요약 임베드에는 출처표시 **불필요**(넥슨 결과 데이터 아님 — 내부 error_log).
