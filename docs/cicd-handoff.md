# 핸드오프 — CI/CD 구축 (GitHub Actions + Render, 다음 세션 인계)

> 반복 개발(이슈 → 개선 → PR)의 **안전망**으로 CI/CD를 세운다. 이 문서는 콜드스타트 인계서로,
> **현재 상태 · 확정된 것 · 다음 세션이 사용자와 확정할 결정 · 구현 범위 · 완료 정의**에 집중한다.
> 다음 세션은 §3의 미확정 결정을 먼저 확정(필요 시 grill/plan)한 뒤 §4를 구현한다.

> **✅ 결정 확정됨 (그릴링 세션 2026-06-09)** — D1~D6 전부 확정·실행지시서로 이관: [cicd-work-order.md](cicd-work-order.md). D1 근거는 [ADR-0003](adr/0003-cd-gating-via-branch-protection.md).
> **정정**: 본문의 "선행 PR #11(미머지)"는 stale — **PR #11 은 이미 MERGED**(`origin/main` `5cafcfb`). CI 작업은 최신 main 에서 `phase-7-cicd` 신규 분기.
>
> **✅ 구현 완료 (2026-06-10)** — PR #12 머지(main `bac8b4b`). 이 문서는 **이력 보존용** — 현재 상태·편차(E501 ignore, 폰트 prod 버그 수정 등)는
> [cicd-work-order.md](cicd-work-order.md) **§6 완료 기록**이 SSOT. 남은 운영자 작업(branch protection·Render 설정)은 동 문서 §4.

## 0. 먼저 읽을 것 (SSOT — 중복 금지, 경로로 참조)

- [deploy-plan.md](deploy-plan.md) §1 — 배포 아키텍처(단일 인스턴스·Render). CI/CD는 이 배포 위에 얹는다.
- [deploy-handoff.md](deploy-handoff.md) — 직전 배포 작업(단계 0+1). 본 문서의 **선행 PR #11**.
- [../render.yaml](../render.yaml) — Render Blueprint. `autoDeploy: true` + `branch` 미지정(=기본 브랜치 main) → **현재 main 머지 시 Render가 이미 자동 배포함**.
- [../Dockerfile](../Dockerfile) — 시작 명령 `alembic upgrade head && python -m maple_mate`. **마이그레이션이 매 배포 자동 실행** → 깨진 마이그레이션 = prod 직격(본 작업의 핵심 동기).
- [../pyproject.toml](../pyproject.toml) — uv 프로젝트(`package = false`), pytest 설정(`addopts = "-m 'not live'"`), Python `>=3.12,<3.13` 단일.

## 1. 시작점 (현재 상태 — 측정값)

