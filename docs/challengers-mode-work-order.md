# 작업 지시서 — 챌린저스 서버 모드 (본서버/챌린저스 realm 분리)

> 여름 이벤트로 열린 **챌린저스 서버**(시즌 한정)를 지원한다. 유저는 본서버 캐릭터와
> 챌린저스 캐릭터를 **동시에 등록**해두고, 캐릭터 관련 명령마다 `모드`(본서버/챌린저스)를 골라
> 실행한다. 본서버 캐릭터와 챌린저스 캐릭터는 **절대 같이 비교되지 않는다**.
> 챌린저스 캐릭터를 등록한 유저만 챌린저스 모드를 쓸 수 있다(자동 자격).
> `/grill-me` 10문으로 아래를 확정했다(2026-06-19).

## 핵심 결론

**realm = `world_name` 접두 `챌린저스`. 모드 = 명령별 무상태 파라미터. 분리는 "대상 집합·발송 빌드" 단계에서만, 데이터 적재는 realm 무관.**

라이브 프로브(제공 닉 `힘찬하악질`·`제주도정민규`·`중망레테`, 전부 `챌린저스3`·Lv.260)로 확정한 사실:
- 챌린저스 캐릭터는 **기존 `id`→`character/*` 흐름 그대로** 조회된다. 별도 API 네임스페이스 없음. realm 신호는 `world_name` 의 `챌린저스` 접두뿐.
- `ranking/overall` 은 챌린저스에 대해 **200 + 빈 배열**(에러 아님). 서버가 6/18 신설이라 누적 랭킹 미생성 — 시간이 지나면 채워진다. 도메인의 **"랭킹 미등재"(Not ranked)** 상태로 자연 흡수된다(ADR-0005).
- `history/starforce` 레코드엔 **`world_name` 이 있으나**(`docs/api/history.md:324·422`), `history/cube`·`history/potential` 레코드엔 **없다**. → 이력류 realm 분리는 명령별로 신호가 다르다(비대칭, ADR-0009).
- `user/union` 은 챌린저스에 대해 전부 null → `/유니온` 제외 근거 확인(요청대로 본서버 전용 유지).

## 확정 결정 10건 (그릴링)

| # | 결정 | 비고 |
|---|---|---|
| 1 | **기능 집합 = 유니온만 제외** (경험치 포함) | 챌린저스 빈 랭킹은 "랭킹 미등재"로 흡수, 새 서버라 곧 채워짐. 폴백 불요 |
| 2 | **모드 선택 = 명령별 `모드` 파라미터**(본서버 기본/챌린저스), 무상태 | 공개 게시 봇에서 숨은 토글 사고 회피. 기존 무상태 철학 유지 |
| 3 | **realm 저장 = `Character.world` 원본 컬럼** + 술어 `startswith("챌린저스")` | NULL=본서버(레거시). `챌린저스N` 전부 한 realm. 무거운 백필 불요 |
| 4 | **대표 = 단일 포인터 + realm 인지 해석** | 수동 핀은 가리키는 캐릭터의 realm에서만 효력, 반대 realm은 자동. 스키마 무변경 |
| 5 | **비교 대상 = `get_targets` realm 필터** | 본서버 모드는 챌린저스 캐릭터 제외(누수 0). `/스펙` @대상 미보유 = 부분성공 |
| 5b | **`/스펙` 대상 필수 유지** (모드 파라미터만 추가) | 무인자화(상위 K 컷)는 ADR-0008(fanout) 별건으로 분리 |
| 6 | **이력류 분리 비대칭** — `/스타포스`=`world_name` 정밀 · `/잠재`=등록 닉맵 · `/비틱`=챌 대표 | 미등록 챌린저스 부캐의 *잠재* 공백 수용(world_name 부재). 실전 무영향 |
| 7 | **등록 = `world_name` 자동 판별**, 신규 명령 없음 | `/캐릭터목록` realm 표시. 챌린저스 모드 자격 자동 충족 |
| 8 | **리더보드 = 길드당 2개 완전 분리**, 각 `MIN_RANKED` 독립 게이트 | 적재는 realm 무관 전원 시도(미등재 스킵). `/경험치알림` **단일 토글**로 양쪽 제어 |
| 9 | **라벨 = `🏆 챌린저스` 프리픽스** | 리더보드 제목 구분, `/비틱` 카드 realm 표기. 본서버 무라벨(회귀 0) |
| 10 | **모드 명령 6개** = `/스펙`·`/아이템`·`/스타포스`·`/잠재`·`/비틱`·`/경험치` | 쿨다운 `(유저,명령)` 공유(모드 미반영). `/유니온` 미부착 |

