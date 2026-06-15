# 결과 문서 (as-built) — 멀티 캐릭터 등록

> 디스코드 유저당 메이플 **캐릭터 N개 등록 + 대표 캐릭터**, **이력류 계정 전체화**.
> 작업지시서 [n-characters-work-order.md](n-characters-work-order.md)(그릴링 12결정) 4단계 수직 슬라이스를 그대로 구현.

- **상태:** 머지 완료 — PR #22, squash `97792f6` → `main` (2026-06-15)
- **검증:** `pytest` 516 passed · `ruff`(E,F,I)+format 클린 · `alembic check` 무드리프트 · 마이그레이션 upgrade/downgrade 가역성 실DB 실증 · CI 3잡(lint·migrations·test) 그린
- **관련:** [ADR-0006](adr/0006-multi-character-data-model.md)(데이터 모델) · [ADR-0007](adr/0007-history-account-wide.md)(이력류 계정 전체화) · [CONTEXT.md](../CONTEXT.md)(등록·캐릭터·대표 용어)

## 무엇이 바뀌었나

`/등록`(닉+키 한 방)을 4개 명령으로 분리하고, 공개/이력 명령의 데이터 범위를 캐릭터 모델에 맞게 재정의했다.

| 구분 | 이전 | 이후 |
|---|---|---|
| 등록 | `/등록 닉네임 [api키]` 1개 | `/캐릭터등록`·`/키등록`·`/대표지정`·`/캐릭터목록` |
| 모델 | `registration` 1테이블(닉·ocid·키 융합), 유저당 1캐릭터 | `registration`(키+대표 포인터) + `character`(N개) 2테이블 |
| 스펙류(`/스펙`·`/아이템`·`/유니온`·`/경험치`) | 등록 캐릭터 1개 | 유저별 **대표 캐릭터** 1명 |
| 이력류(`/스타포스`·`/잠재`) | 등록 닉으로 필터 = 캐릭터 1개 | **계정 전체 합산**(부캐 포함) |
| `/비틱` | 등록 캐릭터 기준 | **대표 기준 유지**(예외) |

## 빌드 단위별 as-built

### Phase 1 — 스키마 + 마이그레이션
- [registration/models.py](../maple_mate/registration/models.py) — `Character` ORM 추가, `Registration`에서 `maple_nickname`·`ocid` 제거 + `representative_ocid`(nullable) 추가.
- [alembic/versions/f3a9c2b81d40_*.py](../maple_mate/alembic/versions/f3a9c2b81d40_multi_character_registration.py) — 단일 리비전: `character` 생성 → 기존 1행 백필(`created_at` 보존) → `representative_ocid` 추가 → 융합 컬럼 제거. 다운그레이드 역방향(N→1 대표 우선 `DISTINCT ON`, 키전용 등록 DELETE).
- **검증:** 로컬 DB(기존 등록 4행)에서 `upgrade head`→백필 확인→2nd 캐릭터+`/대표지정`+키전용 시드→`downgrade -1`(대표우선순위가 레벨200 이김 ✓, 키전용 삭제 ✓, NOT NULL 복원 ✓)→`재upgrade`→`alembic check` 무드리프트. CI `migrations` 잡 그린.

### Phase 2 — 등록/관리 명령
- [registration/service.py](../maple_mate/registration/service.py) — `register`을 `register_character`(ocid 검증→레벨 스냅샷→상한 검사→character upsert+부모 자동 생성)와 `register_key`(검증/암호화→키만 upsert)로 분리. `pick_representative`(순수)·`set_representative`·`get_characters`·`has_personal_key` 신설. 상한 `MAX_CHARACTERS_PER_USER=10`(모듈 상수).
- [registration/commands.py](../maple_mate/registration/commands.py) — `/등록` 제거, 신규 4명령. `/대표지정`은 닉네임 자동완성(본인 캐릭터, 대표 👑 표기). `/캐릭터목록`은 ephemeral(닉·레벨·대표·키 등록 여부).
- **검증:** [tests/test_representative.py](../tests/test_representative.py) 8개(지정 우선·자동 최고레벨·NULL/타이브레이크·빈 목록). `test_cooldowns`에 신규 명령 쿨다운 부착 검증.

