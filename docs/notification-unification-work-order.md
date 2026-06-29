# 작업지시서 — 정기 알림 통일 + 개인 DM 구독 + 스케줄러 realm 제거 (+ 비틱 숨김)

> **근거 결정:** [ADR-0017](adr/0017-notification-unification-and-dm-subscription.md)(8건 확정). 개정: [ADR-0012](adr/0012-scheduler-reminder-per-user-dm.md)(realm 제거), [ADR-0009](adr/0009-challengers-realm-model.md)(스케줄러 알림 한정 realm 분리 폐기). 유지: [ADR-0014](adr/0014-scheduler-category-filter.md)(카테고리 필터). 용어: [CONTEXT.md](../CONTEXT.md).
> **하우스 스타일 레퍼런스:** [scheduler-category-filter-work-order.md](scheduler-category-filter-work-order.md), [notification/commands.py](../maple_mate/notification/commands.py)(켜기/끄기 Choice), [scheduler/commands.py](../maple_mate/scheduler/commands.py)(그룹 켜기/끄기), [leaderboard/broadcast.py](../maple_mate/leaderboard/broadcast.py)(양 realm 발송 패턴).

## 0. 한 줄 목표

정기 알림 4종을 **`/X알림 켜기·끄기` 그룹**으로 통일하고, **권한 없이** 토글하게 하고, 경험치·공지·썬데이에 **개인 DM 구독**(채널 발송과 병행)을 더한다. 스케줄러알림은 **realm 분리를 없애** 한 번 켜면 **등록 캐릭터 전부**에 캐릭터당 DM을 보낸다. 더불어 효용 낮은 `/비틱`을 봇에서 **숨긴다**(코드 보존).

## 1. 확정 제약 (ADR-0017)

- **표면:** 4종 전부 `켜기`/`끄기` 서브커맨드 그룹. 평면 `상태` 인자 폐기. **썬데이 → 썬데이알림** 개명.
- **권한:** 모든 토글 권한 불필요(채널 발송의 `manage_guild` 제거).
- **대상(경험치·공지·썬데이):** `대상`(채널/개인) 인자. 켜기 기본=채널(기존 보존), 끄기 기본=전부. `대상:채널`/`대상:개인`로 콕 집기.
- **저장:** 채널=기존 `channel_settings`(그대로). 개인 DM=신규 `notification_subscription(guild_id, discord_user_id, kind)`, 존재=구독, **시각 없음**.
- **디듀프:** 공지·썬데이 DM은 발송 시 `user_id` distinct(글로벌 콘텐츠). 경험치는 길드별.
- **스케줄러 realm 제거:** `scheduler_subscription` PK `(guild,user)`. `resolve_self_characters` realm 필터 제거 → 전 캐릭터. 임베드 뱃지 per-character world 파생. `/스케줄러`·`/스케줄러알림` 모드 인자 삭제. 카테고리 필터(ADR-0014)는 유지.
- **비대칭:** 스케줄러알림=DM 전용+시각+카테고리, 나머지 셋=대상+고정 시각. (스케줄러에 `대상:채널` 없음, 셋에 시각 없음.)

## 2. 빌드 단위

### #1 비틱 숨김 (ADR 아님 — 단순 비활성)
- [bot/core.py](../maple_mate/bot/core.py): `_register_commands`에서 `from ..bitik.commands import setup as setup_bitik` import + `setup_bitik(self)` 호출 제거. (그 외 줄은 불변.)
- [guide/commands.py](../maple_mate/guide/commands.py): `_GROUPS`의 `"🎴 비틱 (자랑 카드)"` 항목(4줄) 삭제.
- **보존:** `maple_mate/bitik/`·`bot/bitik_card.py`·`tests/test_bitik_*.py`·`tests/test_potential_aggregate.py`(비틱 참조)는 손대지 않는다. 핸들러/서비스 직접 테스트라 등록 해제와 무관하게 통과. 부활 시 두 줄만 되돌리면 됨.
- → **verify:** `test_guide`(드리프트 가드=라이브 트리 기준이라 자동 정합) + 비틱 테스트 그린. 봇 트리에 `비틱` 부재 확인.

