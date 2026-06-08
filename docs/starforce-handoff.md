# 핸드오프 — `/스타포스` 기능 (다음 세션 인계)

> `/스타포스`(Phase 3 이력류 일부)는 **구현·라이브 검증 완료** 상태다. 운빨 지표가 두 번 개편됐고
> (운지수→성공백분위→**메소 백분위**), 기간 1년 확장·손익 부호 직관화·레벨 자동학습이 추가됐다.
> 최근 보강: 운빨 MC 정밀도(N=5000·동일구간 탈상관)·운빨 정수표시·**세트명 부분일치 매칭**·
> **집계 제외정책(특정장비·레벨 100 미만)**·보스장신구 시드 34종(사용자·넥슨 API 교차검증).
> 이 문서 하나로 다음 세션이 이어서 개선할 수 있도록 **현재 상태·핵심 내부·잔류·백로그**를 정리한다.

## 참조 (중복 금지 — 경로로 참조)

- [docs/starforce-work-order.md](starforce-work-order.md) — 최초 작업지시서(빌드 단위·확정 결정)
- [docs/phase3-work-order.md](phase3-work-order.md) — Phase 3 전체(이력류 3명령) 상위 문서
- [docs/starforce-expected-value-data.md](starforce-expected-value-data.md) — **확률표·비용공식·기대값·운빨 모델**(§1~8). 검증 이미지 `기댓값/`는 **로컬 전용(미커밋)** — 엔진 테스트는 이미지에서 읽은 값을 하드코딩.
- [docs/adr/0002-starforce-luck-metric.md](adr/0002-starforce-luck-metric.md) — 운빨 지표 결정·기각 대안(반드시 읽을 것)
- [CONTEXT.md](../CONTEXT.md) — 도메인 용어(운빨 수치·총 사용 메소·기댓값 대비 손익·키미등록 vs 기록없음)
- [docs/api/history.md](api/history.md) — `history/starforce` 필드 실측

## 현재 동작 (한 줄 요약)

`/스타포스 기간:<프리셋> [시작일] [종료일] [대상1~5]` → 키 등록자별로 기간 내 강화 이력을 모아
아이템별 `시작★→최종★`을 잡고, **운빨수치(메소 백분위)·총 사용 메소·기댓값 대비 손익·기준건수**를
PNG 표로 비교한다(운빨 내림차순, 최상위 강조). 부분 성공(키미등록·기록없음·조회실패·미등록)은 묶음 필드.

## 파일 맵 (`maple_mate/history/`, 약 1030줄)

| 파일 | 역할 | 핵심 심볼 |
|---|---|---|
| `starforce_data.py` | 확률표·비용공식·도달스타 (순수 데이터) | `STARFORCE_PROB`(30행), `cost(level,star)`, `reachable_star`, `DESTROY_STAR=12`, `MAX_STAR=30`, `_round100`(round-half-up) |
| `expected_cost.py` | 기대값·운빨 엔진 (순수) | `expected_meso`(마르코프), `actual_meso`, `net_meso`, **`meso_luck_percentile`**(N=5000·아이템별 `_DECORR_STRIDE` 탈상관), `_climb_attempt_samples`(MC,캐시), `_item_meso_samples`, `DEFAULT_SIMS=5000` |
| `equipment_level.py` | 레벨 매칭 + 자동학습 + 제외정책 | `match_level`(세트>장착/학습>시드), `EQUIPMENT_SET_LEVEL`(부분일치 고정레벨), `EQUIPMENT_LEVEL_SEED`(보스장신구 정확일치 34종), `EXCLUDED_ITEMS`·`MIN_AGGREGATE_LEVEL=100`(집계 제외), `_set_level`, `fetch_equipped_levels`, `load_learned_levels`, `learn_equipment_levels` |
| `service.py` | 기간·페치·캐시·집계 (전달-무관) | `resolve_period`(`MAX_PERIOD_DAYS=365`), `HistoryTarget`, `get_history_targets`, `parse_attempts`, `fetch_starforce_records`, **`aggregate_starforce`**(제외정책 `excluded_items`·`min_level` 분기), `StarforceAttempt`, `StarforceSummary` |
| `commands.py` | `/스타포스` 디스코드 어댑터 | `handle_starforce`, `_process_target`, `_build_table`, `_format_luck`(`상위 X%`), `_format_profit`(이득`+`/손해`−`), `_PERIOD_CHOICES` |
| `models.py` | ORM | `HistoryCache`(PK ocid,type,date), `LearnedEquipmentLevel`(PK item_name) |
| `cache.py` | 캐시 TTL 판정(순수) | `is_cache_fresh`(과거=불변, 오늘=5분 TTL) |

재사용: `bot/comparison.py`(`table_image_message`·`highest_indices`·`attach_failures`·`respond_with_pages`), `bot/table_image.py`(`Highlight`), `character/service.py`(`format_eok`), `registration/service.py`(`Target`·`TargetOutcome`·`classify_target_error`), `nexon/client.py`(`starforce_history`·`character_item_equipment`).

## 핵심 엔진 내부 (개선 전 반드시 이해할 것)

