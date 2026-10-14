# 작업지시서 — 계정 캐릭터 가져오기 (`character/list`) (PR3/3)

> **근거 결정:** 개인 키 모델 [ADR-0001](adr/0001-nexon-personal-key-model.md), 멀티 캐릭터 [ADR-0006](adr/0006-multi-character-data-model.md), 유저 설치 DM 워크스페이스 [ADR-0019](adr/0019-user-install-dm-workspace.md). 신규 ADR 없음(§6).
> **하우스 스타일 레퍼런스:** [user-install-work-order.md](user-install-work-order.md)(G0 스파이크 선행 패턴), [my-character-work-order.md](my-character-work-order.md).
> **결정 출처:** 2026-10-12 세션. 사용자 판단: 캐릭터를 하나씩 `/캐릭터등록`하는 온보딩이 번거롭다. 개인 키가 있으면 넥슨 `character/list`로 계정 캐릭터를 한 번에 고를 수 있다.
> **선행 조건:** PR1·PR2 머지 후 착수(코드 의존은 없음 — 순서는 사용자 결정). **G0 스파이크 통과가 구현 착수 조건.**
> **상태:** 미착수. **PR3b로 재정의(2026-10-14):** 진입점은 신규 `/캐릭터가져오기` 대신 `/캐릭터목록` 관리 허브([character-manage-hub-work-order.md](character-manage-hub-work-order.md), PR3a)의 **🔄 계정 동기화** 버튼 + `/키등록` 직후. 범위는 가져오기에 더해 등록 캐릭터 갱신(닉·레벨·월드)·계정 외 캐릭터 정리 제안까지(사용자 결정). 자동(주기) 동기화는 하지 않는다. 본문의 `/캐릭터가져오기` 서술은 착수 시 이 기준으로 고쳐 쓴다.

---

## 0. 한 줄 목표

개인 키가 등록된 유저가 **자기 넥슨 계정의 캐릭터 목록에서 여러 개를 골라 한 번에 등록**하게 한다. 진입점은 둘이다:
- `/키등록` 성공 직후 선택 메뉴
- 신규 `/캐릭터가져오기`

---

## 1. 배경·코드 현황 (재조사하지 말 것)

- **API**: `GET maplestory/v1/character/list`. 파라미터 없음, **키 소유 계정 스코프**.
  - 응답: `account_list[].character_list[]` = `{ocid, character_name, world_name, character_class, character_level}` ([docs/api/character.md](api/character.md) §character/list).
  - 한 넥슨 ID에 메이플 계정이 여럿이면 `account_list`가 복수다.
  - 2024-12 추가, 2025-07 "계정" 그룹 이동(SDK 기준).
