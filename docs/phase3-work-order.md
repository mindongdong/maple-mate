# 작업 지시서 — Phase 3 이력류 (`/스타포스`·`/잠재`·`/잠재합계`)

> Phase 1·2 완료 + Phase 4 `/썬데이` 선개발 완료 상태에서 **이력류(개인 키 게이트, 최난도)** 를 착수한다.
> 그릴링(`/grill-with-docs`)으로 아래 8개 결정을 확정했다. `/스타포스`·cube 는 Spike 0 실측 확정,
> `/잠재`(메소 재설정)는 **미니 스파이크 선행 게이트** 후 착수한다.

## 참조 (중복 금지 — 경로로 참조)

- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §3.4·§3.5·§5①②⑤·§7·§8 — 동작 명세(SSOT)
- [CONTEXT.md](../CONTEXT.md) — 운지수·손익메소·기대값·키미등록 vs 기록없음 + **이번 그릴링 추가**(이력류 스코프 vs 집계 단위, "정가" 분자 적용)
- [docs/adr/0001-nexon-personal-key-model.md](adr/0001-nexon-personal-key-model.md) — 개인 키 = 그 계정 이력(이력류 게이트 근거)
- [docs/api/history.md](api/history.md) — starforce/cube/potential 필드 실측(⚠️ **potential 실측 0건 잔류**, 메소·레벨 필드 부재 확정)
- **[docs/starforce-expected-value-data.md](starforce-expected-value-data.md) — 스타포스 기대값 확률표·비용공식·모델 규칙(메수라이브 자료 추출, 빌드 2 데이터 소스).** 원본: [starforce-simulator-system.md](../starforce-simulator-system.md) + [기댓값/](../기댓값/) 레벨별 검증 이미지
- 이력 실샘플: [spike/raw/BSCAN_starforce_2026-05-31.json](../spike/raw/BSCAN_starforce_2026-05-31.json)(5건), [spike/raw/B2_cube_yday.json](../spike/raw/B2_cube_yday.json)(cube), [spike/raw/A8_item_equipment.json](../spike/raw/A8_item_equipment.json)(레벨 매칭 소스 `base_equipment_level`)

## 현황 진단

**이미 있음 (재사용 — 새로 만들지 말 것):**
- `history/models.py` — `HistoryCache` ORM, PK `(ocid, type, date)`, `payload` JSONB. **Alembic 5테이블 마이그레이션 완료 → 추가 마이그레이션 불필요.**
- `history/cache.py` — `is_cache_fresh(query_date, fetched_at, now)` 순수함수(과거=불변, 오늘=5분 TTL, KST). 적재/조회 service 는 미구현(이 Phase).
- `error_log` — `unmatched_equipment` enum 타입 + `error_log.record(...)` 이미 존재(레벨 미매칭 적재용).
- `NexonClient.character_item_equipment(ocid)` — 레벨 매칭 (A) 소스. `_request(api_key=...)` 로 개인 키 오버라이드 이미 지원.
- `registration.service` — `get_targets`(대상 해석, 입력순서 보존), `fetch_each`/`_fetch_one`(부분 성공·ocid lazy 갱신·error_log 적재), `KeyCipher`(개인 키 복호화).
- `bot/comparison.py` — `resolve_targets`(미등록 부분성공 행), `table_image_message`(깨지지 않는 PNG 수치표), `field_pages`·`respond_with_pages`(페이지네이션), `data_footer`(푸터), `highest_indices`(최고값 강조).
- `bot/table_image.py`·`bot/item_card.py` — PNG 렌더.

**새로 만듦:** `NexonClient` 이력류 3메서드 · `history/expected_cost.py`(기대값 엔진) · `history/equipment_level.py`(레벨 3단 매칭) · `history/service.py`(기간 페치+캐시적재+캐릭터 필터+잠재 집계) · `history/commands.py`(3명령) · 데이터 모듈(확률표·비용공식·레벨 시드 — **사용자 자료 대기**) · `scripts/spike_potential.py`(미니 스파이크).

## 확정 결정 (그릴링 결과)

