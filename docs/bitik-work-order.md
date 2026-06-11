# 작업 지시서 — `/비틱` (스타포스·잠재·득템 자랑)

> Phase 8(스케일 튜닝)까지 완료된 상태에서 신규 기능 `/비틱`을 착수한다.
> 비틱 = 자랑. 스타포스가 잘됐거나, 잠재가 잘 떴거나, 득템했을 때 채널에 자랑 카드를 발송하는 명령.
> 그릴링(`/grill-me`)으로 아래 결정을 확정했다.

## 참조 (중복 금지 — 경로로 참조)

- [docs/phase3-work-order.md](phase3-work-order.md) — 이력류 페치·캐시·레벨 매칭·기대값 엔진(전부 재사용)
- [docs/starforce-expected-value-data.md](starforce-expected-value-data.md) — 확률표·비용공식(손익 계산 근거)
- [docs/api/history.md](api/history.md) — starforce/cube/potential 응답 필드 실측
- 레이아웃 참고 스크린샷: `비틱_스타포스_1.png`(12→19 이득 카드), `비틱_스타포스_2.png`(17→17 손해 카드), `비틱_잠재_1.png`, `비틱_잠재_2.png` (외부 서비스 캡처 — 구성 참고용, 픽셀 카피 아님)

## 현황 진단

**이미 있음 (재사용 — 새로 만들지 말 것):**
- `history/service.py` — `resolve_period`(프리셋 8종+커스텀, **상한 365일** — 주석의 "30일"은 낡은 문구), `fetch_history`(날짜별 페치+`history_cache`+캐릭터 필터), `HistoryTarget`/`get_history_targets`, `StarforceAttempt`/`parse_attempts`.
- `history/expected_cost.py` — `expected_meso(level, start, end)` 마르코프, `cost(level, star)`, `actual_meso`.
- `history/equipment_level.py` — 레벨 3단 매칭(장착→시드→None).
- `history/potential_service.py` — `CubeRecord`/`ResetRecord` 파싱.
- `history/potential_cost.py` — `reset_cost(item_level, grade, type)`, `appraisal_cost(item_level)`.
- `NexonClient` — `starforce_history`/`cube_history`/`potential_history`(개인 키), `character_item_equipment`(아이콘·레벨 소스, 스펙 캐시 30분), 키별 스로틀 버킷.
- `bot/item_card.py`·`bot/table_image.py` — PIL 렌더 팔레트·폰트·`to_thread` 패턴.
- `bot/cooldowns.py` — per-user 쿨다운 헬퍼.

**새로 만듦:** `bitik/` 패키지(집계 `service.py`·명령 `commands.py`) · `bot/bitik_card.py`(카드 렌더) · **`discord.ui.View`+`Select` 인터랙션(코드베이스 최초의 동적 컴포넌트 — 신규 패턴)**.

## 확정 결정 (그릴링 결과)

| # | 결정 | 선택 |
|---|---|---|
| Q1 | **대상 범위** | **본인만.** 실행자 본인의 등록 캐릭터(개인 키 필수). 미등록/키 미등록 시 ephemeral 안내. 자랑은 본인이 하는 것 — 멤버 지정 없음. |
| Q2 | **명령 구조** | `app_commands.Group` — `/비틱 스타포스`, `/비틱 잠재`, `/비틱 득템`. 서브커맨드별 파라미터가 달라(기간 vs 이미지 첨부) 단일 명령+choice 불가. |
| Q3 | **스타포스 목록 필터·정렬** | **전체 포함, 이익순 정렬.** 손해(음수) 아이템도 포함(역비틱 허용 — 스크린샷 2가 실례). 이익 = `expected_meso(level, 시작★, 끝★) − 실제사용`. Discord select 제한으로 **상위 25개**, 라벨에 손익 표기. |
| Q4 | **공개 흐름** | **목록 ephemeral, 카드 공개.** 아이템 select 메뉴는 실행자만 보고, 선택 확정 시 채널에 공개 카드 발송. 스타포스·잠재 공통. |
| Q5 | **아이콘 소싱** | **장착 장비 매칭 best-effort.** 공식 API에 이름→아이콘 엔드포인트 **없음 확인**(히스토리 응답에도 아이콘 필드 없음). `item-equipment`(프리셋 1~3 포함) `item_name == target_item` 매칭으로 `item_icon` URL 취득, 미매칭 시 아이콘 없는 레이아웃. |
| Q6 | **스타포스 카드 내용** | 스크린샷 구성 + **손익 한 줄 추가.** [아이콘 / 아이템명 / ★시작→★끝 / 사용 메소 / 기댓값 대비 ±n 이득·손해 / 강화 n번·파괴 n번 / ★도전성 x성공 y실패 / 기간 footer]. |
| Q7 | **잠재 시작→끝 표시** | **시작 = 등급만, 끝 = 등급+옵션 3줄 풀표시.** 잠재·에디셔널은 기간 내 기록 있는 종류만 각각 섹션 분리. |
| Q8 | **큐브 사용량 표시** | **텍스트 라벨+개수.** `레드 큐브 ×65 · 블랙 큐브 ×23 · 메소 재설정 ×3` 식. 게임 아이콘 자산 번들 안 함(저작권·자산관리 회피). 큐브 종류별 색상 코딩으로 가독성 보강. |
| Q9 | **득템 문구** | **랜덤 문구 풀 + 선택적 코멘트.** "이거 좋은건가요? ㅎㅎ" 등 비틱 톤 문구 5~10개 상수 풀에서 랜덤. `코멘트` 파라미터 입력 시 그 문구 사용. |
| Q10 | **레벨 미상 아이템** | **목록에서 제외.** 장비 매칭 실패(미장착·파괴·판매)로 레벨 미상 → 기댓값·메소 계산 불가 → 목록 하단에 "레벨 미상 n개 제외" 안내만. `error_log(unmatched_equipment)` 적재는 기존 패턴 유지. |

