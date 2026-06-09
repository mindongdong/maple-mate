# 작업 계획 · 진행 현황 — maple-mate 디스코드 봇

> 친구 그룹용 메이플 디스코드 봇. 그릴링(`/grill-with-docs`)으로 기반 결정을 모두 확정함.
> 이 문서는 **Spike 0 → Phase 5** 전체 로드맵이자 진행 현황 기록이다.

## 목적

설계 명세는 상세하나 기술 기반(언어·DB·API 검증·빌드순서·테스트)이 비어 있어, 그릴링에서 5개 포크를
모두 결정하고 빌드 가능한 작업 계획으로 변환했다. **Spike 0 ~ Phase 3은 완료**, **Phase 4(`/썬데이`·
`/공지알림`)는 일부 완료**이며 나머지(수동 HTTP 썬데이·운영 요약)가 남았다. 아래 진행 현황 참조.

## 진행 현황 (2026-06-09 기준)

| 단계 | 상태 | 비고 |
|---|---|---|
| Spike 0 — 넥슨 history API 검증 | ✅ 완료 | 키 스코프(ocid 부재)·과거 1년 조회·장비레벨 미제공 실측 확인 |
| Phase 1 — 기반 + `/등록` | ✅ 완료 | PR #1 |
| Phase 2 — 스펙류(`/스펙`·`/유니온`·`/아이템`) | ✅ 완료 | PR #2 |
| Phase 3 — 이력류 | ✅ 완료 | **`/스타포스`(PR #4)·`/잠재`(PR #5) 완료** · `/잠재합계` 폐기(통합) · G2(메소 단가표) 해소 · G1(등업 라이브 확정)만 잔류 검증 |
| Phase 4 — 알림 | 🟡 일부 | **`/썬데이`+스케줄러(PR #3)·`/공지알림`(PR #7) 완료** · 수동 HTTP 썬데이만 미착수 · 미해결 결정 #3 해소(스파이크 불요 확인) |
| Phase 5 — 운영 요약 | ✅ 완료 | grill 완료 → "운영 오류 대응 보고"로 설계(선별·0건생략·앱키빨강·retention). 작업지시서=docs/phase5-work-order.md |

**다음 작업 후보**: 구현 단계 종료 — 남은 것은 **봇 가동 시 라이브 검증**뿐. **Phase 5 운영 요약** 발송 1회(`scripts/trigger_ops_summary.py` — 앱키 빨강·"외 N종"·헬스 command 분해 눈 확인). `/잠재` G1 등업 라이브 확정은 봇 가동 시 `scripts/spike_potential.py` 1콜로 마무리. `/공지알림` 6시각 폴링·baseline은 봇 가동 시 1주기 관찰.

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

### 🎲 Phase 3 — 이력류 ✅ 완료 *(키 게이트, 최난도)*
- ✅ **기대값·운빨 엔진**(선행) — 성공/파괴 확률표 + 정가 메소 비용공식(round-half-up) → 마르코프 흡수 기대비용. 데이터 소스는 **공식 확률표+비용공식 직접 산출**(미해결 결정 #2 해소), 검증 이미지(`기댓값/`, 로컬 전용) 대조.
- ✅ **/스타포스** (PR #4) — 설계 대비 **진화**: 운빨 지표 `운지수(실제/기대)` → `성공 백분위` → **`운빨수치(메소 백분위)`** 3차 개편(ADR-0002). 기간 상한 30일 → **1년**(최근90일·최근1년 프리셋 추가). 손익 부호 직관화(이득`+`/손해`−`). 레벨 매칭은 **세트명 부분일치 > 현재장착 > 자동학습 > 시드(보스장신구 34종) > 미상** + 집계 제외정책(`EXCLUDED_ITEMS`·레벨 100 미만). `M/N건` 투명표시·`unmatched_equipment` error_log 유지. 상세 [starforce-handoff.md](starforce-handoff.md).
- ✅ **/잠재** (PR #5) — 설계 대비 **통합**: `/잠재`+`/잠재합계` 2분할 → **스타포스식 단일 비교표**로 합치고 `/잠재합계` 폐기(potential-handoff.md D1). 컬럼 `순위·캐릭터·잠재 재설정·사용 큐브·사용 메소·등업`(도달 등급 색 뱃지, `table_image.GradeBadges` 신규 셀; 사용 메소 내림차순 정렬). `history/cube`+`history/potential` 합산, 캐시 type 둘. 레벨 매칭 불필요(`item_level` 직접). 기록0="기록 없음"(키미등록 구분). **사용 메소**=큐브 감정비+메소 재설정비(`potential_cost.py`, 나무위키 단가표, **G2 해소**). **잔류 검증 1**: G1(등업 "성공"=등급 상승 — 봇 가동 시 `scripts/spike_potential.py` 1콜로 확정). 상세 [potential-handoff.md](potential-handoff.md)·[potential-work-order.md](potential-work-order.md).

### 🔔 Phase 4 — 알림 / 스케줄러 ✅ 완료
- ✅ 스케줄러 인프라(APScheduler, KST) — 봇이 소유(setup_hook 시작 / close 종료)
- ✅ **/썬데이** (PR #3) — 금 10:10 정기 발송·1회 재시도無, "썬데이 메이플" title 매칭(다중=전부/0=조용히패스), notice_state 주차 중복방지, 상세 배너(제목+링크+기간) 출력, 알림 채널 켜기/끄기.
- ✅ **/공지알림** (PR #7) — 6회/일(10·12·14·16·18·21시 KST) 폴링, 공지(`notice`)+업데이트(`notice-update`), **이벤트 제외**(`/썬데이` 담당). 신규 판정=카테고리별 `notice_id` 최대값(`id > last_id`), **최초가동=baseline만**(과거 미발송), 다건=오래된→최신 전부. 텍스트 임베드(제목+링크+등록일)·10개 청킹. 미니 스파이크는 **불요로 판명**(Spike 0에서 세 엔드포인트 실호출 검증 완료, 미해결 결정 #3 해소). 리뷰 반영: **마커 전진-only**(짧은 페이지 시 중복 재발송 차단)·`updated_at` on_conflict 명시·`max_instances=1`. 검증 도구 `scripts/trigger_notice.py`. 전달-무관 계층(`notification/notice_service.py`).
- ✅ **수동 썬데이 HTTP 엔드포인트**(FastAPI) — `POST /sunday/broadcast`, Bearer 토큰 상수시간 비교(`secrets.compare_digest`, 실패 401 단일), 바디(제목 필수·링크·기간 선택, 단일 이벤트), sunday_alert 채널 즉시발송 + 주차 중복마킹(자동발송과 공유). **마킹 게이트는 자동잡(`channels>0`)과 의도적 분기 — `sent>0`일 때만** 마킹해 실제 전달 0이면 금요일 자동발송을 살린다(핸드오프 #7). 주차 dedup 미체크(운영자 override). `app.state.bot` 주입으로 HTTP→봇 배선. 검증 도구 `scripts/trigger_sunday.py`(HTTP 호출형으로 교체). 상세 [manual-sunday-handoff.md](manual-sunday-handoff.md)·[manual-sunday-work-order.md](manual-sunday-work-order.md).

### 🛠️ Phase 5 — 운영 ✅ 완료
- ✅ **운영 요약** — 설계 §6 "타입별 건수(전체)" → **"운영 오류 대응 보고"로 진화**(grill). 매일 09:00 KST, 전날 error_log를 **운영자가 대응 가능한 오류만 선별**: ① 미상 장비(`unmatched_equipment` distinct+빈도순 상위10 → 시드 보강) ② 봇 앱키 실패(`auth_invalid` & `discord_user_id IS NULL`, 최우선·🔴빨강) ③ 헬스(nexon_api/timeout/rate_limit, 타입+command 분해+대표 detail). **친구 개인 키 실패는 제외**(자가 발견). **세 섹션 모두 비면 발송 생략**(0건 노이즈 차단). 임베드 1개(섹션 순서 앱키→미상→헬스). 같은 09:00 잡에서 **90일 retention prune**. 단일 채널(`ADMIN_CHANNEL_ID`, 글로벌·`guild_id` 무시). 모듈: `error_log/summary.py`(순수 집계+DB) + `notification/scheduler.py`(임베드·잡). 구현 완료. 상세 [phase5-work-order.md](phase5-work-order.md)·용어 [CONTEXT.md](../CONTEXT.md) `운영 요약`.

### 횡단 규칙 (전 Phase 적용 — design §7)
모든 비교 명령 defer 의무 · 임베드 통일 · 초과인원 버튼 페이지네이션 · /스펙만 5명 상한 · error_log는 **재시도 발생 건만** 기록.

## ⚠️ 미해결 결정 (해당 Phase 도달 시 사용자와 결정)

1. ✅ **Phase 1 (해소)** — Postgres는 docker `maple-mate-db`(postgres:16, host 5433)로 프로비저닝 완료.
2. ✅ **Phase 3 (해소)** — 기대값 데이터 소스 = **공식 확률표 + 강화비용 공식 직접 산출**(엔진), 검증 이미지 대조. 운빨 지표는 ADR-0002로 결정.
3. ✅ **Phase 4 (해소, PR #7 머지)** — `/공지알림` 구현 완료. **미니 스파이크는 불요로 판명**: Spike 0(2026-06-04)에서 `notice`·`notice-update`·`notice-event` 세 엔드포인트를 이미 실호출 검증([docs/api/notice.md](api/notice.md))해 게이트가 stale 이었음. 규칙 확정: 대상=공지+업데이트(이벤트 제외), 신규판정=카테고리별 `notice_id` 최대값, 최초가동=baseline만, 다건=오래된→최신 전부, 썸네일=텍스트만(미리보기 후 제외).
4. ✅ **Phase 3 `/잠재` (해소, PR #5 머지)** — 재설정·큐브·사용 메소·등업 구현 완료. **G2 해소**: 큐브 감정비 공식 + 메소 재설정 단가표(나무위키)를 `potential_cost.py`로 인코딩 → `사용 메소` 컬럼 활성. 잔류 검증: **G1**(등업 "성공"=등급 상승 — 봇 가동 시 `scripts/spike_potential.py` 1콜로 확정). 상세 [potential-handoff.md](potential-handoff.md).

## 📝 기술 스택 · ADR 현황

- **스택 확정: Python/discord.py(봇) + FastAPI(HTTP 엔드포인트) + PostgreSQL(DB).**
  사용자가 FastAPI+PostgreSQL 조합 숙련도 높음 → **스택·Postgres 선택은 ADR 생략**(위 [확정된 결정](#확정된-결정-그릴링-결과) 표가 기록 대신). ADR 번호는 비자명한 결정에만 사용한다(아래).
- **ADR-0001** — [nexon-personal-key-model](adr/0001-nexon-personal-key-model.md): Spike 0 GO 근거 + 죽은 대안 "봇 앱 키 하나로 전원 이력" 기각.
- **ADR-0002** — [starforce-luck-metric](adr/0002-starforce-luck-metric.md): 운빨 지표를 **메소 백분위**로 결정(운지수·성공 백분위 대안 기각).

## 다음 세션 권장 스킬

- **다음 작업(라이브 검증)**: Phase 5 운영 요약 구현 완료(`error_log/summary.py`·09:00 잡·`scripts/trigger_ops_summary.py`·단위테스트 21개). 봇 가동 시 `scripts/trigger_ops_summary.py` 1회로 임베드 눈 확인.
- **API/SDK 사용 불확실 시**: `document-specialist` 에이전트(discord.py·넥슨 API 레퍼런스).

## 주의

- 사용자 전역 룰은 TDD/80% 커버리지를 요구하나, **이 프로젝트는 "실용 테스트"로 명시 합의**(순수 로직만 단위테스트, API mock). 과도한 E2E 강제 금지.
- 프로젝트 `CLAUDE.md`: 가정 금지·단순함 우선·외과적 변경. 추측성 추상화/기능 추가 지양.
- 첨부 작업 디렉터리에 무관한 타 프로젝트(214archives, HAMO) 포함 — maple-mate 외 건드리지 말 것.
