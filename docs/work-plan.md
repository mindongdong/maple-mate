# 작업 계획 · 진행 현황 — maple-mate 디스코드 봇

> 친구 그룹용 메이플 디스코드 봇. 그릴링(`/grill-with-docs`)으로 기반 결정을 모두 확정함.
> 이 문서는 **Spike 0 → Phase 5** 전체 로드맵이자 진행 현황 기록이다.

## 목적

설계 명세는 상세하나 기술 기반(언어·DB·API 검증·빌드순서·테스트)이 비어 있어, 그릴링에서 5개 포크를
모두 결정하고 빌드 가능한 작업 계획으로 변환했다. **Spike 0 ~ Phase 2는 완료**, **Phase 3(`/스타포스`)·
Phase 4(`/썬데이`)는 일부 완료**이며 나머지(잠재류·공지알림·운영 요약)가 남았다. 아래 진행 현황 참조.

## 진행 현황 (2026-06-08 기준)

| 단계 | 상태 | 비고 |
|---|---|---|
| Spike 0 — 넥슨 history API 검증 | ✅ 완료 | 키 스코프(ocid 부재)·과거 1년 조회·장비레벨 미제공 실측 확인 |
| Phase 1 — 기반 + `/등록` | ✅ 완료 | PR #1 |
| Phase 2 — 스펙류(`/스펙`·`/유니온`·`/아이템`) | ✅ 완료 | PR #2 |
| Phase 3 — 이력류 | 🟡 일부 | **`/스타포스` 완료(PR #4)** · **`/잠재` 구현 완료(재설정·큐브·사용 메소·등업, 미push)** — G2(메소 단가표) 해소, `/잠재합계` 폐기(통합) |
| Phase 4 — 알림 | 🟡 일부 | **`/썬데이` + 스케줄러 완료(PR #3)** · `/공지알림`·수동 HTTP 썬데이 미착수 |
| Phase 5 — 운영 요약 | ⬜ 미착수 | |

**다음 작업 후보**: `/잠재` 게이트 해소(G1 등업 미니스파이크 라이브 1콜·G2 메소 단가표 + `사용 메소` 컬럼) · `/공지알림`(Phase 4) · 일일 운영 요약(Phase 5). 공지알림은 미니 스파이크 선행(아래 미해결 결정).

## 참조 문서 (중복 금지 — 경로로 참조)

- [maple-discord-bot-design.md](../maple-discord-bot-design.md) — 제품/동작 명세(명령어·범위규칙·데이터모델 §5·에러처리·알려진 한계). **단일 진실 소스(SSOT)**.
- [CONTEXT.md](../CONTEXT.md) — 도메인 용어 사전(스펙류/이력류, 운빨 수치·총 사용 메소·기댓값 대비 손익, 키미등록 vs 기록없음, 대상). 코드 작성 시 이 용어 그대로 사용.
- 프로젝트 루트: `/Users/dongmin/Documents/GitHub/maple-mate` (DDD 도메인 구조 구현됨 — `maple_mate/{registration,character,union,history,notification,nexon,bot,api,database,security,error_log}/`)

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

### 🔬 Spike 0 — 넥슨 history API 검증 ✅ 완료 *(GO/NO-GO 게이트 → GO)*
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
- **결과(GO)** ✅: 키 스코프(ocid 부재)·장비레벨 미제공 가정 실측 확인. 과거 조회는 30일 가정과 달리 **약 1년까지 가능** → 기간 상한을 1년으로 확장(Phase 3 반영).

### 🏗️ Phase 1 — 기반 ✅ 완료 *(공유 인프라 + 첫 명령 /등록, PR #1)*
1. 프로젝트 스캐폴드 — *검증: 봇 온라인 + FastAPI(uvicorn) 동시 기동(단일 asyncio 진입점)*
2. .env 시크릿 fail-fast 로딩 — 마스터키·봇토큰·앱키·운영자토큰·ADMIN_CHANNEL_ID 누락 시 기동 거부
3. Postgres 프로비저닝 + Alembic 5개 테이블 (design §5 그대로) — *검증: `alembic upgrade head`로 registration/history_cache/channel_settings/notice_state/error_log 생성*
4. Nexon 클라이언트(httpx) + 캐시 계층 — ocid lazy 갱신, 과거=불변/오늘=5분 TTL(KST), 1~2회 재시도→error_log. *검증: TTL 판정 단위테스트 + 실호출 1건*
5. 암호화 유틸(Fernet) — *검증: 암복호화 라운드트립 테스트*
6. 출력 헬퍼 — 임베드 통일, 버튼 페이지네이션, defer, 푸터(지난날짜=YYYY-MM-DD/오늘=HH:MM 기준)
7. 슬래시 커맨드 등록 스캐폴드 — 개발=길드 스코프(즉시반영) / 운영=글로벌
8. **/등록** — *검증: 키無=스펙류만, 키有=검증호출+Fernet 암호화 저장, (guild×user) 1레코드 upsert, 서버 내 닉 중복 허용*

### 📊 Phase 2 — 읽기전용 스펙류 ✅ 완료 *(앱 키만 — 공유 비교 머신, PR #2)*
- **/스펙** — *검증: 인자 필수 에러("1~5명 지정"), 1명=단일상세, 5명 비교, 항목(전투력·어빌·심볼·HEXA코어·HEXA스탯)*
- **/유니온** — *검증: 유니온레벨+아티팩트레벨+챔피언등급분포 카운트, 페이지네이션*
- **/아이템** — *검증: 부위 드롭다운(choices), 동적+정적보정 하이브리드(0성 vs 스타포스불가 구분), 우열판정 안 함*
- 횡단 검증: 부분성공(되는 유저만+실패행), 키미등록 vs 기록없음, ocid lazy 갱신

### 🎲 Phase 3 — 이력류 🟡 일부 완료 *(키 게이트, 최난도)*
- ✅ **기대값·운빨 엔진**(선행) — 성공/파괴 확률표 + 정가 메소 비용공식(round-half-up) → 마르코프 흡수 기대비용. 데이터 소스는 **공식 확률표+비용공식 직접 산출**(미해결 결정 #2 해소), 검증 이미지(`기댓값/`, 로컬 전용) 대조.
- ✅ **/스타포스** (PR #4) — 설계 대비 **진화**: 운빨 지표 `운지수(실제/기대)` → `성공 백분위` → **`운빨수치(메소 백분위)`** 3차 개편(ADR-0002). 기간 상한 30일 → **1년**(최근90일·최근1년 프리셋 추가). 손익 부호 직관화(이득`+`/손해`−`). 레벨 매칭은 **세트명 부분일치 > 현재장착 > 자동학습 > 시드(보스장신구 34종) > 미상** + 집계 제외정책(`EXCLUDED_ITEMS`·레벨 100 미만). `M/N건` 투명표시·`unmatched_equipment` error_log 유지. 상세 [starforce-handoff.md](starforce-handoff.md).
- 🟡 **/잠재** *(구현 완료, 미push)* — 설계 대비 **통합**: `/잠재`+`/잠재합계` 2분할 → **스타포스식 단일 비교표**로 합치고 `/잠재합계` 폐기(potential-handoff.md D1). 컬럼 `순위·캐릭터·잠재 재설정·사용 큐브·사용 메소·등업`(도달 등급 색 뱃지, `table_image.GradeBadges` 신규 셀; 사용 메소 내림차순 정렬). `history/cube`+`history/potential` 합산, 캐시 type 둘. 레벨 매칭 불필요(`item_level` 직접). 기록0="기록 없음"(키미등록 구분). **사용 메소**=큐브 감정비+메소 재설정비(`potential_cost.py`, 나무위키 단가표). **G2(메소 단가표) 해소**. **잔류 게이트 1**: G1(등업 "성공"=등급 상승 — `scripts/spike_potential.py` 라이브 1콜로 확정). 상세 [potential-handoff.md](potential-handoff.md)·[potential-work-order.md](potential-work-order.md).

### 🔔 Phase 4 — 알림 / 스케줄러 🟡 일부 완료
- ✅ 스케줄러 인프라(APScheduler, KST) — 봇이 소유(setup_hook 시작 / close 종료)
- ✅ **/썬데이** (PR #3) — 금 10:10 정기 발송·1회 재시도無, "썬데이 메이플" title 매칭(다중=전부/0=조용히패스), notice_state 주차 중복방지, 상세 배너(제목+링크+기간) 출력, 알림 채널 켜기/끄기.
- ⬜ **/공지알림** *(미착수)* — 6회/일(10·12·14·16·18·21시) 폴링, 공지+업데이트(이벤트 제외), notice_state 카테고리별 식별자, 최초가동=baseline만. 공지/이벤트 API 미니 스파이크 선행(미해결 결정 #3).
- ⬜ **수동 썬데이 HTTP 엔드포인트**(FastAPI) *(미착수 — api는 현재 `/health`만)* — Bearer 토큰 인증, 바디(제목·링크·기간), sunday_alert 채널 즉시발송 + 주차 중복마킹(자동발송과 공유).

### 🛠️ Phase 5 — 운영 ⬜ 미착수
- ⬜ **일일 운영 요약** — *검증: 09:00 KST, 전날 error_log 집계(타입별 건수 + 미매칭 장비 상위 N) → ADMIN_CHANNEL_ID*

### 횡단 규칙 (전 Phase 적용 — design §7)
모든 비교 명령 defer 의무 · 임베드 통일 · 초과인원 버튼 페이지네이션 · /스펙만 5명 상한 · error_log는 **재시도 발생 건만** 기록.

## ⚠️ 미해결 결정 (해당 Phase 도달 시 사용자와 결정)

1. ✅ **Phase 1 (해소)** — Postgres는 docker `maple-mate-db`(postgres:16, host 5433)로 프로비저닝 완료.
2. ✅ **Phase 3 (해소)** — 기대값 데이터 소스 = **공식 확률표 + 강화비용 공식 직접 산출**(엔진), 검증 이미지 대조. 운빨 지표는 ADR-0002로 결정.
3. 🟡 **Phase 4 (부분)** — `/썬데이`로 넥슨 공지 API는 검증됨. `/공지알림`(공지+업데이트 폴링)은 카테고리/이벤트 제외 규칙 미니 스파이크가 여전히 필요.
4. 🟡 **Phase 3 `/잠재` (대부분 해소)** — 구현 완료(재설정·큐브·사용 메소·등업). **G2 해소**: 큐브 감정비 공식 + 메소 재설정 단가표(나무위키)를 `potential_cost.py`로 인코딩 → `사용 메소` 컬럼 활성(감정비+재설정비). 잔류 게이트 1: **G1**(등업 "성공"=등급 상승 가정 — `scripts/spike_potential.py` 라이브 1콜로 확정). 상세 [potential-handoff.md](potential-handoff.md).

## 📝 기술 스택 · ADR 현황

- **스택 확정: Python/discord.py(봇) + FastAPI(HTTP 엔드포인트) + PostgreSQL(DB).**
  사용자가 FastAPI+PostgreSQL 조합 숙련도 높음 → **스택·Postgres 선택은 ADR 생략**(위 [확정된 결정](#확정된-결정-그릴링-결과) 표가 기록 대신). ADR 번호는 비자명한 결정에만 사용한다(아래).
- **ADR-0001** — [nexon-personal-key-model](adr/0001-nexon-personal-key-model.md): Spike 0 GO 근거 + 죽은 대안 "봇 앱 키 하나로 전원 이력" 기각.
- **ADR-0002** — [starforce-luck-metric](adr/0002-starforce-luck-metric.md): 운빨 지표를 **메소 백분위**로 결정(운지수·성공 백분위 대안 기각).

## 다음 세션 권장 스킬

- **다음 작업(`/잠재` 게이트 해소 또는 `/공지알림`)**: `/잠재`는 G1(등업 미니스파이크 라이브 1콜)·G2(메소 단가표) 후 활성. `/공지알림`은 카테고리/규칙 미니 스파이크 선행 후 구현. 코드 작성은 `executor` 에이전트(복잡 작업 model=opus).
- **미니 스파이크 전 규칙 확정**: `/grill-with-docs` 재실행으로 미해결 결정(잠재 단가표·공지 카테고리 규칙) 해소.
- **API/SDK 사용 불확실 시**: `document-specialist` 에이전트(discord.py·넥슨 API 레퍼런스).

## 주의

- 사용자 전역 룰은 TDD/80% 커버리지를 요구하나, **이 프로젝트는 "실용 테스트"로 명시 합의**(순수 로직만 단위테스트, API mock). 과도한 E2E 강제 금지.
- 프로젝트 `CLAUDE.md`: 가정 금지·단순함 우선·외과적 변경. 추측성 추상화/기능 추가 지양.
- 첨부 작업 디렉터리에 무관한 타 프로젝트(214archives, HAMO) 포함 — maple-mate 외 건드리지 말 것.
