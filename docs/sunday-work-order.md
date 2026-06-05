# 작업 지시서 — `/썬데이` (Phase 4 일부 선개발)

> Phase 2 완료 상태에서 **썬데이 알림만 예외적으로 선개발**한다. 같은 Phase 4의 `/공지알림`,
> 그리고 설계 §4의 **수동 썬데이 HTTP 엔드포인트는 보류**(후순위). 그릴링(`/grill-with-docs`)으로
> 아래 결정을 모두 확정했다.

## 참조 (중복 금지 — 경로로 참조)

- [maple-discord-bot-design.md](../maple-discord-bot-design.md) §3.7·§4·§5③④·§7 — 동작 명세(SSOT)
- [CONTEXT.md](../CONTEXT.md) — 도메인 용어("썬데이 메이플", "썬데이 알림" 신규 추가)
- [docs/api/notice.md](api/notice.md) — `notice-event` 검증 결과(⚠️ "썬데이 메이플" 제목 양성 매칭 미실측 잔류)
- 이벤트 응답 실샘플: [spike/raw/C3_notice_event.json](../spike/raw/C3_notice_event.json)

## 현황 진단

**이미 있음(Phase 1):** `channel_settings.sunday_alert` 컬럼, `notice_state` 테이블(`category="sunday"`).
→ **Alembic 마이그레이션 불필요.**

**새로 만듦:** APScheduler 인프라(의존성조차 없음) · `NexonClient.notice_event()` · `notification/service.py` ·
`notification/scheduler.py` · `notification/commands.py` · 봇 라이프사이클 배선.

## 확정 결정 (그릴링 결과)

| # | 결정 | 선택 |
|---|---|---|
| Q1 | 스케줄러 인프라 | **APScheduler `AsyncIOScheduler`(KST)** 도입. 잡 등록 지점만 일반화(공지알림 잡은 미리 안 만듦). |
| Q2 | 제목 매칭 | **공백 무시 부분일치**: `"썬데이메이플" in title.replace(" ", "")`. 기간 필터 없음(`notice-event`가 진행 중만 반환). |
| Q3 | 주차 중복방지 | ① ISO 연-주차 `"YYYY-Www"`(KST). ② **매칭 ≥1 + 전 채널 발송 시도 후에만** 마킹(0매칭=마킹 안 함). 잡 시작 시 이번 주 마킹돼 있으면 통째 스킵. ③ 채널 부분 실패해도 **마킹 강행**(로그만). |
| Q4 | 재시도 | ① 발송 시점: `NexonClient` 내부 재시도(타임아웃·429)만, **그 위 별도 재시도 루프 없음**. 최종 실패 시 `error_log` 후 이번 주 포기. ② 봇이 10:10에 꺼져 있었으면 **당일 따라잡기**(`misfire_grace_time` 당일 + `coalesce=True`, 주차 마커가 중복 차단). |
| Q5 | `/썬데이` 명령 | 권한 **`manage_guild`**(인라인 체크 + ephemeral 거부). 모양 **단일 `/썬데이` + 필수 choice `상태:[켜기,끄기]`**(평면 구조). DM 가드. `channel_settings` upsert 시 `sunday_alert`만 set(`notice_alert` 보존). |
| Q6 | 발송 임베드 | 제목=클릭 하이퍼링크(`embed.url`), description=기간, **썸네일 포함**(`thumbnail_url` None 가드), 다중 매칭=**단일 메시지 다중 임베드**(`send(embeds=[...])`), 데이터-푸터 없음. |
| Q7 | 배선 | 스케줄러를 **봇이 소유**: `setup_hook`에서 1회 시작, `close()` 오버라이드에서 `shutdown()`. 모듈 2분리(service=전달무관 / scheduler=어댑터+라이프사이클). 채널 해석 `get_channel`→`fetch_channel` 폴백, 실패 시 앱로그만. **넥슨 페치 실패만 `error_log`**(디스코드 발송 실패는 미적재 — enum·설계 경계 보존). |
| Q8 | 검증 | 순수 함수 단위테스트(매칭·주차·포맷터·dedup). 라이브는 **`scripts/` 일회성 트리거 + 이벤트 목록 덤프** 스크립트로 확인(수동 HTTP 엔드포인트 대용). |

## 빌드 단위 (의존 순서)

