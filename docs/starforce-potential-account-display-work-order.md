# 작업지시서 — `/스타포스`·`/잠재` 계정 정체성 표시 + 모드 제거 + 잠재/에디 등업 분리

> **근거 결정:** [ADR-0015](adr/0015-history-account-identity-display.md)(6건 확정). 관련 [ADR-0007](adr/0007-history-account-wide.md)(계정 전체 합산), [ADR-0009](adr/0009-challengers-realm-model.md)(모드·realm — 본 작업이 두 명령에 한해 결정 2·4 되돌림), [CONTEXT.md](../CONTEXT.md)(이력류·등업·모드 용어).
> **하우스 스타일 레퍼런스:** [history/commands.py](../maple_mate/history/commands.py)·[potential_commands.py](../maple_mate/history/potential_commands.py)(대상 모델·표 빌드), [bot/comparison.py](../maple_mate/bot/comparison.py)(공유 범례/실패 헬퍼 — **무변경**), [bitik/service.py](../maple_mate/bitik/service.py)(`_kind_of` 종류 판정 — 단일 출처화 대상).

## 0. 한 줄 목표

`/스타포스`·`/잠재`를 **"캐릭터 비교"가 아니라 "디스코드 유저(계정) 비교"**로 정렬한다 — ① 표·범례·실패줄의 **캐릭터 닉 → 디스코드 유저(서버 표시명)**, ② **모드(realm) 파라미터 제거**(본+챌 한 계정 합산), ③ **잠재/에디 등업 분리**(현재 항상 `before_pot`만 봐 에디 오집계). 집계·페치 로직(운빨·메소·큐브)은 불변, **정체성 표시 + 등업 종류 분리**만 더한다.

## 1. 확정 제약 (ADR-0015)

- **다인 비교 유지.** 행 = 디스코드 유저 1명(전원 또는 지정 멤버). 라벨만 계정화, 비교 자체는 그대로.
- **캐릭터 닉 0 노출.** 표 `대상`=서버 표시명, 범례=`표시명 @멘션`, 실패줄=표시명. **공유 헬퍼(`owner_legend`·`_failure_lines`) 무변경** — `Target.nickname`에 표시명 주입으로 자동 반영(스펙·아이템 등 무영향).
- **members 인텐트 필수.** `Intents.members=True` + 개발자 포털 토글. 서버 이탈 유저(`get_member=None`)는 **전원 조회 결과 제외**.
- **모드 완전 제거.** realm 필터·orphan 헬퍼·🏆 프리픽스 삭제. 본+챌 합산.
- **등업 종류 분리 정정.** `_kind_of`로 가르고 에디=`before_add`·잠재=`before_pot`에서 from-등급 → 2버킷. 표 2컬럼 + 보조 2줄.

## 2. 빌드 단위

### #1 종류 판정 단일 출처화 — `history/potential_service.py` (+ `bitik/service.py`)
- `bitik/service.py`의 `_kind_of(record)`·`POTENTIAL_KIND`·`ADDITIONAL_KIND`를 **`potential_service.py`로 이관**(이력류 도메인의 자연 거처). `bitik`은 import로 전환(중복 제거, 동작 불변).
- → **verify:** 큐브(에디 cube_type)·메소 재설정(`potential_type="에디셔널 잠재능력"`)이 각각 `ADDITIONAL_KIND`로, 일반은 `POTENTIAL_KIND`로 판정되는 단위테스트.

### #2 등업 종류 분리 집계 — `history/potential_service.py` `aggregate_potential` (순수)
- `PotentialSummary`: `tierups`/`tierup_total` → **`tierups_pot: tuple[(grade,int),...]`·`tierups_add: tuple[(grade,int),...]`** 로 교체(각 from-등급 오름차순, 0건 제외). 합계가 필요하면 property로.
- 집계 루프: 레코드별 `_kind_of` → 에디면 `_tierup_from(rec.result, rec.before_add)`, 잠재면 `_tierup_from(rec.result, rec.before_pot)`. `_tierup_from`은 before 배열을 인자로 받게(현재 `before_pot` 고정) 일반화.
- 기존 `by_grade`(등급별 재설정, 잠재/에디 각 카운트)·메소·큐브 집계는 **불변**.
- → **verify:** ① 에디 큐브 성공 → `tierups_add`에 카운트·`tierups_pot` 불변(현재 버그=잠재로 샘) ② 잠재 메소 재설정 성공 → `tierups_pot` ③ 레전드리 from·실패는 양쪽 제외 ④ 혼합 입력 2버킷 동시.