| # | 결정 | 선택 |
|---|---|---|
| Q1 | **운지수 계산 모델** | **A. 구간 기대값(표준).** 메소·레벨 필드가 API에 없으므로 분자·분모 **둘 다 공식 역산**. 아이템별 `시작★→최종★` 구간에서 **실제 소모**=실제 시도들의 시도당 비용 합(+파괴 복구비), **기대 소모**=그 구간을 올리는 이론적 기대 메소(확률표+비용공식 마르코프). 운지수=실제/기대(<100%=운 좋음). |
| Q2 | **기대값 데이터 소스** | **✅ 수령 — 메수라이브 자료.** 확률표(0~29성)·비용공식·도달가능스타는 [starforce-expected-value-data.md](starforce-expected-value-data.md)에 추출(검증 이미지 = 정가 기준, 단위테스트 oracle). 엔진은 데이터 주입형 + "알려진 케이스" 검증. **잔여 룰셋 확인:** 파괴 처리(12성 하락+스페어 0 제안)·하락 없음 모델(§6). **미수령:** 잠재 메소 단가표·장비레벨 시드. (작업계획 미해결 결정 #2 해소) |
| Q3 | **할인 처리** | **분자도 정가.** 이력의 `cost_discount_rate`(썬데이 등) 미반영 → 실제·기대 둘 다 정가 단가 → 운지수=순수 RNG 운만 측정(할인 타이밍 상쇄). **비용 측면 `starforce_event_list` 파싱 불필요.** |
| Q4 | **캐릭터 스코프** | **등록 캐릭터만.** 개인 키는 계정 전체 이력 반환(`character_name` 캐릭별 상이) → **`character_name == 등록 닉네임` 필터**. 비교 단위가 스펙류와 동일. 부캐 강화는 제외(MVP). ⚠️ 닉 변경 시 과거 이력 불일치 잔류. |
| Q5 | **장비 레벨 매칭** | (A) 현재 장착(`item-equipment` `item_name`==`target_item` → `base_equipment_level`) → (B) **큐레이션 시드 맵 + `error_log(unmatched_equipment)` 상위N 점진 확장** → (C) 둘 다 실패=그 시도 **기대값 산출 제외** + "N건 중 M건" 투명표시 + 제보 안내. (A)·(C)는 설계 §3.4 확정. |
| Q6 | **페치 latency** | **단순 유지.** 글로벌 스로틀 그대로 + `history_cache`(과거일 불변→반복 즉시) + **30일 상한**으로 worst case 바운드. 키별 병렬 스로틀은 백로그. |
| Q7 | **potential 잔류 리스크** | **미니 스파이크 선행 게이트.** 메소 재설정 기록 있는 키로 `history/potential` 1회 실호출 → 스키마·`potential_type`·은 필드 확정 후 `/잠재`·`/잠재합계` 착수(Spike 0 패턴 재사용). |
| Q8 | **/잠재 시작/최종 잠재** | **일반 + 에디셔널 둘 다.** `potential_option` + `additional_potential_option` 시작→최종 모두. 단일 상세에 적합 → 렌더는 per-person 카드/필드 + 페이지네이션. |

**설계·실측에서 파생(재확인):**
- `date` 파라미터 = **정확히 그 하루치만** 반환(실측) → 기간 조회 = **날짜별 1콜 반복**. `count=1000`(max)로 하루치 한 번에(친구 그룹 일일 >1000 불가 → cursor 누적은 잔류·무관).
- `item_upgrade_result` = `"성공"`/`"실패(유지)"`/`"실패(하락)"`/`"파괴"` (접미사 포함 — `"실패("` 접두 매칭으로 파싱).
- 큐브 = **메소 0**(현금/이벤트 큐브) → `/잠재합계`엔 **횟수만**. 메소는 potential(메소 재설정) 단가표(`item_level` 기준)로만 산출(설계 §8 "현 메타 메소 위주").

## 선행 게이트 (코딩 전)

1. **사용자 자료 수령** — ✅ **스타포스 완료**(메수라이브 확률표·비용공식·검증 이미지 → [starforce-expected-value-data.md](starforce-expected-value-data.md)). 별캐치=상시, 파괴방지·할인=정가 미적용, **파괴=12성 하락+스페어 0 확정**. ⬜ **잔여:** 잠재 메소 재설정 단가표 + 장비명→레벨 리스트(없으면 큐레이션). ⬜ **잔류:** 하락 없음 모델(실제는 영향無, 데이터문서 §6).
2. **potential 미니 스파이크** (`scripts/spike_potential.py`) — 메소 재설정 기록 있는 키로 `history/potential` 1회 → 스키마 확정. 0건이면 사용자가 메소 재설정 1회 후 재시도.

## 빌드 단위 (의존 순서)

### 1. `NexonClient` 이력류 메서드
- `starforce_history(api_key, date, count=1000)` / `cube_history(...)` / `potential_history(...)` — **개인 키 오버라이드**, `count` + `date`(오늘 KST 포함 200 수용), 래퍼 키(`starforce_history`/`cube_history`/`potential_history`) 리스트 반환(null→빈 리스트 정규화). `next_cursor` 비-null이면 누적(고볼륨 일자 대비, 친구 그룹은 사실상 미발생).
- *검증: 미니 스파이크 실호출 1건 + 스키마 키 확인(starforce·cube는 `spike/raw` 대조).*

### 2. `history/expected_cost.py` — 기대값 엔진 (데이터 주입형, 순수)
- 데이터: [starforce-expected-value-data.md](starforce-expected-value-data.md) §1 확률표(0~29성 `[성공,유지,파괴]`, 별캐치 반영·하락 없음) + §2 `cost(level, star)` 비용공식 + §3 `reachable_star`. 상수 모듈로 인코딩.
- `expected_meso(level, start_star, end_star) -> int` — 마르코프 기대비용(전이: 성공→+1 / 유지→유지 / 파괴→12성, 정가 plain).
- `actual_meso(attempts) -> int` — 각 이력 행 `cost(level, before_star)` 합(파괴 추가비 0). 재등반은 이력에 별도 행으로 이미 존재.
- `luck_index(actual, expected) -> float` / `net_meso(actual, expected) -> int` — CONTEXT.md 정의.
- *검증: **알려진 케이스 단위테스트** — `cost()`는 이미지 "강화비용" 컬럼 재현, `expected_meso(level,0,N)`는 이미지 "누적기댓값" 재현(레벨 100~250 픽스처). 교차검증 완료(200레벨 223,200 / 250레벨 435,000).*

### 3. `history/equipment_level.py` — 레벨 3단 매칭
- `match_level(target_item, equipped: dict[name,level], seed: dict[name,level]) -> int | None` — (A) 장착 → (B) 시드 → (C) None. **순수.**
- `EQUIPMENT_LEVEL_SEED` — 흔한 엔드게임 장비 큐레이션 시드(아케인셰이드 200 등). error_log 미매칭 상위N으로 확장.
- *검증: (A)/(B)/(C) 분기 + 미매칭 None 단위테스트.*

### 4. `history/service.py` — 기간 페치 + 캐시 + 캐릭터 필터 (전달-무관)
- `resolve_period(preset, start, end, now_kst) -> list[date]` — 프리셋(오늘·어제·최근7일[기본]·최근30일·이번주·이번달) + 선택 날짜, **30일 상한 클램프**. 순수.
- `fetch_history(deps, ocid, api_key, type, dates) -> list[record]` — 날짜별 `is_cache_fresh` 확인 → 미스 시 개인 키 호출 → `history_cache` upsert(payload=원본) → **`character_name == 등록 닉` 필터**. 키 복호화는 registration 레코드에서.
- 키 미등록(api_key None)=비대상 / 기록 없음(필터 후 0건)=별도 표시(CONTEXT.md 구분). `fetch_each` 패턴 차용(부분 성공·error_log).
- *검증: 기간 분해·캐시 판정·캐릭터 필터·키미등록 vs 기록없음 단위테스트(넥슨 mock).*

### 5. `/스타포스` (`history/commands.py`)
- 대상 = **키 등록된 등록자만**(키 없는 등록자는 "키 미등록" 부분성공 행). 기간 페치 → 아이템별 `시작★→최종★` + 시도 목록 집계 → 레벨 매칭 → 운지수·손익메소.
- 출력 = **PNG 수치표**(`table_image_message` 재사용): 순위·캐릭터·운지수·손익메소·(매칭 누락 시) "N건 중 M건 기준". ⚠️ **운지수 낮을수록 운 좋음 → 최저 행 강조**(`highest_indices` 역방향: 최소값 강조 헬퍼 신규).
- 미매칭 시도 → `error_log.record(error_type="unmatched_equipment", detail=장비명)` + "제보되었습니다" 안내.
- *검증: 운지수·손익메소 계산, N/M 투명표시, 미매칭 적재 단위테스트.*

### 6. `/잠재` (potential 미니 스파이크 통과 후)
- cube + potential 합산 → 아이템별 재설정 횟수(큐브+메소 **합산**, 동점=**사용 메소 큰 쪽**) → **최다 단일 아이템** 선정.
- 그 아이템의 **시작 잠재**(기간 첫 레코드 before)→**최종 잠재**(마지막 레코드 after), **일반+에디셔널 둘 다** + 사용 메소(potential 단가표) + 큐브 횟수.
- 재설정 0건 = **"기록 없음"**(키 미등록과 구분). 출력 = per-person 카드/필드 + 페이지네이션.
- *검증: 최다 선정·동점(메소 우선)·기록없음·시작/최종 추출 단위테스트.*

### 7. `/잠재합계`
- 기간 내 **총 사용 메소**(potential 단가표 합) + **총 큐브 횟수**(cube len) 랭킹. 출력 = PNG 수치표.
- *검증: 합산·랭킹 단위테스트.*

### 8. `scripts/`
- `spike_potential.py` — 빌드 0 게이트. 개인 키로 `history/potential` 덤프 → 스키마 확정.

## 렌더 전략

| 명령 | 성격 | 렌더 |
|---|---|---|
| `/스타포스` | 수치 비교(운지수·손익) | PNG 표(`table_image_message`), 최저 운지수 강조 |
| `/잠재합계` | 수치 랭킹(메소·횟수) | PNG 표 |
| `/잠재` | 옵션 텍스트 진행 | per-person 카드/필드 + 페이지네이션 |

푸터: 오늘 포함 시 `HH:MM 기준`, 과거만이면 `YYYY-MM-DD`(`data_footer` 패턴). 모든 명령 `defer` 의무.

## 테스트 전략 (실용 테스트 합의)

순수 로직만 단위테스트: 기대값/운지수/손익메소 · 레벨 3단 매칭 · 기간 분해(상한 클램프) · 캐릭터 필터 · 최다 아이템 선정/동점 · 결과 파싱(`"실패(유지)"` 등). Nexon/Discord mock. 무거운 E2E·스케줄러 통합 생략. 라이브 확인은 `scripts/` 일회성.

## 미해결 / 후속

- **ADR-0002(기대값 엔진)** — 사용자 자료 수령·룰셋 확정 후 작성 예정. 기록 대상: 운지수=구간 기대값 + **정가 분자**(순수 운) + 죽은 대안(B 시도합산만 / C 횟수근사) 기각 + 별캐치/파괴방지/복구 룰셋 가정. 되돌리기 비싼 핵심 엔진이라 ADR 가치 충족.
- **룰셋 모델링(자료 검토 시 확정):** 기대(정가)의 별캐치 적용 여부 · 파괴방지 가정(비용↑/파괴0) · star cap(30성) · 파괴 복구비 정의(재구매가 vs 누적강화비).
- **잔류 리스크:** 닉 변경 시 `character_name` 불일치(과거 이력 누락) · 고볼륨 일자 cursor 누적 미실측(`count=1000`으로 회피, 친구 그룹 무관) · 큐레이션 시드 초기 커버리지(error_log로 확장) · 콜드 30일 다인원 latency(캐시·상한 의존).

## 스코프 밖 (보류)

- Phase 5 일일 운영 요약(`error_log` 집계) — 이력류와 분리.
- GPT 종합 비교 · 키 라이프사이클(삭제/갱신/만료) — 설계 §9 백로그.
</content>
</invoke>
