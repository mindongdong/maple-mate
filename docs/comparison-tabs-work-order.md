# 작업지시서 — 비교 결과 탭 전환 버튼 (PR2/3)

> **근거 결정:** ADR-0022(본 작업으로 작성 — §6). 선행 [target-unification-work-order.md](target-unification-work-order.md)(PR1, ADR-0021).
> **하우스 스타일 레퍼런스:** [my-character-work-order.md](my-character-work-order.md), [random-fanout-work-order.md](random-fanout-work-order.md).
> **결정 출처:** 2026-10-12 세션. 사용자 판단: 같은 사람들을 스펙→아이템→유니온으로 이어 볼 때마다 대상을 다시 입력해야 해서 불편하다.
> **선행 조건:** **PR1 머지 후 착수.** PR1의 통합 대상 해석(`resolve_mixed_targets`)과 3종 핸들러 시그니처가 전제다.
> **상태:** 구현 완료 — PR #72(브랜치 `claude/comparison-tabs`, PR1 머지 후 main 위로 재배치). §7 as-built 참고.

---

## 0. 한 줄 목표

`/스펙`·`/아이템`·`/유니온` 결과 메시지에 **탭 전환 컴포넌트**(스펙·유니온 버튼 + 아이템 부위 선택 메뉴)를 붙인다. 실행자가 **같은 대상 그대로** 다른 비교를 보도록 메시지를 제자리에서 교체한다.

---

## 1. 배경·코드 현황 (재조사하지 말 것)

