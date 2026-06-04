# Phase 1 핸드오프 — 기반 (공유 인프라 + 첫 명령 `/등록`)

> **목적:** [work-plan.md](./work-plan.md)의 **Phase 1**을 다른 세션이 단독으로 착수·완료하기 위한 단일 지침서.
> Spike 0(넥슨 API 검증)은 **완료·GO**([api-verification-plan.md](./api-verification-plan.md)). 이제 코드 구현을 시작한다.
>
> **원칙:** 설계는 복사하지 않고 **경로로 참조**(중복 금지). 이 문서는 *Phase 1 범위 + Spike 0 파생 구현 제약 + 합격 기준*만 담는다.
> **이 프로젝트는 "실용 테스트"** — 순수 로직만 단위테스트, Nexon/Discord는 mock. 과도한 E2E 금지([work-plan §주의](./work-plan.md)).

## 0. 먼저 읽을 것 (SSOT)

| 문서 | 역할 |
|---|---|
| [maple-discord-bot-design.md](../maple-discord-bot-design.md) | 제품/동작 명세. **§5 데이터모델 · §6 보안 · §7 횡단규칙 · §3 명령어**가 Phase 1 직접 근거 |
| [CONTEXT.md](../CONTEXT.md) | 도메인 용어(스펙류/이력류, 키 미등록 vs 기록 없음, 등록, 대상) — **코드 네이밍에 그대로 사용** |
| [docs/adr/0001-nexon-personal-key-model.md](./adr/0001-nexon-personal-key-model.md) | 키 모델 결정(이력류=개인 키, 스펙류=앱 키) + 결과(암호화·부분성공) |
| [docs/api/README.md](./api/README.md) | 넥슨 공통 규약 + **에러코드→error_type 매핑** + 클라이언트 패턴 |
| [docs/api/character.md](./api/character.md) · [history.md](./api/history.md) | `/등록` 검증 호출에 쓰는 엔드포인트 스펙(실호출 확정 주석 포함) |
| [docs/api-verification-plan.md](./api-verification-plan.md) | Spike 0 결과 — 아래 §3 구현 제약의 출처 |

## 1. Phase 1 범위 (8개 빌드 단위 · work-plan 그대로)

순서 = 빌드 순서. 각 단위는 합격 기준 충족 후 다음으로.

| # | 빌드 단위 | 합격 기준(검증) |
|---|---|---|
| 1 | **프로젝트 스캐폴드** | 봇(게이트웨이) + FastAPI(uvicorn)가 **단일 asyncio 진입점**에서 동시 기동. `python -m maple_mate`(또는 동등) 실행 시 봇 온라인 로그 + uvicorn 리슨 로그 |
| 2 | **.env 시크릿 fail-fast 로딩** | 필수 키(아래 §4) 누락 시 **기동 거부**(명확한 누락 항목 메시지). 단위테스트: 누락→예외 |
| 3 | **Postgres + Alembic 5테이블** | `alembic upgrade head` → `registration`/`history_cache`/`channel_settings`/`notice_state`/`error_log` 생성([design §5](../maple-discord-bot-design.md) 그대로). `downgrade`도 동작 |
| 4 | **Nexon 클라이언트(httpx) + 캐시 계층** | ocid lazy 갱신, history_cache TTL(**과거=불변 / 오늘(KST)=5분**). 단위테스트: TTL 판정 순수함수 + 에러코드 매핑 + 실호출 1건(앱 키 `id` 또는 `character/basic` 무지정) |
| 5 | **암호화 유틸(Fernet)** | 암↔복호 라운드트립 단위테스트. 마스터 키는 `.env`([design §6](../maple-discord-bot-design.md)) |
| 6 | **출력 헬퍼** | 임베드 통일 · 버튼 페이지네이션 · `defer` · 푸터(지난날짜=`YYYY-MM-DD` / 오늘=`HH:MM 기준`, [design §7](../maple-discord-bot-design.md)) |
| 7 | **슬래시 커맨드 등록 스캐폴드** | 개발=길드 스코프(즉시 반영, `DEV_GUILD_ID`) / 운영=글로벌. 빈 명령 1개라도 등록·응답 확인 |
| 8 | **`/등록`** | 아래 §5 합격 기준 |