### 1. 비용공식 `cost(level, star)` — `starforce_data.py`
- 0~9성/10성+ 두 공식, **round-half-up**(`math.floor(x/100+0.5)*100`, Python 기본 round 아님).
- 검증: 200·250레벨 [기댓값/](../기댓값/) "강화비용" 전 셀 일치(`test_starforce_data.py`).

### 2. 기대값 `expected_meso(level, start★, end★)` — 마르코프 흡수 기대비용
- 전이: 성공→s+1 / 유지→s / 파괴→12성. `C[s]=a[s]+b[s]·X`(X=C[12]) 하향전개 → `X=a[12]/(1−b[12])` 고정점.
- 검증: `expected_meso(level,0,N)` == 이미지 "누적기댓값"(±1, floor vs round)(`test_expected_cost.py`).

### 3. 운빨수치 `meso_luck_percentile(items)` — **메소 백분위 (ADR-0002 최종)**
- `items = [(level, 시작★, 최종★, 실제메소), ...]`(레벨 매칭 아이템). 실제 총 메소가 가능 분포에서 차지하는 백분위 `L`(높을수록 싸게=운 좋음). 표시 `상위 (100−L)%`.
- **분포 = 몬테카를로(N=`DEFAULT_SIMS`=5000).** 핵심: "성수별 시도횟수" 분포는 **레벨 무관** → `_climb_attempt_samples(start,end)`를 `lru_cache`+결정적 시드로 1회만 계산, 런타임은 `cost(level,·)` 곱(`_item_meso_samples`). 매 요청 재시뮬 없음.
- **동일 구간 탈상관**: 같은 `(시작★,최종★)` 아이템(예: 방어구 세트 동시 강화)은 표본열을 공유 → 인덱스 그대로 더하면 합 분포가 완전 상관(표준편차 √m→m배, 운빨이 50%로 압축). 아이템별 `_DECORR_STRIDE` 오프셋 회전으로 독립 페어링 복원(`meso_luck_percentile`).
- ⚠️ **기준점**: "상위 50%"=중앙값. 비용 분포 우편향이라 중앙값<평균(기댓값) → "기댓값대로 쓴 사람"은 상위 ~65%. **손익과 정렬은 일치, 중립점만 다름**.
- 이력: ①운지수(실제÷기대,무진행시`—`) → ②성공 확률 백분위(포아송-이항,손익과 어긋남) → ③메소 백분위. ②③ 전환 근거는 ADR-0002.

### 4. 레벨 매칭 — `세트명(무조건) > 현재 장착 > 자동학습 > 시드 > None`
- **세트명 부분일치(`EQUIPMENT_SET_LEVEL`)**: 아이템명에 세트명 포함 시 무조건 고정레벨. 에테르넬250·아케인200·앱솔랩스160·파프니르/하이네스/트릭스터/이글아이150·마이스터140. 세트 방어구는 직업군별 부위명이 달라(에테르넬 나이트아머/메일/헬름…) 정확일치로는 누락이 잦아 부분일치로 일괄 커버. `match_level`이 `_set_level` 먼저 확인.
- **정확일치 시드(`EQUIPMENT_LEVEL_SEED`)**: 부위별 레벨이 제각각인 보스 장신구(보스장신구·여명·칠흑·광휘) 34종 + 제네시스 무기. 레벨은 사용자 제공·넥슨 API 학습값과 교차검증(충돌 0).
- `match_level`은 순수((equipped, seed)만). 명령부(`_process_target`)가 `{**learned, **equipped}`로 합쳐 넘김(현재 장착 우선).
- **자동학습**: `/스타포스`가 각 대상의 현재 장착 레벨을 `learn_equipment_levels`로 upsert → 누군가 지금 낀 장비는 학습돼 나중에 교체돼도 매칭. `load_learned_levels`는 명령당 1회.
- **집계 제외(매칭과 별개, §5)**: `EXCLUDED_ITEMS`(예: 슈피겔만의 평범한 목걸이)·`MIN_AGGREGATE_LEVEL=100` 미만은 집계에서 통째 제외(분모·제보에서도) — '미상'과 구분.

### 5. 집계 `aggregate_starforce(attempts, level_of, *, excluded_items, min_level)` — `service.py`
- 아이템별: 시작★=첫(시간순) before_star, 최종★=기간 내 최고 after_star.
- **운빨·메소 모두 레벨 매칭 아이템만**(동일 기준). 미매칭(레벨 미상)은 `unmatched_items`+`error_log(unmatched_equipment)`, 표에 `M/N건`.
- **제외정책**: `excluded_items`/`min_level 미만`은 집계·**분모(`total_count`)**·제보 모두에서 빠짐(미상과 구분). `total_count`=매칭+미상.
- `StarforceSummary(luck_score, total_meso, net_meso, expected, matched_count, total_count, unmatched_items)`.

## 라이브 환경 · 실행

