# 작업지시서 — 스케줄러 숙제 카테고리 필터 (opt-out 4묶음)

> **근거 결정:** [ADR-0014](adr/0014-scheduler-category-filter.md)(7건 확정), 구독 모델 [ADR-0012](adr/0012-scheduler-reminder-per-user-dm.md), 표시 카테고리 [ADR-0013](adr/0013-scheduler-field-derived-categories.md), 용어 [CONTEXT.md](../CONTEXT.md)("숙제 카테고리 필터").
> **하우스 스타일 레퍼런스:** [scheduler-work-order.md](scheduler-work-order.md)(선행 빌드), [modes.py](../maple_mate/bot/modes.py)(공유 Choice 파라미터), [notification/commands.py](../maple_mate/notification/commands.py)(켜기/끄기 Choice).

## 0. 한 줄 목표

`/스케줄러`·스케줄러 알림 DM이 보여주는 숙제를 **사용자 어휘 4묶음(일일·주간·보스·길드)** 으로 묶어, 보고 싶지 않은 묶음을 **끌 수 있게** 한다. 기본은 전부 켜짐(opt-out)이라 **미지정 시 기존과 100% 동일**. 데이터·페치는 불변, **표시 필터만** 더한다.

## 1. 확정 제약 (ADR-0014)

- **4묶음 = 8필드 파생 카테고리의 사용자 묶음.** 일일={일일 퀘스트+일일 콘텐츠}, 주간={주간 퀘스트+주간 콘텐츠}, 보스={일간·주간·월간 + 기타 cycle 폴백}, 길드={길드 콘텐츠}. 묶음 정의는 [ADR-0013](adr/0013-scheduler-field-derived-categories.md) 카테고리/`cycle` 위에 1:N 매핑.
- **opt-out + 무회귀.** 아무 파라미터도 안 적으면 제외집합 비어 8필드 전부 표시(기존 출력 그대로).
- **온디맨드 = 무상태**(저장 read/write 없음, 안 적음=켜기). **알림 = 지속 병합**(미지정=기존 유지, 초기 baseline=전부 켜기).
- **저장 = EXCLUDED 집합**(NULL/빈=제외 없음=전부 표시). enabled 아님 — 하위·상위호환.
- **페치 불변.** 캐릭터별 full state 그대로 페치, 임베드 조립에서만 묶음을 가린다(콜 수·스로틀 동일).

## 2. 빌드 단위

### #1 필터 코어 — 신규 `scheduler/category_filter.py` (순수)
- **묶음 상수:** `BUCKET_DAILY="일일"`, `BUCKET_WEEKLY="주간"`, `BUCKET_BOSS="보스"`, `BUCKET_GUILD="길드"`. `ALL_BUCKETS` 순서 고정(표시 순서와 동일).
- **Choice 정의(공유):** `CATEGORY_ON_OFF = [Choice("켜기","on"), Choice("끄기","off")]`(notification 패턴 재사용). 4묶음 rename/describe 라벨.
- **온디맨드 파싱:** `parse_ondemand(daily, weekly, boss, guild) -> frozenset[str]` — 각 인자(`Choice|None`)가 `off`인 묶음만 제외집합에. `None`/`on` = 표시.
- **알림 병합:** `merge_excluded(stored: frozenset, *, daily, weekly, boss, guild) -> frozenset` — tri-state: `off`→추가, `on`→제거, `None`→유지.
- **직렬화:** `to_csv(frozenset) -> str|None`(빈 집합→None), `from_csv(str|None) -> frozenset`. 미상 토큰은 무시(상위호환).
- **가드:** `is_all_excluded(frozenset) -> bool`(4묶음 전부).
- → **verify:** 매핑·`parse_ondemand`(off만 제외)·`merge_excluded`(3-state)·CSV 라운드트립·all-off 단위테스트.

### #2 임베드 필터 적용 — `scheduler/broadcast.py` + `scheduler/service.py`
- **service(순수) 추가:**
  - `visible_remaining(hw, excluded) -> (done, total)` — `remaining_total`을 보이는 묶음만 집계(보스 제외 시 보스 빠짐, 일일/주간 제외 시 해당 콘텐츠 빠짐, 길드는 원래 집계 제외 유지).
  - `is_empty_filtered(hw, excluded) -> bool` — 보이는 묶음에 항목 0개면 True(`is_empty`의 필터 버전).
- **broadcast 수정:** `build_embed(hw, realm, now, excluded=frozenset())` — 각 `_content_field`/`_guild_field`/`_boss_field` 호출 앞에 `if 묶음 not in excluded` 가드(일일 2필드=일일 묶음, 주간 2필드=주간 묶음, 보스 4필드=보스 묶음, 길드 1필드=길드 묶음). 부제·상태색은 `visible_remaining` 기준.
- → **verify:** 묶음별 제외 시 해당 필드 사라짐·헤드라인 재집계·보스만 표시·all-off=0필드 임베드 테스트(`test_scheduler_embed.py`).

### #3 온디맨드 파라미터 — `scheduler/commands.py`
- `/스케줄러`에 4 파라미터 추가(`@rename` 일일/주간/보스/길드, `@choices` `CATEGORY_ON_OFF`, 각 `Choice|None=None`) + 기존 `모드` 공존. `parse_ondemand`→`excluded`.
- `handle_scheduler`: all-off면 "표시할 카테고리를 최소 하나는 켜주세요" 안내(빌드 전). 캐릭터 루프에서 `is_empty_filtered`로 스킵, `build_embed(..., excluded)`.
- spec_cooldown 불변(페치 동일).