**파생 결정 (그릴링 중 질문 없이 확정):**
- **시작→끝 정의:** 기간 내 해당 아이템 **첫 시도의 `before_star` → 마지막 시도의 `after_star`**. 끝≤시작이면 `expected_meso`=0 → 자연스럽게 전액 손해(분기 불필요).
- **★도전 줄:** 도전성 = 기간 내 `max(before_star)+1`. 해당 `before_star == max` 시도들의 성공/실패 집계 (스크린샷 "★19도전 1성공 4실패" 재현).
- **아이템 그룹핑:** 스타포스 = `target_item` 이름 단위(개체 ID 없음 — 동명 장비 2개 병합은 알려진 제약). 잠재 = `(target_item, item_level)` 단위.
- **슈페리얼 장비:** `superior_item_flag` true는 확률표·비용공식이 상이 → Q10과 동일하게 목록 제외 + 제외 안내에 합산.
- **잠재 정렬:** 재설정 횟수(큐브 + 메소 재설정 합산) 내림차순, 상위 25개. 잠재 비용 = `reset_cost` 합(본문) + `appraisal_cost` 합(별도 줄, 스크린샷 "+ 감정 n 메소"). 큐브 현금 가치는 미환산(알려진 제약).
- **기간 UX:** `resolve_period` 그대로(프리셋 8종 + `YYYY-MM-DD`, 기본 최근7일). 손익은 **정가 기준**(Phase 3 Q3과 동일 — 썬데이 할인 미반영, 순수 운 측정).
- **득템 검증:** attachment `content_type`이 `image/*` 아니면 ephemeral 거절.
- **쿨다운:** 스타포스·잠재 = `HISTORY_PER`(30초, 이력류 동일), 득템 = 10초(API 콜 없음, 스팸 방지).
- **select 타임아웃:** View 120초, 만료 시 컴포넌트 비활성화. 선택 1회 후에도 비활성화(중복 발송 방지).

## 빌드 단위 (의존 순서)

### 1. `bitik/service.py` — 아이템 단위 집계 (순수)
- `@dataclass(frozen=True) StarforceBitik` — `item, level, start_star, end_star, attempt_count, destroy_count, actual_meso, expected_meso, net_meso(=expected−actual), challenge_star, challenge_success, challenge_fail`.
- `group_starforce(attempts, level_of) -> tuple[list[StarforceBitik], int]` — 이름별 그룹 → 시간순 정렬 → 시작/끝/도전 집계 → 레벨 미상·슈페리얼 제외 카운트 반환 → net 내림차순.
- `@dataclass(frozen=True) PotentialBitik` — `item, item_level, reset_count, cube_counts: tuple[(type, n)], meso_reset_count, reset_meso, appraisal_meso, sections: tuple[PotentialSection]`(종류별 시작 등급 / 끝 등급+옵션 3줄).
- `group_potential(cube_records, reset_records) -> list[PotentialBitik]` — `(이름, 레벨)` 그룹 → 횟수 합산 내림차순.
- *검증: 시작→끝·도전 집계·끝≤시작 손해·제외 카운트·잠재 섹션 추출·정렬 단위테스트(픽스처는 스크린샷 수치 재현 — 12→19/19번/0번/★19도전 1성공 4실패).*