### #2 개인 DM 구독 저장 — 신규 `notification_subscription`
- **모델([notification/models.py](../maple_mate/notification/models.py)):** `NotificationSubscription` — PK `(guild_id: BigInteger, discord_user_id: BigInteger, kind: String(16))`, `created_at`. `kind ∈ {"exp","notice","sunday"}`(상수로 고정). 시각·realm 컬럼 없음.
- **마이그레이션(신규 alembic):** `notification_subscription` create. down_revision=현 head `d5b3a8e417c2`(또는 #5 마이그레이션 뒤 체이닝). **가역성 실DB 검증**(레포 관례).
- **service([notification/service.py](../maple_mate/notification/service.py)) 추가:**
  - `subscribe_dm(guild_id, user_id, kind)` / `unsubscribe_dm(guild_id, user_id, kind) -> bool`(존재 여부 반환) — pg_insert on_conflict_do_nothing / delete.
  - `dm_subscribers(kind) -> list[(guild_id, user_id)]`(경험치=길드별), `dm_subscriber_users(kind) -> list[user_id]`(공지·썬데이=user distinct).
- → **verify:** DB 함수는 통합 영역(기존 방침 — 단위테스트 제외), 디듀프 SQL은 쿼리 형태 점검.

### #3 명령 통일 — 경험치·공지·썬데이알림 그룹화 + 대상 인자
- **공유 헬퍼(신규 작은 모듈 또는 notification/commands.py 상단):** `대상` Choice = `[Choice("채널","channel"), Choice("개인","personal")]`. `대상` 파싱 헬퍼(켜기 None→채널, 끄기 None→전부).
- **[leaderboard/commands.py](../maple_mate/leaderboard/commands.py):** `/경험치알림` 평면 명령 → `app_commands.Group("경험치알림")` + `켜기`/`끄기`(각 `대상` 인자). `handle_exp_alert`를 (a) 대상=채널 → 기존 `set_exp_alert`(단, **manage_guild 체크 제거**), (b) 대상=개인 → `subscribe_dm(...,"exp")`, 끄기 전부 → 둘 다. 확인 메시지는 대상별.
- **[notification/commands.py](../maple_mate/notification/commands.py):** `/공지알림`·`/썬데이`(→`썬데이알림`) 동일 변환. `manage_guild` 체크·DM 가드(길드 밖)는 채널 대상에서만 의미 — 개인 대상은 길드 컨텍스트만 확인. `set_notice_alert`/`set_sunday_alert`는 그대로(권한 체크만 호출부에서 제거).
- **권한 제거:** 세 핸들러의 `perms.manage_guild` 분기 삭제.
- → **verify:** `test_leaderboard_commands`·`test_notice_*`·`test_sunday_*`·신규 테스트 — 대상별 분기(채널 set / DM subscribe), 끄기 전부, 권한 없는 유저 통과, 썬데이알림 개명.

### #4 DM 팬아웃 — 3개 잡에 개인 구독 발송 추가
- **[leaderboard/broadcast.py](../maple_mate/leaderboard/broadcast.py) `run_leaderboard_job`:** 채널 발송 후, `dm_subscribers("exp")`의 (guild,user)별로 그 길드 양 realm payload(이미 메모이즈)를 DM. payload 빌드는 채널과 공유(추가 페치 0). DM 실패는 앱로그만(스케줄러 `_send_dm` 패턴 재사용).
- **[notification/scheduler.py](../maple_mate/notification/scheduler.py) `run_notice_job`/`_poll_notice_category`:** 신규 공지 선별 후 채널 발송 + `dm_subscriber_users("notice")`에 **user distinct** DM. 마커 전진은 불변(채널·DM 공유 last_id).
- **[notification/scheduler.py](../maple_mate/notification/scheduler.py) `run_sunday_job`:** 금 10:10 이벤트를 채널 발송 + `dm_subscriber_users("sunday")`에 **user distinct** DM. 주차 dedup 마커는 채널 기준 유지(DM도 같은 주차에 1회).
- **공유 DM 헬퍼:** `scheduler/broadcast.py`의 `_fetch_user`/`_send_dm`를 공통 위치(예: `bot/embeds` 인근 또는 신규 `bot/dm.py`)로 올려 4종이 공유하거나, notification 측에 동형 헬퍼. (중복 회피 — 한 곳.)
- → **verify:** 잡 테스트(`test_leaderboard_job`·`test_notice_job`·`test_sunday_job`) +: 구독자 0명=DM 0건, 구독자 N명=DM N건, 글로벌 디듀프(다중 길드 같은 user=1건), DM 실패 스킵.

### #5 스케줄러 realm 제거 — PK 축소 + 전 캐릭터 + per-char 뱃지
- **마이그레이션(신규 alembic):** `scheduler_subscription` PK `(guild_id, discord_user_id, realm)` → `(guild_id, discord_user_id)`, `realm` 컬럼 drop. **기존 행 병합:** (guild,user)별 다중 realm 행 → 최신 `updated_at` 1행 유지(나머지 삭제) 후 컬럼 drop. **가역성 실DB 검증**(down = realm 컬럼 복구 + 'main' 기본값 — 정보손실은 불가역이나 스키마 가역).
- **[scheduler/models.py](../maple_mate/scheduler/models.py):** `realm` mapped_column 제거, PK 2열.
- **[scheduler/service.py](../maple_mate/scheduler/service.py):**
  - `Subscription` 데이터클래스에서 `realm` 제거. `get_subscription`/`set_subscription`/`clear_subscription`/`subscriptions_at_hour` 시그니처에서 `realm` 제거(`index_elements`·where 갱신).
  - `resolve_self_characters(session_factory, guild_id, user_id)` — **realm 필터 제거**, `get_characters` 전체 반환. 가드: 미등록 → 키 미등록 → 캐릭터 0개(realm 분기 메시지 제거, 단일 "등록 캐릭터 없음" 안내).
- **[scheduler/broadcast.py](../maple_mate/scheduler/broadcast.py):**
  - `build_embed(hw, now, excluded=...)` — `realm` 인자 제거. `_embed_title(name, hw.world_name)`로 뱃지 파생(신규 `realm_of_world(world)` 또는 기존 `is_challengers` 활용). `build_homeworks(deps, guild_id, user_id)` realm 인자 제거.
  - `run_scheduler_reminder_job` — `sub.realm` 미사용, `build_embed`에 realm 미전달.
- **[registration/realm.py](../maple_mate/registration/realm.py):** 필요 시 `realm_of_world(world: str|None) -> Realm` 헬퍼 추가(접두 `챌린저스` 판정 — 기존 `is_challengers` 재사용).
- **[scheduler/commands.py](../maple_mate/scheduler/commands.py):** `/스케줄러`·`/스케줄러알림 켜기/끄기`에서 **`모드` 파라미터·`parse_mode`·`realm_title` realm 인자 제거**. 제목은 고정("스케줄러 숙제"/"스케줄러 알림"). 카테고리 필터 인자·시각은 유지.
- → **verify:** `test_scheduler_service`·`test_scheduler_embed`·`test_scheduler_command`·`test_realm` 갱신 — 전 캐릭터 반환(realm 무필터), per-char 뱃지(본서버/챌린저스 혼재 캐릭터 리스트), 모드 인자 부재, 마이그레이션 가역성.

### #6 가이드·문서
- **[guide/commands.py](../maple_mate/guide/commands.py):** `🔔 알림 설정` 그룹 재작성 — 권한 라벨 제거, 4종을 `켜기·끄기`로, 대상(채널/개인) 설명, 썬데이알림. `🗓 스케줄러 숙제` 그룹 — 모드·realm 문구 제거, "등록 캐릭터 전부". `_ONBOARDING`의 모드 안내(챌린저스 모드) 점검(스타포스/잠재는 ADR-0015로 이미 모드 없음 — 영향 없음). 비틱 그룹 삭제(#1).
- `CONTEXT.md`(완료 — 본 작업과 함께), `ADR-0017`(완료), `ADR-0012`·`ADR-0009` 개정 포인터(완료).
- 전체 `pytest -q` 그린 + `ruff check`(E,F,I)·`ruff format` clean + alembic 가역성.

## 3. 명령 표면 (확정)

| 명령 | 켜기 | 끄기 |
|---|---|---|
| `/스케줄러알림` | `켜기 [시각][일일/주간/보스/길드]` (DM 전용) | `끄기` |
| `/경험치알림` | `켜기 [대상=채널]` | `끄기 [대상=전부]` |
| `/공지알림` | `켜기 [대상=채널]` | `끄기 [대상=전부]` |
| `/썬데이알림` | `켜기 [대상=채널]` | `끄기 [대상=전부]` |

## 4. 극단·실패 UX

| 상황 | 처리 |
|---|---|
| 권한 없는 유저 토글 | 허용(권한 체크 없음) |
| 채널 끄기인데 안 켜져 있던 채널 | "켜져 있던 알림 없음" 안내(기존 패턴) |
| 개인 끄기인데 미구독 | 멱등 — "구독 없음" 안내 |
| DM 차단(Forbidden) | 앱로그만, 스킵(결정 — 친구 자가발견) |
| 공지·썬데이 DM 다중 길드 동일 user | user distinct로 1회 |
| 스케줄러 등록 캐릭터 0 | 단일 가드 메시지(realm 분기 없음) |
| 스케줄러 캐릭터 4xx | 그 캐릭터만 조용히 스킵(불변) |

## 5. 테스트 전략 (오프라인)

- `test_guide.py` +: 비틱 부재, 알림 그룹 4종·서브커맨드, 썬데이알림 개명.
- `test_scheduler_service.py`/`_embed`/`_command`/`test_realm.py` +: realm 무필터 전 캐릭터, per-char 뱃지(혼재), 모드 인자 부재, 가드 단일화.
- `test_leaderboard_commands.py`/`test_notice_*`/`test_sunday_*` +: 대상 분기(채널 set/DM subscribe), 끄기 전부, 권한 없는 유저 통과, 썬데이알림.
- `test_leaderboard_job`/`test_notice_job`/`test_sunday_job` +: DM 팬아웃(0명/N명), 글로벌 디듀프, DM 실패 스킵.
- 신규 `test_notification_subscription.py`(있으면): subscribe/unsubscribe 멱등·디듀프 헬퍼.

## 6. 커밋 전략 (레포 고유 — 필독)

작업 트리에 **무관한 미커밋/언트랙 변경 잔존**(README·railway.json·기댓값/·docs/adr/0010·provider-cutover-runbook 등). 절대 함께 스테이징 금지.
1. `origin/main` 기준 신규 브랜치 `feat/notification-unification`.
2. **이번 작업 파일만 외과적 스테이징** — 위 빌드 단위에서 손댄 소스·신규 alembic 2건·`tests/*`·`docs/adr/0017-*`·`docs/adr/0012-*`·`docs/adr/0009-*`·`docs/notification-unification-work-order.md`·`CONTEXT.md`. (broadcast/service에 선행 미커밋이 섞였으면 hunk 단위 또는 선행 분리 커밋.)
3. 논리 단위 커밋(비틱 숨김 / DM 저장+명령 / DM 팬아웃 / 스케줄러 realm 제거 / 문서) → push → squash PR.
4. CI(lint/test/migrations 가역성) 그린 후 머지. 머지 후: 배포 반영 + 실 디스코드 1회 확인(채널·개인 DM 각 1, 스케줄러 다캐릭 DM).

## 7. 비목표

- 단일 `/알림` 허브(기각 — 인자 충돌), 평면 통일(기각 — 스케줄러 퇴행), 채널 권한 유지(사용자가 제거 선택), 개인 DM 시각 선택(기각 — 고정 콘텐츠), 스케줄러 채널 방송(기각 — 프라이버시·스팸).
- 비틱 **삭제**(숨김만 — 코드 보존). 경험치/공지/썬데이 **콘텐츠·주기 변경**(DM은 채널과 동일 산출물 재사용). 인게임 스케줄러 수정.