### #4 알림 지속·병합 — `scheduler/models.py` + alembic + service.py + commands.py
- **마이그레이션:** `scheduler_subscription`에 `excluded_categories: Mapped[str|None] = mapped_column(String(64), nullable=True)`. down_revision=현 head(확인 후 기입). 기존 행 NULL=전부 표시(무회귀). **가역성 실DB 검증**(레포 관례).
- **service:**
  - `get_subscription(guild,user,realm) -> Subscription|None`(병합 베이스 읽기, 신규는 None→빈 제외).
  - `set_subscription(..., excluded: frozenset)` — values/`on_conflict_do_update`에 `excluded_categories=to_csv(excluded)` 추가.
  - `Subscription` 데이터클래스 + `subscriptions_at_hour`에 `excluded: frozenset` 필드(`from_csv`).
- **commands `/스케줄러알림 켜기`:** 4 tri-state 파라미터 추가. `get_subscription`로 기존 제외집합 로드→`merge_excluded`→`is_all_excluded`면 거부 안내(저장 안 함)→`set_subscription(excluded)`. **확인 메시지에 결과 필터 표시**(예: "표시: 일일·주간·보스 / 숨김: 길드"). `끄기`는 불변.
- **broadcast `run_scheduler_reminder_job`:** `sub.excluded`를 `build_embed`에 전달, `is_empty_filtered`로 빈 캐릭터 스킵.
- → **verify:** `merge_excluded` 시나리오·CSV 라운드트립 단위테스트. DB 함수는 통합 영역 → 단위테스트 제외(기존 방침), 병합 로직은 순수 헬퍼로 분리해 테스트.

### #5 문서·커밋
- `CONTEXT.md`(완료), `ADR-0014`(완료), `ADR-0012` 개정 포인터(완료). 본 작업지시서 = 빌드 레퍼런스.
- 전체 `pytest -q` 그린 + `ruff check` clean.

## 3. 동작 규약

| 표면 | 파라미터 의미(안 적음) | 상태 |
|---|---|---|
| `/스케줄러` | 켜기(보임) | 무상태 — 매 호출 완전 선언 |
| `/스케줄러알림 켜기` | 기존 유지(None) | 지속 — 제외집합 병합 저장 |

- **헤드라인·상태색:** 보이는 묶음만 재집계(`visible_remaining`). 보스만 켜고 다 잡았으면 `✅ 남은 숙제 0개`+초록.
- **8필드→4묶음:** 일일(2)·주간(2)·보스(4: 주/일/월/기타)·길드(1). 묶음 제외 시 그 묶음 필드 전부 생략.

## 4. 극단·실패 UX

| 상황 | 온디맨드 | 알림 켜기 / cron |
|---|---|---|
| 4묶음 전부 끄기 | "최소 하나는 켜주세요" 안내(빌드 전) | (병합 결과) 거부 — 저장 안 함, 안내 |
| 필터 후 빈 캐릭터 | 그 캐릭터 스킵(`is_empty_filtered`) | 스킵 |
| 필터 후 전 캐릭터 빈 | 기존 "숙제 없어요" 메시지 | DM 0건 |
| 미등록·키없음·realm 0 | 기존 가드 메시지 | 스킵(불변) |

## 5. 테스트 전략 (오프라인)

- `test_scheduler_category_filter.py`(신규): 묶음 매핑, `parse_ondemand`(off만 제외/None·on=표시), `merge_excluded`(tri-state 3케이스 + 초기 baseline), `to_csv`/`from_csv` 라운드트립·미상 토큰 무시, `is_all_excluded`.
- `test_scheduler_service.py` +: `visible_remaining`(묶음별 제외 재집계), `is_empty_filtered`.
- `test_scheduler_embed.py` +: `build_embed(excluded=…)` 묶음별 필드 생략·헤드라인 재집계·보스만·all-off=0필드.
- `test_scheduler_command.py` +: `/스케줄러` 4파라미터 off 반영(monkeypatch build_homeworks), all-off 안내.

## 6. 커밋 전략 (레포 고유 — 필독)

작업 트리에 **무관한 미커밋/언트랙 변경 잔존**(README·railway.json·기댓값/·broadcast/service 미세조정 등). 절대 함께 스테이징 금지.
1. `origin/main` 기준 신규 브랜치 `feat/scheduler-category-filter`.
2. **이번 작업 파일만 외과적 스테이징** — `scheduler/category_filter.py`·`scheduler/broadcast.py`·`scheduler/service.py`·`scheduler/commands.py`·`scheduler/models.py`·신규 alembic 리비전·`tests/test_scheduler_*.py`·`docs/adr/0014-*`·`docs/adr/0012-*`·`CONTEXT.md`·본 작업지시서.
   - ⚠️ broadcast/service에는 **선행 미커밋 가독성 변경**이 섞여 있을 수 있음 — hunk 단위로 이번 변경만 스테이징하거나, 선행 변경을 먼저 분리 커밋.
3. 논리 단위 커밋(코어+임베드 / 명령+마이그레이션 / 문서) → push → squash PR.
4. CI(lint/test/migrations 가역성) 그린 후 머지.

## 7. 비목표

다중선택 select 컴포넌트(기각 — Choice 파라미터로 충분), 온디맨드-알림 선호 공유(기각 — 숨은 토글), 8개 개별 토글(기각 — 4묶음), 페치 비용 절감(필터는 표시 전용), 캐릭터 단위 개별 필터(필터는 호출 전역), 인게임 스케줄러 수정.
