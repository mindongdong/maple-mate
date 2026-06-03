# Handoff — maple-mate 디스코드 봇 착수

> 친구 그룹용 메이플 디스코드 봇. 그릴링(`/grill-with-docs`)으로 기반 결정을 모두 확정함.
> 이 문서는 다음 에이전트가 **Spike 0 → Phase 5**를 순서대로 착수하기 위한 작업 계획서다.

## 목적

설계 명세는 이미 상세하나 기술 기반(언어·DB·API 검증·빌드순서·테스트)이 비어 있었음.
그릴링 세션에서 이 5개 포크를 모두 결정했고, 그 결과를 빌드 가능한 작업 계획으로 변환했다.
다음 세션은 **Spike 0(넥슨 API 검증)부터** 시작하면 된다.

## 참조 문서 (중복 금지 — 경로로 참조)

- [maple-discord-bot-design.md](../maple-discord-bot-design.md) — 제품/동작 명세(명령어·범위규칙·데이터모델 §5·에러처리·알려진 한계). **단일 진실 소스(SSOT)**.
- [CONTEXT.md](../CONTEXT.md) — 도메인 용어 사전(스펙류/이력류, 운지수, 손익메소, 기대값, 키미등록 vs 기록없음, 대상). 코드 작성 시 이 용어 그대로 사용.
- 프로젝트 루트: `/Users/dongmin/Documents/GitHub/maple-mate` (현재 greenfield — README + design doc + CLAUDE.md + CONTEXT.md만 존재, 소스 없음)

## 확정된 결정 (그릴링 결과)

| 결정 | 선택 | 함의 |
|---|---|---|
| 언어/런타임 | **Python + discord.py 2.x** | FastAPI · APScheduler · httpx · SQLAlchemy 2.0+asyncpg · Alembic · cryptography(Fernet) · pytest |
| DB | **PostgreSQL** | JSONB payload, Mac Mini 프로비저닝 필요 |
| API 검증 상태 | **스펙류 확인됨 / 이력류 미검증** | 이력류(starforce·cube·potential history)가 최대 리스크 → Spike 0 |
| 빌드 순서 | **신뢰 우선** | 검증된 스펙류 명령부터, 이력류는 그 다음 |
| 테스트 | **실용 테스트** | 순수 로직만 단위테스트, Nexon/Discord API는 mock, 무거운 E2E 생략 |

**핵심 아키텍처 가정 (Spike 0에서 검증 대상):** 스펙류(character/union/item/hexa/symbol)는 봇 앱 키 + ocid로 조회되는 공개 D-1 데이터. 이력류는 개인 넥슨 키 소유 계정에 스코프됨(`/history/*` 엔드포인트에 ocid 파라미터 없음). → "키 있으면 스타포스·잠재 해제"의 근거.

## 작업 계획

### 🔬 Spike 0 — 넥슨 history API 검증 *(GO/NO-GO 게이트, 코딩 전 필수)*
이력류 설계가 실제 API와 맞는지 실측. 키 모델이 깨지면 이력류 명령 설계를 재그릴해야 함.
- 본인 계정 개인 넥슨 API 키 발급 → `/maplestory/v1/history/starforce`·`/cube`·`/potential` 실호출
- 확인 항목:
  1. **키 스코프** — 개인 키가 그 계정 캐릭터 이력만 반환하는가 (ocid 파라미터 부재 확인)
  2. **오늘 데이터 조회 가능 여부** — `/스타포스 오늘` 프리셋 + history_cache 5분 TTL 설계 좌우
  3. **과거 조회 범위** — design의 상한 30일과 호환?
  4. **rate limit** 수치
  5. **응답 스키마** — 시도별 장비명/레벨 포함 여부 (design §8 "장비 레벨 미제공" 가정 실측)
- 산출물: 세 엔드포인트 raw JSON 샘플 + 위 항목 표
- **게이트**: 키 모델이 설계와 다르면 → 다음 작업 중단, 사용자와 재그릴

### 🏗️ Phase 1 — 기반 *(공유 인프라 + 첫 명령 /등록)*
1. 프로젝트 스캐폴드 — *검증: 봇 온라인 + FastAPI(uvicorn) 동시 기동(단일 asyncio 진입점)*
2. .env 시크릿 fail-fast 로딩 — 마스터키·봇토큰·앱키·운영자토큰·ADMIN_CHANNEL_ID 누락 시 기동 거부
3. Postgres 프로비저닝 + Alembic 5개 테이블 (design §5 그대로) — *검증: `alembic upgrade head`로 registration/history_cache/channel_settings/notice_state/error_log 생성*
4. Nexon 클라이언트(httpx) + 캐시 계층 — ocid lazy 갱신, 과거=불변/오늘=5분 TTL(KST), 1~2회 재시도→error_log. *검증: TTL 판정 단위테스트 + 실호출 1건*
5. 암호화 유틸(Fernet) — *검증: 암복호화 라운드트립 테스트*
6. 출력 헬퍼 — 임베드 통일, 버튼 페이지네이션, defer, 푸터(지난날짜=YYYY-MM-DD/오늘=HH:MM 기준)
7. 슬래시 커맨드 등록 스캐폴드 — 개발=길드 스코프(즉시반영) / 운영=글로벌
8. **/등록** — *검증: 키無=스펙류만, 키有=검증호출+Fernet 암호화 저장, (guild×user) 1레코드 upsert, 서버 내 닉 중복 허용*

