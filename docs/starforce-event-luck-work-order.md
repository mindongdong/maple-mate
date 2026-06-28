# 작업지시서 — `/스타포스` 이벤트 보정 운빨수치 + 레벨/미상 정리

> **근거 결정:** [ADR-0016](adr/0016-starforce-event-adjusted-luck.md)(본 작업으로 작성 — 초안 §10), 기존 지표 [ADR-0002](adr/0002-starforce-luck-metric.md)(이벤트·정가 전제 **부분 개정**), 계정 합산 [ADR-0007](adr/0007-history-account-wide.md), 표시 정체성 [ADR-0015](adr/0015-history-account-identity-display.md).
> **하우스 스타일 레퍼런스:** [scheduler-category-filter-work-order.md](scheduler-category-filter-work-order.md), [starforce-work-order.md](starforce-work-order.md), [starforce-handoff.md](starforce-handoff.md).
> **그릴링 출처:** `/grill-me` 세션(2026-06-28). 사용자 피드백 2건(상위 0% 불합리 / 레벨 미상 문구·표시 제거) → 데이터 실증 기반 설계.
> **상태:** 설계 확정·**미구현**. 스키마 변경 없음(마이그레이션 불요). 기존 `history_cache` 원본으로 재집계·검증 가능(재페치 불요).

---

## 0. 한 줄 목표

`/스타포스` 운빨수치가 **"상위 0%"로 떼몰리는 근본 원인(이벤트 무반영)** 을 고친다 — 강화 당시 이벤트(파괴확률 감소·비용 할인)를 기대값·분포 계산에 반영해 "같은 조건에서 남들보다 잘 풀렸나"만 남긴다. 동시에 **11성 이상만 집계**로 전환해 1+1 이벤트·저성 잡음·레벨 미상 장비를 한꺼번에 걸러내고, "레벨 미상 장비 제외" 문구와 표의 `M/N건` 표시를 제거한다.

---

## 1. 배경·증거 (다음 세션이 재도출하지 말 것)

**문제 재현 (이미지 `starforce_0628.png`):** 상위 2명이 동시에 운빨 "상위 0%", 임우석은 **271만 메소 사용에 +18억 손익**. 비현실적.

**데이터 실증** (로컬 DB = 본 운영 데이터 미러, `DATABASE_URL` localhost:5433, `history_cache` 원본 jsonb 분석):

- 운빨수치 정의(현행)는 사용자 의도와 **부합**: `meso_luck_percentile`은 같은 등반을 MC 5천 회 돌린 메소 분포 대비 백분위. 중앙값=상위 50%. → 정의는 옳음.
- **진짜 원인 = 이벤트 무반영.** 모델은 *정가·무이벤트 파괴확률* 로 기대치를 잡는데([starforce_data.py](../maple_mate/history/starforce_data.py) docstring "할인/파괴방지 미적용"), 실제 **15성+ 시도 1,335건 중 898건(67%)이 파괴확률 30% 감소 이벤트 중**. 파괴↓ → 재등반↓ → 실제 메소가 무이벤트 기대치보다 구조적으로 쌈 → 거의 전원 99~100 백분위 → 표시 반올림 `:.0f`로 "상위 0%".
- **데이터에 존재하는 이벤트** (전체 5,145시도, API `starforce_event_list` per-record):
  | 이벤트 | 값 | 비율 | 처리 |
  |---|---|---|---|
  | 파괴확률 감소 | `destroy_decrease_rate=30` | 48%(고성 67%) | **모델링(중립화)** |
  | 강화비용 할인 | `cost_discount_rate=30` | 51% | **모델링(실지불·중립화)** |
  | 1+1(성공시 2성↑) | `plus_value=1` | 6% | **11성 필터로 무력화**(10성 이하 전용) |
  | 5/10/15 100%성공 | `success_rate=100,100,100` | 3% | 미모델(게임에서 폐지됨) |
  | 복구비 할인 | `recovery_cost_discount_rate` | 9% | 무관(모델 복구비=0) |
  | 찬스타임 | — | 0% | 없음 |
  | 별캐치 | `starcatch_result` 성공/실패 | 성공30%·실패55% | **운으로 유지**(달력 이벤트 아님) |