- **현재 등록 흐름**: `/캐릭터등록 닉네임` → `register_character`([registration/service.py:138](../maple_mate/registration/service.py#L138)) = `resolve_ocid`(1콜) + `_fetch_level_and_world`(`character/basic` 1콜) + 상한 10 검사 + `Registration` 자동 생성 + `Character` upsert. **`character/list`는 ocid·닉·레벨·월드를 이미 주므로 추가 콜이 0이다.**
- **키 등록**: `handle_key_register`([registration/commands.py:102](../maple_mate/registration/commands.py#L102)). ephemeral 응답이고 `resolve_scope`(길드 or DM 워크스페이스 0)를 쓴다.
- **개인 키 복호 패턴**: `deps.cipher.decrypt(api_key_encrypted)`(예: [scheduler/broadcast.py:70](../maple_mate/scheduler/broadcast.py#L70)). 키 조회는 `resolve_self_characters`([scheduler/service.py:424](../maple_mate/scheduler/service.py#L424))가 참고 구현이다. 개인 키 호출은 `_request(..., api_key=)` → 키별 스로틀 버킷(ADR-0004)을 탄다.
- **Select View 전례**: `BitikSelectView`([bitik/commands.py:234](../maple_mate/bitik/commands.py#L234)) — ephemeral select, 120s, 선택 후 disabled, `origin.edit_original_response`.
- **자동완성 라벨 헬퍼**: `_char_label(nickname, level, world)`([registration/commands.py:25](../maple_mate/registration/commands.py#L25)) — 챌린저스만 월드를 표기한다.
- **realm 자동 판별**: `Character.world` = `world_name` 스냅샷(ADR-0009). list의 `world_name`을 그대로 저장하면 된다.
- **명령 추가 = 사이트 동반 필수**: 드리프트 가드가 `site/data/commands.json`↔봇 트리를 비교하므로 신규 명령을 넣고 사이트를 안 고치면 CI가 깨진다. 공개/비공개 매핑 `_EXPECTED_VISIBILITY`([tests/test_website_command_drift.py](../tests/test_website_command_drift.py))에도 추가해야 한다.

---

## 2. 확정 결정

1. **진입점 2개**:
   - (a) `/키등록` 성공 시 같은 ephemeral 응답에 가져오기 선택 메뉴를 바로 붙인다(list 1콜). 실패하면 키 등록 성공 메시지 + "`/캐릭터가져오기`로 다시 시도" 안내만 낸다. **키 등록 자체는 성공으로 유지**한다.
   - (b) 신규 `/캐릭터가져오기`(인자 없음, ephemeral): 이미 키가 있는 유저용. 키가 없으면 "먼저 `/키등록`" 안내.
2. **선택 UI = 다중 선택 Select 1개.**
   - 옵션 = 계정 캐릭터 중 **이 스코프에 미등록**인 것, 레벨 내림차순 **상위 25개**(디스코드 상한).
   - `max_values = min(남은 슬롯(10 − 등록 수), 옵션 수)`.
   - 남은 슬롯이 0이면 메뉴 없이 "이미 10개 등록" 안내. 미등록 후보가 0이면 "계정 캐릭터가 모두 등록돼 있어요".
   - 25개 초과 계정이면 메뉴 위에 "레벨 상위 25개만 표시 — 그 외는 `/캐릭터등록`" 한 줄.
3. **옵션 라벨** = `_char_label` 재사용 + `description=직업`. value = ocid.
4. **등록 = 추가 넥슨 콜 0.** list의 닉·레벨·월드로 upsert한다. 선택 값은 **View가 보관한 후보 dict로만 매핑**한다(클라이언트 값 무신뢰).
5. **대표**: 자동 규칙을 유지한다(`representative_ocid` 미변경 → 최고 레벨 자동). 결과 메시지에 기존 `/캐릭터등록`과 같은 대표 안내를 붙인다.
6. **스코프**: 길드·DM 워크스페이스 모두 개방(`/캐릭터등록`과 동일 `allowed_installs(guilds=True, users=True)`·`allowed_contexts(guilds, dms)`). 응답은 항상 ephemeral이다.
7. **timeout 120s**(Bitik 전례). 선택 1회 후 disabled. 만료 시 disabled.
8. **에러 분류**:
   - 키 무효(`AUTH_INVALID`) → "키가 무효예요. `/키등록`으로 다시 등록해 주세요."
   - 넥슨 장애 → 재시도 안내
   - 빈 목록 → "계정에 캐릭터가 없어요". error_log는 남기지 않는다. 개인 키 오류는 운영 요약 제외 철학을 따른다(CONTEXT "운영 요약").

### 비목표
- 자동 동기화(주기적 재가져오기)
- 등록 캐릭터 삭제
- 25개 초과 페이지네이션
- `user/achievement` 등 다른 계정 API
- 대표 자동 변경

---

## 3. G0 스파이크 (구현 전, `scripts/spike_character_list.py`)

실제 개인 키 1개로 다음을 확인하고 결과를 본 문서 §7에 기록한다. **하나라도 실패하면 결정을 재검토한 뒤 착수**한다.

1. 개인 키로 200 응답이 오는가(앱 키·개발 단계 키 차이 포함).
2. 응답 스키마가 §1과 일치하는가(필드명·`account_list` 복수 여부).
3. **list의 `ocid` == 앱 키 `/id?character_name=` 의 ocid**인가. 이게 다르면 저장 ocid가 스펙류 조회에 못 쓰인다 → 치명적.
4. `character_level`의 신선도(실시간 vs D-1) — 등록 스냅샷 용도라 D-1도 허용한다.
5. 챌린저스·저레벨·삭제 대기 캐릭터 포함 여부, 캐릭터 수가 많은 계정의 응답 시간.

---

## 4. 설계 핵심

### 4-1. 클라이언트 (`nexon/client.py`)

```python
async def character_list(self, api_key: str) -> list[dict]:
    """개인 키 계정의 전체 캐릭터(account_list 평탄화). 키 무효면 NexonAPIError(AUTH_INVALID)."""
```

### 4-2. 서비스 (`registration/service.py`)

```python
@dataclass(frozen=True)
class AccountCharacter:
    ocid: str; nickname: str; world: str | None; job: str | None; level: int | None

def import_candidates(account: list[AccountCharacter], registered_ocids: set[str], limit: int = 25
) -> tuple[list[AccountCharacter], int]:   # 순수: 미등록·레벨 DESC·상위 limit, (후보, 전체 미등록 수)

async def list_account_characters(*, nexon, cipher, session_factory, guild_id, discord_user_id
) -> tuple[list[AccountCharacter] | None, str | None]:  # 키 없음/무효/장애 → (None, 사용자메시지)

async def register_characters(*, session_factory, guild_id, discord_user_id, picks: list[AccountCharacter]
) -> CharacterRegisterResult:   # 일괄 upsert, 상한 재검사(동시 등록 경합), 넥슨 콜 0
```

- `register_character`의 DB 블록(부모 자동 생성 + upsert + 상한)을 `_upsert_characters(session, ...)`로 추출해 단건·일괄이 공유한다(동작 불변 리팩터).
- 상한은 **커밋 직전 재검사**한다. 메뉴를 띄운 뒤 다른 경로로 등록돼 슬롯이 줄었으면 앞에서부터 남은 슬롯만큼 넣고 나머지 개수를 결과에 알린다.
- `CharacterRegisterResult`에 `added: int`, `skipped: int`를 추가한다(기본 0 — 단건 경로 무영향).

### 4-3. 전달 (`registration/commands.py`)

- `AccountImportView(discord.ui.View)`: 다중 Select. 콜백 → `register_characters` → `origin.edit_original_response(embed=결과, view=disabled)`. 실행자 1인 전용이고, ephemeral이라 타인 접근은 구조적으로 불가하다.
- 공용 `async def send_import_menu(deps, interaction, scope, *, header_lines)`: `/키등록` 성공과 `/캐릭터가져오기`가 공유한다. 후보 조회·빈/만석 분기·View 발송을 담당한다.
- `/키등록`: 성공 임베드 본문 + `send_import_menu` 결과를 **한 메시지**로 보낸다(followup 1회). list 실패 시 안내 줄로 대체한다.
- `/캐릭터가져오기`: `settings_cooldown()`, defer ephemeral, `resolve_scope` 가드.

---

## 5. 빌드 단위·테스트

| # | 작업 | 검증 |
|---|---|---|
| 0 | G0 스파이크 + §7 기록 | 5항목 결과 |
| 1 | `NexonClient.character_list` | httpx MockTransport: 평탄화(계정 2개), 개인 키 헤더, AUTH_INVALID raise |
| 2 | `_upsert_characters` 추출(동작 불변) | 기존 `test_registration_service` 그린 |
| 3 | `import_candidates` | 순수: 등록분 제외·레벨 DESC·None 레벨 후순위·25 절단·전체 수 |
| 4 | `list_account_characters` | 키 없음/무효/장애/빈 목록 메시지 분기 |
| 5 | `register_characters` | DB: 일괄 추가·기존 ocid upsert·상한 재검사 부분 추가(`skipped`)·Registration 자동 생성 |
| 6 | `AccountImportView` + `send_import_menu` | 가짜 Interaction: max_values 계산, 만석·빈 후보 분기, 선택 → 서비스 호출 인자(보관 dict 매핑) |
| 7 | `/키등록` 연결(list 실패해도 키 성공 유지) | 핸들러 테스트 |
| 8 | `/캐릭터가져오기` 명령 | 핸들러 테스트 + DM 워크스페이스 scope 0 |
| 9 | 사이트: `commands.json` 등록 그룹에 `캐릭터가져오기` 카드, `/키등록` summary에 가져오기 언급 / `_EXPECTED_VISIBILITY["캐릭터가져오기"] = "private"` | `uv run pytest tests/test_website_command_drift.py` |

공통 게이트: `uv run pytest` · `uv run ruff check . && uv run ruff format --check .`

---

## 6. 기록·배포

- **ADR 신규 없음**: ADR-0001(개인 키) 범위 안의 활용 확장이다. 구조 결정이 아니다. ADR-0001에 "개인 키 용도: 이력류 + 계정 캐릭터 가져오기" 개정 노트 한 줄을 추가한다.
- **CONTEXT.md**:
  - "이력류" 옆에 **계정 캐릭터 목록(Account character list)** 용어를 신설한다. 개인 키 스코프이고 등록 보조 전용이며 비교 데이터가 아니다.
  - "등록" 정의에 `/캐릭터가져오기` 경로를 추가한다.
- PR 1개(봇 + 사이트 동시 — 드리프트 가드 때문에 분리 불가). 머지 = Render 자동배포.
- 라이브 확인:
  - 새 키 등록 → 메뉴 → 3개 선택 → `/캐릭터목록` 반영
  - 만석 유저 `/캐릭터가져오기` → 안내
  - DM 워크스페이스에서 동일 흐름

---

## 7. G0 스파이크 결과

_(착수 시 기록)_
