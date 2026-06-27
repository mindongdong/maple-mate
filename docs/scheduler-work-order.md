# 작업지시서 — 스케줄러 알리미 (per-user DM 구독)

> **근거 결정:** [ADR-0012](adr/0012-scheduler-reminder-per-user-dm.md)(9건 확정), [핸드오프](scheduler-feature-handoff.md), API 스펙 [docs/api/scheduler.md](api/scheduler.md), 용어 [CONTEXT.md](../CONTEXT.md)("스케줄러 숙제"·"스케줄러 알리미").
> **하우스 스타일 레퍼런스:** [exp-leaderboard-work-order.md](exp-leaderboard-work-order.md)(빌더 공유 + cron 잡), [bitik](../maple_mate/bitik/commands.py)(본인 개인 키 카드).

## 0. 한 줄 목표

넥슨 `scheduler/character-state`(개인 키 + ocid)로 **본인 대표 캐릭터의 인게임 스케줄러 숙제 체크리스트**를
(1) `/스케줄러` 온디맨드 조회(ephemeral)와 (2) **매일 정해진 시각 본인 DM**(per-user 구독)으로 보여준다.

## 1. 확정 제약 (scheduler.md / ADR-0012)

- **개인 키 + `ocid`**(이력류 친척, per-character). 봇 앱 키로는 불가. `registration_flag=="true"` 항목만 '내 숙제'.
- **오늘은 `date` 무지정으로만**(명시 시 400). 알리미는 항상 오늘 → `date_iso=None`.
- 비대상/저활동 캐릭터는 빈 응답이 아니라 4xx(`OPENAPI00003/00004`) → 조회 불가로 흡수.
- `registration_flag`/`complete_flag`는 **문자열** `"true"`/`"false"`. `now_count`/`max_count`는 int.

## 2. 빌드 단위

### #1 넥슨 클라이언트 — `nexon/client.py`
`scheduler_character_state(api_key, ocid, date_iso=None) -> dict`. 개인 키 헤더 오버라이드 + `ocid` 파라미터.
오늘=무지정. 4xx 는 `_request` 가 `NexonAPIError` 로 raise(호출자가 흡수). scheduler.md "봇 통합 메모" 제안 구현 그대로.

### #2 구독 모델 — `scheduler/models.py` + alembic
`SchedulerSubscription`: PK `(guild_id, discord_user_id, realm)`, `hour`(0–23, 기본 없음 — 앱이 매 upsert 명시),
`created_at`/`updated_at`. realm 은 `Realm.value`("본서버"/"챌린저스") 디스크리미넌트(String(16)). 신규 테이블 1개.
down_revision = `c3d4e5f6a7b8`(현 head).

### #3 service(전달-무관) — `scheduler/service.py`
- **순수:** `parse_homework(data) -> Homework`(DTO: 일일/주간 `ContentItem`, 보스 `BossItem`, 주간보스 클리어 수/한도).
  `registration_flag=="true"` 필터. `daily_contents`·`weekly_contents`·`boss_contents` 섹션별. 완료/미완료 모두 보존(체크리스트).
- **순수:** `content_line`(게이지 `now/max`), `boss_line`(✅/⬜ + 난이도), `section_lines`(1024자 클램프 `…외 N개`). 단위테스트 대상.
- **DB:** `set_subscription`(켜기 upsert: hour+realm), `clear_subscription`(끄기 delete), `subscriptions_at_hour(hour) -> list[Sub]`(cron 조회), `_resolve_self(guild,user,realm) -> (key_enc|None, ocid|None, error|None)`(키+realm 대표 ocid 해석, bitik `_self_target` 패턴).
  DB 함수는 pg_insert/delete 통합 영역 → 단위테스트 제외(기존 방침).

### #4 broadcast(어댑터) — `scheduler/broadcast.py`
- `build_homework(deps, guild, user, realm) -> (Homework|None, str|None)` — `_resolve_self` → 키 복호화 → `scheduler_character_state(date=None)` → `parse_homework`. 실패는 `(None, 사용자메시지)`, 성공은 `(homework, None)`(homework 는 `is_empty` 일 수 있음). **온디맨드·알림 공유**(결정 6).
- `build_embed(homework, realm, now) -> discord.Embed` — 필드 파생 카테고리별 필드(퀘/회수/점수/보스 cycle, [ADR-0013](adr/0013-scheduler-field-derived-categories.md)) + 부제 전체 잔여 + 푸터(`HH:MM 기준 · NEXON Open API`). 챌린저스 `🏆` 제목, 잔여 0=초록.
- `run_scheduler_reminder_job(bot, deps)` — 매시 정각 cron 본체. now.hour 구독 0개면 스킵(넥슨 0콜) → 구독별 `build_homework` → DM 발송. 키없음·4xx·`is_empty`·DM 차단 모두 **조용히 스킵 + 앱로그**(결정 7). cron 등록은 `notification/scheduler.py:start_scheduler`(잡 본체는 지연 import — 리더보드 패턴).

### #5 commands(전달) — `scheduler/commands.py`
- `/스케줄러 [모드]` — defer(ephemeral) → `build_homework` → 결과 분기(키 미등록·realm 대표 없음·등록 숙제 0개·체크리스트). spec_cooldown(10초).
- `/스케줄러알림` `app_commands.Group` — `켜기 [시각=21] [모드]`(구독 시점 키·대표 가드 = fail fast, 결정 7a), `끄기 [모드]`. settings_cooldown.
- `bot/core.py:_register_commands` 에 `setup_scheduler(bot)` 배선.

## 3. 표시 규약 (as-built — 필드 파생 카테고리, [ADR-0013](adr/0013-scheduler-field-derived-categories.md))

