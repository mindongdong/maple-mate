# 작업지시서 — `/내캐릭터` (본인 캐릭터 비교: 스펙·아이템·경험치)

> **근거 결정:** ADR-0018(본 작업으로 작성 — §7), realm 판정 [ADR-0009](adr/0009-challengers-realm.md), 리더보드 표시 [ADR-0011](adr/0011-exp-leaderboard-display.md), exp_snapshot PK 확장 전례 ADR-0006→0009.
> **하우스 스타일 레퍼런스:** [starforce-event-luck-work-order.md](starforce-event-luck-work-order.md), [n-characters-work-order.md](n-characters-work-order.md), [exp-leaderboard-work-order.md](exp-leaderboard-work-order.md).
> **그릴링 출처:** `/grill-me` 세션(2026-07-02). 사용자 문제 제기: 비교류 기능이 많은데 같은 디스코드에 친구가 없는 솔로 유저는 쓸 게 없다 → 본인이 등록한 캐릭터(유저당 최대 10개)끼리 비교하게 하자.
> **상태:** 설계 확정 · **미구현**. **PR1(스펙·아이템)은 스키마 무변경**, **PR2(경험치)는 마이그레이션 1건**(exp_snapshot PK 확장).

---

## 0. 한 줄 목표

같은 서버에 비교할 친구가 없는 유저도 쓸 수 있게, **본인이 등록한 캐릭터들끼리 비교하는 통합 명령 `/내캐릭터`**(서브커맨드 `스펙`·`아이템`·`경험치`)를 신설한다. 기존 `/스펙`·`/아이템`·`/경험치`(유저 간 비교)는 **한 줄도 바꾸지 않는다**(회귀 0).

---

## 1. 배경·코드 현황 (다음 세션이 재조사하지 말 것)