### Phase 3 — 공개 명령 대표 배선
- [registration/service.py](../maple_mate/registration/service.py) `get_targets` — `registration`+`character` 조인 후 유저별 `pick_representative`로 `(닉, ocid)` 산출. **단일 출처라 `/스펙`·`/아이템`·`/유니온`(`bot/comparison.resolve_targets` 경유)·`/경험치`(`leaderboard`)가 자동 배선**(`Target` DTO 불변).
- `refresh_ocid` — 스테일 ocid 시 `character.ocid` 갱신 + 옛 ocid를 가리키던 `representative_ocid` 포인터 정합.

### Phase 4 — 이력류 계정 전체화
- [history/service.py](../maple_mate/history/service.py)·[potential_service.py](../maple_mate/history/potential_service.py) — `parse_attempts`·`parse_cube_records`·`parse_reset_records` 닉 필터 제거 + `character_name` 보존. `aggregate_starforce` 그룹 키 `(character_name, target_item)`(동명 장비 병합 버그 차단). `get_history_targets`는 유저별 1대상(대표 닉 라벨 + **캐시 앵커**=`min(created_at)` ocid + 키).
- [history/commands.py](../maple_mate/history/commands.py)·[potential_commands.py](../maple_mate/history/potential_commands.py) — 표 컬럼 "캐릭터"→"대상", "계정 전체 합산(부캐 포함)" 안내 필드.
- [bitik/commands.py](../maple_mate/bitik/commands.py) — `/비틱`은 대표 기준 유지: 계정 전체 결과를 대표 닉으로 필터 + 아이콘/장착레벨은 대표 ocid(캐시 앵커와 분리 해석).
- `/등록` 사용자 문구 전부 `/캐릭터등록`·`/키등록`으로 갱신.

## 작업지시서 대비 구체화 (판단 사항)

- **`Character` 위치** — 별도 `character_models.py` 대신 `registration/models.py`에 `Registration`과 동거(같은 도메인, 파일 작음).
- **상한 상수** — `Config`(env)가 아닌 모듈 상수(환경 무관 고정 규칙).
- **레벨 스냅샷** — `register_character`가 `character_basic` best-effort(실패 시 NULL, 등록 자체는 진행). 대표 타이브레이크가 NULL 흡수.
- **표시 라벨** — 작업지시서 "닉 대신 디스코드 유저/계정 전체 라벨"을 "대상" 컬럼(대표 닉) + "계정 전체 합산" 안내 필드로 구현(범례 닉↔태그 매핑 보존).
- **`/비틱` ocid** — 대표 ocid(아이콘·장착레벨)와 캐시 앵커 ocid(이력 캐시)가 다를 수 있어 둘을 따로 해석(`get_targets` + `get_history_targets`).

## 남은 작업 (운영자)

- [ ] **배포**(Render) 반영 후 운영 글로벌 슬래시 동기화 → 구 `/등록` 소멸 확인(최대 1시간).
- [ ] **라이브 검증:** N개 등록 → `/대표지정` → 스펙/경험치 반영 · 계정 전체 이력 합산(동명 장비 분리) · `/비틱` 대표 기준 유지.

## 한계 (작업지시서에서 수용)

- `/캐릭터삭제` 없음(같은 ocid 재등록=닉/레벨 갱신만) · 레벨 스냅샷 고정(`/대표지정` 보정) · 합산 운지수에 서로 다른 월드/레벨 혼합 · 다른 넥슨 계정 캐릭터 이력 미표시 · 닉 변경 시 과거 `character_name` 불일치(캐시 앵커는 무관).