- **CI 전무**: `.github/` 디렉터리 없음. Makefile·workflow 없음.
- **테스트**: `uv run pytest` → **381 통과·0.77초**, **외부 의존 0**(DB·네트워크 불필요 — "실용 테스트": 순수 로직 단위테스트 + API/DB mock, FastAPI는 인메모리 TestClient). live 테스트는 `addopts`로 기본 제외.
- **린트**: ruff를 **로컬 ad-hoc 으로만** 사용(`.ruff_cache/` 존재) — pyproject에 **핀·설정 없음**. mypy 미사용.
- **배포(CD)**: Render가 GitHub App 웹훅으로 **main 변경 자동 감지 → Docker 빌드 → 마이그레이션 → 기동**. 즉 "배포" 자체는 이미 동작. **빠진 건 머지 전 게이트(CI)와 마이그레이션 사전검증**.
- **워크플로**: 피처 브랜치 → PR → main 머지(최근 커밋 #5~#11 패턴). 기본 브랜치 `origin/main`.
- **branch protection**: 없음(추정) — 현재 main 직접 푸시 가능 → CI 우회 가능.

## 2. 범위

**포함**: GitHub Actions CI(린트·테스트·**마이그레이션 검증**) + main 게이팅 전략 확정·구현 + 개발자 워크플로 문서 1줄.
**불포함**(§8): 기능 코드 변경 / Render 인프라 재설계 / mypy 전면 도입 / 멀티 Python 매트릭스(단일 3.12).

## 3. 미확정 결정 — **다음 세션이 사용자와 확정** (구체화 핵심)

각 항목에 **권장 기본안**을 달았다. 다음 세션은 이를 사용자와 확정(이견 시 grill)한 뒤 §4를 구현한다.

| # | 결정 | 권장 기본안 | 비고 |
|---|---|---|---|
| D1 | **CD 게이팅 방식** | **A안: Render 네이티브 autoDeploy 유지 + branch protection(PR 필수·required check=CI)**. main은 CI 통과 PR로만 갱신 → Render가 그 머지를 자동 배포 | B안(autoDeploy off + GHA가 main CI 통과 후 Render **Deploy Hook** 호출)은 더 엄격하나, branch protection이면 A로 충분. **비자명·되돌리기 어려운 선택이라 ADR 1건 고려**([[adr-usage-preference]]) |
| D2 | **마이그레이션 검증 CI** | **YES — Postgres service container 띄워 `alembic upgrade head` 실행**(빈 DB→head 성공 확인). 매 배포 자동실행이라 prod 전 차단 가치 최상 | 추가 옵션: `alembic check`(모델 drift) · downgrade 1스텝 왕복. 1-3에서 raw `postgresql://`→asyncpg 정규화 검증도 이 잡에서 실제 연결로 재확인됨 |
| D3 | **린트/포맷 게이트** | **ruff 도입**: dev deps 핀 + `[tool.ruff]` 설정(line-length·target 3.12·룰셋) + CI에서 `ruff check`·`ruff format --check` | 기존 ad-hoc 사용을 표준화. **mypy는 점진**(초기 제외 또는 비차단 잡) |
| D4 | **Docker 빌드 CI** | **PR에선 생략**(빠른 피드백, Render가 어차피 빌드) · 선택: Dockerfile/pyproject/uv.lock 변경 PR에만 `paths` 필터로 빌드 | 빌드 ~분 소요. main 머지 후 별도 비차단 잡도 가능 |
| D5 | **커버리지 게이트** | **리포트만(비차단)**. 전역 규칙은 80% 커버리지지만 본 레포는 "실용 테스트" 합의 → **강제 게이트는 컨벤션과 충돌**. 측정·표시만 | 사용자 합의 시에만 임계 도입 |
| D6 | **트리거 범위** | `pull_request`(→main) + `push`(main). concurrency로 중복 실행 취소 | 태그/릴리스 트리거는 불필요(Render가 배포 담당) |

## 4. 작업 항목 (결정 확정 후 구현)

### 4-1 CI 워크플로 — `.github/workflows/ci.yml` 🔴 핵심
- **트리거**(D6): `pull_request: [main]` + `push: [main]`, `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`.
- **공통 셋업**: `actions/checkout` → `astral-sh/setup-uv`(캐시 enable) → `uv sync --frozen`(또는 `--frozen --no-dev` + 필요 그룹). Python은 pyproject 핀(3.12) 사용.
- **job: lint**(D3): `uv run ruff check .` + `uv run ruff format --check .`.
- **job: test**: `uv run pytest`(오프라인이라 service 불필요). (D5면 `--cov` 리포트 추가·비차단.)
- **job: migrations**(D2): `services: postgres:16`(health 대기) → `DATABASE_URL=postgresql://...@localhost:5432/...` 주입 → `uv run alembic upgrade head` (+옵션 `alembic check`). **raw `postgresql://` 로 넣어 env.py 정규화까지 실검증**([../maple_mate/alembic/env.py](../maple_mate/alembic/env.py)).
- **verify**: 의도적으로 ① 실패 테스트 ② 깨진 마이그레이션 ③ 린트 위반을 각각 1회 넣어 **CI가 빨강으로 막는지** 확인 후 되돌림.

### 4-2 ruff 표준화 — `pyproject.toml`
- dev deps에 `ruff` 핀 추가 → `uv lock`. `[tool.ruff]`(target-version `py312`, line-length, select 룰셋) + `[tool.ruff.format]` 추가.
- **verify**: 로컬 `uv run ruff check .` 통과(기존 코드가 룰에 걸리면 룰 완화 또는 자동수정 — **기능 변경 금지**, §8).

### 4-3 (D1=B안 채택 시만) 배포 게이팅 — `deploy.yml` + Render Deploy Hook
- render.yaml `autoDeploy: false` 로 전환 → `push: [main]` 워크플로가 CI 통과 후 `curl <RENDER_DEPLOY_HOOK_URL>` 호출.
- 시크릿 `RENDER_DEPLOY_HOOK_URL`(GitHub Actions secret, 운영자 §6).
- **A안이면 이 항목 전체 생략**(render.yaml 그대로).

### 4-4 개발자 워크플로 문서
- [README.md](../README.md) 또는 신규 `CONTRIBUTING.md` 에 dev 루프 1블록: `docker compose up -d` → `uv run alembic upgrade head` → `uv run pytest` → 로컬 봇은 `DEV_GUILD_ID` 채워 즉시 동기화 / PR → CI 그린 → 머지 → Render 자동배포.

## 5. 테스트 / 검증 방침

완료 기준 = **PR에서 CI 3잡(lint·test·migrations) 그린**, 그리고 의도적 실패 주입 시 각 잡이 **머지를 차단**. 로컬 `uv run pytest`·`uv run ruff check .` 동등 통과. (실DB·실배포 트리거 확인은 §6.)

## 6. 사람(운영자) 작업 — 에이전트 불가

- **branch protection**(D1 A안): GitHub repo Settings → main 에 "Require a pull request" + "Require status checks to pass"(CI 잡 지정) + "직접 푸시 금지".
- **(D1 B안 채택 시)**: Render 대시보드에서 web 서비스 **Deploy Hook URL** 발급 → GitHub Actions secret `RENDER_DEPLOY_HOOK_URL` 등록 + render.yaml `autoDeploy:false` 반영.
- **머지 → Render 자동배포 1회 실증**: 로그에서 마이그레이션 성공 + "글로벌 동기화 N개" 확인(배포 핸드오프 §7 라이브 검증과 연계).

## 7. 산출물 체크리스트 (완료 정의)

- [ ] §3 미확정 결정(D1~D6) 사용자와 확정(필요 시 ADR 1건)
- [ ] `.github/workflows/ci.yml` — lint·test·migrations 3잡
- [ ] `pyproject.toml` ruff 핀 + `[tool.ruff]` 설정, `uv.lock` 갱신
- [ ] (B안 시) `deploy.yml` + Deploy Hook 연동
- [ ] 개발자 워크플로 문서 1블록
- [ ] PR에서 CI 그린 + 의도적 실패 주입 시 차단 확인
- [ ] 커밋(`ci:`/`chore:`) + main 대상 PR
- [ ] (운영자) branch protection 활성화

## 8. 스코프 밖 / 주의

- **기능 코드 변경 금지**(CLAUDE.md 외과적): ruff 도입으로 기존 코드가 룰에 걸리면 룰 조정/자동포맷만, 로직 변경 금지.
- **Render 인프라 재설계 금지**: render.yaml은 D1 결정에 따른 `autoDeploy` 토글 외 손대지 않음.
- **mypy 전면 도입·커버리지 강제**는 별도(점진). 본 작업은 게이트 골격까지.
- **커밋 금지 파일**: 루트 `기댓값/`·`starforce-simulator-system.md` 등 untracked 로컬 파일.
- CI는 비밀 없이 동작(테스트가 env mock) — 단 migrations 잡의 `DATABASE_URL`은 service Postgres 로컬 값(시크릿 아님).