## 기능별 realm 처리

| 명령 | API 기반 | realm 거름 수단 | 본서버 모드 | 챌린저스 모드 |
|---|---|---|---|---|
| `/스펙` | 공개 ocid | 대표 캐릭터 realm | 본서버 대표(@대상 필수) | 챌린저스 대표(@대상 필수) |
| `/아이템` | 공개 ocid | 대표 캐릭터 realm | 본서버 등록자 | 챌린저스 등록자 |
| `/스타포스` | 개인 키 | **레코드 `world_name`** | `world_name ≠ 챌린저스*` | `world_name = 챌린저스*` |
| `/잠재` | 개인 키 | **등록 `{닉→realm}` 맵** | 챌린저스 닉 외 전부 | 등록된 챌린저스 닉만 |
| `/비틱` | 개인 키 + ocid | 대표 닉 필터(기존) | 본서버 대표 | 챌린저스 대표 |
| `/경험치` | 공개 ocid(`ranking/overall`) | 대표 캐릭터 realm | 본서버 리더보드 | 챌린저스 리더보드 |
| `/유니온` | 공개 ocid | — | **본서버 전용**(모드 미부착) | (불가) |
| `/경험치알림`·`/공지알림`·`/썬데이` | `channel_settings` | — | 무관(채널 단위) | 무관 |
| `/캐릭터등록`·`/키등록`·`/대표지정`·`/캐릭터목록` | — | `world` 저장/표시 | realm 무관(전 캐릭터) | — |

> **누수 방지(요구사항 핵심):** 본서버 모드의 모든 비교·리더보드에서 챌린저스 캐릭터는 일절 안 나온다.
> `/스타포스` 는 `world_name` 으로 정밀 차단, `/잠재` 는 닉맵으로 차단(미상 닉→본서버 기본).

## 참조 (중복 금지 — 경로로 참조)

