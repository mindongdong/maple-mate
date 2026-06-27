# 핸드오프 — 스케줄러 API 기반 신규 봇 기능

> **상태: 미설계·미구현 (2026-06-26).** API 문서화·실호출 검증만 끝났다(PR [#28](https://github.com/mindongdong/maple-mate/pull/28) MERGED).
> 다음 세션은 **이 문서로 맥락을 이어받아 → 설계 그릴링 → 작업지시서 → 구현**으로 진행한다.
> API 스펙·필드·가용성·실호출 회귀는 **[docs/api/scheduler.md](api/scheduler.md)** 에 전부 있다(여기서 중복 금지, 경로 참조).

## 0. 한 줄 목표

넥슨 신규 **스케줄러 정보 조회** API(`GET maplestory/v1/scheduler/character-state`)로
캐릭터의 **일일/주간 콘텐츠·퀘스트·보스 "숙제" 수행 현황**을 디스코드에서 보여주는 명령을 만든다.

## 1. 직전까지 한 일 (완료)

- `docs/api/scheduler.md` 신규 — 공식 OpenAPI YAML로 스키마 1:1 확인 + 실호출 검증 결과 반영.
- `docs/api/README.md` 카테고리 인덱스에 `id=57` 행 추가.
- **실호출 검증(2026-06-26):** docker compose 스택에서 **DB 저장 개인 키(Fernet 복호화)** 로
  등록 캐릭터 8명(5계정) 호출 → **전원 200 OK**(챌린저스 포함). 상세·회귀는 scheduler.md "✅ 실호출 검증" 참고.

## 2. 설계에 직결되는 **확정 제약** (scheduler.md에서 발췌 — 반드시 숙지)

이 5개가 기능 형태를 좌우한다. 원문·근거는 [scheduler.md](api/scheduler.md).

1. **계정 스코프 = 이력류 모델.** `ocid`는 **API 키 소유 계정의 캐릭터만** 조회된다.
   → **봇 앱 키로는 불가.** 유저별로 그 유저의 **개인 키**(미등록 유저는 조회 불가)가 필요하다.
   `history/*`(/스타포스·/잠재)와 같은 키 모델([ADR-0001](adr/0001-nexon-personal-key-model.md)).
   단 `history/*`와 달리 **`ocid`로 계정 내 어느 캐릭터인지 지정**한다(per-account 아님, per-character).
2. **오늘 데이터는 `date` 무지정으로만.** `date`에 오늘을 명시하면 `400 OPENAPI00004`. 과거(−14일)는 명시.
3. **per-character 데이터.** 보스/일일/주간 숙제는 캐릭터마다 다르다 → "어느 캐릭터(들)을 보여줄지"가 핵심 결정.
4. **응답이 크다.** 활성 캐릭터는 daily=18, weekly=22, boss=77까지. 그대로 쏟으면 임베드 초과 → 필터·요약 필수.
   `registration_flag`("true"/"false") = 인게임 스케줄러에 그 유저가 직접 등록한 항목 → **이걸로 1차 필터**가 자연스럽다.
5. **비대상 캐릭터는 빈 응답이 아니라 4xx**(`OPENAPI00003`/`00004`). 미접속·신규 캐릭터 흡수 처리 필요.

## 3. 열린 설계 결정 — **다음 세션 그릴링 대상** (아직 미확정)

> `/grill-with-docs` 또는 `/grill-me`로 아래를 CONTEXT.md·ADR에 비춰 확정한 뒤 작업지시서를 써라.

| # | 결정할 것 | 선택지 / 쟁점 |
|---|---|---|
| 1 | **명령 형태** | (a) **개인 카드**(본인만·ephemeral, `/비틱`·`/캐릭터목록` 계열) vs (b) **비교 명령**(등록자 대상 집합, `/스타포스` 계열). 숙제 현황은 본인 관심사+응답이 커서 (a)가 자연스러우나, "길드원 숙제 비교"는 (b). |
| 2 | **명령 이름** | `/스케줄러`·`/숙제`·`/보스숙제` 등. 도메인 용어 정합([CONTEXT.md](../CONTEXT.md)) |
| 3 | **캐릭터 범위** | per-character라 핵심. 대표 1명만? 등록 캐릭터 전체(N콜)? 유저가 캐릭터 선택? `character/list`로 계정 전체(79~96명, 과다)에서 고르긴 비현실적 → **등록 캐릭터**로 한정이 유력 |
| 4 | **표시 콘텐츠** | daily/weekly/boss 중 무엇을. `registration_flag=="true"`만? 보스(`complete_flag`)만 vs 전체. 미완료만 vs 전부 |
| 5 | **렌더** | 임베드(진행도 텍스트) vs PIL 이미지(`bot/table_image.py`·`leaderboard_image.py` 계열). 보스=체크리스트, 일일/주간=`now_count/max_count` 게이지 |
| 6 | **realm/모드** | 본서버/챌린저스 분리([ADR-0009](adr/0009-challengers-realm-model.md), `bot/modes.py parse_mode`) 적용 여부 — 응답 `world_name` 있음 |
| 7 | **키 미등록·비대상 UX** | 개인 키 없는 유저, 4xx 떨어지는 캐릭터를 어떻게 안내(이력류 미등록 안내 패턴 재사용) |
| 8 | **쿨다운·스로틀** | 다캐릭터 시 개인 키 throttle 0.2s × N. `bot/cooldowns.py` 정책 정합 |
| 9 | **문서화 수준** | 결정이 비자명하면 ADR(예: "스케줄러 데이터 분류"), 관례적이면 work-order만([[adr-usage-preference]]) |

## 4. 통합 계획 (방향 — 결정 후 확정)

### 4-1. 넥슨 클라이언트 (선행, 결정 무관하게 필요)
- [maple_mate/nexon/client.py](../maple_mate/nexon/client.py) 에 `scheduler_character_state(api_key, ocid, date_iso=None)` 추가.
  **이미 scheduler.md "봇 통합 메모"에 제안 구현 + 실호출 규약 주석이 있다** — 그대로 옮기면 된다(오늘=무지정, 과거=명시, 4xx 흡수).
  `history/*` 메서드들(`starforce_history` 등, client.py 231행~)이 개인 키 오버라이드 레퍼런스.

### 4-2. 키·대상·대표·realm 해석 (재사용할 기존 코드)
- **이력류 비교 골격:** [history/commands.py](../maple_mate/history/commands.py) `handle_starforce`(246행) —
  대상 중 **키 보유자만 필터**(`keyed = [t for t in targets if t.api_key_encrypted is not None]`, 294행),
  `_process_target`(115행)로 per-target 호출, `_report_unmatched`로 누락 안내. (b) 형태면 이 구조 복제.
- **개인 카드 골격:** [maple_mate/bitik/](../maple_mate/bitik/) — 본인 키 1명 카드(ephemeral 목록→공개 카드). (a) 형태면 참고.
- **대표/키/캐릭터:** [registration/service.py](../maple_mate/registration/service.py) — `pick_representative`(263행, realm 인지), `get_characters`(305행), `verify_and_encrypt_key`(93행).
- **키 복호화:** [security/crypto.py](../maple_mate/security/crypto.py) `KeyCipher.decrypt` (deps.cipher로 주입됨, [dependencies.py](../maple_mate/dependencies.py)).
- **realm:** [registration/realm.py](../maple_mate/registration/realm.py)(`in_realm`·`realm_title`), [bot/modes.py](../maple_mate/bot/modes.py)(`parse_mode`).

### 4-3. 신규 모듈 (관례: 도메인별 commands.py + setup(bot), [bot/core.py](../maple_mate/bot/core.py) `_register_commands` 배선)
- `maple_mate/scheduler/__init__.py` + `commands.py`(+ 필요 시 `service.py`). 순수 함수 분리해 오프라인 테스트 가능하게.
- 이미지 렌더 시 `maple_mate/bot/scheduler_*.py` 추가([bot/table_image.py](../maple_mate/bot/table_image.py)·[bot/leaderboard_image.py](../maple_mate/bot/leaderboard_image.py) 패턴).

## 5. 실호출 재검증 레시피 (필요 시)

검증 스크립트는 `/tmp`에 있었고 레포 미커밋(휘발). 재현법:

```
docker exec -i maple-mate-app uv run --no-sync python - < <스크립트>
```
스크립트 골자: `os.environ`의 `DATABASE_URL`/`FERNET_MASTER_KEY`/`NEXON_APP_KEY` →
`create_async_engine` → `Registration.api_key_encrypted is not None` 조회 → `KeyCipher.decrypt` →
`NexonClient._request("maplestory/v1/scheduler/character-state", api_key=키, ocid=…, date=…)`.
**계정 소유 보장 ocid가 필요하면** 같은 키로 `maplestory/v1/character/list`(파라미터 없음) 먼저 호출해
`account_list[].character_list[].ocid`를 얻는다. **복호화 키는 절대 출력 금지(길이만).**

## 6. 비목표 (이번 범위 아님으로 제안 — 그릴링에서 확정)

- 앱 키로 임의 유저 스케줄러 조회(불가 — 계정 스코프).
- 14일 초과·미래 조회, 인게임 스케줄러 수정(읽기 전용 API).
- `character/list` 전체(수백 명) 나열.

## 7. 다음 세션 추천 스킬

1. **`/grill-with-docs`** — §3 열린 결정을 CONTEXT.md·ADR에 비춰 확정(용어·분류 정합까지).
2. **`/oh-my-claudecode:omc-plan`** 또는 **planner** — 확정 결정으로 작업지시서(docs/scheduler-work-order.md) 작성.
3. **`/tdd`** — red-green-refactor로 구현(이 레포 테스트 관례: 오프라인 봇 픽스처, 순수 함수 단위테스트).
4. 코드 후 **code-reviewer** / 머지 전 CI(lint·migrations·test).

## 8. 참조 (중복 금지 — 경로/URL)

- [docs/api/scheduler.md](api/scheduler.md) — **API 스펙·필드·가용성·실호출 회귀의 단일 출처.**
- PR [#28](https://github.com/mindongdong/maple-mate/pull/28) — 문서화 머지(머지 커밋 `3d5a942`).
- [CONTEXT.md](../CONTEXT.md) — 스펙류/이력류 도메인 분류(스케줄러는 이력류 친척으로 편입 검토 대상).
- [docs/exp-leaderboard-work-order.md](exp-leaderboard-work-order.md)·[docs/guide-work-order.md](guide-work-order.md) — 작업지시서 하우스 스타일 레퍼런스.
- 미커밋 더미 주의: `main` 작업트리에 challengers/leaderboard/provider 등 **이전 세션 미커밋 변경**이 남아 있다(이번 기능과 무관, 손대지 말 것).