### 2. `bot/bitik_card.py` — PNG 카드 렌더
- `render_starforce_card(bitik, icon_bytes | None, period_label) -> BytesIO` / `render_potential_card(...)` — 스크린샷 구성의 다크 카드(기존 팔레트·폰트), 손익 줄 색상(이득=금색 강조, 손해=빨강), 아이콘 미매칭 시 텍스트 중심 레이아웃. `asyncio.to_thread` 호출 전제의 순수 함수.
- 아이콘: `item-equipment` 응답 매칭 → `item_icon` URL fetch(실패 시 None 폴백, 카드 발송은 진행).
- *검증: 렌더 스모크(예외 없이 PNG 생성) + 아이콘 None 분기.*

### 3. `bitik/commands.py` — Group + Select View
- `Group(name="비틱")` + 서브커맨드 3개. 스타포스·잠재는 `period`/`start`/`end` 파라미터(이력류와 동일 시그니처).
- 흐름: defer(ephemeral) → 본인 `HistoryTarget` 해석(미등록/키 미등록 ephemeral 안내) → `fetch_history` → 집계 → 0건이면 "자랑할 기록이 없네요" ephemeral → select 목록(ephemeral, 라벨 = `아이템명 ★12→19 · +3.2억` / 잠재 = `아이템명 · 재설정 ×136`) → 선택 인터랙션에서 카드 렌더 → **공개** `send_message` → View 비활성화.
- `/비틱 득템`: `이미지: Attachment`(필수) + `코멘트: str | None` → image/* 검증 → 공개 embed(작성자 표기 + 문구 + 이미지 첨부). defer 불필요.
- `bot/core.py` `setup()`에 `setup_bitik(bot)` 등록 + 쿨다운 적용.
- *검증: 대상 해석 분기·0건·목록 라벨 포맷 단위테스트(Discord mock). select 인터랙션은 라이브 확인.*

## 렌더 전략

| 서브커맨드 | 성격 | 렌더 |
|---|---|---|
| `/비틱 스타포스` | 단일 아이템 자랑 카드 | PNG 카드(아이콘+성수+메소+손익+도전기록), footer = 기간 |
| `/비틱 잠재` | 단일 아이템 자랑 카드 | PNG 카드(아이콘+메소+감정+큐브 텍스트 라벨+시작→끝 잠재), footer = 기간 |
| `/비틱 득템` | 이미지 중계 | embed(작성자+랜덤/지정 문구+첨부 이미지), 렌더 없음 |

## 테스트 전략 (실용 테스트 합의)

순수 로직만 단위테스트: 아이템 그룹핑·시작/끝·도전 집계·손익 부호·제외 카운트·잠재 섹션·정렬·목록 라벨. Nexon/Discord mock. 카드 렌더는 스모크. select 인터랙션·공개 발송은 라이브 1회 확인.

## 미해결 / 잔류 리스크

- **동명 장비 병합** — 개체 ID 부재로 같은 이름 2개를 기간 내 같이 강화하면 한 카드로 합쳐짐. 회피 불가, 카드가 이상하면 기간을 좁히라는 안내로 갈음.
- **장기간 콜드 조회 latency** — 365일 콜드 = 날짜당 1콜(개인 키 0.2s 간격) ≈ 70s+. 기존 이력류와 동일 특성(400일 캐시 의존). defer + 진행 안내 문구로 완화, 추가 최적화는 백로그.
- **select 인터랙션 신규 패턴** — 코드베이스 최초의 View/Select. 봇 재시작 시 기존 View 무효(persistent view 미사용 — 120초 수명이라 무관).
- **아이콘 URL 핫링크** — 넥슨 static CDN 직링크. 2024-11-21 URL 구조 변경 전례 → fetch 실패 시 None 폴백으로 방어(이미 설계에 포함).

## 스코프 밖 (보류)

- 멤버 지정/대리 비틱 — Q1에서 본인만으로 확정.
- 큐브 게임 아이콘 자산 번들 — Q8에서 텍스트로 확정.
- 운지수 백분위 카드 표기 — Q6에서 손익 한 줄로 확정(몬테카를로 비용 회피).
- 득템 이미지의 OCR/아이템 인식 — API 부재로 영구 스코프 밖.