요약형(개정 1)도 "할 일 즉시 파악" 요구를 못 맞춰 폐기. 라이브 9캐릭 실 API 조사로 콘텐츠를 **이름 하드코딩 없이 필드로 분류**(`type`/`quest_state`/`max_count`/`cycle`)하고 **할 일 우선(todo-first)**으로 재설계:

```
🗓 손바 의 스케줄러 숙제                        (챌린저스는 🏆 프리픽스)
Lv.287 · 크로아                                (부제 = 레벨·월드)
🔥 남은 숙제 21개 (2/23 완료)                  (전체 잔여 — 길드(점수제)·qs0 제외, 잔여0=✅+초록)

🎯 일일 회수 — 남은 1  0/1
  🟡 몬스터파크 `2/14`                         (회수형 max>1, 진행중만 게이지)
📆 주간 퀘스트 — 남은 0  1/1
  ✅ 완료 1개 · 익스트림 몬스터파커에 도전해보겠…   (완료=수+이름 한 줄)
⚔️ 주간 콘텐츠 — 남은 7  1/8
  ⬜ 에르다 스펙트럼 / ⬜ 배고픈 무토 …            (max 0/1, done=now>0, 에픽던전·무릉 포함)
  ✅ 완료 1개 · 에픽 던전 : 앵글러 컴퍼니
🏰 길드 콘텐츠                                  ([길드]프리픽스, 점수제·완료개념 없음)
  🔹 주간 미션 포인트 `1240` / ⬜ 지하 수로        (now>0=점수, now==0=⬜ 아직)
🗡 주간 보스 — 남은 14  0/14  (처치 0/12)
  ⬜ 스우(익스트림) / ⬜ 데미안(하드) …            (cycle별, 난이도 한글, 미처치 ⬜)
🗡 월간 보스 — 남은 0  1/1
  ✅ 처치 1개 · 검은 마법사
푸터: 21:00 기준 · NEXON Open API
```
- **카테고리(필드 파생):** `type=quest`→완료/미완료(`quest_state` 2완료/1미완료/0제외), 이름 `[길드]`프리픽스→길드 콘텐츠(점수제), `contents`+`max>1`→회수형 `n/m`, 그 외(`max` 0/1)→완료/미완료(`done=now>0`, 에픽던전·무릉 포함), 보스→`cycle`(bossDaily/Weekly/Monthly)별. 난이도 영문→한글(이지/노멀/하드/카오스/익스트림). 주간 보스만 `(처치 c/12)` 부가(0/이상값=12 폴백).
- **표시:** 헤더 `남은 N + 완료/총`(**진행바 없음**). 미완료 전부 `⬜` 개별(1024 초과만 클램프), 완료 `✅ 완료 N개 · 이름…` 한 줄. 회수형 `0<now<max`만 `🟡 n/m` 게이지. 길드(점수제)는 `now>0=🔹 점수 / now==0=⬜`. 부제 전체 잔여(잔여0=✅+초록, 그 외 🔥+오렌지).
- **이름 정리:** 앞 `[...]` 프리픽스 제거(`strip_prefix`) + 18자 말줄임(`truncate`) — 구조적, 하드코딩 아님. 길드 식별은 strip 전 `[길드]` 프리픽스로.
- 렌더 순수함수는 service.py(`by_category`/`content_field_value`/`score_field_value`/`boss_cycle_value`/`field_counts`/`boss_counts`/`progress_bar`/`difficulty_ko`/`weekly_boss_limit` 등), 임베드 조립은 broadcast.`build_embed`(카테고리별 필드).

## 4. 부재/실패 UX (결정 7)

| 상황 | 온디맨드 `/스케줄러` | 알림 cron |
|---|---|---|
| 미등록(캐릭 0) | "등록 먼저(`/캐릭터등록`)" | 스킵 |
| 키 미등록 | "키 등록(`/키등록`)" | 스킵 |
| realm 대표 없음 | 챌린저스/본서버 안내 | 스킵 |
| 4xx(비대상·저활동) | `classify_target_error` | 스킵 + 앱로그 |
| 등록 숙제 0개(`is_empty`) | "인게임 스케줄러에 등록된 숙제가 없어요" | 스킵(빈 DM 금지) |
| 전부 완료 | ✅ 체크리스트 | ✅ DM 발송 |

구독 가드(켜기): 키·realm 대표 없으면 구독 거부(fail fast). DM 차단 유저는 cron 조용히 스킵(자가 발견).

## 5. 테스트 전략 (오프라인 픽스처)

- `test_nexon_client.py` +: `scheduler_character_state` 오늘=date 무지정 / 과거=명시 / 개인 키 헤더 / ocid 파라미터.
- `test_scheduler_service.py`: `parse_homework`(registration_flag 필터·게이지·보스 플래그·is_empty), `content_line/boss_line/section_lines`(1024 클램프).
- `test_scheduler_embed.py`: `build_embed` 카테고리별 필드·챌린저스 제목·전부완료(초록).
- `test_scheduler_job.py`: `run_scheduler_reminder_job` — hour 구독 0 스킵, 구독별 DM, 키없음/4xx/empty/DM차단 조용히 스킵(monkeypatch I/O).
- `test_scheduler_command.py`: `/스케줄러` 결과 분기(monkeypatch build_homework), `/스케줄러알림 켜기` 가드.

## 6. 비목표

앱 키 임의 유저 조회(불가), 14일 초과·미래, 인게임 스케줄러 수정, 시:분 단위 시각(시 단위로 충분), 채널 브로드캐스트(기각 — ADR-0012).