- **멀티 캐릭 모델은 이미 있음**: `Character` PK `(guild_id, discord_user_id, ocid)`, 유저당 상한 10([registration/service.py:35](../maple_mate/registration/service.py#L35) `MAX_CHARACTERS_PER_USER`), 컬럼 `maple_nickname`·`level`(등록 시 스냅샷)·`world`(realm 신호). 대표는 `Registration.representative_ocid`(NULL=자동: 최고 등록레벨).
- **비교류 타깃 해석은 전부 "유저당 대표 1명"**: `Target(guild_id, discord_user_id, nickname, ocid, world)` frozen dataclass([registration/service.py:374](../maple_mate/registration/service.py#L374)), `get_targets()`([:397](../maple_mate/registration/service.py#L397)), `resolve_targets()`([bot/comparison.py:124](../maple_mate/bot/comparison.py#L124)). **렌더링은 이미 `Target.nickname` 기준**이라 캐릭터 Target을 넣으면 캐릭 닉이 그대로 라벨이 된다.
- **`/스펙`은 member1 필수(1~5명)**([character/commands.py:332](../maple_mate/character/commands.py#L332)~) — 디스코드 슬래시는 조건부 필수를 표현 못 하므로 기존 명령에 "내캐릭터" 파라미터를 얹으면 member1을 optional로 풀어야 함(기존 동작 변경) → **별도 명령이 근거 있는 결론**(결정 #2).
- **`/경험치`는 DB 스냅샷 기반**: `ExpSnapshot` PK `(guild_id, discord_user_id, snapshot_date, realm)`([leaderboard/models.py:24](../maple_mate/leaderboard/models.py#L24)) — **캐릭터 차원이 없어** 캐릭별 추이는 스키마 확장 필수. 수집 경로 = `ensure_guild_data`([leaderboard/broadcast.py:192](../maple_mate/leaderboard/broadcast.py#L192)) → `get_targets(realm)`(대표만) → `backfill`(멱등, 빠진 날짜만) + `fetch_and_store`(D-1). 소스는 넥슨 **랭킹 API(날짜 지정 가능, 앱 키)**라 과거 백필 가능.
- **`app_commands.Group` 전례 있음**: `/경험치알림 켜기·끄기`([leaderboard/commands.py:104](../maple_mate/leaderboard/commands.py#L104)~136).
- **캐릭터 자동완성 전례 있음**: `/대표지정`의 ocid 자동완성([registration/commands.py:227](../maple_mate/registration/commands.py#L227)).
- **명령 추가 = 문서 동반 필수**: 사이트 드리프트 가드 [tests/test_website_command_drift.py](../tests/test_website_command_drift.py) + [site/scripts/check-command-drift.mjs](../site/scripts/check-command-drift.mjs)가 `site/data/commands.json`↔봇 트리를 비교 — 새 명령을 넣고 사이트를 안 고치면 **CI가 깨진다**. `/가이드`([guide/commands.py](../maple_mate/guide/commands.py))도 갱신 대상.
- **스로틀 전제**: 전역 4req/s(넥슨). `/스펙`의 5명 상한은 렌더 폭+팬아웃 비용 겸용.

---

## 2. 확정 결정 (그릴링 9)

1. **스코프 = 스펙·아이템·경험치 3종.** 유니온은 계정 단위 수치라 캐릭터 비교 무의미 → 제외. 이력류(스타포스·잠재)는 계정 합산 정체성(ADR-0015)과 충돌 → 스코프아웃.
2. **모드 진입 = 별도 명령.** 기존 명령 파라미터 확장 기각(member1 조건부 필수 불가, 무인자 `/스펙`이라는 새 상태가 팬아웃 경계와 충돌).
3. **명명 = 통합 그룹 1개 + 서브커맨드**: `/내캐릭터 스펙` · `/내캐릭터 아이템` · `/내캐릭터 경험치`. (`app_commands.Group(name="내캐릭터")`, 그룹명 미세조정 여지 있음.)
4. **캐릭 선택(스펙·아이템)**: 무인자 = 등록 캐릭 전체, **5개 초과 시 등록 레벨(DB) 상위 5 + "나머지는 캐릭터 파라미터로 지정" 안내 푸터**. `캐릭터1~5` 자동완성 파라미터(선택)로 명시 지정 가능. 경험치는 저비용(DB 조회)이라 **무인자 = 전체 최대 10**(Top10 파이프라인과 정합).
5. **경험치 수집 = 스케줄러 전 캐릭터 확장.** 매일 수집 대상을 대표 → 등록 전 캐릭터로. 온디맨드 백필 단독안 기각(응답 즉시성 우선, 일일 콜 증가 감수).
6. **스키마 = exp_snapshot 단일 테이블 PK에 ocid 추가.** 기존 행은 "그 realm의 현재 대표 ocid"로 백필 마이그레이션. 서버 리더보드는 대표 ocid 행만 조회. 새 테이블 분리안 기각(대표 캐릭 이중 수집 = 같은 사실 소스 2개).
7. **챌린저스 = 혼합, 모드 파라미터 없음.** 본인 캐릭끼리라 realm 공정성 전제가 없음. 챌린저스 캐릭은 **라벨에 월드명 표기**. 특정 realm만 보고 싶으면 캐릭터 지정으로 해결.
8. **출력 = 채널 공개**(기존 비교류와 동일, ephemeral 아님). PNG 첨부와도 궁합.
9. **분할 = 2 PR.** PR1 = `/내캐릭터` 그룹 + 스펙·아이템(스키마 무변경) + 가이드·사이트 갱신. PR2 = 경험치(마이그레이션 + 스케줄러 확장 + 서브커맨드).

**부수 결정(에이전트 판단, 그릴링에서 고지됨):**
- 0캐릭 등록 → "등록된 캐릭터가 없어요. `/캐릭터등록`으로 추가해 주세요" 에러(ephemeral).
- 1캐릭 → 스펙은 기존 단일 상세 임베드 경로, 아이템은 카드 1장, 경험치는 1라인 그래프로 **graceful 동작**(에러 아님).
- 라벨 = 캐릭터 닉(전부 본인이라 유저 멘션·표시명 불필요). 챌린저스 캐릭만 월드 표기.
- 경험치 정렬·표시 = 기존 `_rank_key`(레벨, exp%)·Top10 임베드·그래프 파이프라인 재사용.
- 쿨다운 = 기존 `spec_cooldown` 계열 재사용.

### 비목표
기존 `/스펙`·`/아이템`·`/경험치`·`/유니온` 동작 변경, 이력류(스타포스·잠재) 캐릭터 분리, 매일 10:00 자동 방송의 표시 변경(서버 리더보드 = 대표 기준 유지), 팬아웃 경계 이슈0001(별도 작업지시서), 캐릭터 삭제 명령 신설.

---

## 3. 설계 핵심

### 3-1. 캐릭터 타깃 해석 (신규 헬퍼, PR1)

`registration/service.py`에 추가:

```python
async def get_my_character_targets(
    session_factory, guild_id: int, discord_user_id: int,
    ocids: list[str] | None = None,
) -> list[Target]
```

- 그 유저의 `Character` 전부를 **캐릭터당 Target 1개**로 반환(`nickname=maple_nickname`, `ocid`, `world` 보존). realm 필터 없음(결정 #7).
- 정렬 = 등록 `level` DESC(동률 시 닉 오름차순) — 팬아웃 경계 작업의 "대표레벨 DB정렬" 전례와 동일 원칙.
- `ocids` 지정 시 그 캐릭들만, **입력 순서 보존**(기존 `get_targets`의 user_ids 순서 보존 관행).
- 기존 `Target`을 그대로 재사용하므로 `comparison.table_image_message`·아이템 카드·스펙 fetch 루프가 무수정으로 받는다.

### 3-2. 라벨 규칙

- 기본 = `truncate_display(캐릭닉, 20)` (스펙 표) / 14~20 기존 폭 관행 유지.
- 챌린저스 캐릭(`realm_of(target.world) is CHALLENGERS`, [registration/realm.py:29](../maple_mate/registration/realm.py#L29))만 `닉 (챌린저스N)` 형태로 월드 병기. 순수 헬퍼 `char_label(target) -> str` 하나로 스펙·아이템·경험치 공통화.

### 3-3. exp_snapshot 스키마·마이그레이션 (PR2)

**목표 스키마**: PK `(guild_id, discord_user_id, ocid, snapshot_date)`. `ocid: String` PK 승격, **`realm`은 PK에서 강등해 일반 컬럼으로 존치**(ocid가 행 유일성을 보장하므로 realm은 서버 리더보드 필터용 디스크리미넌트만 남음 — ADR-0009의 "두 realm 대표가 같은 날 공존" 문제를 ocid가 더 정밀하게 해결).

**upgrade 순서**:
1. `ocid` 컬럼 추가(nullable).
2. 백필: 각 `(guild_id, discord_user_id, realm)` 그룹의 기존 행에 **그 realm의 현재 대표 ocid** 주입 — 대표 해석 규칙은 `get_targets`와 동일(수동 `representative_ocid`가 그 realm이면 그것, 아니면 그 realm 최고 등록레벨 캐릭).
3. 대표를 해석할 수 없는 고아 행(등록 해제 유저 등)은 **삭제**(리더보드에 이미 안 잡히는 데이터).
4. `ocid` NOT NULL + PK 재구성 `(guild, user, ocid, date)`.

**downgrade**: PK 원복 `(guild, user, date, realm)` — 같은 키에 여러 캐릭 행이 있으면 **대표 ocid 행 우선, 없으면 `total_exp` 최대 행**만 남기고 삭제 → `ocid` 드랍. **실 DB 가역성 검증 필수**(업→다운→업, 하우스 관행).

### 3-4. 수집·조회 흐름 변화 (PR2)

| 경로 | 현행 | 변경 |
|---|---|---|
| 수집 타깃 | `get_targets(realm)` = 대표만 ([broadcast.py:195](../maple_mate/leaderboard/broadcast.py#L195)) | **`get_all_character_targets(guild_id, realm)`** 신규(등록 전 캐릭, realm 필터는 수집 루프 유지용) |
| `backfill`·`fetch_and_store`·`_upsert_snapshot`·`_existing_dates` | 유저 키 | **ocid 키 추가**(멱등 판정 = 날짜×ocid) |
| 서버 리더보드 `build_payload` | 유저 행 조회 | **대표 ocid 행만** 조회(`get_targets` 대표 목록의 ocid로 필터) — 표시 결과 불변 |
| `/내캐릭터 경험치` | — | 내 캐릭 ocid들 행 조회 + 실행 시 멱등 백필(빈 날짜만) |
| `prune_old_snapshots`(400일) | 무변경 | 무변경(ocid 행에도 동일 적용) |

**API 부하**: 일일 수집이 대표 수 → 등록 캐릭 수(≤10배)로 증가. 랭킹 API 캐릭당 1콜/일 + 신규 캐릭 최초 백필 ≤8콜. 전역 4req/s 스로틀 내 순차 처리로 수집 윈도우가 늘어나는 것을 감수(결정 #5). 방송 잡 시각(10:00 KST) 불변.

---

## 4. 빌드 단위 — PR1 (`/내캐릭터 스펙`·`아이템`, 스키마 무변경)

> 신규 패키지 [maple_mate/mychar/](../maple_mate/mychar/) (commands.py 중심, 파일 작게 유지).

### #1 캐릭터 타깃 헬퍼 — `registration/service.py`
- §3-1 `get_my_character_targets` 추가. 기존 함수 무수정.
- → **verify:** 0캐릭=빈 리스트, 레벨 정렬, ocids 지정 순서 보존, 챌 캐릭 포함(혼합), frozen Target 필드 보존.

### #2 자동완성 공용화 — `registration/commands.py`
- `/대표지정`의 `_representative_autocomplete`([:227](../maple_mate/registration/commands.py#L227)) 로직을 순수 헬퍼로 추출(본인 캐릭 목록 → `Choice(name=f"{닉} (Lv.{level})", value=ocid)`), `/대표지정`과 `/내캐릭터`가 공유. 기존 동작 불변.
- → **verify:** 기존 `/대표지정` 자동완성 테스트 그린 유지 + 공유 헬퍼 단위 테스트.

### #3 명령 그룹 — `mychar/commands.py` (신규)
- `app_commands.Group(name="내캐릭터", description=...)` + 서브커맨드 `스펙`(캐릭터1~5 선택, 자동완성) · `아이템`(부위 필수 — 기존 `/아이템` part choices 재사용 + 캐릭터1~5 선택).
- 흐름: defer → `get_my_character_targets` → 0캐릭 에러 / 5 초과 시 상위 5 절단 + 안내 푸터 → 기존 스펙·아이템의 fetch·렌더 경로 호출 → **공개 발송**.
- `character/commands.py`의 스펙 fetch 루프·`_single_detail_embed`·비교표 빌드·아이템 카드 빌드를 **Target 리스트를 받는 내부 함수로 소폭 추출해 공유**(기존 handle_spec/handle_item은 추출 함수를 호출하는 형태로 동작 불변 리팩터). 1캐릭이면 스펙은 상세 임베드 경로.
- 라벨은 §3-2 `char_label`(챌 캐릭 월드 병기). 쿨다운 `spec_cooldown` 재사용. 부분 실패는 기존 비교류 부분성공 형식 그대로.
- `bot/core.py` setup 체인에 등록.
- → **verify:** 무인자=전체(≤5), 6캐릭 유저 상위5+푸터, 캐릭터 지정 순서 보존, 0캐릭 에러, 1캐릭 상세, 챌 캐릭 라벨 병기, 기존 `/스펙`·`/아이템` 테스트 전량 그린(회귀 0).

### #4 가이드·사이트 동반 갱신
- `/가이드`([guide/commands.py](../maple_mate/guide/commands.py)) 그룹 목록에 `/내캐릭터` 추가(전제조건 라벨: 캐릭터 등록만·키 불필요).
- `site/data/commands.json` + 명령어 페이지 MDX에 `/내캐릭터` 3서브커맨드 추가(경험치는 PR2 머지 전이면 PR2에서 추가 — **드리프트 테스트가 봇 트리와 비교하므로 각 PR에서 그 PR에 든 명령만** 추가).
- → **verify:** `tests/test_website_command_drift.py` + `site/scripts/check-command-drift.mjs` 그린, 사이트 빌드 그린.

---

## 5. 빌드 단위 — PR2 (`/내캐릭터 경험치`, 스키마 확장)

### #1 마이그레이션 — `alembic`
- §3-3 upgrade/downgrade. 배포 전 실 DB(로컬 미러)에서 업→다운→업 가역성 검증.
- → **verify:** 백필 후 기존 리더보드 조회 결과가 마이그레이션 전과 동일(대표 ocid 행), 고아 행 삭제 수 로그.

### #2 모델 — `leaderboard/models.py`
- `ocid` PK 컬럼 추가, `realm` PK 강등(컬럼 존치), 모듈 docstring의 PK 서술 갱신.

### #3 서비스 ocid 차원 — `leaderboard/service.py`
- `_upsert_snapshot`·`_existing_dates`·`fetch_and_store`·`backfill`·`snapshots_on`·`history_progress`·`build_rows`에 ocid 키 반영. 랭킹 API 호출 자체는 ocid 단위라 페치 로직 불변, 저장 키만 확장.
- → **verify:** 기존 `test_leaderboard_service.py` 픽스처를 ocid 포함으로 갱신하되 **대표만 있는 입력에서 결과 불변**(회귀 가드), 같은 유저 2캐릭 같은 날 공존.

### #4 수집 타깃 교체 — `leaderboard/broadcast.py`
- 수집 경로(`ensure_guild_data`·방송 잡의 수집 단계)만 `get_all_character_targets`로 교체. **표시 경로 `build_payload`는 `get_targets`(대표) + 대표 ocid 필터 유지** — 서버 리더보드 표시 불변.
- → **verify:** `test_leaderboard_job.py`·`test_leaderboard_commands.py` 그린, 수집이 전 캐릭 upsert하는 테스트 추가, 방송 임베드 스냅샷 불변.

### #5 서브커맨드 — `mychar/commands.py`
- `/내캐릭터 경험치`: defer → 내 캐릭 멱등 백필(스케줄러가 웜 상태 유지하므로 통상 0~1콜/캐릭, 콜드 시 ≤8콜/캐릭) → 내 ocid들 행으로 `_rank_key` 정렬 Top10 임베드 + 7일 추이 그래프(display_rows·팔레트 10색 재사용) → 공개 발송.
- 혼합 그래프(본+챌 절대레벨 그대로, ADR-0011 절대레벨 원칙과 정합), 챌 캐릭 라벨 월드 병기. 1캐릭=1라인 허용(2명 게이트는 서버 리더보드 전용, 여기 미적용). 데이터 미준비 시 기존 `_MSG_NOT_READY` 톤 재사용.
- 가이드·사이트에 경험치 서브커맨드 추가(드리프트 그린).
- → **verify:** 1캐릭 그래프, 10캐릭 Top10, 혼합 realm 한 그래프, 콜드 백필 멱등(재실행 시 추가 콜 0), 기존 `/경험치` 결과 불변.

---

## 6. 검증 게이트 (머지 조건)

1. 전체 pytest 그린 + `ruff check`(E,F,I)·`ruff format` clean(CI 게이트 그대로).
2. 드리프트 2종(웹사이트·가이드) 그린 — **각 PR에 포함된 명령만** 문서 반영.
3. PR2: 마이그레이션 실 DB 가역성(업→다운→업) 증빙.
4. 기존 명령 회귀 0: `/스펙`·`/아이템`·`/경험치` 테스트 전량 무수정 통과(리팩터로 픽스처 갱신이 필요하면 결과 동일성 명시).
5. 라이브 확인(배포 후): 5캐릭 유저로 `/내캐릭터 스펙` 무인자·지정, 챌 혼합 라벨, `/내캐릭터 경험치` 콜드→웜 2회 실행.

---

## 7. 문서 갱신

- **ADR-0018 신설**(`docs/adr/0018-my-character-solo-comparison.md`): 결정 #2(별도 명령 — member1 조건부 필수 불가 근거), #5·#6(스케줄러 전 캐릭 수집 + 단일 테이블 PK ocid 확장, realm PK 강등 — ADR-0009의 exp_snapshot PK 서술 부분 개정), #7(솔로 모드는 realm 혼합 — "본서버 비교에 챌린저스 불혼입" 불변식은 **유저 간 비교 한정**으로 정밀화).
- CONTEXT.md 용어 추가: "캐릭터 타깃"(유저 타깃과 구분), `/내캐릭터` 명령군.
- 사이트 명령어 페이지 + `/가이드` (§4-#4, §5-#5에 포함).

---

## 8. 리스크·엣지

- **대표 교체 이력**: 마이그레이션 백필이 "현재 대표" ocid를 과거 행에 소급하므로, 과거에 다른 대표였던 기간의 행이 현재 대표 이름표를 달게 됨 — 데이터가 유저 단위였던 이상 불가피한 근사(ADR-0018에 명기). 이후로는 캐릭별로 정확히 쌓임(부수효과: 대표 교체해도 이력 보존).
- **수집 윈도우 증가**: 등록 캐릭이 늘면 10:00 수집이 길어짐. 전역 스로틀이 보호하므로 기능 위험은 없고 지연만 증가. 캐릭 수 급증 시 팬아웃 경계 작업(이슈0001)에서 재론.
- **닉 변경·캐릭 삭제(게임 내)**: 랭킹 API가 ocid 기준이라 닉 변경은 무해(표시 닉은 등록 갱신 시 upsert). 게임에서 삭제된 캐릭은 랭킹 미등재 → 그 날짜 행이 안 쌓일 뿐(기존 대표 미등재 처리와 동일).
- **PR1↔PR2 사이 기간**: `/내캐릭터`에 경험치 서브커맨드가 없는 상태가 잠깐 존재 — 가이드·사이트가 PR별로 정확히 그 시점 명령만 싣도록 드리프트 가드가 강제하므로 문서 불일치 위험 없음.
- **같은 ocid를 두 유저가 등록**: `Character` PK가 유저 포함이라 허용되는 기존 상태. exp_snapshot 새 PK도 유저 포함이라 충돌 없음(수집만 중복 1콜 — 무시).