### #3 잠재 표 2컬럼 + 보조 2줄 — `history/potential_commands.py`
- `_upgrade_cell` → 종류별 셀 2개(`_upgrade_cell_pot`·`_upgrade_cell_add` 또는 `(tierups, )→GradeBadges` 헬퍼 1개 재사용). 도달등급 매핑(`_TIERUP_TO`)·`GradeBadges`·`—` 폴백 그대로.
- `headers`: `… "사용 메소", "잠재 등업", "에디 등업"` (기존 `"등업"` 자리). `aligns`에 `"left"` 1개 추가.
- `_aux_fields` `⬆️ 등업 진행`: `summary.tierups_pot`→`잠재: …`, `tierups_add`→`에디: …` 두 줄(빈 종류는 줄 생략). from→to 화살표·`nxt` 매핑 재사용.
- → **verify:** 표 2컬럼 렌더(에디 0건=`—`)·보조 2줄(`test_potential_command.py`·`test_potential_aggregate.py`).

### #4 명령 계층 정체성 주입 + 모드 제거 — `history/commands.py`·`potential_commands.py`
- **표시명 해석:** `handle_starforce`/`handle_potential`에서 `interaction.guild.get_member(uid).display_name` 맵 구성. **이탈(None) keyed 대상은 제외**(전원 조회). 명시 지정 멤버는 이미 `Member`라 항상 해석.
- **주입:** 행 라벨·범례 `Target`·`no_key`/`failures`/`missing` outcome의 `nickname`에 **표시명** 주입(`_to_spec_target`가 메이플 닉을 넣던 자리). `missing`은 이미 `m.display_name` 사용 중(불변).
- **표 `대상` 헤더 주석:** "대표 닉" → "디스코드 유저(서버 표시명)".
- **모드 제거:** `mode` param·`@choices(mode=…)`·`@rename(mode=…)`·`@describe(mode=…)`·`parse_mode`·`MODE_CHOICES`/`MODE_DESCRIBE` import·`realm` 인자(`handle_*`/`_process_target`/`_build_table`) 전부 제거. `realm_title(...)` → 평문 제목(`"스타포스 운빨 비교"`·`"잠재 메소·큐브 비교"`·전체실패 `"스타포스 운지수 비교"`·`"잠재 큐브·등업 비교"`).
- **realm 필터 제거:** starforce `attempts_in_realm(...)` 호출·potential `records_in_realm(...)`·`realm_by_nick`/`get_realm_by_nickname` 로드 삭제.
- → **verify:** 표/범례/실패에 캐릭터 닉 부재·표시명 존재, 이탈 유저 제외, 모드 인자 없음(`test_starforce_command.py`·`test_potential_command.py`).

### #5 orphan 코드·인텐트·문서 정리
- **삭제:** `service.py` `attempts_in_realm`, `potential_service.py` `records_in_realm`, `registration/service.py` `get_realm_by_nickname`(타 호출처 0 재확인). `tests/test_history_realm.py` 삭제(전부 이 둘 전용).
- **인텐트:** [bot/core.py](../maple_mate/bot/core.py) `intents = discord.Intents.default()` → `intents.members = True`. ⚠️ **배포 전 Discord 개발자 포털 Server Members Intent 토글**(운영 체크리스트에 1줄 추가).
- **CONTEXT.md 갱신:** 모드 명령 6→4개(`/스펙`·`/아이템`·`/비틱`·`/경험치`), 이력류 표시 라벨(캐릭터 닉→디스코드 유저), 등업(잠재/에디 분리·종류별 from-등급), realm 분리 비대칭 표(`/스타포스`·`/잠재` 행 제거, `/비틱`만 잔존).
- **ADR-0009:** 결정 2·4에 "`/스타포스`·`/잠재`는 ADR-0015로 모드·realm 분리 제거" 포인터(완료).
- 전체 `pytest -q` 그린 + `ruff check` clean.