### 📊 Phase 2 — 읽기전용 스펙류 *(앱 키만, 검증됨 — 공유 비교 머신 완성)*
- **/스펙** — *검증: 인자 필수 에러("1~5명 지정"), 1명=단일상세, 5명 비교, 항목(전투력·어빌·심볼·HEXA코어·HEXA스탯)*
- **/유니온** — *검증: 유니온레벨+아티팩트레벨+챔피언등급분포 카운트, 페이지네이션*
- **/아이템** — *검증: 부위 드롭다운(choices), 동적+정적보정 하이브리드(0성 vs 스타포스불가 구분), 우열판정 안 함*
- 횡단 검증: 부분성공(되는 유저만+실패행), 키미등록 vs 기록없음, ocid lazy 갱신

### 🎲 Phase 3 — 이력류 *(키 게이트, 최난도)*
- **기대값 고정 표 구축**(선행) — 성별 성공/파괴 확률 + 메소 비용 공식 → 장비레벨별 기대 소모 표. *검증: 알려진 케이스 단위테스트*
- **/스타포스** — *검증: 운지수=실제/기대, 손익메소 병기, 기간 프리셋(기본 최근7일/상한 30일), 장비레벨 3단 매칭(장착→매핑표→제외), "N건 중 M건" 투명표시, unmatched_equipment error_log*
- **/잠재** — *검증: 기간내 최다재설정 단일아이템 자동선정(큐브+메소 합산/동점=메소큰쪽), 시작/최종 잠재, 재설정0="기록 없음"*
- **/잠재합계** — *검증: 총 사용메소+총 큐브횟수 랭킹*

### 🔔 Phase 4 — 알림 / 스케줄러
- 스케줄러 인프라(APScheduler, KST)
- **/공지알림** — *검증: 6회/일(10·12·14·16·18·21시) 폴링, 공지+업데이트(이벤트 제외), notice_state 카테고리별 식별자, 최초가동=baseline만, 출력=제목+링크+등록일*
- **/썬데이** — *검증: 금 10:10 1회 재시도無, "썬데이 메이플" title 매칭(다중=전부/0=조용히패스), notice_state 주차 중복방지, 출력=제목+링크+기간*
- **수동 썬데이 HTTP 엔드포인트**(FastAPI) — *검증: Bearer 토큰 인증, 바디(제목·링크·기간), sunday_alert 채널 즉시발송 + 주차 중복마킹(자동발송과 공유)*

### 🛠️ Phase 5 — 운영
- **일일 운영 요약** — *검증: 09:00 KST, 전날 error_log 집계(타입별 건수 + 미매칭 장비 상위 N) → ADMIN_CHANNEL_ID*

### 횡단 규칙 (전 Phase 적용 — design §7)
모든 비교 명령 defer 의무 · 임베드 통일 · 초과인원 버튼 페이지네이션 · /스펙만 5명 상한 · error_log는 **재시도 발생 건만** 기록.

## ⚠️ 미해결 결정 (해당 Phase 도달 시 사용자와 결정)

1. **Phase 1** — Postgres가 Mac Mini에 이미 설치돼 있나, 아니면 설치부터?
2. **Phase 3** — 기대값 고정 표 **데이터 소스**: 공식 확률표+강화비용 공식 직접 산출 vs 커뮤니티 시트 차용? (별도 그릴링 권장)
3. **Phase 4** — 넥슨 **공지/이벤트 API**는 미검증. 스펙류·이력류와 별개 엔드포인트라 Phase 4 진입 전 미니 스파이크 필요.

## 📝 보류 중인 작업 (사용자 승인 대기)

그릴링에서 ADR 2건을 제안했으나 사용자가 아직 작성 승인 안 함:
- **ADR-0001 — Python/discord.py 스택** (기존 TS 생태계 거스름)
- **ADR-0002 — PostgreSQL 채택** (단일프로세스·소규모엔 SQLite가 당연한데 거스름)
- (넥슨 개인 키 모델 ADR은 Spike 0 검증 **후** 작성 권장)

→ 다음 세션 시작 시 "이 ADR들 `docs/adr/`에 작성할까요?" 재확인할 것.

## 다음 세션 권장 스킬

- **현재 단계(Spike 0)**: 일반 작업. 넥슨 API 실호출 검증이라 코딩 스킬 불필요.
- **Phase 1~ 본격 구현 시**: `/oh-my-claudecode:autopilot` 또는 `/oh-my-claudecode:ultrawork`(병렬 다작업), 코드 작성은 `executor` 에이전트(복잡 작업 model=opus).
- **Phase 3 기대값 표 데이터 소스 결정** 또는 **Phase 4 진입 전**: `/grill-with-docs` 재실행으로 미해결 결정 해소.
- **API/SDK 사용 불확실 시**: `document-specialist` 에이전트(discord.py·넥슨 API 레퍼런스).

## 주의

- 사용자 전역 룰은 TDD/80% 커버리지를 요구하나, **이 프로젝트는 "실용 테스트"로 명시 합의**(순수 로직만 단위테스트, API mock). 과도한 E2E 강제 금지.
- 프로젝트 `CLAUDE.md`: 가정 금지·단순함 우선·외과적 변경. 추측성 추상화/기능 추가 지양.
- 첨부 작업 디렉터리에 무관한 타 프로젝트(214archives, HAMO) 포함 — maple-mate 외 건드리지 말 것.