- **`starforce_event_range`** 가 이벤트 적용 성수까지 명시(파괴감소=`15,16,...,21`, 할인=`0~29`) → 성수별 정확 반영 가능.
- **레벨 미상 장비 전수**(error_log `unmatched_equipment`)가 도달한 최고 성수: 블랙 완드 7성, 슈피겔만의 평범한 목걸이 7성, 페어리 하트 7성, 10주년 화이트 슈트/치클/케이프 4성. → **전부 11성 미달.** 11성 필터가 곧 레벨 미상 필터.
- **11성 = 108레벨 이상에서만 가능**(`reachable_star`: ≤107레벨 → 최대 10성). 11성+ 도달 67종은 전부 엔드게임 장비 → 세트/시드 매칭됨. **슈페리얼 장비 11성+ = 0건**(오집계 위험 없음).
- 파괴감소 ON/OFF 결과분포는 성수 혼재로 미결정(ON 파괴 2.7% vs OFF 3.0%, 방향만 일치) → **공식 메커니즘 채택**(§3).

---

## 2. 확정 결정 (그릴링 6+)

### #1 운빨수치 = 이벤트 보정
1. **집계 범위: `before_star ≥ 11`(11성 이상 시도)만.** 1+1(10성 이하 전용) 자동 무력화 + 저성 잡음·레벨 미상 제거. 파괴 바닥 12성이라 11성부터 등반이 닫혀 있어(11성에선 파괴 없음, 파괴→12 복귀도 ≥11) 계산 자기완결.
2. **운에서 제외(중립화): 파괴확률 30% 감소 · 강화비용 30% 할인.** 시뮬레이션·기대치를 **사용자가 실제 강화한 이벤트 조건과 동일하게** 돌려 공정 비교. → 이벤트 때 강화했다는 이유만으로 "운 좋음" 안 됨.
3. **운으로 유지: 실제 성공/파괴 결과 + 별캐치 성공/실패.** 별캐치는 달력 이벤트가 아니라 본인 미니게임 → 현 "별캐치 상시 성공" 확률표 유지(자주 놓치면 운 나쁘게 나옴 = 의도).
4. **파괴감소 처리: `d' = d×0.7`, 줄어든 `0.3d`는 유지로, 성공 `p` 불변**(공식 메커니즘, §3).
5. **메소 표시 = 실지불액(할인 반영).** 총 사용 메소 = 실제 낸 메소(할인 반영) / 기댓값 = 같은 이벤트 조건 기대치 / 손익 = 둘의 차 = **순수 운**. ⚠️ 양쪽 모두 할인 반영이라 **손익은 여전히 할인-중립**(CONTEXT §165 의도 유지) — 정가 폐기는 *표시 금액*만 바꿈.
6. **운빨 표시: "상위 1% 미만" 바닥**(절대 "상위 0%" 금지), 정수 %, **동점은 손익(이득)으로 순위.** (대칭으로 불운 극단도 "상위 99% 초과" 권장 — 미세 폴리시.)

### #2 레벨/미상 정리 (11성 필터가 대부분 자동 해결)
7. **"레벨 미상 장비 제외" 임베드 필드 삭제.** (미상 장비 전부 ≤7성 → 11성 필터로 진입 차단, 문구 생길 일 없음.)
8. **표 기준건수 `21/47건` → 단일 건수 `21건`.** 11성 필터로 미상이 사라져 분자=분모.
9. **새 임베드 필드: "11성 이상 강화만 집계해요 (저성·이벤트 장비 제외)".** (별 기준만 — 레벨 숫자 미표기, 사용자 선택.)
10. **잔여 11성+ 미상**(신규 고레벨, 현재 0건): 화면엔 조용히 제외, **`error_log`(`unmatched_equipment`) 유지** — 운영자 시드 보강 신호(유저 비노출, CONTEXT §121 운영 요약 정책 부합).
11. `MIN_AGGREGATE_LEVEL`(100)·`EXCLUDED_ITEMS`는 11성 필터에 흡수돼 사실상 무발화 → **안전망으로 존치**(삭제 안 함).

### 비목표
모델 파괴확률 캘리브레이션(OFF에서도 현실보다 높아 보임 — **별도 이슈**), 중립점 변경(상위 50%=중앙값 유지), 별캐치 중립화, 1+1/5·10·15 모델링, 슈페리얼 특수처리(데이터 0건), 잠재(`/잠재`) 변경, 재페치/스키마 변경.

