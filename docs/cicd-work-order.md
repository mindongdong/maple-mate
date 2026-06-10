# 작업지시서 — CI/CD 구축 (GitHub Actions + Render)

> [cicd-handoff.md](cicd-handoff.md)의 미확정 결정(D1~D6)을 그릴링 세션(2026-06-09)에서 전부 확정한
> **실행용 SSOT**. 핸드오프는 배경·근거, 이 문서는 "확정된 대로 무엇을 만드는가"에 집중한다.

> **✅ 구현 완료 (2026-06-10)** — PR #12 squash 머지(main `bac8b4b`). 실제 작업 기록과 지시서 대비 편차는 **§6 완료 기록** 참조.
> 남은 것은 §4 운영자 작업: **branch protection 은 2026-06-10 기준 아직 미설정**(API 확인 — PR #12 는 보호 룰 없이 머지됨),
> Render 서비스도 미생성이라 배포 실증은 Render Blueprint 설정 후 진행.

## 0. 시작점 (그릴링 세션 갱신 — 핸드오프 대비 정정)

- **선행 PR #11 = MERGED** (squash → `origin/main` `5cafcfb`). 핸드오프의 "PR #11 미머지"는 **stale**.
- 로컬 `phase-6-deploy`(=`b3f10c1`)는 squash 머지로 내용이 main 에 반영된 **죽은 브랜치** → 폐기.
- **새 브랜치**: 최신 `origin/main`(`5cafcfb`)을 fetch → 거기서 **`phase-7-cicd`** 분기.
- 빌드 위에 얹는 구조: Render 가 main 을 이미 autoDeploy 중([../render.yaml](../render.yaml)). 빠진 건 머지 전 게이트(CI)뿐.

## 1. 확정 결정 (그릴링 세션)

| # | 결정 | 확정 |
|---|---|---|
| D1 | CD 게이팅 | **A안 + branch protection + admin 우회 허용**. `render.yaml` 무변경. `deploy.yml`·Deploy Hook·시크릿 **없음**. → [ADR-0003](adr/0003-cd-gating-via-branch-protection.md) |
| D2 | 마이그레이션 검증 | **`alembic upgrade head` + `alembic check`** (둘 다 blocking). downgrade 왕복 **제외**(prod 미사용). 빈 Postgres:16 service container |
| D3 | 린트/포맷 | **ruff `E,F,I` + `ruff format` 강제**. 1회 `chore: adopt ruff` 커밋(11 자동수정 + 82파일 포맷, 로직 불변). mypy **제외**(점진) |
| D4 | Docker 빌드 CI | **생략**(Render 가 빌드). `paths` 필터 빌드도 안 함 |
| D5 | 커버리지 | **완전 생략**. pytest-cov 미추가 |
| D6 | 트리거 | `pull_request:[main]` + `push:[main]` + `concurrency{cancel-in-progress}` |

> **CONTEXT.md 변경 없음** — CI/CD 용어(CI·게이트·branch protection)는 봇 도메인 언어가 아니라 인프라 일반 용어. CONTEXT.md 는 도메인 글로사리이므로 추가하지 않는다.

## 2. 작업 항목

### 2-1 `.github/workflows/ci.yml` 🔴 핵심

- **트리거**(D6): `pull_request: {branches:[main]}` + `push: {branches:[main]}`, `concurrency: {group: ci-${{github.ref}}, cancel-in-progress: true}`.
- **공통 셋업**: `actions/checkout` → `astral-sh/setup-uv`(`enable-cache: true`) → `uv sync --frozen`. Python 은 pyproject 핀(3.12).
- **job: lint**(D3): `uv run ruff check .` + `uv run ruff format --check .`.
- **job: test**: `uv run pytest`(오프라인 — service 불필요. `addopts="-m 'not live'"`로 live 제외).
- **job: migrations**(D2): `services: {postgres: {image: postgres:16, env: POSTGRES_PASSWORD…, options: --health-cmd pg_isready 대기}}` → `DATABASE_URL=postgresql://postgres:…@localhost:5432/postgres`(raw `postgresql://`로 주입해 [env.py](../maple_mate/alembic/env.py)의 `normalize_db_url`→asyncpg 정규화를 실연결로 검증) → `uv run alembic upgrade head` → `uv run alembic check`.
- **verify**(임시 결함 주입): PR 브랜치에 ① 실패 테스트 ② 깨진 마이그레이션 ③ 린트 위반을 **각각 1회 커밋** → 해당 잡이 빨강으로 PR 머지를 막는지 PR 체크 히스토리에서 확인 → **머지 전 되돌림**(main 오염 없음).

### 2-2 ruff 표준화 — `pyproject.toml` + 1회 정규화

- `[dependency-groups].dev` 에 `ruff` 핀 추가 → `uv lock`.
- `[tool.ruff]`: `target-version = "py312"`, `line-length`(기본 88 또는 현행 코드에 맞춰 결정), `[tool.ruff.lint] select = ["E","F","I"]`. `[tool.ruff.format]` 기본.
- **1회 정규화 커밋**(`chore: adopt ruff`): `uv run ruff check --fix .`(11건) + `uv run ruff format .`(82파일). **로직 변경 0 — 서식·미사용 import·import 정렬뿐.** 룰에 걸리는 게 있으면 자동수정/포맷만, 기능 변경 금지(§5).
- **verify**: `uv run ruff check .` · `uv run ruff format --check .` 로컬 그린, `uv run pytest` 그린.
- **첫 CI 실행 컨틴전시**: `alembic check` 가 type/server-default 비교로 **허위 drift** 를 내면 → 마이그레이션을 날조하지 말고 해당 잡을 비차단으로 완화(또는 check 제외). 진짜 drift 면 마이그레이션 보강.

### 2-3 개발자 워크플로 문서

- [README.md](../README.md)(현재 1줄) 보강 또는 신규 `CONTRIBUTING.md` 에 dev 루프 1블록:
  `docker compose up -d`(Postgres :5433) → `uv run alembic upgrade head` → `uv run pytest` → 로컬 봇은 `DEV_GUILD_ID` 채워 즉시 동기화 / **PR → CI 그린 → 머지 → Render 자동배포**.

### (드롭) 2-4 ~~배포 게이팅 `deploy.yml`~~

- D1=A안 확정 → **항목 전체 생략**. `render.yaml` 그대로.

## 3. 산출물 체크리스트 (완료 정의)

- [x] D1~D6 확정 (그릴링 세션) + ADR-0003 작성
- [x] 새 브랜치 `phase-7-cicd` (origin/main `5cafcfb`에서 분기)
- [x] `.github/workflows/ci.yml` — lint·test·migrations 3잡
- [x] `pyproject.toml` ruff 핀 + `[tool.ruff]`(`E,F,I`+format) + `uv.lock` 갱신 — 단, **E501 ignore**(§6-1)
- [x] `chore: adopt ruff` 1회 정규화 커밋(실측: 자동수정 12 + 포맷 87, 로직 불변 — pytest 381 그린)
- [x] 개발자 워크플로 문서 1블록 (README)
- [x] PR 에서 CI 3잡 그린 + 임시 결함 주입 시 차단 확인 후 되돌림 (§6-3)
- [x] 커밋(`ci:`/`chore:`) + main 대상 PR — **PR #12 머지 완료**(`bac8b4b`, 2026-06-10)
- [ ] (운영자) branch protection 활성화 — **미설정**(2026-06-10 API 확인)
- [ ] (운영자) Render Blueprint 설정 + 배포 1회 실증 — Render 서비스 미생성

## 4. 사람(운영자) 작업 — 에이전트 불가

- **branch protection**(D1 A안): GitHub repo Settings → main 룰 — "Require a pull request before merging" + "Require status checks to pass"(**lint·test·migrations 3잡 지정**) 켜기. **"Do not allow bypassing" 은 끈 채로**(admin 우회 허용).
  - ⚠️ required status check 는 **CI 가 최소 1회 실행된 뒤**라야 체크 이름을 선택 가능 → ~~첫 PR CI 그린 이후 설정~~ **CI 실행 이력 있음 — 즉시 설정 가능**. 2026-06-10 기준 **미설정**(설정 전까지 main 직푸시·CI 우회 머지가 그대로 가능 = D1 게이트 미가동).
- **머지 → Render 자동배포 1회 실증**: 로그에서 마이그레이션 성공 + "글로벌 동기화 N개"(배포 핸드오프 §6 라이브 검증과 연계) + **표 이미지 한글 렌더링 확인**(§6-2 폰트 수정 효과). ⚠️ Render 서비스 자체가 미생성(배포 계획의 운영자 수동작업 선행) — Blueprint 설정 후 진행.

## 5. 스코프 밖 / 주의

- **기능 코드 변경 금지**(CLAUDE.md 외과적): ruff 도입으로 룰에 걸리면 룰 조정/자동포맷만, 로직 변경 금지.
- **`render.yaml` 무변경**(D1=A). mypy 전면 도입·커버리지 강제는 별도(점진).
- **커밋 금지 파일**: 루트 `기댓값/`·`starforce-simulator-system.md` 등 untracked 로컬 파일.
- CI 는 비밀 없이 동작(테스트가 env mock). migrations 잡의 `DATABASE_URL` 은 service Postgres 로컬 값(시크릿 아님).

## 6. 완료 기록 (as-built, 2026-06-10) — 지시서 대비 편차

구현 = **PR #12**(phase-7-cicd → main, squash `bac8b4b`). 커밋 5개: ruff 설정 → 정규화 → ci.yml → docs → 폰트 수정.

### 6-1 D3 편차: `E501` lint 제외 (룰 조정, §5 허용 범위)

- `select = ["E","F","I"]` 유지하되 `ignore = ["E501"]`. **줄 길이는 `ruff format`(88)이 CI 에서 강제**하므로 코드 줄은 통제됨.
- 근거: 포맷 적용 후에도 E501 **269건** 잔존 — 전부 포맷터가 줄바꿈 못 하는 **긴 한국어 문자열·주석**. 수동 수정은 §5 "로직 변경 금지" 리스크라 룰 조정 선택(ruff 기본 룰셋도 같은 이유로 E501 제외).
- 실측치 정정: 자동수정 11→**12건**(I001 8·F401 4), 포맷 82→**87파일**(ruff 0.15.16 기준).

### 6-2 스코프 추가: 리눅스 한글 폰트 — CI 가 발견한 **프로덕션 버그** 수정

- 첫 CI 에서 test 잡 2건 실패(`test_comparison.py` 금색 하이라이트 픽셀 단언). 원인: [table_image.py](../maple_mate/bot/table_image.py) `_FONT_CANDIDATES` 가 **전부 macOS 경로** → 리눅스(CI 러너·**Render 컨테이너**)에선 비트맵 폴백 폰트로 렌더링(한글 글리프 없음·하이라이트 색 소실). 즉 prod 표 이미지도 깨진 상태였을 버그.
- 수정(별도 커밋, §5 "기능 코드 변경 금지"의 의도적 예외로 PR 에 명시): 후보에 debian `fonts-nanum` 경로 1줄 추가 + CI test 잡·[Dockerfile](../Dockerfile) 에 `fonts-nanum` 설치. **첫 Render 배포부터 한글 정상 렌더링.**

### 6-3 검증 결과

- **§2-2 컨틴전시 미발동**: 빈 DB + raw `postgresql://` 로 `alembic upgrade head`+`check` 통과 — 허위 drift 없음(로컬·CI 동일).
- **결함 주입 차단 검증**: 각 결함이 **정확히 해당 잡만** 빨강 — 실패 테스트→test([run](https://github.com/mindongdong/maple-mate/actions/runs/27257691610)) / 깨진 마이그레이션→migrations([run](https://github.com/mindongdong/maple-mate/actions/runs/27257733870)) / F401→lint([run](https://github.com/mindongdong/maple-mate/actions/runs/27257777561)). 검증 후 force-push 로 제거(머지 이력 미오염).
- migrations 잡 첫 실행에서 Docker Hub pull 타임아웃 1회(일시적) — 재실행으로 해소, 구조 문제 아님.