- [maple_mate/registration/models.py](../maple_mate/registration/models.py) — `Character` 에 `world` 컬럼 추가 대상
- [maple_mate/registration/service.py](../maple_mate/registration/service.py) — `register_character`(world 저장)·`pick_representative`/`get_targets`(realm 인자)·`refresh_ocid`(world 갱신)
- [maple_mate/character/service.py:294](../maple_mate/character/service.py#L294) — 이미 `world=basic.get("world_name")` 읽음(저장만 배선)
- [maple_mate/character/commands.py](../maple_mate/character/commands.py) — `/스펙`·`/아이템` 모드 파라미터 + 라벨
- [maple_mate/history/service.py:177-210·356-373](../maple_mate/history/service.py#L177) — `StarforceAttempt`(world_name 보존)·집계 realm 필터
- [maple_mate/history/commands.py](../maple_mate/history/commands.py) · [potential_commands.py](../maple_mate/history/potential_commands.py) — 모드 파라미터
- [maple_mate/bitik/commands.py](../maple_mate/bitik/commands.py) — 챌린저스 대표 앵커 분기
- [maple_mate/leaderboard/broadcast.py](../maple_mate/leaderboard/broadcast.py) — `build_payload(realm)`·`run_leaderboard_job`(2개 발송)
- [maple_mate/leaderboard/service.py](../maple_mate/leaderboard/service.py) · [commands.py](../maple_mate/leaderboard/commands.py) — realm 스코프 rows·`/경험치` 모드
- [maple_mate/union/commands.py](../maple_mate/union/commands.py) — **무변경**(본서버 전용)
- [maple_mate/guide/commands.py](../maple_mate/guide/commands.py) — 챌린저스 모드 안내 + 드리프트 가드
- [maple_mate/alembic/versions/f3a9c2b81d40_multi_character_registration.py](../maple_mate/alembic/versions/f3a9c2b81d40_multi_character_registration.py) — 리비전 패턴 참조

## 데이터 모델

```
Character (변경)
  + world: Mapped[str | None]   # 등록 시 basic.world_name 스냅샷. NULL=본서버(레거시)
```

- realm 판정 = 순수 술어 `is_challengers(world) -> bool = bool(world) and world.startswith("챌린저스")`.
  공용 헬퍼로 한 곳에 둔다(예: `registration/realm.py` 또는 `character` 모듈).
- 마이그레이션: 단일 리비전, `character.world` nullable 추가(비파괴). 다운그레이드 = 컬럼 drop.
  기존 행 백필 없음(전부 본서버 = NULL 의미). lazy 갱신은 `refresh_ocid`·재등록 시 편승.

## 빌드 단위 (수직 슬라이스 6단계)

### 1단계 — 기반: world 컬럼 + realm 술어
- alembic 리비전(`character.world` nullable). `is_challengers` 술어 + 단위 테스트.
- `register_character` 가 등록 시 `world` 저장(`character/service.py` 이미 읽는 값 배선).
- `/캐릭터목록` 에 realm 표시(예: `힘찬하악질 (Lv.260, 챌린저스3)`).
- **검증:** 마이그레이션 up/down 실DB 가역성. 3개 테스트 닉 등록 → `world` 저장 확인.

### 2단계 — 모드 인프라: 파라미터 + realm 인지 해석
- `모드` 파라미터 공용 정의(choices 본서버/챌린저스, 기본 본서버) + Discord 어댑터 헬퍼.
- `pick_representative`/`get_targets` 에 realm 인자 추가(realm 필터 + realm 내 대표 해석).
- 자격 검증 헬퍼(챌린저스 모드인데 챌린저스 캐릭터 0 → 안내 메시지).
- `🏆 챌린저스` 라벨 헬퍼(제목 프리픽스, 본서버는 무라벨).
- **검증:** `get_targets(realm)` 순수 단위 테스트(본서버는 챌린저스 제외, 챌린저스는 챌린저스만). 대표 realm 인지 해석 테스트.

### 3단계 — 스펙류 모드: `/스펙`·`/아이템`
- 두 명령에 `모드` 파라미터. `/아이템` 무인자 = 해당 realm 등록자. `/스펙` 대상 필수 유지.
- `/스펙` @대상이 해당 realm 캐릭터 미보유 = 부분성공("챌린저스 캐릭터 미등록").
- 챌린저스 모드 출력에 `🏆 챌린저스` 라벨.
- **검증:** 챌린저스 모드 비교가 챌린저스 대표만 잡음. 본서버 모드에 챌린저스 캐릭터 안 섞임.

### 4단계 — 이력류 모드: `/스타포스`·`/잠재`·`/비틱`
- `/스타포스`: 집계 전 레코드 `world_name` 필터(챌린저스/본서버). `StarforceAttempt` 에 `world_name` 보존.
- `/잠재`: 등록 `{닉→realm}` 맵으로 cube/potential 레코드 `character_name` 필터. 미상 닉→본서버.
- `/비틱`: 챌린저스 모드면 챌린저스 대표로 닉 필터 + ocid 아이콘 교체. 카드에 realm 표기.
- 챌린저스 모드 출력에 `🏆 챌린저스` 라벨.
- **검증:** 같은 계정 mixed 이력 픽스처 → 챌린저스 모드가 챌린저스 강화만 합산(스타포스 world_name, 잠재 닉맵). 본서버 모드 회귀 없음.

### 5단계 — 경험치 모드: 리더보드 2개 + `/경험치`
- `build_payload(guild_id, realm)` realm 인자화. realm별 `get_targets`·rows·그래프.
- `run_leaderboard_job`: 길드별 본서버 payload + 챌린저스 payload 둘 다 빌드·발송(각 `MIN_RANKED` 독립 게이트). 적재(`fetch_and_store`)는 realm 무관 전원(미등재 스킵).
- 리더보드 제목 구분(`📈 경험치 리더보드` vs `🏆 챌린저스 경험치 리더보드`).
- `/경험치` 에 `모드` 파라미터. 챌린저스 랭킹 전이면 "아직 챌린저스 랭킹 집계 전" 안내.
- `/경험치알림` 단일 토글로 양쪽 제어(스키마 무변경).
- **검증:** 챌린저스 등재 0명 → 챌린저스 payload None(발송 0). 등재 ≥2 → 발송. 본서버 리더보드 회귀 없음.

### 6단계 — 가이드 + 드리프트 가드
- `/가이드` 에 챌린저스 모드 한 줄 설명 추가.
- 모드 파라미터 추가가 드리프트 가드를 깨면 가드 갱신(`test_guide`).
- **검증:** `test_guide` 그린.

## 플래그된 한계·리스크 (수용 결정됨)

- **미등록 챌린저스 부캐의 잠재 공백:** cube/potential 레코드에 `world_name` 부재 → 등록 안 한 챌린저스 부캐의 *잠재* 는 본서버로 떨어질 수 있다. `/스타포스` 는 `world_name` 으로 정확. 실전(챌린저스 캐릭터를 등록함)에선 무영향. (ADR-0009)
- **닉 변경 스테일:** `/잠재` 닉맵은 과거 `character_name`(구 닉) 불일치 잔류 — 기존 이력류 한계와 동일(CONTEXT.md 플래그).
- **두 realm 동시 수동 핀 불가:** 단일 포인터라 챌린저스 캐릭터 핀 시 본서버 핀 덮어씀(결정 4). 챌린저스 부캐 ≈1개라 실수요 낮음. 필요 시 포인터 2개로 확장.
- **챌린저스 랭킹 생성 대기:** 현재 `ranking/overall` 빈 배열 — 챌린저스 리더보드/`/경험치` 는 등재 ≥2 전까지 빈 상태(에러 아님). 넥슨 생성 즉시 자동 작동.
- **모드 파라미터 전역 노출:** Discord 슬래시 파라미터는 유저별 숨김 불가 → 챌린저스 미보유 유저에게도 보임. 런타임 안내로 처리(결정 7).
- **`/스펙` 무인자화 미포함:** 본서버 무인자 `/스펙` 은 여전히 대상 필수 — ADR-0008(fanout) 범위.

## 산출물 메모

- **ADR-0009** (`docs/adr/0009-challengers-realm-model.md`): realm=`world_name` 접두 모델 + 모드 파라미터 + **이력류 분리 비대칭**(starforce=world_name / 잠재=닉맵)의 증거·결정. fanout ADR-0008 머지 충돌 회피로 0009 채번.
- **CONTEXT.md**: "realm(본서버/챌린저스)"·"모드" 용어 inline 추가, "대상" 항목에 realm 스코프 한 줄, 이력류 분리 비대칭 플래그.
- 테스트 인벤토리: 1단계(마이그레이션·술어·world 저장) / 2단계(get_targets realm·대표 해석) / 3단계(스펙류 realm) / 4단계(이력류 mixed 픽스처) / 5단계(리더보드 2개·게이트) / 6단계(가이드).
