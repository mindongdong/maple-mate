# 작업 지시서 — `/잠재` (Phase 3 마지막 명령, 통합 비교표)

> Phase 3 이력류의 마지막 명령. **잠재+잠재합계 분리 → 스타포스식 단일 비교표**로 통합한다(기획 변경 근거·결정은 짝 문서
> [potential-handoff.md](potential-handoff.md) 참조). **총 큐브·등업은 즉시 구현 가능**, **메소만 단가표 게이트(G2)**, **등업 "성공" 의미만 미니스파이크 게이트(G1)**.
> 다른 세션이 이 문서로 착수한다. 복잡 로직은 `executor` `model=opus` 권장. 테스트는 순수 로직 단위테스트(실용 테스트 합의).

## 참조 (중복 금지 — 경로로 참조)

- **[potential-handoff.md](potential-handoff.md) — 결정(D1~D6)·실현가능성·게이트·등업 메커니즘·뱃지 결정(WHY). 반드시 먼저 읽을 것.**
- [starforce-work-order.md](starforce-work-order.md) — 쌍둥이 구조의 완성 지시서(빌드 단위 패턴 그대로 차용)
- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §3.5·§5①②·§7·§8 — 동작 명세(SSOT)
- [docs/api/history.md](api/history.md) — `history/cube`·`history/potential` 필드 실측(메소 부재, `item_level` 존재)
- [CONTEXT.md](../CONTEXT.md) — 키미등록 vs 기록없음·이력류 집계 단위(등록 캐릭터)
- 실샘플: [spike/raw/B2_cube_yday.json](../spike/raw/B2_cube_yday.json), [spike/raw/BSCAN_cube_2026-05-31.json](../spike/raw/BSCAN_cube_2026-05-31.json)

## 확정 결정 (핸드오프 D1~D6 요약)

| 결정 | 선택 |
|---|---|
| 명령 구조 | `/잠재` 단일 비교표. `/잠재합계` 폐기 |
| 컬럼 | `순위`·`캐릭터`·`총 큐브`·`등업`(from-등급 뱃지)·`사용 메소`(게이트)·기간 푸터 |
| 출시 순서 | 큐브·등업 먼저, 메소는 단가표(G2) 후 |
| 등업 표시 | 단일 컬럼 + 등급 색 뱃지(`/아이템` 재사용), 0건 생략 |
| 분포(예시2/3) | 단일 대상 조회 시만 보조 노출 |
| 집계 단위 | 등록 캐릭터(`character_name == 등록 닉네임` 필터) |
| 기간 | `resolve_period` 재사용(프리셋·**365일 상한**, 스타포스와 동일) |

## 현황 진단

**재사용 (새로 만들지 말 것):**
- [history/service.py](../maple_mate/history/service.py) `resolve_period`(`MAX_PERIOD_DAYS=365`)·`HistoryTarget`·`get_history_targets`·`fetch_starforce_records`(페치+캐시+`character_name` 필터 **패턴 차용**). [history/cache.py](../maple_mate/history/cache.py) `is_cache_fresh`. [history/models.py](../maple_mate/history/models.py) `HistoryCache`(PK `ocid,type,date`; `type` ∈ {starforce, **cube**, **potential_reset**}; **마이그레이션 완료**).
- [nexon/client.py](../maple_mate/nexon/client.py) `starforce_history`(라인 185, **시그니처 미러링 대상**)·`_request(path, *, api_key=None, **params)`. [nexon/errors.py](../maple_mate/nexon/errors.py) `NexonAPIError`·`to_error_log_type`.
- [registration/service.py](../maple_mate/registration/service.py) `Target`·`TargetOutcome`·`classify_target_error`. [security/crypto.py](../maple_mate/security/crypto.py) `KeyCipher.decrypt`.
- [bot/comparison.py](../maple_mate/bot/comparison.py) `table_image_message`·`highest_indices`·`all_failed_embed`·`attach_failures`·`respond_with_pages`·`truncate_display`·`data_footer`. [bot/embeds.py](../maple_mate/bot/embeds.py) `defer`·`make_embed`. [character/service.py](../maple_mate/character/service.py) `format_eok`.
- [bot/item_card.py](../maple_mate/bot/item_card.py) `_GRADE`(등급→색)·`_draw_pill`(라운드 뱃지) — **등업 뱃지 셀이 공유**. [bot/table_image.py](../maple_mate/bot/table_image.py) `render_table_image`·`Highlight`·`NumGrid`·`_load_fonts`.
- [history/commands.py](../maple_mate/history/commands.py) — `/스타포스` 어댑터(흐름·부분성공·푸터 **그대로 본뜸**). [dependencies.py](../maple_mate/dependencies.py) `Deps`.

