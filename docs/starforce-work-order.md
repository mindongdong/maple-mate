# 작업 지시서 — `/스타포스` (Phase 3 일부)

> Phase 3 이력류 중 **`/스타포스`만** 구현한다(`/잠재`·`/잠재합계`는 스코프 밖). 기대값 자료가 완비돼
> 순수 로직만으로 단위테스트까지 완결 가능하다. 그릴링·자료 검토로 아래 결정을 모두 확정했다.
> **다른 세션이 이 문서 하나로 착수**할 수 있도록 작성됨. 복잡 로직(기대값 엔진)은 `executor` `model=opus` 권장.

## 참조 (중복 금지 — 경로로 참조)

- [docs/phase3-work-order.md](phase3-work-order.md) — Phase 3 전체 결정·재사용 자산 진단(상위 문서)
- **[docs/starforce-expected-value-data.md](starforce-expected-value-data.md) — 확률표·비용공식·모델 규칙(이 작업의 데이터 소스). 검증 이미지 = [기댓값/](../기댓값/)**
- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §3.4·§7·§8 — `/스타포스` 동작 명세(SSOT)
- [CONTEXT.md](../CONTEXT.md) — 운지수·손익메소·기대값·키미등록 vs 기록없음·이력류 집계 단위(등록 캐릭터)
- [docs/api/history.md](api/history.md) — `history/starforce` 필드 실측(접미사 `"실패(유지)"` 등, 메소·레벨 부재)
- 실샘플: [spike/raw/BSCAN_starforce_2026-05-31.json](../spike/raw/BSCAN_starforce_2026-05-31.json)(5건), [spike/raw/A8_item_equipment.json](../spike/raw/A8_item_equipment.json)(`base_equipment_level`)

## 확정 결정 (그릴링 + 자료 검토)

| # | 결정 |
|---|---|
| 운지수 모델 | **구간 기대값.** 메소·레벨이 API에 없어 분자·분모 **둘 다 공식 역산**. 운지수=실제/기대(%), 손익메소=실제−기대. (<100%=운 좋음) |
| 정가 기준 | **분자·분모 모두 정가.** 이벤트/MVP/PC방 할인 미반영(이력 `cost_discount_rate` 무시). 파괴방지 미적용. |
| 파괴 처리 | **12성 하락 + 스페어/복구비 0**(plain). 재등반 시도는 이력에 별도 행으로 존재 → 실제에 자동 반영. |
| 별캐치·하락 | 별캐치 **상시 반영**(확률표값 그대로). **성수 하락 없음**(실패=유지). API `"실패(하락)"`는 분자가 이력 직접 합산이라 무영향(잔류). |
| 캐릭터 스코프 | **등록 캐릭터만** — 이력 레코드를 `character_name == 등록 닉네임`으로 필터(개인 키는 계정 전체 반환). |
| 레벨 매칭 | (A) 현재 장착(`item-equipment` `item_name`==`target_item` → `base_equipment_level`) → (B) 큐레이션 시드 → (C) 제외 + "N건 중 M건" + `error_log(unmatched_equipment)` + "제보되었습니다". |
| 기간 | 프리셋(`오늘`·`어제`·`최근7일`[기본]·`최근30일`·`이번주`·`이번달`) + 선택 시작/종료일, **30일 상한 클램프**. |
| 페치 | `date`별 1콜(`count=1000`) 반복, `history_cache`(과거=불변/오늘=5분 TTL) 활용. 글로벌 스로틀 유지(키별 병렬 백로그). |

## 현황 진단

**재사용 (새로 만들지 말 것):**
- [history/cache.py](../maple_mate/history/cache.py) `is_cache_fresh(query_date, fetched_at, now, ttl)` · [history/models.py](../maple_mate/history/models.py) `HistoryCache`(PK `ocid,type,date`; `type="starforce"`). **마이그레이션 완료.**
- [nexon/client.py](../maple_mate/nexon/client.py) `_request(path, *, api_key=None, **params)`(개인 키 오버라이드·스로틀·재시도), `character_item_equipment(ocid)`(레벨 (A) 소스), `KST`. [nexon/errors.py](../maple_mate/nexon/errors.py) `NexonAPIError`·`ErrorClass`·`to_error_log_type`.
- [registration/service.py](../maple_mate/registration/service.py) `Target`·`TargetOutcome`·`refresh_ocid`·`classify_target_error`·`_STALE_OCID`(이력류 페치 패턴 차용). [registration/models.py](../maple_mate/registration/models.py) `Registration`(`api_key_encrypted` nullable). [security/crypto.py](../maple_mate/security/crypto.py) `KeyCipher.decrypt`.
- [bot/comparison.py](../maple_mate/bot/comparison.py) `resolve_targets`·`table_image_message`·`all_failed_embed`·`respond_with_pages`·`attach_failures`·`highest_indices`·`truncate_display`·`mention`·`data_footer`. [bot/embeds.py](../maple_mate/bot/embeds.py) `defer`·`make_embed`·`format_footer`. [bot/table_image.py](../maple_mate/bot/table_image.py) `render_table_image`·`Highlight`. [character/service.py](../maple_mate/character/service.py) `format_eok`(메소 한글 표기).
- [dependencies.py](../maple_mate/dependencies.py) `Deps(config, session_factory, nexon, cipher)`.

