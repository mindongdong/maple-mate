# 작업지시서 — 공개 대비 스케일 튜닝 (deploy-plan 단계 2 선행)

> [deploy-plan.md](deploy-plan.md) §3 단계 2(공개 커뮤니티 대비 튜닝)를 그릴링 세션(2026-06-10)에서
> 전부 확정한 **실행용 SSOT**. deploy-plan 은 로드맵·근거, 이 문서는 "확정된 대로 무엇을 만드는가"에 집중한다.
> 시나리오 기준: **100서버 × 활성 5명 × 10명령/일 = 5,000명령/일**.
>
> **✅ 구현 완료 (2026-06-10)** — 3-1~3-6 전부 [PR #14](https://github.com/mindongdong/maple-mate/pull/14)
> (브랜치 `phase-8-scale-tuning`, 항목별 커밋, CI 그린). 지시서 대비 편차·구현 노트는 §7.

## 0. 시작점

- 베이스: `origin/main`(`bac8b4b`, Phase 7 CI 머지 완료) → 새 브랜치 **`phase-8-scale-tuning`** 분기.
- CI 게이트(lint·test·migrations)는 이미 구축([cicd-work-order.md](cicd-work-order.md)) — 본 작업도 PR → CI 그린 → 머지.
- **단계 3(샤딩·프로세스 분리·Redis)은 스코프 제외** — 100서버는 디스코드 샤딩 강제선(~2,500길드)의 4%.

## 1. 부하 산정 (그릴링 세션 — 모든 결정의 토대)

| 항목 | 수치 | 함의 |
|---|---|---|
| 넥슨 호출량 | ~30,000+ 콜/일 (스펙류 평균 ~6콜 × 5,000명령) | 개발단계 한도 1,000/일의 **30배** → 서비스단계 등록(§4) 없이는 코드 개선 무의미 |
| 피크 처리량 | ~1–2콜/초 | 전역 4/s로도 평균은 감당 — 문제는 평균이 아니라 **독점** |
| 독점 시나리오 | 이력류 cold 1건 = 최대 365콜 = 전역 스로틀 ~90초 점유 | 500명 유저면 일상적으로 발생 → **D2 키별 버킷**이 해소 |
| 구조적 낭비 | 개인키 호출(유저별 쿼터 별도)이 앱키와 같은 전역 버킷에 직렬화 | 넥슨 한도는 **키 단위** — 봇이 스스로 묶고 있었음 |

## 2. 확정 결정 (그릴링 세션)

| # | 결정 | 확정 |
|---|---|---|
| D1 | 스코프 | **단계 2 전체 선행**(코드 2-2~2-6 + 부하 시뮬 검증). 2-1·2-7은 운영자 작업으로 분리(§4). 단계 3 제외 |
| D2 | 스로틀 구조(2-2) | **키별 버킷**. 앱키 간격 = 환경변수(기본 0.25 → 서비스단계 등록 후 0.02), 개인키 = **0.2초(5/s) 고정**. 전역 단일 버킷 폐기 → [ADR-0004](adr/0004-per-key-throttle-buckets.md) |
| D3 | 쿨다운(2-4) | **명령군별 차등**(per-user): 이력류(`/스타포스`·`/잠재`) 30초당 1회 · 스펙류(`/스펙`·`/아이템`·`/유니온`) 10초당 1회 · 등록·설정류(`/등록`·`/썬데이`·`/공지알림`) 5초당 1회 · `/핑` 제외. discord.py 내장 `app_commands.checks.cooldown`(in-memory — 단일 인스턴스 전제). 초과 시 ephemeral 로 남은 시간 안내 |
| D4 | history_cache prune(2-5) | **`date` 기준 400일**(조회대상 날짜 < 오늘−400일 삭제). deploy-plan 원안(fetched_at 90일·error_log 답습)은 **기각** — 불변 과거 데이터를 지워 `최근1년` 재조회 시 개인키 수백 콜 재발생. 실행은 운영 요약 일일 잡의 error_log prune([summary.py:133](../maple_mate/error_log/summary.py#L133))에 편승 |
| D5 | 최신 스펙 캐시(2-6) | **클라이언트 레벨 TTL 30분**. `NexonClient._spec` 에서 `date=None` 응답을 `(path, ocid)` 키 in-memory 캐시 — 스펙류 전 엔드포인트를 한 곳에서 커버, 서비스 계층 무수정. 스펙류는 일 단위(D-1) 스냅샷이라 30분 stale 무해 |
| D6 | CPU 오프로딩(2-3) | 렌더·계산 호출부 3곳을 `asyncio.to_thread` 로: [table_image.py](../maple_mate/bot/table_image.py)·[item_card.py](../maple_mate/bot/item_card.py)·[expected_cost.py](../maple_mate/history/expected_cost.py)(마르코프). ProcessPool 기각(수십 ms 작업에 과잉) |
| D7 | 검증 | **httpx MockTransport 부하 시뮬 + 항목별 단위테스트**(CI 재현 가능·결정적). 라이브 부하테스트 없음(넥슨 한도·약관) |
| D8 | 작업 단위 | **한 브랜치 한 PR, 항목별 커밋**. 순서: D2 → D5 → D3 → D6 → D4 → D7 부하 시뮬 |

> **CONTEXT.md 변경 없음** — 스로틀·쿨다운·캐시는 봇 도메인 언어가 아니라 인프라 구현 용어.

## 3. 작업 항목 (커밋 순서대로)

### 3-1 키별 스로틀 버킷 (D2) 🔴 핵심

- [client.py:63-86](../maple_mate/nexon/client.py#L63-L86) 의 단일 `_lock`/`_next_allowed` 를
  **키별 dict**(`api_key → next_allowed`) 로 교체. 키 식별: `_request` 의 `api_key` 인자
  (None = 앱키 버킷, 그 외 = 해당 개인키 버킷).
- 간격: 앱키 = 생성자 인자 `throttle`(config 연결, 기본 0.25 유지), 개인키 = 상수 0.2초(5/s).
- [config.py](../maple_mate/config.py) 에 `NEXON_THROTTLE`(float, 기본 0.25) 환경변수 추가 → `main.py` 조립부에서 주입.
- 버킷 dict 는 entry 가 (등록 유저 수)개라 정리 불요 — 단, 주석으로 단일 프로세스 전제 명시(단계 3에서 Redis 대체).
- *→ verify: 단위테스트 — ① 개인키 A 연타 중 앱키 호출이 대기 없이 통과 ② 같은 키 연속 호출 간격 ≥ 버킷 간격 ③ `NEXON_THROTTLE` 주입 반영.*

### 3-2 최신 스펙 단기 캐시 (D5)

- `NexonClient._spec`([client.py:285-286](../maple_mate/nexon/client.py#L285-L286)) 에서 `date is None` 인 경우만
  `(path, ocid) → (응답, 저장시각)` in-memory 캐시, TTL 30분(상수). `date` 지정 호출은 비캐시(기존 `CombatPowerCache` 가 담당).
- *→ verify: 단위테스트 — 30분 내 동일 (path, ocid) 재호출 시 HTTP 0회 / TTL 경과 후 재조회 / date 지정 호출 비캐시.*

### 3-3 명령군별 쿨다운 (D3)

- 각 명령 데코레이터에 `@app_commands.checks.cooldown(1, N, key=lambda i: (i.guild_id, i.user.id))` 부착
  (이력류 30 · 스펙류 10 · 등록·설정류 5).
- `tree.on_error`(또는 공통 핸들러)에서 `CommandOnCooldown` 을 잡아 **ephemeral** 로
  "○초 후 다시 시도" 안내 — 기존 에러 임베드 경로([embeds.py](../maple_mate/bot/embeds.py)) 답습.
- *→ verify: 단위테스트 — 쿨다운 내 재호출이 `CommandOnCooldown` → ephemeral 안내, 경과 후 정상 실행.*

### 3-4 CPU 작업 `to_thread` (D6)

- 명령 계층에서 표 렌더·아이템 카드 렌더·마르코프 기대값 계산을 호출하는 지점을 `await asyncio.to_thread(...)` 로 래핑.
  대상 함수 자체는 순수 동기 유지(테스트 불변).
- *→ verify: 기존 렌더·기대값 테스트 그린(출력 불변) + 부하 시뮬(3-6)에서 이벤트루프 블로킹 부재.*

### 3-5 history_cache prune (D4)

- [summary.py:133](../maple_mate/error_log/summary.py#L133) 의 error_log prune 패턴을 답습해
  같은 일일 잡에서 `DELETE FROM history_cache WHERE date < (오늘 KST − 400일)` 추가.
- *→ verify: 단위테스트 — 401일 전 행 삭제 · 399일 전 행 보존 · error_log prune 와 같은 주기로 실행.*

### 3-6 부하 시뮬레이션 테스트 (D7)

- httpx `MockTransport` 에 인위 지연(~100ms)을 넣은 가짜 넥슨으로, **동시 20명령**
  (스펙류 다수 + 이력류 cold 1년 1건 혼합) 투입.
- 단언: ① 이력류 cold 진행 중에도 스펙류 응답이 시간 상한 내(전역 비차단 입증)
  ② 개인키 호출 간격 ≥ 0.2초 ③ 전 명령 완료(유실 없음).
- pytest 마커(예: `slow`)로 분리하되 CI 포함 가능한 수초 내 실행 목표.
- *→ verify: 이 테스트 자체가 deploy-plan 단계 2의 "동시 명령 20건 부하 시 큐 누적 없이 응답" 기준의 코드화.*

## 4. 운영자 작업 (코드 밖 — 머지 후)

| 작업 | 시점 | 효과 |
|---|---|---|
| 넥슨 **서비스단계 등록**(2-1) | 공개 홍보 전 | 앱키 한도 5/s·1,000/일 → 500/s·2,000만/일 |
| Render 환경변수 `NEXON_THROTTLE=0.02` | 서비스단계 승인 후 | 앱키 처리량 12배+ (등록 전 설정 금지 — 429 유발) |
| Render 인스턴스 0.5→2 vCPU(2-7) | 공개 홍보 전 | 렌더·마르코프 CPU 여유 + discord.py 메모리 |

## 5. 잔류 한계 (스코프 밖 — 인지만)

- **이력류 cold 1년 = 그 유저 기준 ~73초 대기**(365콜 ÷ 5/s). 키별 버킷으로 타인은 비차단이나 본인 UX 는 느림 — 캐시 워밍·진행 표시는 미채택(단순함 우선).
- **개인키 일일 1,000 한도**: `/스타포스`+`/잠재` cold 1년을 같은 날 치면 최대 365+730콜로 초과 가능 → 기존 429/에러 안내 경로로 처리, 쿨다운·캐시가 완화.
- **앱키 SPOF**·샤딩·분산 리미터는 단계 3([deploy-plan.md](deploy-plan.md) §3) 그대로 유보.

## 6. 산출물 체크리스트 (완료 정의)

- [x] D1~D8 확정 (그릴링 세션 2026-06-10) + [ADR-0004](adr/0004-per-key-throttle-buckets.md) 작성
- [x] 3-1 키별 스로틀 버킷 + `NEXON_THROTTLE` config
- [x] 3-2 스펙 30분 캐시
- [x] 3-3 명령군별 쿨다운 + ephemeral 안내 ([bot/cooldowns.py](../maple_mate/bot/cooldowns.py) + 트리 공통 핸들러)
- [x] 3-4 `to_thread` 오프로딩 (표 렌더 4명령 + 아이템 카드 + 마르코프 집계)
- [x] 3-5 history_cache prune(date−400일) — 운영 요약 일일 잡 편승
- [x] 3-6 부하 시뮬 테스트 그린 ([test_load_simulation.py](../tests/test_load_simulation.py), `slow` 마커 ~2.4초)
- [x] PR [#14](https://github.com/mindongdong/maple-mate/pull/14) + CI 그린 (lint·test·migrations, 전체 413 passed)
- [ ] 머지 → §4 운영자 작업 안내

## 7. 구현 기록 — 지시서 대비 편차·노트 (as-built, 2026-06-10)

| 항목 | 편차/노트 |
|---|---|
| 3-1 | 개인키 0.2s 는 모듈 상수 `PERSONAL_KEY_THROTTLE` + 생성자 인자 `personal_throttle`(기본값=상수)로 구현 — **env 비노출은 유지**(ADR-0004), 인자는 타이밍 단위테스트 주입용. 버킷은 `_ThrottleBucket`(키별 Lock + next_allowed) — 같은 키만 직렬화, 타 키 비차단 |
| 3-2 | 계획대로 [client.py `_spec`](../maple_mate/nexon/client.py) 에 `(path, ocid)` 캐시, `SPEC_CACHE_TTL=30분`. 캐시 엔트리 수 = 엔드포인트(10) × 조회 캐릭터 수라 정리 불요 |
| 3-3 | [bot/cooldowns.py](../maple_mate/bot/cooldowns.py) **팩토리 함수**로 구현 — `checks.cooldown` 데코레이터 객체를 여러 명령에 재사용하면 쿨다운 매핑이 공유되므로(이력류끼리 서로 차단) 명령마다 새로 생성. 안내는 명령별 핸들러가 아니라 **트리 공통 `on_app_command_error`**([bot/core.py](../maple_mate/bot/core.py)) — 비-쿨다운 에러의 앱로그 안전망 겸함 |
| 3-4 | "3곳" = 모듈 3개의 호출부 **6지점**: 표 렌더 4명령(스타포스·잠재·유니온·스펙) + 아이템 카드 1 + `aggregate_starforce`(마르코프) 1. 대상 함수는 동기 유지 → 기존 렌더·기대값 테스트 무수정 그린 |
| 3-5 | prune 함수는 [history/service.py](../maple_mate/history/service.py) 소유(`prune_old_history_cache` + 순수 `history_cache_cutoff`), 실행만 운영 요약 잡([scheduler.py](../maple_mate/notification/scheduler.py)) 편승 — error_log 도메인에 history 의존을 넣지 않기 위함 |
| 3-6 | cold "1년 1건"은 **12일치로 축소** — 365콜 × 0.2s ≈ 73초라 CI 불가. 비차단 속성(스펙류가 cold 종료 전 전부 완료)은 동일하게 단언, 실행 ~2.4초. 앱키 간격도 시뮬용 0.05s(실값 0.25면 5초+) |
| 테스트 함정 | discord.py `Cooldown.update_rate_limit` 은 `current or time.time()` — **epoch 0 타임스탬프로 시각 주입하면 실시간으로 폴백**해 깨진다. 테스트는 0 아닌 기준점(`_BASE`) 사용 |
| 부수 변경 | `NEXON_THROTTLE` 을 [.env.example](../.env.example) 에 추가(서비스단계 승인 전 설정 금지 경고 포함) · pytest `slow` 마커 등록 · ConfigError 메시지 "정수 필요"→"숫자 필요"(float 키 수용) |