**새로 만듦:** `NexonClient.cube_history`·`potential_history` · `history/potential_service.py`(또는 `service.py` 확장) · `history/potential_cost.py`(메소 단가표 — **G2 대기**) · `bot/table_image.GradeBadges` 셀 + 렌더 · `history/potential_commands.py`(`/잠재`) · `scripts/spike_potential.py` · 테스트.

> ⚠️ 스타포스와 달리 **레벨 매칭(`equipment_level.py`)·`error_log(unmatched_equipment)`·`기준건수` 컬럼은 불필요** — 레코드에 `item_level`이 직접 있음(핸드오프 "핵심 차이").

## 선행 게이트 (코딩 전)

- **G1 — 미니스파이크(빌드 0)**: `scripts/spike_potential.py`로 등업 "성공" 의미 확정. 총 큐브·분포는 G1 전에도 가능, **등업만** G1 후 활성.
- **G2 — 메소 단가표**: `사용 메소` 컬럼만 막음. 미수령이면 빌드 4·해당 컬럼 보류, 나머지 먼저 출시(D3).

## 빌드 단위 (의존 순서)

### 0. `scripts/spike_potential.py` — G1 게이트
- 개인 키로 `history/potential` 1콜 덤프(Spike 0 패턴). 확인: ① 응답 스키마 키(DTO 교차검증) ② **`item_upgrade_result=="성공"` = 등급 상승인가** ③ 천장(`upgrade_guarantee=true`) 등업 시 결과 문자열 ④ `before_potential_option[0].grade`가 등업 전 등급인가.
- 0건이면 사용자가 메소 재설정 1회 후 재시도. 결과를 [potential-handoff.md](potential-handoff.md) "등업 메커니즘"에 반영.

### 1. `NexonClient.cube_history` · `potential_history`
```python
async def cube_history(self, api_key: str, date_iso: str, count: int = 1000) -> list[dict]:
    """개인 키로 그 계정 cube 이력(해당 KST 1일). next_cursor 누적, null→[]."""
async def potential_history(self, api_key: str, date_iso: str, count: int = 1000) -> list[dict]:
    """개인 키로 그 계정 potential(메소 재설정) 이력(해당 KST 1일). null→[]."""
```
- `_request("maplestory/v1/history/cube", api_key=api_key, count=count, date=date_iso)` → `cube_history` 리스트(potential은 `.../potential` → `potential_history`). `starforce_history`(라인 185) 미러링. `next_cursor` 비-null이면 `cursor=`로 누적(친구 그룹 보통 1콜).
- *검증: `B2_cube_yday.json`·`BSCAN_cube_2026-05-31.json` 스키마 키 대조. potential은 미니스파이크 덤프 대조.*