## 3. 동작 규약

| 표면 | 변경 전 | 변경 후 |
|---|---|---|
| 행 라벨(표) | 대표 캐릭터 닉 | 디스코드 **서버 표시명** |
| 임베드 범례 | `캐릭터닉 @멘션` | `표시명 @멘션` |
| 실패줄 | `**캐릭터닉** — 사유` | `**표시명** — 사유` |
| 모드 파라미터 | 본서버/챌린저스 | **없음**(본+챌 합산) |
| 잠재 등업 컬럼 | `등업`(잠재만, 에디 오집계) | `잠재 등업` + `에디 등업` |
| 보조 `등업 진행` | 1줄(before_pot만) | `잠재:`/`에디:` 2줄 |

## 4. 극단·실패 UX

| 상황 | 처리 |
|---|---|
| 전원 조회 시 이탈 유저 | 결과 제외(표·범례·실패 모두 미표시) |
| 표시명 미해석(인텐트 OK인데 None) | 이탈로 간주 → 제외 |
| 지정 멤버가 이탈 | `Member` 객체가 없어 애초에 지정 불가(N/A) |
| 에디 등업 0건 | `에디 등업` 셀 `—`, 보조 `에디:` 줄 생략 |
| 키 미등록·기록 없음·미등록 멤버 | 기존 분기·문구 불변(표시명만 교체) |

## 5. 테스트 전략 (오프라인)

- `test_potential_aggregate.py` +: 종류 분리 등업(에디 큐브→`tierups_add`, 잠재→`tierups_pot`, 혼합, 레전드리/실패 제외), `PotentialSummary` 필드 교체 반영.
- `test_potential_command.py` +: 표 `잠재 등업`/`에디 등업` 2컬럼·`—` 폴백, 보조 2줄, 모드 인자 제거, 표시명 라벨(get_member monkeypatch), 이탈 제외.
- `test_starforce_command.py` +: 모드 인자 제거, 표시명 라벨, 이탈 제외.
- `tests/test_history_realm.py` **삭제**. `_kind_of` 이관 후 bitik 테스트 그린 확인.
- 라이브(머지 전 1회): 에디 큐브 이력 있는 키로 `/잠재` 단일·다인 → `에디 등업` 채워짐·캐릭터명 0·본+챌 합산. `/스타포스` 동일 점검.

## 6. 커밋 전략 (레포 고유 — 필독)

작업 트리에 **무관한 미커밋/언트랙 변경 잔존**(README·railway.json·기댓값/·docs/adr·runbook 등). 절대 함께 스테이징 금지.
1. `origin/main` 기준 신규 브랜치 `feat/history-account-display`.
2. **이번 작업 파일만 외과적 스테이징** — `history/service.py`·`potential_service.py`·`commands.py`·`potential_commands.py`·`bitik/service.py`·`registration/service.py`·`bot/core.py`·`tests/test_potential_*.py`·`test_starforce_command.py`·(삭제)`test_history_realm.py`·`docs/adr/0015-*`·`docs/adr/0009-*`(포인터)·`CONTEXT.md`·본 작업지시서.
3. 논리 단위 커밋(종류판정 이관+등업집계 / 표·보조 / 명령계층+모드제거+orphan / 인텐트+문서) → push → squash PR.
4. CI(lint/test/migrations 가역성) 그린 후 머지. **머지 후 운영자: 개발자 포털 members 인텐트 토글 + 재배포.**

## 7. 비목표

- 본인 단일 계정 전용 명령화(기각 — 비교 유지, ADR-0015 결정 1).
- 표시명 DB 저장/캐싱·`fetch_member`(기각 — 라이브 `get_member` + 인텐트).
- `/비틱` realm·대표 닉 동작 변경(범위 밖 — 비틱은 대표 자랑 성격 유지).
- 운빨·메소·큐브 집계 로직 변경(불변 — 표시·등업 종류만).
- 마이그레이션(없음 — 스키마 무변경).