---

## 3. 엔진 수학 (구현 핵심)

### 3-1. 파괴감소 (rate `r=0.30`)
성수 `s`가 파괴감소 이벤트 적용 시:
```
p' = p                      (성공 불변)
d' = d × (1 − r) = d × 0.7  (파괴 감소)
m' = m + d × r = m + 0.3d   (줄어든 파괴분이 유지로)
검산: p' + m' + d' = p + m + d = 1 ✓
```
파괴 없는 성수(s<15, d=0)는 영향 없음.

### 3-2. 할인 (rate `0.30`)
적용 성수 `s`의 시도 비용: `cost'(level,s) = cost(level,s) × 0.7`. 집계 내부는 float 유지, 표시에서 정수화(기존 `format_eok`). (정가 round-half-up 후 ×0.7 근사 — 게임 정밀도 차이는 무시 수준.)

### 3-3. 성수별 이벤트 마스크 (아이템 단위)
한 아이템(`(character_name, target_item)` 그룹)에 대해, 성수 `s`별로:
- `destroy_reduced[s]` = 그 유저의 `before_star=s` 시도 중 **과반**이 `destroy_decrease_rate` 보유(且 `starforce_event_range`에 s 포함). 동률 → True(이벤트 인정=보수적, 거짓 "운 좋음" 방지).
- `discounted[s]` = 동일 규칙으로 `cost_discount_rate`.
- **ACTUAL 비용**은 각 시도의 *실제* 플래그로 정확 계산(과반 규칙은 시뮬 카운터팩추얼 reclimb 가정에만).

### 3-4. 기대값·분포·백분위 (이벤트 반영)
- `expected_meso`: 동일 마르코프 흡수 해법이되 **성수별 조정 확률 `(p',m',d')` + 조정 비용 `cost'`** 사용. 전역 `STARFORCE_PROB`/`cost` 직접참조 → **주입형 테이블**로 리팩터.
- `_climb_attempt_samples`: 조정 확률표로 시뮬. **캐시 키에 파괴감소 마스크 포함**(현행 `(start,end,n_sims)` → `(start,end,destroy_mask,n_sims)`). 결정적 시드 유지.
- `_item_meso_samples`: 조정 비용표(`cost'`)로 환산.
- `meso_luck_percentile`: actual = Σ 실지불(할인 반영), 분포 = 조정 확률·비용. 백분위 산식·mid-p·탈상관 회전(`_DECORR_STRIDE`) 불변.

---

## 4. 빌드 단위 (파일별)