- **3종 핸들러 = 해석 → 조회 → 렌더 → send 한 덩어리**: `handle_spec`([character/commands.py:214](../maple_mate/character/commands.py#L214)), `handle_item`([:364](../maple_mate/character/commands.py#L364)), `handle_union`([union/commands.py:29](../maple_mate/union/commands.py#L29)). 렌더 일부는 이미 공유 함수로 추출돼 있다:
  - `fetch_spec_outcomes`·`build_spec_comparison`([:110](../maple_mate/character/commands.py#L110))·`single_detail_embed`
  - `fetch_item_outcomes`·`build_item_cards`([:324](../maple_mate/character/commands.py#L324))
  - 유니온은 핸들러 안에 표 렌더가 인라인으로 있다 → 추출이 필요하다.
- **출력 형태가 제각각**:
  - 스펙: 1명이면 임베드만, 2명+면 임베드 + PNG
  - 아이템: 항상 PNG
  - 유니온: 1명이면 임베드만, 2명+면 PNG
  - 탭 전환 시 첨부 교체·제거를 다뤄야 한다.
- **View 전례 2개**:
  - `EmbedPaginator`([bot/embeds.py:69](../maple_mate/bot/embeds.py#L69)): `author_id` 검사(`interaction_check` → "본인만 조작할 수 있어요." ephemeral), timeout 180s.
  - `BitikSelectView`([bitik/commands.py:234](../maple_mate/bitik/commands.py#L234)): Select 콜백, `on_timeout`에서 `origin.edit_original_response(view=…)` 비활성, `discord.HTTPException` 무시.
  - 둘 다 non-persistent이고, 재시작 무효를 감수했다.
- **부위 24개**(`SLOT_CHOICES`, [character/equipment_slots.py](../maple_mate/character/equipment_slots.py)) → Select 1개(상한 25)에 전부 들어간다.
- **쿨다운은 슬래시 전용**: `cooldowns.spec_cooldown()`(10s)은 `app_commands.checks.cooldown`이라 **컴포넌트 클릭엔 적용되지 않는다**. 버튼 연타 방지는 View가 스스로 해야 한다.
- **조회 캐시**: 최신 스펙 단기 캐시(D5, `NexonClient._spec_cache`)와 `deps.combat_power_cache`(과거 전투력 영구)가 있다. 같은 탭 재방문·스펙 재진입은 대부분 캐시 히트다.
- **토큰 수명**: 원 인터랙션 followup 웹훅 토큰은 15분이다. 클릭마다 새 인터랙션 토큰이 생기므로 교체는 클릭 인터랙션으로 한다. `on_timeout` 비활성화만 원 메시지 핸들로 한다 → **timeout < 15분 필수**.

---

## 2. 확정 결정

1. **대상 명령 = `/스펙`·`/아이템`·`/유니온`.** 아래는 제외한다:
   - `/경험치`: 리더보드 의미와 대상 집합이 다르다.
   - `/내캐릭터`: 유니온이 없고 캐릭터 타깃 모델이 다르다. 후속 검토로 둔다.
   - 이력류.
2. **조작 = 실행자만, 메시지 제자리 교체.** 타인 클릭은 `EmbedPaginator`와 같은 ephemeral 거부를 받는다. 새 메시지는 만들지 않는다(채널 도배 방지).
3. **대상 집합 고정**: 최초 실행 때 해석된 `targets` + 사전 실패 `missing`(미등록·닉 못 찾음)을 View 상태로 보관한다. 탭을 바꿔도 **재해석·재랜덤 없이 동일 집합**을 쓴다. 푸터의 무인자 안내 문구(`fanout_note`·본인 미포함)도 보관해 재부착한다.
4. **`/스펙` 탭 상한 5**: 집합이 6명 이상이면(무인자 아이템·유니온은 최대 10) 스펙 탭은 **앞 5명**만 조회한다. 본인은 `select_with_self`가 맨 앞에 두므로 보존된다. 푸터에 "스펙은 최대 5명 — 앞 5명만 비교했어요"를 붙인다(PR1 결정 2의 비용 근거 유지).
5. **컴포넌트 구성** (2행):
   - 1행: 버튼 `스펙` `유니온`. 현재 탭은 `primary`·disabled, 나머지는 `secondary`.
   - 2행: Select `아이템 부위 선택`(24개). 현재 아이템 탭이면 그 부위를 `default=True`로 표시한다.
6. **연타 방지 = View 단위 in-flight 락.** 클릭 즉시 모든 컴포넌트를 disabled로 바꿔 `response.edit_message(view=…)`로 즉시 응답한다(3초 응답 기한 충족). 조회 후 `edit_original_response`로 결과와 재활성 컴포넌트를 반영한다. 락 중 클릭은 무시한다. 별도 시간 쿨다운은 두지 않는다(캐시 + 락이면 충분).
7. **timeout = 600초**(15분 토큰 수명 내). 만료 시 컴포넌트를 전부 제거한다(`view=None`). 비활성 버튼이 남아 헷갈리는 것보다 깔끔하다.
8. **오류 처리**: 탭 조회가 전원 실패하면 기존 `all_failed_embed`로 교체하고 컴포넌트는 유지한다(다른 탭으로 복귀 가능). 예외는 로그 후 컴포넌트를 재활성화한다.

### 비목표
- persistent view(재시작 후 복구)
- 누구나 조작/새 메시지 모드
- `/내캐릭터`·`/경험치` 탭
- 대상 추가·제거 UI
- 탭별 최초 진입 데이터 프리페치

---

## 3. 설계 핵심

### 3-1. 렌더 함수 추출 (동작 불변 리팩터 — 먼저 커밋)

3종이 공유할 **메시지 빌더 시그니처**를 통일한다:

```python
@dataclass(frozen=True)
class ComparisonMessage:
    embed: discord.Embed
    file: discord.File | None  # None = 첨부 없음(단일 상세 임베드·전원 실패)

async def build_spec_message(deps, targets, missing, *, notes: list[str]) -> ComparisonMessage
async def build_item_message(deps, targets, missing, slot, *, notes, self_id) -> ComparisonMessage
async def build_union_message(deps, targets, missing, *, notes) -> ComparisonMessage
```

- 각 빌더 = 조회(`fetch_*_outcomes` / `fetch_each`) + 기존 렌더 경로(단일/다수/전원 실패 분기 포함).
- `handle_*`는 "가드·해석·무인자 선정 → 빌더 → send"로 얇아진다.
- 유니온 인라인 렌더는 `union/commands.py` 안 `build_union_message`로 옮긴다.
- 위치: 스펙·아이템은 `character/commands.py`, 유니온은 `union/commands.py`(도메인 유지). View가 둘을 import한다.
- **이 커밋만으로 기존 테스트 전부 그린 + 출력 불변**이어야 한다.

### 3-2. `ComparisonTabsView` (신규 `bot/comparison_tabs.py`)

```python
class ComparisonTabsView(discord.ui.View):
    def __init__(self, *, deps, author_id, targets, missing, notes, current: Tab, slot: str | None): ...
    async def interaction_check(...)   # author_id 외 거부(ephemeral) — EmbedPaginator 동일 문구
    async def _switch(self, interaction, tab: Tab, slot: str | None):
        # 1) 락·전체 disabled → interaction.response.edit_message(view=self)
        # 2) msg = await build_*_message(...)
        # 3) self.current/slot 갱신·_sync_components()
        # 4) interaction.edit_original_response(embed=msg.embed,
        #        attachments=[msg.file] if msg.file else [], view=self)
    async def on_timeout(self): # self.message.edit(view=None), HTTPException 무시
```

- 순환 import 회피: `character`·`union` → `bot.comparison` 방향 의존이 이미 있다. 따라서 View는 빌더를 **생성자 주입 콜러블**(`builders: dict[Tab, Callable]`)로 받고, 조립은 핸들러 쪽에서 한다.
- `Tab = Literal["spec", "item", "union"]`.
- `self.message` = 최초 `interaction.followup.send(..., view=view, wait=True)`의 반환값.
- 스펙 탭 5명 절단(결정 4)은 View가 builders 호출 전에 적용하고 note를 추가한다.

### 3-3. 핸들러 연결

3종 핸들러 마지막 send를 `followup.send(embed, file?, view=ComparisonTabsView(...), wait=True)`로 바꾸고 `view.message`를 지정한다. 아래 경로에는 View를 붙이지 않는다(대상 없음):
- 최초 결과가 **조회 이전 가드 실패**(DM, 등록자 0명, 전원 미등록)인 경우

---

## 4. 빌드 단위·테스트

| # | 작업 | 검증 |
|---|---|---|
| 1 | §3-1 빌더 추출(동작 불변) | 기존 `test_*command*`·`test_item_card`·`test_union_service` 전부 그린 |
| 2 | `ComparisonTabsView` 상태·`_sync_components`(현재 탭 disabled, Select default) | 순수 단위: 탭별 컴포넌트 상태 |
| 3 | `interaction_check` 타인 거부 | 가짜 Interaction: 타 uid → ephemeral·빌더 0회 |
| 4 | `_switch` 흐름(즉시 disabled 응답 → 빌드 → 교체, 첨부 None이면 `attachments=[]`) | 빌더 mock 호출 인자: 동일 targets/missing 전달 |
| 5 | 스펙 탭 5명 절단 + note | 10명 집합 → 빌더에 앞 5명, 본인 포함 |
| 6 | 락: 진행 중 재클릭 무시 | 동시 2회 → 빌더 1회 |
| 7 | 전원 실패·예외 시 컴포넌트 재활성 | 빌더 raise → view 재활성·로그 |
| 8 | `on_timeout` → `view=None`, HTTPException 무시 | 단위 |
| 9 | 3종 핸들러 연결(가드 실패 경로는 view 없음) | 핸들러 테스트 |
| 10 | 사이트 카피: `commands.json` 스펙·아이템·유니온 tip에 "결과 아래 버튼으로 같은 대상의 스펙·아이템·유니온 전환" | 드리프트 테스트 그린(명령 추가 없음) |

공통 게이트: `uv run pytest` · `uv run ruff check . && uv run ruff format --check .`

**라이브 확인(배포 후):**
- 실행자 클릭 → 3초 내 로딩 상태 → 교체(첨부가 바뀌거나 사라짐)
- 타인 클릭 → ephemeral 거부
- 10분 후 컴포넌트 사라짐
- 무인자 `/아이템` → 스펙 탭에서 5명·본인 포함

---

## 5. 수용 기준

- [ ] `/아이템 부위:무기` 결과에서 `스펙` 클릭 → 같은 사람들의 스펙 비교로 교체(재랜덤 없음)
- [ ] 이어서 Select `모자` → 같은 사람들의 모자 카드로 교체
- [ ] 단일 상세(임베드만) ↔ PNG 탭 전환 시 첨부가 정확히 붙거나 제거됨
- [ ] PR1 게스트 대상·"조회 실패" 행이 탭 전환 후에도 유지됨
- [ ] 버튼 연타 시 넥슨 조회가 1회만 일어남
- [ ] 버튼을 안 누르면 기존 출력과 동일(임베드·PNG 회귀 0, 컴포넌트만 추가)

---

## 6. 기록·배포

- **ADR-0022 "비교 결과 탭 전환"**: 결정 2(실행자·제자리), 3(대상 집합 고정), 4(스펙 5명 절단), 6(락 vs 시간 쿨다운), 7(600s·토큰 수명 근거), non-persistent 감수.
- **CONTEXT.md**: "대상" 항목에 "탭 전환 시 최초 해석 집합을 고정 재사용" 한 줄.
- PR 1개. 단 커밋은 **#1 리팩터(동작 불변) / #2~9 기능**으로 분리해 리뷰 가능하게 한다.

---

## 7. As-built

- **빌더**: `character/commands.py` — `build_spec_message(deps, targets, missing, *, notes, realm)`·`build_item_message(deps, targets, missing, slot, *, notes, self_id, realm)`, `union/commands.py` — `build_union_message(deps, targets, missing, *, notes)`. 모두 `comparison.ComparisonMessage(embed, file|None)` 반환. 푸터는 `comparison.footer_with_notes(raw_date, notes)` — `notes` 는 **위→아래 표시 순**(팬아웃 안내 → 본인 미포함)이며 기존 출력과 바이트 동일.
- **View**: [bot/comparison_tabs.py](../maple_mate/bot/comparison_tabs.py) `ComparisonTabsView(author_id, targets, missing, notes, current, slot, slots, builders)` · `switch()` · `send()`(followup `wait=True` → `message` 보관). 상수 `TABS_TIMEOUT=600`·`SPEC_TAB_CAP=5`·`SPEC_TRUNCATED_NOTE`.
- **조립**: `character/commands.py` `make_tab_builders(deps, self_id, realm)`(union 빌더는 함수 안 지연 import — `union.commands` → `character.commands` 방향 import 순환 회피)·`send_with_tabs(...)`. 3종 핸들러의 마지막 send 를 대체한다. 조회 이전 가드 실패(DM·등록자 0·전원 미등록)는 View 없이 기존대로 보낸다.
- **§4 #1 커밋 분리는 생략**: 리팩터와 기능을 한 커밋에 담았다. 단 기존 테스트 878건이 리팩터 후 무수정 통과(동작 불변)를 확인했다.
- **리뷰 반영(PR2 리뷰)**: ① 스펙 탭 절단은 **본인 우선**(안정 정렬 후 5명 — 등록자 ≤10 무인자는 DB 순서라 본인이 뒤일 수 있음), 안내 문구 "본인 우선 5명". ② View timeout은 discord.py에서 **유휴 시간**(클릭마다 연장)이라 `on_timeout`은 마지막 클릭 인터랙션 토큰으로 정리(§1·§2-7의 "원 토큰 15분 안" 전제 정정). ③ 결과 교체 실패 시 탭 상태를 이전으로 복원. ④ `/유니온` 경유 스펙·아이템 탭의 realm 무필터는 수용(ADR-0022 결정 9). ⑤ 조립 함수의 중립 모듈 분리는 보류 — 각 핸들러가 세 빌더를 모두 필요로 해 순환이 구조적이라 지연 import 1곳이 최소.
- **테스트**: [tests/test_comparison_tabs.py](../tests/test_comparison_tabs.py)(21건 — 본인 우선 절단·실패 복원·마지막 토큰 정리·빌더 전원 실패·스펙/아이템 핸들러 배선·realm 전달 포함).