**새로 만듦:** `NexonClient.starforce_history` · `history/starforce_data.py` · `history/expected_cost.py` · `history/equipment_level.py` · `history/service.py` · `history/commands.py` · `bot/comparison.lowest_indices` · `bot/core.py` 배선 · 테스트.

## 빌드 단위 (의존 순서)

### 1. `NexonClient.starforce_history`
```python
async def starforce_history(self, api_key: str, date_iso: str, count: int = 1000) -> list[dict]:
    """개인 키로 그 계정 starforce 이력(해당 KST 1일). next_cursor 누적, null→[]."""
```
- `_request("maplestory/v1/history/starforce", api_key=api_key, count=count, date=date_iso)` → `starforce_history` 리스트. `next_cursor` 비-null이면 다음 호출은 `cursor=`(date 빼고) 누적(친구 그룹 <1000/일이라 보통 1콜).
- *검증: `BSCAN_starforce_2026-05-31.json`(5건) 스키마 키 대조 — `item_upgrade_result`·`before/after_starforce_count`·`target_item`·`character_name`·`date_create`.*

### 2. `history/starforce_data.py` + `history/expected_cost.py` — 기대값 엔진 (순수)
**`starforce_data.py`** — [데이터문서](starforce-expected-value-data.md) §1~3 인코딩:
- `STARFORCE_PROB: tuple[tuple[float, float, float], ...]` — 0~29 인덱스 `(성공, 유지, 파괴)`.
- `def cost(level: int, star: int) -> int` — §2 공식(0~9성 / 10성+ divisor표).
- `def reachable_star(level: int) -> int` — §3.

**`expected_cost.py`:**
- `def expected_meso(level: int, start_star: int, end_star: int) -> float` — 마르코프 흡수 기대비용. 상태=성수, 전이: 성공→s+1 / 유지→s / 파괴→**12**. 비용=`cost(level,s)` 매 시도. `C[end]=0`,
  `C[s] = (cost(level,s) + p_s·C[s+1] + d_s·C[12]) / (1 − m_s)`. 파괴(d>0)가 12로 되돌리므로 **`C[12]`를 미지수 X로 두고** `C[s]=a_s+b_s·X`로 하향 전개 → `C[12]=X` 고정점으로 X 해 → 역대입. (의존성 없이 풀이; 상태 ≤30.) 반환 `expected_meso` = `C[start_star]`.
- `def actual_meso(level: int, before_stars: list[int]) -> int` — `sum(cost(level, s) for s in before_stars)`. (파괴 추가비 0.)
- `def luck_index(actual: int, expected: float) -> float | None` — `actual/expected*100`, `expected<=0`이면 None. `def net_meso(actual, expected) -> int`.
- *검증(**알려진 케이스**): `cost()`가 `기댓값/{레벨}_기댓값.png` "강화비용" 컬럼 재현(예 200레벨 0→1=223,200 / 250레벨=435,000). `expected_meso(level,0,N)`가 같은 이미지 "누적기댓값" 재현(레벨 100·150·200·250 몇 셀 픽스처, 반올림 허용오차). `luck_index`/`net_meso` 경계.*

### 3. `history/equipment_level.py` — 레벨 3단 매칭
- `EQUIPMENT_LEVEL_SEED: dict[str, int]` — 흔한 엔드게임 장비 큐레이션 시드(예: `"아케인셰이드 ...": 200`, 에테르넬류 250, 보스 장신구류). 초기 소규모, error_log 미매칭 상위N으로 확장.
- `def match_level(target_item: str, equipped: dict[str, int], seed: dict[str, int] = EQUIPMENT_LEVEL_SEED) -> int | None` — (A) `equipped.get` → (B) `seed.get` → (C) None. **순수.**
- `async def fetch_equipped_levels(nexon, ocid) -> dict[str, int]` — `character_item_equipment(ocid)` → `{item_name: item_base_option.base_equipment_level}`.
- *검증: (A)/(B)/(C) 분기 + 미매칭 None 단위테스트.*