- **실행**: `uv run python -m maple_mate` (discord 봇 + uvicorn :8080 동시). `.env` 필수 키 채워져 있음.
- **DB**: docker `maple-mate-db`(postgres:16, host 5433). `DATABASE_URL` in `.env`. **마이그레이션 수동**: `uv run alembic upgrade head`(현재 head `1215f787176d` = learned_equipment_level).
- **테스트**: `uv run pytest`(283 passed, 1 deselected=라이브). `uvx ruff check maple_mate/`.
- **등록 현황**(guild `1511938398942662787`, `DEV_GUILD_ID`와 일치→즉시 동기화): 키 등록자 4명 — 손바·점프투파이썬·라딘라면·네벨루크. 4명 모두 365일 starforce 캐시 적재됨.
- **검증 팁**: 날짜당 1콜이라 콜드 1년은 느림(개인 단위 권장). 표 렌더만 눈으로 보려면 `_build_table`에 합성 `StarforceSummary` 넣어 PNG 저장(net = total−expected, 음수=이득).
- ⚠️ 진단 스크립트 `/tmp/sf_diag.py`는 stale(제거된 `luck_score` import) — 참고 말 것.

## 알려진 이슈 · 잔류 리스크

1. **운빨 중립점 ≠ 손익 0** — 상위 50%=중앙값, 손익 0=평균(우편향). 정렬 방향은 일치하나 중립점 어긋남(ADR-0002 결정 5).
2. **운빨(상대 백분위) vs 손익(절대액) 순위** — 강화 규모가 매우 다른 두 사람은 미세하게 다를 수 있음(성공운 시절보다 훨씬 완화).
3. **레벨 매칭 한계** — 세트 부분일치 + 보스장신구 시드 34종으로 커버리지 대폭 확대. 자동학습은 현재 누군가 장착 중인 장비만 가능. 남는 미상은 `M/N건` 투명 표시+제보. **슈피겔만 평범한 목걸이**는 `EXCLUDED_ITEMS`로 명시 제외('미상' 아님), **페어리 하트(Lv100)**는 매칭됨(100 미만이 아니라 포함).
4. **콜드 1년 latency** — 글로벌 스로틀 0.25초 × 날짜당 1콜. 서버 전체 콜드 ≈6분(캐시 후 즉시). 키별 병렬·스로틀 튜닝은 백로그.
5. **MC 워밍업** — 새 `(시작★,최종★)` 쌍 첫 등장 시 시뮬 비용(프로세스 캐시 후 즉시, 재기동 시 콜드).
6. **파괴 모델** — 12성 하락 + 스페어/복구비 0(plain). 라이브 하락 빈도·복구비 미반영(실제는 이력 직접합산이라 무영향, 기대값은 메수라이브 기준).
7. **닉 변경** — `character_name` 불일치로 과거 이력 누락 가능(잔류).
8. **오늘 캐시 TTL 5분** — 당일 반영 지연 미측정.

## 백로그 · 다음 개선 아이디어

- **`/잠재`·`/잠재합계`** (스코프 밖, 미착수) — potential 미니 스파이크 게이트(`scripts/spike_potential.py`) + 메소 재설정 단가표 필요. [phase3-work-order.md](phase3-work-order.md) §6·§7.
- **운빨 표시 옵션** — 사용자가 `상위 X%` 대신 `0~100 운빨점수`, 또는 손익 절대액 기준 정렬을 원할 수 있음(쉬운 변경).
- **레벨 커버리지** — 세트 부분일치 + 보스장신구 시드로 상당 부분 해결. 추가 세트/단품은 `EQUIPMENT_SET_LEVEL`/`EQUIPMENT_LEVEL_SEED`에 보강. 또는 정적 아이템 DB API 도입.
- **latency** — numpy 도입(MC 벡터화)·키별 병렬 스로틀·시작 시 흔한 (start,end) 프리워밍.
- **파괴/복구 모델 정교화** — 흔적복구·스페어 비용(restoreResourceTable, 수치 미수령) 반영 시 기대값·운빨 재검토.
- **중립점 정렬** — 손익의 "기댓값"을 중앙값 기준으로 바꾸면 운빨 50%와 정렬되나, 표시 "기댓값" 의미가 바뀜(트레이드오프, ADR-0002 대안 검토).

## 테스트 맵

- `test_starforce_data.py` — cost vs 이미지·reachable·확률표 형태
- `test_expected_cost.py` — `expected_meso` vs 누적기댓값·`meso_luck_percentile`(MC평균≈마르코프·쌀수록 운↑·무진행)
- `test_equipment_level.py` — 매칭 우선순위·세트 부분일치(마이스터 포함)·보스장신구 시드·학습 병합·장착 파싱
- `test_history_period.py` — 프리셋(최근90일·최근1년 포함)·365 클램프·미래컷
- `test_history_aggregate.py` — 시작/최종★·matched/total·캐릭터 필터·결과파싱·운빨=매칭만·제외정책(명시제외·100미만)
- `test_starforce_command.py` — 기록없음 vs 조회실패·미매칭 적재·`_format_profit` 부호
- `test_comparison.py` — `highest_indices`·표 렌더

> 순수 로직만 단위테스트(실용 테스트 합의). DB 적재(`fetch_starforce_records`·learned upsert)·E2E는 라이브 검증.