### 2. `history/potential_service.py` — 기간·페치·캐시·집계 (전달-무관, 순수 우선)
- `resolve_period`·`get_history_targets`·`HistoryTarget`는 **재사용**(import).
- `async def fetch_potential_records(deps, target, dates) -> tuple[list[CubeRecord], list[ResetRecord]]` — 날짜별 `is_cache_fresh` → 미스 시 `cipher.decrypt`로 `cube_history`/`potential_history` 호출 → `history_cache` upsert(`type="cube"` / `type="potential_reset"`) → **`character_name == target.nickname` 필터**. `fetch_starforce_records` 패턴 차용.
- 파싱 dataclass(frozen): `CubeRecord(cube_type, item_level, item_part, target_item, result, pot_grade, add_grade, before_pot, after_pot, before_add, after_add, date_create)`, `ResetRecord(potential_type, item_level, item_part, target_item, result, ..., date_create)`.
- `def aggregate_potential(cubes, resets, *, meso_cost=None) -> PotentialSummary` — **순수**:
  - `cube_count = len(cubes)`, `reset_count = len(resets)`.
  - **등업**: cube+reset 합쳐 `result == "성공"`인 레코드를 from-등급별로 카운트. from-등급 = `before_pot[0].grade`(또는 before 최고 등급; 미니스파이크 확정값). 버킷 = {레어, 에픽, 유니크} → 0건 제외 후 `tierups: tuple[(grade, count), ...]`(등급 순). `tierup_total`.
  - **메소**: `meso_cost`(단가표 함수, G2) 주입 시 `Σ meso_cost(item_level, item_part)` (potential 위주; cube 메소는 0 가정). 미주입(None)이면 `total_meso=None`.
  - **단일 대상 보조**: `by_cube_type: tuple[(cube_type, count), ...]`(내림차순), `by_grade: tuple[(grade, 잠재횟수, 에디횟수), ...]`(예시3).
  - 반환 `PotentialSummary(cube_count, reset_count, tierups, tierup_total, total_meso, by_cube_type, by_grade)`.
- 등급 순서 상수: `GRADE_ORDER = {"레어":1, "에픽":2, "유니크":3, "레전드리":4}`.
- *검증: cube_count·reset_count·등업 from-등급 버킷팅(성공만·0건 제외)·동급내 실패는 등업 0·by_cube_type/by_grade 집계. 넥슨 mock. `character_name` 필터.*

### 3. `bot/table_image.py` — `GradeBadges` 셀 타입
```python
@dataclass(frozen=True)
class GradeBadges:
    """등업 from-등급 뱃지 셀. items=[(grade_name, count), ...](0건 제외).
    각 등급을 item_card._GRADE 색 라운드 pill(라벨 ×count)로 가로 나열. 빈 목록이면 호출부가 '—' 문자열 전달."""
    items: tuple[tuple[str, int], ...]
```
- `render_table_image`의 셀 분기에 `GradeBadges` 추가: 컬럼 폭 = 각 pill 폭 합 + 간격. 그리기는 [item_card.py](../maple_mate/bot/item_card.py) `_draw_pill`/`_GRADE`를 공유(필요 시 작은 pill 변형 헬퍼를 `table_image`로 추출해 두 모듈이 공유 — 순환 import 주의: 색·pill 그리기를 `table_image`에 두고 `item_card`가 import).
- *검증: 0건→호출부 `—`, 다등급 뱃지 폭 계산, 색 매핑(미상 등급 회색). 렌더 스모크(PNG bytes 생성).*

### 4. `history/potential_cost.py` — 메소 단가표 (⚠️ G2 대기)
- 단가표 수령 후: `def meso_reset_cost(item_level: int, item_part: str | None = None) -> int` — 레벨(부위) 기준 메소 재설정 단가. 스타포스 `cost()` 인코딩 패턴.
- 수령 전엔 **이 빌드·`사용 메소` 컬럼 스킵**(D3). `aggregate_potential(meso_cost=None)`로 호출.
- *검증(수령 후): 단가표 알려진 케이스 픽스처 대조.*