### 4. `history/service.py` — 기간·페치·캐시·집계 (전달-무관)
- `def resolve_period(preset: str, start: date|None, end: date|None, today_kst: date) -> list[date]` — 프리셋→날짜 목록, **30일 상한 클램프**, 미래 컷. 순수.
- `HistoryTarget(guild_id, discord_user_id, nickname, ocid, api_key_encrypted)` + `async def get_history_targets(session_factory, guild_id, user_ids=None) -> list[HistoryTarget]` — `Registration` 조회(키 포함, 입력순서 보존). 키 없는 등록자는 호출자가 "키 미등록" 행 처리.
- `async def fetch_starforce_records(deps, target, dates) -> list[StarforceAttempt]` — 날짜별 `is_cache_fresh` 확인 → 미스 시 `cipher.decrypt(api_key_encrypted)`로 `starforce_history` 호출 → `history_cache` upsert(원본 payload, `type="starforce"`) → 파싱 + **`character_name==target.nickname` 필터**. `StarforceAttempt(target_item, before_star, after_star, result, date_create)`.
- `def aggregate_starforce(attempts, level_of) -> StarforceSummary` — 아이템별: **시작★=첫(시간순) before_star**, **최종★=기간 내 최고 after_star**. `expected += expected_meso(level, 시작★, 최종★)`(레벨 매칭 성공分만), `actual += actual_meso(level, [그 아이템 시도들의 before_star])`. **matched/total 카운트 + unmatched 장비명 집합**. `StarforceSummary(luck_index, net_meso, actual, expected, matched_count, total_count, unmatched_items)`.
- *검증: `resolve_period`(프리셋·클램프) · 캐릭터 필터 · 시작/최종★ 추출 · matched/total · `"실패(*)"` 파싱 단위테스트(넥슨 mock).*

### 5. `history/commands.py` — `/스타포스`
- 인자: `기간`(필수 choice: 오늘/어제/최근7일/최근30일/이번주/이번달, 기본 최근7일) + 선택 `시작일`·`종료일`(YYYY-MM-DD) + `대상1~5`(미지정=서버 전체). `@app_commands.choices`.
- 흐름: `defer` → guild 가드 → `get_history_targets` + 미등록/키미등록 분리(키 없으면 "키 미등록" `TargetOutcome` 행) → `resolve_period` → 대상별 `fetch_starforce_records`→레벨 매칭(대상별 `fetch_equipped_levels` 1회)→`aggregate_starforce` → PNG 표.
- 표(`table_image_message`): 컬럼 순위·캐릭터·운지수·손익메소·기준건수. **운지수 낮을수록 운 좋음 → 최저 행 강조**(신규 `lowest_indices`). 매칭 누락 있으면 셀/푸터에 "N건 중 M건". 메소는 `format_eok`.
- unmatched_items 있으면 대상별 `error_log.record(error_type="unmatched_equipment", command="스타포스", guild_id, discord_user_id, target_ocid, detail=장비명)` + 임베드에 "일부 장비는 레벨 미상으로 제외(제보되었습니다)".
- 부분 성공(키미등록·기록없음·조회실패)은 `attach_failures`. 푸터=기간 범위 텍스트. 2장+면 `respond_with_pages`.
- *검증: 운지수·손익·N/M·키미등록 vs 기록없음 분기(넥슨 mock).*

### 6. 배선 + 보조
- `bot/comparison.py`에 `def lowest_indices(values) -> set[int]` 추가(`highest_indices` 거울 — None 제외, 최소값 행).
- `bot/core.py._register_commands`에 `from ..history.commands import setup as setup_history` + `setup_history(self)`.

### 7. 테스트 (`tests/`)
- `test_starforce_data.py`(cost vs 이미지 셀·reachable) · `test_expected_cost.py`(expected_meso vs 누적기댓값·luck/net) · `test_equipment_level.py`(3단) · `test_history_period.py`(프리셋·클램프) · `test_history_aggregate.py`(시작/최종★·matched/total·필터·`"실패(*)"`). 넥슨/디스코드 mock. E2E 생략(실용 테스트 합의).

## 산출물
- 위 코드 + 단위테스트 통과(특히 이미지 픽스처 대조) + `uv run pytest` 그린. 가능 시 개인 키로 라이브 `/스타포스` 1회 눈 확인.

## 미실측 / 리스크
- ⚠️ **하락 없음 모델** — API `"실패(하락)"` 존재하나 기대=메수라이브 기준, 실제=이력 직접 합산이라 무영향. 라이브에서 하락 빈도 확인 시 재검토([데이터문서](starforce-expected-value-data.md) §6).
- ⚠️ **레벨 시드 초기 커버리지** — (B) 시드가 작으면 (C) 제외 비율↑("N건 중 M건"이 받쳐줌). error_log 미매칭으로 점진 확장.
- ⚠️ **닉 변경 시 `character_name` 불일치** — 과거 이력 누락 가능(잔류).
- 콜드 30일 다인원 latency(캐시·30일 상한 의존, 글로벌 스로틀).

## 스코프 밖 (이 작업 아님)
- **`/잠재`·`/잠재합계`** — 별도 작업(potential 미니 스파이크 게이트 + 메소 단가표 필요).
- 흔적복구/스페어 비용 반영, 키별 병렬 스로틀, 이벤트/할인 반영 — 전부 백로그.
- **ADR-0002(기대값 엔진)** — 구현 후 작성 예정(운지수=구간 기대값 + 정가 + plain 파괴 + 대안 기각).
</content>