### 1. 의존성 + 클라이언트
- `pyproject.toml`에 `apscheduler>=3.10` 추가 → `uv lock` / `uv sync`.
- `NexonClient.notice_event()` — 앱 키, `maplestory/v1/notice-event` GET, `event_notice` 리스트 반환. *검증: `BSCAN`/`C3` 스타일 실호출 1건 + 스키마 키 확인.*

### 2. `notification/service.py` (전달-무관: 순수 + DB)
- `match_sunday(title) -> bool` — 공백 무시 부분일치. **순수.**
- `current_week_id(now_kst) -> str` — `"YYYY-Www"` (ISO). **순수.**
- `format_period(start_iso, end_iso) -> str` — `"YYYY-MM-DD HH:MM ~ ..."` KST. **순수.**
- `select_sunday_events(nexon) -> list[SundayEvent]` — 페치+매칭. `SundayEvent(title,url,thumbnail_url,period_text)` 데이터클래스.
- `already_sent_this_week(session_factory, week_id) -> bool` / `mark_week_sent(session_factory, week_id)` — `notice_state(category="sunday")` 읽기/upsert.
- `enabled_sunday_channels(session_factory) -> list[(guild_id, channel_id)]` — `channel_settings.sunday_alert=true`.
- *검증: 매칭·주차·포맷터·dedup 판정 단위테스트(넥슨 mock).*

### 3. `notification/scheduler.py` (전달 어댑터 + 라이프사이클)
- `AsyncIOScheduler` 생성(트리거 tz=`ZoneInfo("Asia/Seoul")`), cron `금 10:10`, `misfire_grace_time`=당일, `coalesce=True`.
- `broadcast_sunday(bot, deps, events)` — **재사용 가능**(미래 수동 엔드포인트 재사용): 채널 해석(폴백)→임베드 빌드(클릭제목+기간+썸네일)→`send(embeds=[...])`→실패 앱로그.
- 잡 본체 순서: **주차 체크→스킵 / 채널 0개→스킵(넥슨 호출 안 함) / 매칭 0개→스킵 / 발송→마킹**. 넥슨 페치 실패 시 `error_log.record(command="썬데이", ...)`.
- `start_scheduler(bot, deps) -> AsyncIOScheduler` / `shutdown`.
- *검증: 잡을 직접 호출하는 일회성 스크립트로 테스트 채널 발송 확인.*

### 4. `notification/commands.py` (`/썬데이`)
- 단일 `/썬데이` + 필수 `상태` choice(`켜기`/`끄기`). `manage_guild` 인라인 체크. DM 가드.
- `channel_settings` upsert(`sunday_alert`만 set). ephemeral 확인 임베드.
- *검증: 길드 동기화 후 켜기/끄기 → DB 토글 + `notice_alert` 보존 확인.*

### 5. 배선 (`bot/core.py`)
- `setup_hook`에서 `start_scheduler(self, self.deps)`(1회), `close()` 오버라이드에서 `shutdown()`.
- `_register_commands`에 `setup_notification(self)` 추가.

### 6. 스크립트 (`scripts/`)
- `trigger_sunday.py` — Deps 조립 후 `broadcast_sunday`를 테스트 채널에 직접 호출(라이브 발송 눈으로 확인).
- `dump_events.py` — 현재 `notice-event` 제목 전체 덤프(지금 썬데이 이벤트가 떠 있는지 즉시 확인 → 양성 매칭 미실측 보완).

### 7. 테스트 (`tests/`)
- `test_sunday_match.py` 등: 매칭(공백 변형 케이스)·주차·포맷터·dedup. 넥슨 mock. 스케줄러/디스코드 통합테스트 생략.

## 산출물
- 위 코드 + 단위테스트 통과 + 스크립트로 라이브 발송 1회 확인 + (가능 시) 실제 진행 이벤트 덤프로 매칭 양성 확인.

## 미실측 / 리스크
- ⚠️ **"썬데이 메이플" 제목 양성 매칭 미실측**(notice.md 잔류). 매칭 함수는 공백 무시로 완화했으나, 실제 이벤트가 뜬 주에 `dump_events.py`로 한 번 눈 확인 필요.
- "재시도 없음 + 당일 따라잡기"는 의도적 절충(엄격 해석 아님). 변경 비용 낮아 ADR 생략.

## 스코프 밖 (보류)
- **수동 썬데이 HTTP 엔드포인트**(설계 §4) — `broadcast_sunday`·주차 마커를 재사용하도록 이음새만 마련. 엔드포인트 자체는 미구현.
- `/공지알림` 6회/일 폴링 — 같은 스케줄러에 나중에 잡 1개 추가하면 됨.
