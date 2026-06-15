# 작업 지시서 — 멀티 캐릭터 등록 (유저당 N개 + 대표 캐릭터)

> 디스코드 유저당 **메이플 캐릭터 N개 등록**을 지원한다.
> 기존 `/등록`(닉+키 한 방)을 **`/캐릭터등록`(캐릭터)** 과 **`/키등록`(개인 API 키)** 으로 분리하고,
> 공개 ocid 기반 명령(`/스펙`·`/아이템`·`/유니온`·`/경험치`)은 유저별 **대표 캐릭터** 기준으로 표시한다.
> 개인 키 기반 이력류(`/스타포스`·`/잠재`)는 키가 본래 반환하는 **계정 전체**로 확장한다.
> 그릴링(`/grill-me`) 12문으로 아래를 확정했다.

## 핵심 결론

**대표 캐릭터 = 공개 ocid 명령을 지배 / 개인 키 = 계정 전체 명령을 지배.**
사용자 추측("개인 키 기반 기능은 계정 전체 데이터")은 **정확했다** — 넥슨 history API는 키로 계정의 모든 캐릭터를 반환하나, 현재 코드가 등록 닉 1개로 **되돌려 필터**하고 있었다([history/service.py:165-188](../maple_mate/history/service.py#L165-L188)). 이번에 그 필터를 푼다.

## 확정 결정 12건 (그릴링)

| # | 결정 | 비고 |
|---|---|---|
| 1 | **키 = 유저당 1개** (같은 넥슨 계정 가정), 전 캐릭터 공유 | 다른 계정 캐릭터는 이력 미표시 → 안내 메시지 |
| 2 | **스키마 = 2테이블 + 포인터** | `registration`(키 + `representative_ocid`) / `character`(N개) |
| 3 | **범위 = 서버(길드)별 유지** | `(guild_id, discord_user_id)` 경계 보존 |
| 4 | **마이그레이션 = 단일 리비전, 제자리 변환 + 백필** | 비파괴, 다운그레이드 역방향 |
| 5 | **레벨 = 등록 시 스냅샷만** | 자동 대표 = 저장 레벨 최고값(읽기 시 정렬). 스테일 시 `/대표지정` |
| 6 | **대표 명령 = `/대표지정` + 닉네임 자동완성** | 본인 캐릭터만 드롭다운 |
| 7 | **`/등록` 제거**, `/캐릭터등록` + `/키등록` 완전 분리 | |
| 8 | **보조 명령 = `/캐릭터목록`만** | 삭제·키삭제 제외(아래 한계 참조) |
| 9 | **상한 = 유저당 10개** | config 상수 |
| 10 | **이력류 = 계정 전체 합산** | `/스타포스`·`/잠재`만 |
| 11 | **리더보드 = 유저당 대표 1명** | `exp_snapshot` PK 불변 |
| 12 | 본캐끼리 비교 **제외** · 이력 표시 = **합산 통합값만** · `/비틱` **대표 기준 유지** | |

## 기능별 데이터 범위 (요구사항 #2 답변)

| 명령 | API 기반 | 데이터 범위 | N개 캐릭터 시 해석 |
|---|---|---|---|
| `/스펙` | 공개 ocid (`character/*`) | **캐릭터** | 각 멤버 → 대표 |
| `/아이템` | 공개 ocid (`character/item-equipment`) | **캐릭터** | 각 멤버 → 대표 |
| `/유니온` | 공개 ocid (`user/union*`) | **캐릭터**(실질 계정+월드 공유) | 각 멤버 → 대표 |
| `/경험치` | 공개 ocid (`ranking/overall`) | **캐릭터** | 유저당 대표 1명 |
| `/스타포스` | 개인 키 (`history/starforce`) | **계정** | 계정 전체 합산 |
| `/잠재` | 개인 키 (`history/cube`·`potential`) | **계정** | 계정 전체 합산 |
| `/비틱` 스타포스·잠재 | 개인 키 + ocid(아이콘) | 계정 API지만 **대표 필터** | 대표 기준(예외) |
| `/비틱` 득템 | 없음(이미지) | self | 무관 |
| `/경험치알림`·`/썬데이`·`/공지알림` | 없음(`channel_settings`) | **길드/채널** | 무관 |

> `/유니온` 보충: MapleStory 유니온/레기온은 **계정+월드 공유**라 같은 계정/월드의 어느 ocid로 조회해도 동일. 대표 ocid가 올바른 앵커이며, 캐릭터가 여러 월드에 걸칠 때만 차이가 난다.

## 참조 (중복 금지 — 경로로 참조)

- [maple_mate/registration/models.py](../maple_mate/registration/models.py) — `Registration`(현재 닉·ocid·키 융합). 분해 대상
- [maple_mate/registration/service.py](../maple_mate/registration/service.py) — `register`·`get_targets`·`refresh_ocid`·`Target`. 분리/대표 해석 추가
- [maple_mate/registration/commands.py](../maple_mate/registration/commands.py) — `/등록` 어댑터(얇은 전달). 제거 후 신규 4개로 교체
- [maple_mate/history/service.py](../maple_mate/history/service.py) — `get_history_targets`·`parse_attempts`(닉 필터)·`aggregate_starforce`·`_cached_records`(ocid 키). 계정 전체화 핵심
- [maple_mate/leaderboard/service.py](../maple_mate/leaderboard/service.py) · [broadcast.py](../maple_mate/leaderboard/broadcast.py) — 대표 ocid 사용으로 배선
- [maple_mate/character/service.py:283](../maple_mate/character/service.py#L283) — `character_basic(ocid)` → `character_level` (레벨 스냅샷 재사용)
- [maple_mate/bitik/commands.py:178](../maple_mate/bitik/commands.py#L178) — `find_icon_url`·`_fetch_item_icon`·`fetch_equipped_levels(ocid)` (대표 ocid로 앵커 교체)
- [maple_mate/nexon/client.py](../maple_mate/nexon/client.py) — `get_ocid`·`character_basic`·`ranking_overall`·`starforce_history`·`cube_history`·`potential_history`
- [maple_mate/alembic/versions/](../maple_mate/alembic/versions/) — 리비전 패턴(`d247740d0e37_initial_5_tables.py` 참조)

## 현황 진단

**이미 있음 (재사용 — 새로 만들지 말 것):**
- `registration/service.py` — `register(...)`(ocid 검증→키 검증/암호화→upsert), `get_targets(guild_id, user_ids)`→`Target`, `refresh_ocid`(닉변경 lazy 갱신), `Target`/`TargetOutcome`/`fetch_each`(부분 성공 머신).
- `history/service.py` — `get_history_targets`(키 포함 대상), `parse_attempts(records, nickname)`(닉 필터), `aggregate_starforce(attempts, level_of)`(아이템별 시작★→최종★), 날짜별 `_cached_records`/`_store_records`(ocid 키 캐시).
- `nexon/client.py` — `character_basic(ocid)`(레벨 포함), `get_ocid(name)`, `verify_personal_key`, `ranking_overall(ocid, date)`, 이력 3종(api_key).
- `bot/embeds.py` — `defer`·`make_embed`; `cooldowns.settings_cooldown()`(등록류 쿨다운).
- `dependencies.py` — `Deps`(session_factory·nexon·cipher·config). config 상수 추가 지점.

**새로 만듦:**
- `maple_mate/registration/character_models.py`(또는 models.py에 추가) — `Character` ORM(PK `(guild_id, discord_user_id, ocid)`, `maple_nickname`·`level`·timestamps).
- 알렘빅 리비전 1개 — `character` 생성 + 백필 + `registration` 변환.
- 신규 명령 4개 — `/캐릭터등록`·`/키등록`·`/대표지정`(자동완성)·`/캐릭터목록`.

**변경:**
- `Registration` — `maple_nickname`·`ocid` 제거, `representative_ocid`(nullable) 추가, `api_key_encrypted` 잔존.
- `registration/service.py` — `register` 분리, 대표 해석/지정/목록 함수 추가, `get_targets` 대표 기반화.
- `history/service.py` — `parse_attempts` 닉 필터 제거, `aggregate_starforce` `(character_name, target_item)` 그룹핑, 캐시 앵커 ocid.
- `leaderboard`·`bitik` — 대표 ocid/닉 앵커로 배선.

## 데이터 모델

```
registration  (유저/계정 레벨)
  PK (guild_id, discord_user_id)
  api_key_encrypted    String   nullable     ← 유저당 1개 키
  representative_ocid  String   nullable     ← NULL=자동(최고레벨) / 값=수동 지정
  created_at, updated_at

character  (N개)
  PK (guild_id, discord_user_id, ocid)
  maple_nickname  String(64)
  level           Integer  nullable          ← 등록 시 스냅샷
  created_at, updated_at
  (논리적 FK → registration; 부모 행은 캐릭터/키 등록 시 자동 upsert)
```

**대표 해석 규칙** (`resolve_representative`):
1. `representative_ocid`가 set이고 해당 character 존재 → 그 캐릭터.
2. NULL이거나 가리키는 캐릭터 부재 → `level` 최고값(동률·NULL은 `created_at`/`ocid`로 결정적 타이브레이크).
3. character 0개 → None(명령은 "먼저 `/캐릭터등록` 하세요" 안내).

## 빌드 단위 (수직 슬라이스 4단계)

### 1단계 — 기반: 스키마 + 마이그레이션
- `Character` 모델 추가; `Registration`에서 닉·ocid 제거 + `representative_ocid` 추가.
- 알렘빅 1리비전:
  1. `create_table("character", ...)`.
  2. 백필 `op.execute(INSERT INTO character(...) SELECT guild_id, discord_user_id, ocid, maple_nickname, NULL, now(), now() FROM registration)`.
  3. `add_column("registration", representative_ocid)` (NULL 유지 = 자동).
  4. `drop_column("registration", "maple_nickname")` · `drop_column("registration", "ocid")`.
  - downgrade는 역순(컬럼 복원 → 백필 역방향 → character drop).
- **검증:** DB 사본에 `alembic upgrade head` / `downgrade -1`; `alembic check`; 기존 행이 캐릭터 1개 + `representative_ocid` NULL로 백필되어 day-1 동작 동일.

### 2단계 — 등록/관리 명령
- `service.register` 분리:
  - `register_character(...)` — ocid 검증 → `character_basic`로 레벨 스냅샷 → 상한(10) 검사 → ocid 중복=upsert(닉/레벨 갱신) → 부모 registration 자동 생성.
  - `register_key(...)` — `verify_and_encrypt_key` 재사용 → registration upsert(키만).
- 신규: `resolve_representative`, `set_representative(ocid)`, `get_characters(guild_id, user_id)`.
- 명령: `/등록` 제거; `/캐릭터등록`·`/키등록`·`/대표지정`(닉네임 자동완성=본인 캐릭터)·`/캐릭터목록`(ephemeral: 닉·레벨·대표 표시·키 등록 여부).
- **검증:** 단위(상한·중복·대표 해석 순수함수) + 라이브(N개 등록→대표 지정→목록).

### 3단계 — 공개 명령 대표 배선
- `get_targets`(스펙류) — 유저별 `resolve_representative`로 `(nickname, ocid)` 산출. user_ids 없으면 길드 전원 각자 대표.
- `/스펙`·`/아이템`·`/유니온` 비교: 각 멤버 → 대표.
- `/경험치` 일일 잡·온디맨드 부트스트랩 → 유저당 대표 ocid 1개 스냅샷(`exp_snapshot` PK 불변).
- `refresh_ocid` — `character.ocid` 갱신 + `representative_ocid` 포인터·캐시 앵커 정합.
- **검증:** 단일/비교 모두 각 멤버 대표로 표시; 대표 변경 후 반영.

### 4단계 — 이력류 계정 전체화
- `get_history_targets` — 닉 필터 제거; `HistoryTarget`에 키 + **안정적 캐시 앵커 ocid**(최초 등록 ocid = `min(created_at)`).
- `parse_attempts` — 닉 필터 삭제(전체 반환).
- `aggregate_starforce` — **(character_name, target_item)** 그룹핑으로 동명 장비 병합 버그 차단 → 운지수·손익메소 전체 합산.
- 표시: 합산 통합값만; 헤더는 닉 대신 디스코드 유저/"계정 전체" 라벨.
- `/비틱` — 대표 닉 필터 + 대표 ocid 아이콘(현 로직 앵커만 교체, 계정 전체화 아님).
- **검증:** `/스타포스`·`/잠재` 계정 합산(동명 장비 분리 확인); `/비틱` 대표 기준 유지.

## 플래그된 한계·리스크 (수용 결정됨)

- ⚠️ **`/캐릭터삭제` 없음** — 원치 않는 캐릭터 제거 불가. 같은 ocid 재등록=닉/레벨 갱신뿐. (그릴링 8: 보조 명령 `/캐릭터목록`만 선택)
- ⚠️ **레벨 스냅샷 고정** — 레벨업해도 자동 대표 불변 → `/대표지정` 보정. (그릴링 5)
- ⚠️ **합산 운지수** — 서로 다른 월드/레벨 캐릭터가 한 백분위에 혼합. (그릴링 10·12 수용)
- ⚠️ **다른 넥슨 계정 캐릭터** — 키 불일치로 이력 미표시 → 사용자 안내 메시지 필요. (그릴링 1)
- ⚠️ **캐시 앵커** — 앵커 캐릭터 닉변경 시 일시적 재페치 가능.

## 산출물 메모

- ADR·메모리 저장은 이번 그릴링에서 **미선택**(작업지시서만). 1단계 착수 후 '이력류 계정 전체화'·'키=유저당 1개 + 2테이블'이 ADR 승격 후보(비자명·증거기반).