> 모두 [maple_mate/history/](../maple_mate/history/). 현 위치: `StarforceAttempt`=[service.py:176](../maple_mate/history/service.py#L176), `parse_attempts`=[:191](../maple_mate/history/service.py#L191), `StarforceSummary`=[:316](../maple_mate/history/service.py#L316), `aggregate_starforce`=[:346](../maple_mate/history/service.py#L346); 표시=[commands.py](../maple_mate/history/commands.py).

### #1 이벤트 파싱 — `service.py` `parse_attempts` + `StarforceAttempt`
- `StarforceAttempt`에 필드 추가(frozen dataclass): `destroy_decrease: bool`, `cost_discount: bool`(또는 rate `int`), 그리고 적용 성수 판정을 위해 `event_range_destroy: frozenset[int]`·`event_range_discount: frozenset[int]`(혹은 helper로 파싱). 최소안: `(destroy_reduced_here: bool, discounted_here: bool)` — "이 시도의 성수에 이벤트가 걸렸나"를 파싱 시점에 `before_star ∈ range` 로 확정해 boolean 2개만 보존(단순·테스트 용이).
- `starforce_event_list`(배열/스칼라/None 가드 — 일부 레코드 `"starforce": []` 및 비배열 관측) 순회해 `destroy_decrease_rate`/`cost_discount_rate` + `starforce_event_range` 파싱. `starforce_event_range` 포맷: `"0~29"`(범위) 또는 `"15,16,17,..."`(목록) → 정수 집합으로 정규화하는 순수 헬퍼 `parse_event_range(str) -> set[int]`.
- → **verify:** `parse_event_range`("0~29"/"15,16,17"/None/""), 이벤트 보유/미보유 레코드, 스칼라 event_list 가드.

### #2 비용·확률 엔진 — `starforce_data.py` + `expected_cost.py`
- `starforce_data.py`: `apply_destroy_reduction(prob_row, r=0.30) -> (p,m,d)` 순수 헬퍼(§3-1). `discounted_cost(level, star, r=0.30) -> float` 헬퍼(§3-2).
- `expected_cost.py`:
  - `expected_meso` 시그니처 확장 → 성수별 조정 확률/비용 주입 받게. 무이벤트 호출은 기존 결과와 **동일**(회귀 가드: 기존 `test_expected_cost.py` 픽스처 유지, 마스크 빈 경우 = 현 값).
  - `_climb_attempt_samples`/`_item_meso_samples` 캐시 키에 destroy 마스크/discount 마스크 반영.
  - `actual_meso` → 실지불(할인 반영)로 변경 또는 신규 `actual_paid_meso(items_with_flags)`.
  - `meso_luck_percentile` 입력 튜플에 성수별 마스크 동반.
- → **verify:** 파괴감소 적용 시 기대값↓·분포↓·동일 actual에서 백분위가 50%쪽으로 회귀하는지. 무이벤트=기존 값 동일(회귀). 할인 적용 actual/expected 양쪽 ×0.7 시 손익 불변(중립성).

### #3 집계 — `service.py` `aggregate_starforce` + `StarforceSummary`
- **11성 필터:** 그룹핑 전 `attempts = [a for a in attempts if a.before_star >= 11]`(상수 `MIN_AGGREGATE_STAR = 11`). 이후 기존 그룹/시작★/최종★/cost 로직 그대로(필터된 집합에).
- 아이템별 성수 마스크 구성(§3-3) → 조정 expected/actual/luck.
- `total_meso`=실지불, `expected`=조정 기대, `net_meso`=차.
- `StarforceSummary`: `matched_count`==`total_count`가 정상(미상 거의 소멸) — 필드 유지하되 표시에서 단일화(#4). `unmatched_items`는 11성+ 미상만 담김 → `_report_unmatched` 그대로.
- → **verify:** 10성 이하 시도 제외, 11성+만 집계, 파괴감소 아이템 기대값↓, 무진행(11성 유지만) 아이템 expected=0·actual>0.

### #4 표시 — `commands.py`
- `_format_luck`([:104](../maple_mate/history/commands.py#L104)): `top = 100 − luck_score`; `top < 1 → "상위 1% 미만"`; `top > 99 → "상위 99% 초과"`(권장); else `f"상위 {top:.0f}%"`. None→"—".
- `_format_count`([:114](../maple_mate/history/commands.py#L114)): 항상 `f"{matched_count}건"`(M/N 분기 삭제).
- `_build_table`([:199](../maple_mate/history/commands.py#L199)) 정렬: 키에 손익 타이브레이크 추가 → `(luck is None, -luck, -saving)`(saving=−net_meso=이득). 운빨 동점 시 이득 큰 쪽 상위.
- ℹ️ 필드: "레벨 미상 장비 제외" 블록([:247-252](../maple_mate/history/commands.py#L247)) **삭제** → "11성 이상 강화만 집계해요 (저성·이벤트 장비 제외)" 신규 필드. "계정 전체 합산" 필드 유지.
- → **verify:** 상위 0% 미발생, 동점 손익 정렬, 단일 건수, 신규/삭제 필드.

### #5 문서
- **ADR-0016 작성**(§10 초안 → `docs/adr/0016-starforce-event-adjusted-luck.md`).
- **ADR-0002 개정 노트**: "이벤트·정가 전제는 ADR-0016이 부분 개정(이벤트 보정·실지불·11성 필터)" 한 줄 추가. 메소 정렬 일관성·중립점 결론은 유효.
- **CONTEXT.md 갱신:**
  - [:61](../CONTEXT.md#L61) 총 사용 메소 "정가 비용 합산" → "실지불(할인 반영)·11성 이상 시도만".
  - [:165](../CONTEXT.md#L165) "정가로 손익 할인-중립" → "실지불이되 기대도 동일 이벤트 조건이라 손익 할인-중립 유지".
  - [:166](../CONTEXT.md#L166) "기준건수 M/N건" 서술 삭제(미상 소멸), 이벤트 보정 한 줄 추가.
- 전체 `pytest -q` 그린 + `ruff check`/`ruff format` clean.

---

## 5. 동작 규약 / 표시

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 집계 대상 | 레벨 매칭된 모든 성수 시도 | **11성 이상 시도만**(레벨 매칭 + ≥11성) |
| 운빨 기준선 | 정가·무이벤트 분포 | **강화 당시 이벤트 조건** 분포 |
| 총 사용 메소 | 정가 합 | **실지불(할인 반영)** |
| 손익 | 정가 실제 − 정가 기대 | 실지불 − 조건부 기대(둘 다 할인 반영 = 중립) |
| 운빨 표시 | `상위 {100−L:.0f}%`(→상위 0% 발생) | `상위 1% 미만`~`상위 99% 초과`, 동점=손익순 |
| 기준건수 | `M/N건`(미상 시 분수) | `N건`(단일) |
| 임베드 ℹ️ | "레벨 미상 장비 제외" | "11성 이상 강화만 집계 (저성·이벤트 장비 제외)" |

---

## 6. 극단·실패 UX

| 상황 | 처리 |
|---|---|
| 11성+ 시도 0건(저성만 강화) | 해당 대상 "기간 내 11성 이상 강화 기록이 없어요"(기록없음 분기 재사용/메시지 조정) |
| 11성+ 미상 장비(신규 고레벨) | 화면 조용히 제외 + error_log 제보(유저 비노출) |
| 무진행(11성 유지만) | expected=0, actual=실지불 → 헛돈이 불운으로(현 `meso_luck_percentile` 무진행 처리 유지) |
| 키 미등록·미등록·조회실패·이탈 | 기존 부분성공/제외 로직 불변(ADR-0015) |

---

## 7. 테스트 전략 (오프라인·순수 우선)

- `test_starforce_data.py` +: `apply_destroy_reduction`(합=1·성공불변·d=0무영향), `discounted_cost`, `parse_event_range`.
- `test_expected_cost.py` +: 무이벤트=기존 픽스처 동일(회귀), 파괴감소 적용 기대값·분포↓, 할인 양쪽 적용 시 백분위/손익 중립, 동일 actual에서 이벤트 보정이 백분위를 50%쪽으로 끌어내림.
- `test_history_aggregate.py` +: 11성 필터(10성 이하 제외), 성수 마스크 구성(과반/동률), 실지불 집계, 미상 11성+만 unmatched.
- `test_starforce_command.py` +: `_format_luck` 1%/99% 경계·동점 손익정렬·단일 건수·신규/삭제 ℹ️ 필드.
- **실데이터 검증(수동):** 로컬 DB 재집계로 `starforce_0628.png` 행들이 상위 0% 소멸·손익 합리화되는지 눈확인(스크립트는 1회성, 커밋 제외).

---

## 8. 커밋 전략 (레포 고유 — 필독)

작업 트리에 **무관한 미커밋/언트랙 잔존**(README·railway.json·docs/adr/0010·docs/provider-cutover-runbook·기댓값/·starforce-simulator-system.md 등). **절대 함께 스테이징 금지.**
1. `origin/main` 기준 신규 브랜치 `feat/starforce-event-luck`.
2. **이번 작업 파일만 외과적 스테이징** — `history/starforce_data.py`·`history/expected_cost.py`·`history/service.py`·`history/commands.py`·`tests/test_starforce_data.py`·`tests/test_expected_cost.py`·`tests/test_history_aggregate.py`·`tests/test_starforce_command.py`·`docs/adr/0016-*`·`docs/adr/0002-*`(개정 노트)·`CONTEXT.md`·본 작업지시서.
3. 논리 단위 커밋(엔진 수학 / 집계·필터 / 표시 / 문서) → push → squash PR.
4. CI(lint/test) 그린 후 머지. 배포 후 실 디스코드 `/스타포스` 1회 확인.

---

## 9. 파일 맵 (빠른 진입)

| 파일 | 역할 | 손볼 곳 |
|---|---|---|
| `history/starforce_data.py` | 확률표·비용·도달성수 | `apply_destroy_reduction`·`discounted_cost`·`parse_event_range` 신규 |
| `history/expected_cost.py` | 기대·분포·운빨 엔진 | 주입형 확률/비용표, 캐시 키, 실지불 actual |
| `history/service.py` | 파싱·집계 | `parse_attempts`(이벤트 필드), `aggregate_starforce`(11성 필터·마스크) |
| `history/commands.py` | 디스코드 표시 | `_format_luck`·`_format_count`·`_build_table`·ℹ️ 필드 |
| `history/equipment_level.py` | 레벨 매칭 | 불변(안전망 존치) |

---

## 10. ADR-0016 초안 (→ `docs/adr/0016-starforce-event-adjusted-luck.md`로 분리)

```markdown
# ADR-0016: 스타포스 운빨수치 이벤트 보정 + 11성 집계 기준

## 상태
채택 (2026-06-28). ADR-0002(스타포스 운빨 지표)의 "정가·무이벤트" 전제를 부분 개정.

## 맥락
운빨수치(`meso_luck_percentile`, ADR-0002)가 상위 다수에게 "상위 0%"를 부여.
데이터 실증: 15성+ 시도의 67%가 파괴확률 30% 감소 이벤트 중 발생했으나, 기대값·분포는
정가·무이벤트 확률로 계산 → 현실이 구조적으로 싸져 거의 전원이 99~100 백분위로 압축.
즉 지표 정의(중앙값=상위 50%, 분포 대비 백분위)는 옳으나 *기준선(무이벤트)* 이 현실과 어긋남.

## 결정
1. 기대값·분포·운빨을 강화 당시 이벤트 조건(파괴확률 30% 감소·강화비용 30% 할인)으로 보정한다.
   넥슨 API가 강화 기록마다 제공하는 `starforce_event_list`(+`starforce_event_range`)를 사용 —
   재페치·스키마 변경 없음.
2. 파괴감소: d'=d×0.7, 줄어든 0.3d는 유지로, 성공 불변(공식 메커니즘).
3. 메소 표시를 정가→실지불(할인 반영)로 바꾼다. 기대도 동일 이벤트 조건이라 손익은 할인-중립 유지.
4. 집계 범위를 11성 이상 시도로 한정한다. 1+1(10성 이하 전용) 무력화 + 저성·레벨 미상 장비 제거.
   (11성은 108레벨+에서만 가능 → 자동 고레벨 한정.)
5. 별캐치 성공/실패는 본인 몫 → 운에 포함(중립화 안 함).
6. 운빨 표시는 "상위 1% 미만"~"상위 99% 초과" 클램프, 동점은 손익순.

## 근거
- 이벤트 무반영이 "상위 0%"의 67% 책임(데이터). 정가 단독 폐기 아님 — 양쪽 보정이라 손익 중립 유지.
- 11성 필터가 레벨 미상(전수 ≤7성)·1+1·저성 잡음을 한 규칙으로 해소(증거: unmatched 전수·도달성수).
- 별캐치는 달력 외부요인이 아니라 플레이어 행동 → 운으로 측정하는 게 타당.

## 영향
- ADR-0002: 메소 기반·정렬 일관성·중립점 결론 유효, 기준선만 이벤트 보정으로 개정.
- CONTEXT.md 운빨 지표·메소 컬럼·기준건수 서술 갱신.
- 마이그레이션 없음. 기존 캐시로 재집계.

## 대안 (기각)
- 표시만 수정(상위 0% 숨김): 이벤트 편향 잔존 → 여전히 떼몰림.
- 비교군 내 상대화: "전체 메이플 대비" 의미 상실.
- 성공확률 백분위(ADR-0002 ② 재도입): 손익과 정렬 어긋남(고성 한방 왜곡) — 이미 기각된 길.
```

---

## 11. 핸드오프 메모

- 이 문서 = 단일 진입점. 엔진 내부 더 깊은 맥락은 [starforce-handoff.md](starforce-handoff.md), 비용/확률 검증은 [starforce-impl 메모], 데이터 포맷은 [docs/api/history.md](api/history.md).
- 로컬 검증 환경: `.env`의 `DATABASE_URL`(localhost:5433) = 운영 미러. `history_cache.payload`에 이벤트 플래그 원본 있음. psql로 `jsonb_array_elements(payload->'starforce')` 순회해 재현 가능.
- **미해결 별도 이슈(범위 밖):** 모델 파괴확률이 현실(OFF 표본)보다 높아 보임 → 캘리브레이션 검토는 신규 작업지시서로.