## 2. 권장 프로젝트 구조 (참고 — "작은 파일 다수, 도메인별" 룰)

> 확정 스택: **Python/discord.py(봇) + FastAPI(HTTP) + SQLAlchemy 2.0 + asyncpg + Alembic + cryptography(Fernet) + pytest**. 단일 프로세스([design §1](../maple-discord-bot-design.md)).

```
maple_mate/
  __init__.py
  __main__.py            # 단일 asyncio 진입점: discord.py + uvicorn 동시 기동
  config.py              # .env fail-fast 로딩(필수값 검증)
  db/
    engine.py            # async engine + session factory (asyncpg)
    models/              # 테이블별 1파일 (registration.py, history_cache.py, ...)
  nexon/
    client.py            # httpx AsyncClient + 재시도/스로틀 + 에러 매핑
    errors.py            # OPENAPIxxxxx → error_type, 예외 클래스
    cache.py             # history_cache TTL 판정(순수함수) + 조회/적재
  crypto.py              # Fernet 암복호화
  bot/
    client.py            # discord.py 봇 + 커맨드 트리 등록
    embeds.py            # 출력 헬퍼(임베드/페이지네이션/푸터)
    commands/register.py # /등록
  http/
    server.py            # FastAPI 앱(수동 썬데이 엔드포인트는 Phase 4 — 골격만)
  alembic/               # 마이그레이션
tests/                   # 순수 로직 단위테스트(TTL 판정·에러 매핑·암복호·fail-fast)
.env.example             # 키 이름만(값 없음) — 커밋 대상
alembic.ini · pyproject.toml
```

`.env`(실제 값)·로컬 시크릿은 이미 [.gitignore](../.gitignore)로 제외됨. **절대 커밋 금지.**

## 3. ⚠️ Spike 0에서 확정된 구현 제약 (반드시 반영)