### 5. `history/potential_commands.py` — `/잠재`
- 인자: `기간`(choice: 오늘/어제/최근7일[기본]/최근30일/최근90일/최근1년/이번주/이번달) + 선택 `시작일`·`종료일` + `대상1~5`(미지정=서버 키 등록자 전원). `/스타포스`와 동일 시그니처.
- 흐름(`handle_potential`): `defer` → guild 가드 → `get_history_targets` + 미등록/키미등록 분리(`TargetOutcome`) → `resolve_period` → 대상별 `fetch_potential_records`→`aggregate_potential` → PNG 표.
- 표(`table_image_message`): 컬럼 `순위`·`캐릭터`·`총 큐브`·`등업`(`GradeBadges` 또는 `—`)·(`사용 메소` — G2 후, `format_eok`). **정렬**: MVP=등업 총횟수 내림차순(동률 시 총 큐브), 메소 활성 후=사용 메소 내림차순(옵션). 최상위 행 강조(`highest_indices`).
- **단일 대상(대상1만 지정 & 1명)**: 표 아래 보조 임베드 필드/카드 — 큐브종류 분포(`by_cube_type` 상위 N)·등급별 재설정(`by_grade`, 예시3 표)·등업 FROM→TO 뱃지 진행. 다인 비교 시 생략(D5).
- 부분 성공(키미등록·기록없음·조회실패·미등록) = `attach_failures`/`all_failed_embed`. 기록 없음(필터 후 cube+reset 0건) vs 키미등록 **구분**(CONTEXT.md). 푸터=기간 범위. 2장+면 `respond_with_pages`.
- *검증: 키미등록 vs 기록없음 분기·정렬·단일 대상 보조 노출 조건(넥슨 mock).*

### 6. 배선 + 테스트
- `bot/core.py._register_commands`에 `from ..history.potential_commands import setup as setup_potential` + `setup_potential(self)`.
- 테스트(`tests/`): `test_potential_aggregate.py`(cube_count·등업 버킷·by_cube_type/by_grade·필터)·`test_potential_command.py`(키미등록 vs 기록없음·정렬·단일 보조)·`test_table_image_badges.py`(GradeBadges 렌더·0건). 넥슨/디스코드 mock. E2E 생략.

## 렌더 전략

| 모드 | 렌더 |
|---|---|
| `/잠재` 다인 비교 | PNG 비교표(`table_image_message`), `등업`=`GradeBadges` pill, 최상위 강조 |
| `/잠재` 단일 대상 | 위 표 1행 + 보조(큐브종류 분포·등급별 재설정·FROM→TO 뱃지) |

푸터: 오늘 포함 시 `HH:MM 기준`, 과거만이면 `YYYY-MM-DD ~ ...`(`data_footer`/`_period_footer` 패턴). 모든 명령 `defer` 의무.

## 산출물
- 위 코드 + 단위테스트 통과 + `uv run pytest` 그린 + `uvx ruff check maple_mate/`. 가능 시 개인 키로 라이브 `/잠재` 1회 눈 확인.
- (G2 후) `사용 메소` 컬럼 활성 + 단가표 픽스처 테스트.
- 문서 갱신: design §3.5(통합 반영)·work-plan(잠재 상태)·CONTEXT.md(`등업` 용어).

## 미실측 / 리스크
- ⚠️ **G1 "성공" 의미** — 미니스파이크 전엔 가정 구현, 라이브 1건 후 확정.
- ⚠️ **G2 단가표 미수령** — 메소 컬럼 보류. 단가표 형태에 따라 `potential_cost.py` 모양 결정.
- potential 메소 재설정이 **등급 상승을 일으키는지** 불명 — 등업은 cube 주도일 수 있음(미니스파이크 관찰).
- 큐브 메소(장인의/명장의) 0 가정 — 친구 그룹이 쓰면 후속 단가 보강.
- 닉 변경 시 `character_name` 불일치(잔류). 콜드 1년 다인 latency(캐시·365 상한·글로벌 스로틀 의존).

## 스코프 밖 (이 작업 아님)
- 누적 캐시·감정 비용(예시1)·천장 스택 현황·옵션 분포 상세 — 백로그.
- 키별 병렬 스로틀·이벤트 할인 반영 — 백로그.