이 절이 핸드오프의 핵심이다. Nexon 클라이언트(#4)·`/등록`(#8) 설계가 여기 의존한다. 출처: [api-verification-plan.md](./api-verification-plan.md).

1. **에러코드 → error_type 매핑** ([README.md](./api/README.md) 표 그대로):
   - `OPENAPI00005`(키 무효) → `auth_invalid` → **"키 미등록/무효"** 처리(=`/등록` 키 검증 실패 신호).
   - `OPENAPI00009`("data not ready") → **에러 아님**, "전일 미생성/기록 없음"으로 처리(스펙류 D-1이 아직 안 만들어진 상태).
   - `OPENAPI00007`(429, rate limit) → `rate_limit` → **재시도 대상**.
   - `OPENAPI00004`(파라미터 오류) → 잘못된 닉/날짜/범위. 없는 닉 조회도 이 코드.
   - `OPENAPI00001/00006/00011` → `nexon_api`(장애).
2. **Rate limit 실측:** 검증에 쓴 `test_` 키는 `x-ratelimit-limit: 5`(~5/sec). 클라이언트는 **스로틀 + 429 재시도(백오프)** 필수. 운영 live 키 한도는 미확인 → 설정값으로 빼고 보수적 기본값. *참고 구현:* `spike/verify_nexon_api.py`의 `call()`(throttle 0.8s + 429 재시도)을 그대로 이식 가능(단 일회용 코드이므로 정식 클라이언트로 재작성).
3. **스펙류 D-1 경계는 soft:** "1AM 이후 D-1" 보장 아님(검증 시 01:10 KST에 D-1=`00009`, 최신 ready=D-2). → **봇은 D-1을 직접 계산해 `date`로 넘기지 말고, `date` 무지정(최신 ready) 호출**을 기본으로. 무지정 호출은 200 + 응답 `date:null`. `00009` 수신 시 폴백/재시도.
4. **이력류는 당일(오늘) 수용:** `history/*`는 오늘 날짜도 200(스펙류 today=`00004`와 대비). → history_cache **오늘=5분 TTL** 설계 유효. 단 반영 지연은 미측정.
5. **이력류 조회 범위 = 롤링 ~2년:** 30일 상한([design §3.4](../maple-discord-bot-design.md))엔 무관. `date+cursor` 동시 전달은 에러 아님(date 우선) — 클라이언트는 **둘 중 하나만** 보낼 것. `count` 필수(누락→`00004`).
6. **필드 주의(파싱 영향):** `access_flag`=`"true"/"false"`(문자열). `champion_grade`=`SSS/SS/S`. starforce `item_upgrade_result`=`"실패(유지)"`류 접미사형(성공/실패/파괴 집계 시 접두 매칭). starforce 플래그(`destroy_defence` 등)=서술형 한글. 비용/레벨 필드 없음(기대값 별도 표는 Phase 3). 상세는 [history.md](./api/history.md)·[character.md](./api/character.md).
7. **0성 vs 스타포스 불가 부위:** API에 구분 신호 없음 → `/아이템`(Phase 2)에서 **정적 부위표** 필요. Phase 1엔 영향 없음(인지만).

## 4. 환경변수(.env) — fail-fast 검증 대상

| 키 | 용도 | 비고 |
|---|---|---|
| `DISCORD_BOT_TOKEN` | 봇 토큰 | 필수 |
| `NEXON_APP_KEY` | 스펙류·알림 앱 키 | 필수 |
| `FERNET_MASTER_KEY` | 개인 키 암호화 마스터 키 | 필수. `cryptography` Fernet 키 생성값 |
| `OPERATOR_TOKEN` | 수동 썬데이 HTTP Bearer 토큰([design §4](../maple-discord-bot-design.md)) | 필수(엔드포인트는 Phase 4지만 로딩은 지금) |
| `ADMIN_CHANNEL_ID` | 운영 요약 채널([design §6](../maple-discord-bot-design.md)) | 필수 |
| `DATABASE_URL` | Postgres(asyncpg) DSN | 필수 |
| `DEV_GUILD_ID` | 개발용 길드 스코프 즉시 등록 | 개발 시 필수, 운영 글로벌은 미사용 |

→ `.env.example`에는 **키 이름만**(값 없음) 넣어 커밋. 실제 값은 사용자에게 받아 `.env`에(커밋 금지).

## 5. `/등록` 상세 (Phase 1의 종착점)

- 시그니처: `/등록 [닉네임] [API키(선택)]` ([design §3](../maple-discord-bot-design.md)). 레코드 단위 = (`guild_id`, `discord_user_id`) **1레코드 upsert**, 서버 내 닉 중복 허용([design §5①](../maple-discord-bot-design.md)).
- **키 없음:** 닉 → `id`로 ocid 조회·검증 후 등록(스펙류만 가능 상태). ocid 캐싱.
- **키 있음(이력류 해제):**
  1. 키 유효성 **검증 호출** — 개인 키로 `history/starforce`(또는 `/cube`) `count=10` 호출.
     - `200` → 키 유효(빈 배열이어도 유효). **Fernet 암호화 후 `api_key_encrypted` 저장.**
     - `OPENAPI00005` → 키 무효 → **명확한 에러로 거부**(잘못된 키 저장 금지). 닉만 등록할지 전체 거부할지는 UX 결정(권장: "키가 무효입니다. 키 없이 등록하려면 키 인자 빼고 다시" 안내).
  2. (비목표/백로그) "등록 닉 == 키 소유 계정 캐릭" 정합성 cross-check는 이력이 비면 불가([Spike 0 잔류](./api-verification-plan.md)) → **Phase 1 범위 밖.** 단순하게 유효성만.
- 합격 기준: 키無=스펙류만 등록 / 키有=검증호출+암호화 저장 / (guild×user) upsert 동작 / 서버 내 닉 중복 허용 / 키 무효 시 거부.
- 용어: 결과 메시지는 [CONTEXT.md](../CONTEXT.md) 용어("등록", "키 미등록" 등) 사용.

## 6. 테스트 방침 (실용 테스트)

**단위테스트(순수 로직만):**
- history_cache TTL 판정 함수(오늘(KST)인가? → 5분 / 아니면 불변).
- 에러코드 → error_type 매핑.
- Fernet 암↔복호 라운드트립.
- .env fail-fast(누락 시 예외).
- 푸터 포맷(지난날짜 vs 오늘).

**mock:** Nexon httpx 응답·discord.py 상호작용은 mock. **무거운 E2E·실 디스코드 봇 통합 테스트 강제 금지.** 실호출은 #4 검증의 1건만(앱 키, 무지정).

## 7. 사전 결정 필요 (착수 전 사용자 확인)

1. **Postgres 프로비저닝** ([work-plan 미해결 #1](./work-plan.md)): Mac Mini에 Postgres가 **이미 설치돼 있는지**, 아니면 설치/도커부터인지 — `DATABASE_URL` 형태가 여기서 갈림.
2. **시크릿 수령:** `.env` 값(봇 토큰·앱 키·`ADMIN_CHANNEL_ID`·`DEV_GUILD_ID` 등)을 사용자에게 받아 로컬 `.env`에. 봇 토큰 없으면 #1·#7만 부분 진행 가능.
3. **Fernet 마스터 키:** 신규 생성(`Fernet.generate_key()`)해 `.env`에 보관.

## 8. 범위 밖 (Phase 1에서 하지 말 것)

- `/스펙`·`/아이템`·`/유니온`·`/스타포스`·`/잠재`·`/잠재합계`·알림·스케줄러·운영 요약(= Phase 2~5).
- 기대값 고정 표(Phase 3), 정적 부위표(Phase 2), 수동 썬데이 엔드포인트 본 구현(Phase 4 — 골격만).
- GPT 비교·키 라이프사이클 등 백로그([design §9](../maple-discord-bot-design.md)).
- 추측성 추상화/설정화([CLAUDE.md](../CLAUDE.md) 단순함 우선).

## 9. 산출물 체크리스트

- [ ] 단일 진입점에서 봇 + uvicorn 동시 기동
- [ ] `.env` fail-fast(누락 거부) + `.env.example`(이름만) 커밋
- [ ] `alembic upgrade head`로 5테이블 생성([design §5](../maple-discord-bot-design.md))
- [ ] Nexon 클라이언트: ocid lazy 갱신 + history_cache TTL + 에러 매핑 + 스로틀/재시도 + 실호출 1건
- [ ] Fernet 암복호 유틸 + 라운드트립 테스트
- [ ] 출력 헬퍼(임베드/페이지네이션/푸터) + 슬래시 등록 스캐폴드(개발 길드 스코프)
- [ ] `/등록`: 키無=스펙류만 / 키有=검증호출+암호화 저장 / upsert / 닉 중복 허용 / 키 무효 거부
- [ ] 단위테스트 통과(TTL·에러매핑·암복호·fail-fast·푸터), Nexon/Discord mock
- [ ] 시크릿 미커밋 확인(`git status`)

## 참조

- 작업 계획 전체: [work-plan.md](./work-plan.md) (Phase 1~5)
- 검증 결과·잔류: [api-verification-plan.md](./api-verification-plan.md)
- 키 모델 결정: [docs/adr/0001-nexon-personal-key-model.md](./adr/0001-nexon-personal-key-model.md)
