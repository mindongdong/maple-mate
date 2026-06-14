# 작업 지시서 — 경험치 리더보드 (`/경험치` + 매일 10시 자동 발송)

> `/비틱`까지 완료된 상태에서 신규 기능 **경험치 리더보드**를 착수한다.
> 등록 캐릭터들의 **누적 경험치 순위**를 매일 오전 10시(KST) 채널에 발송하고, `/경험치` 명령으로도 조회한다.
> 행마다 **어제 하루 획득량(Δ)**과 **전체 서버 순위**를 병기하고, **최근 7일 일일 Δ 라인 그래프**를 함께 보여준다.
> 그릴링(`/grill-me`) 12문 + 라이브 스파이크(G0)로 아래를 확정했다.

## 참조 (중복 금지 — 경로로 참조)

- [docs/api/ranking.md](api/ranking.md) — `ranking/overall` 응답 필드(스파이크로 실측 보정 — 아래 G0 참조)
- [spike/verify_ranking.py](../spike/verify_ranking.py) — G0 검증 스파이크(일회용, 재실행 가능). 원본은 `spike/raw/R*.json`(gitignore)
- [maple_mate/notification/scheduler.py](../maple_mate/notification/scheduler.py) — APScheduler 라이프사이클·잡 등록·`broadcast_*` 어댑터 패턴(재사용)
- [maple_mate/bot/table_image.py](../maple_mate/bot/table_image.py) — PNG 표 렌더(팔레트·한글 폰트·`NumGrid`·`format_eok`)
- [maple_mate/character/service.py](../maple_mate/character/service.py) — `format_eok`(억/만 포맷), 인메모리 캐시 패턴
- [maple_mate/registration/service.py](../maple_mate/registration/service.py) — `get_targets(session_factory, guild_id)` = 길드 등록자 전원(개인 키 무관)
- [maple_mate/notification/service.py](../maple_mate/notification/service.py) — `enabled_*_channels`·`set_*_alert`(채널 토글 패턴)

## 현황 진단

**이미 있음 (재사용 — 새로 만들지 말 것):**
- `registration/service.py` — `get_targets(session_factory, guild_id, user_ids=None)` → `Target`(ocid·닉 포함) 리스트. user_ids 없으면 길드 전원.
- `notification/scheduler.py` — `start_scheduler`(잡 등록), `run_sunday_job`/`run_ops_summary_job`(잡 본체 패턴), `_resolve_channel`(캐시→fetch 폴백), `broadcast_*`(채널 목록 발송 + 부분실패 앱로그).
- `notification/service.py` — `ChannelSettings` upsert/조회 토글(`set_sunday_alert`·`enabled_sunday_channels`) — 그대로 복제해 `exp_alert` 판.
- `bot/table_image.py` — 다크 팔레트·한글 폰트 후보·`format_eok`(character/service)·`asyncio.to_thread` 렌더 패턴.
- `error_log/service.py` — `record(...)`(넥슨 장애만 적재), `to_error_log_type`. 운영 요약 09:00 잡에 prune 편승 지점(`run_ops_summary_job`).
- `nexon/client.py` — 앱 키 스로틀 버킷(None 키), `_request`(429·타임아웃 재시도·에러분류).
- `dependencies.py` — `Deps`(session_factory·nexon·config). 인메모리 캐시 추가 패턴(`combat_power_cache`).

**새로 만듦:**
- `maple_mate/leaderboard/` 패키지 — `models.py`(ExpSnapshot) · `service.py`(페치·집계·prune·백필, 전달-무관) · `broadcast.py`(Discord 잡 어댑터) · `commands.py`(`/경험치`·`/경험치알림`).
- `maple_mate/bot/leaderboard_image.py` — 순위표 PNG + **7일 Δ 라인 그래프 PNG(PIL 직접 그리기 — 코드베이스 최초의 선그래프)**.
- `nexon/client.py`에 `ranking_overall(ocid, date)` 메서드.
- alembic 마이그레이션 — `exp_snapshot` 테이블 + `channel_settings.exp_alert` 컬럼.

## G0 — 라이브 스파이크 결과 (착수 전 게이트, 완료)

[spike/verify_ranking.py](../spike/verify_ranking.py) 실행(2026-06-14 12:47 KST, `손바`·`라딘라면` Lv287)로 확정:

| # | 항목 | 결과 |
|---|---|---|
| ① | `character_exp`=누적인가 | ✅ 72조@Lv287, D-8~D-1 단조비감소. Δ=인접일 차=그날 획득량. 비활동일 Δ=0(정상). |
| ② | 대상 식별법 | ✅✅ `ocid+date` → `ranking` 배열에 **대상 1건만**(`ranking[0]`이 곧 대상). **닉 매칭·닉변경 리스크 없음.** |
| ③ | 미등재 응답형태 | ⚠️ 고렙 2명 다 200/1건. 진짜 저렙 미등재 형태 미관측 → **방어적: `ranking` 비었거나 없으면 '미등재'(그날 제외), 에러 아님**. |
| ④ | 과거 date 백필 | ✅✅ D-1~D-8 전부 200 READY. 8일 백필 가능. |
| ⑤ | D-1 readiness | ✅ 12:47에 D-1·당일까지 READY. 10:00 정확시점 미검증 → **잡에 readiness 가드**(미준비 캐릭 그날 제외). |

**구현 필수 발견:**
- ⚠️ **`ranking/overall`은 `ocid`와 함께 `date` 필수** — date 무지정 시 `400 OPENAPI00004`(문서엔 선택이라 표기). `/스펙`의 date 무지정 패턴과 **반대**. → `ranking_overall(ocid, date)`는 항상 명시적 D-1(KST) 전달.
- 한 콜 응답 필드(실측): `date, world_name, ranking, character_name, character_level, character_exp, class_name, sub_class_name, character_popularity, character_guildname`.
- ⚠️ **필드명 함정**: 랭킹은 `character_guildname`(언더스코어 없음), `character/basic`은 `character_guild_name`. 혼동 금지.
- 응답 `date`==요청 `date` 일치(클램프 없음) — Δ 신뢰 가능.

## 확정 결정 (그릴링 12문)

| # | 결정 | 선택 |
|---|---|---|
| Q1 | **헤드라인 정렬** | **절대 누적 경험치 순위**(길드 내림차순). 정렬 키 = `total_exp`(히든). |
| Q2 | **행 구성** | 순위 · 닉 · 레벨(exp%) · **어제Δ**(억/만) · **전체 서버 순위(#)**. 누적 raw 숫자는 표시 안 함(14자리). |
| Q3 | **온디맨드** | 자동 발송 + **`/경험치`** 명령 둘 다(표 + 7일 그래프 동일 산출물). |
| Q4 | **그래프 위치** | **자동 발송 + 명령 둘 다.** 매일 10시 = 순위표 PNG + 그래프 PNG 2장. |
| Q5 | **그래프 내용** | **일일 Δ · 최근 7일 · 유저별 라인.** 누적 라인 금지(레벨격차로 평행선). |
| Q6 | **데이터 소스** | **`ranking/overall?ocid=&date=D-1` 단일.** 앱 키 → **개인 키 없는 친구도 포함.** |
| Q7 | **미등재 처리** | 종합랭킹 미등재 = 그날 **'랭킹 미등재'로 순위 제외**(EXP 테이블 폴백 안 함). |
| Q8 | **발송 채널** | `channel_settings`에 **`exp_alert`** 불리언 추가 + **`/경험치알림`** on/off 토글(공지/썬데이 패턴 복제). |
| Q9 | **렌더** | 순위표=`table_image` 재사용, 그래프=**PIL 직접 그리기**(matplotlib 안 씀). |
| Q10 | **포함 대상** | 등록자 **전원 자동**, 옵트아웃 없음. **랭킹 등재 2명 미만이면 그날 발송 생략.** |
| Q11 | **백필** | 첫 실행 시 과거 **~8일** `ranking_overall(date)` 선적재 → 그래프 첫날부터 채움. |
| Q12 | **명령 인자** | `/경험치` 고정 7일(인자 없음). 보존 90일(09:00 잡 prune 편승). |

**파생 결정 (그릴링/스파이크 중 질문 없이 확정):**
- **Δ 정의:** `total_exp(D-1) − total_exp(D-2)` = 어제 하루 획득. **이전 스냅샷 없으면 Δ='—'**(신규/측정불가). 음수 발생 시(데이터 보정 등) 0으로 클램프·`—` 표기.
- **기준일 라벨:** 발송 본문/footer에 "기준: 어제(MM/DD) KST"(누적은 D-1 마감값임을 명시).
- **readiness 가드:** 잡은 각 캐릭 `date=D-1` 조회 → 미준비/미등재(빈 `ranking`)면 그 캐릭만 그날 제외(에러 아님). 넥슨 장애(타임아웃·429·5xx)·앱키 실패만 `error_log`(기존 운영 요약 경로 재사용).
- **순위 의미:** 표 좌측 "순위" = 길드 내 `total_exp` 내림차순 1,2,3…. "전체 서버 순위(#)" = 응답 `ranking` 그대로.
- **스냅샷 키:** `(guild_id, discord_user_id, date)` — 같은 ocid가 복수 길드면 길드별 행(친구 그룹 단일 길드 전제, 중복 콜 미세 최적화는 백로그).
- **그래프 라벨:** 닉네임. 비활동(전 구간 Δ=0)도 라인 표시(0 바닥선). 라인 색은 고정 팔레트 순환, 범례 포함.
- **숫자 포맷:** Δ는 `format_eok`(억/만) 재사용. 누적 raw 미표시이므로 조 단위 확장 불필요.
- **쿨다운:** `/경험치` = 10초(스냅샷 DB 조회만, 넥슨 콜 없음 — 스파이크 외엔 잡이 적재). `/경험치알림` 토글 = 쿨다운 불요.

## 빌드 단위 (의존 순서)

### 1. DB — 마이그레이션 (선행)
- `exp_snapshot`: PK `(guild_id BigInt, discord_user_id BigInt, snapshot_date Date)` + `character_level Int`, `total_exp BigInteger`(정렬키), `world_rank Int|null`, `fetched_at DateTime(tz)`.
- `channel_settings.exp_alert Boolean NOT NULL DEFAULT false`(기존 테이블 ALTER).
- alembic autogenerate → `alembic check` 통과 확인(CI 게이트, ADR-0003).
- *검증: 업·다운그레이드 스모크.*

### 2. `nexon/client.py` — `ranking_overall`
- `async def ranking_overall(self, ocid: str, date_iso: str) -> dict | None` — 앱 키, **date 필수**. 응답 `ranking` 리스트의 `[0]` 반환(없거나 빈 리스트면 `None` = 미등재/미준비). 넥슨 에러는 `NexonAPIError`로 전파(호출자 best-effort).
- *검증: mock transport로 200/1건·빈배열·에러 분기 단위테스트.*

### 3. `leaderboard/models.py` + `leaderboard/service.py` — 페치·집계·prune (전달-무관)
- `ExpSnapshot` ORM(위 스키마).
- `@dataclass(frozen=True) LeaderRow` — `rank, nickname, level, exp_rate, delta|None, world_rank|None`.
- `async def fetch_and_store(deps, guild_id, targets, date_iso) -> int` — 대상별 `ranking_overall(ocid, D-1)` → 스냅샷 upsert. 미등재/미준비는 건너뜀(스킵 카운트 반환). 넥슨 장애·앱키 실패만 `error_log.record`.
- `async def backfill(deps, guild_id, targets, days=8) -> None` — 과거 date 루프 upsert(이미 있으면 skip). 첫 실행 1회.
- `def build_rows(today_snaps, prev_snaps) -> tuple[list[LeaderRow], int]` — **순수.** `total_exp` 내림차순 정렬·순위 부여·Δ 계산(prev 없으면 None)·미등재 제외 카운트.
- `async def history_deltas(session_factory, guild_id, days=7) -> dict[str, list[(date, delta|None)]]` — 그래프용 유저별 7일 Δ 시계열(순수 변환은 분리).
- `async def prune_old_snapshots(session_factory, now, days=90) -> int` — `snapshot_date < now-90d` 삭제.
- *검증: `build_rows` 정렬·순위·Δ·미등재 제외, `history_deltas` 변환, prune 경계 단위테스트(스파이크 수치 픽스처: 72.295조−71.360조=9351억).*

### 4. `bot/leaderboard_image.py` — PNG 렌더 (순수, `to_thread` 전제)
- `render_table(rows, ref_date) -> BytesIO` — `table_image` 팔레트로 순위표. 컬럼: 순위·닉·`Lv.287 (45.2%)`·`+9351억`·`#129,978`. Δ 최고값 금색 강조, Δ='—' 회색.
- `render_delta_graph(series, ref_date) -> BytesIO` — 7일 Δ 라인 그래프(축·격자·범례·유저별 색). 빈 데이터(첫날) 가드.
- *검증: 렌더 스모크(예외 없이 PNG) + 빈/단일 유저 분기.*

### 5. `leaderboard/broadcast.py` — Discord 잡 어댑터 + 명령 본체 공유
- `async def build_payload(bot, deps, guild_id) -> (files | None)` — get_targets → today/prev 스냅샷 조회 → `build_rows` → 2명 미만이면 None → 표·그래프 렌더. `/경험치`와 잡이 공유.
- `async def run_leaderboard_job(bot, deps)` — `exp_alert` 채널 0개면 스킵(넥슨 콜 없음). 길드별: (첫 실행) 백필 → `fetch_and_store(D-1)` → `build_payload` → `_resolve_channel`로 발송(부분실패 앱로그, 썬데이 패턴). prune는 09:00 ops 잡에 편승(`run_ops_summary_job`에 `prune_old_snapshots` 한 줄 추가).
- *검증: 채널 0개 스킵·2명 미만 스킵·발송 분기(Discord mock). 실제 발송은 라이브 1회.*

### 6. `leaderboard/commands.py` — `/경험치` · `/경험치알림`
- `/경험치` — defer → `build_payload(현재 길드)` → 표+그래프 공개 응답(2명 미만/데이터 없음 시 안내). 쿨다운 10초.
- `/경험치알림 [on|off]` — `channel_settings.exp_alert` 토글(`set_exp_alert` 신설, `set_sunday_alert` 복제). 권한은 기존 알림 명령과 동일.
- `bot/core.py setup_hook`에 `setup_leaderboard(self)` 등록.

### 7. 스케줄러 등록
- `notification/scheduler.py start_scheduler`에 `run_leaderboard_job` 잡 추가: `CronTrigger(hour=10, minute=0, tz=KST)`, `coalesce=True`, `misfire_grace`(당일 따라잡기, 썬데이와 동일), `max_instances=1`. 잡 함수는 `leaderboard/broadcast.py`에서 import(파일 비대화 방지).
- *검증: 잡 등록 스모크(기존 `test_*_job` 패턴).*

## 렌더 전략

| 산출물 | 성격 | 렌더 |
|---|---|---|
| 순위표 | 길드 누적 순위 + Δ + 전체순위 | PNG 표(`table_image` 재사용), footer="기준: 어제(MM/DD) KST" |
| 7일 그래프 | 유저별 일일 Δ 추세 | PNG 선그래프(PIL 직접, 축·범례·색 순환) |

## 테스트 전략 (실용 — 기존 합의 계승)

순수 로직만 단위테스트: `build_rows`(정렬·순위·Δ·미등재 제외)·`history_deltas` 변환·prune 경계·`ranking_overall` 파싱·토글 upsert·명령 분기(2명 미만/데이터 없음). 픽스처는 스파이크 실측치 재현. 렌더는 스모크. 발송·그래프 시각·10:00 readiness는 **라이브 1회 확인**(첫 자동 발송 다음 날 또는 `/경험치`로 즉시). `-m live` 마커로 ranking_overall 실호출 테스트 1개 추가 가능.

## 미해결 / 잔류 리스크

- **저렙 미등재 응답형태 미관측(G0 ③)** — 친구 전원 고렙이라 실관측 불가. 방어적(빈 `ranking`=미등재 제외)으로 처리. 첫 저렙 등록자 등장 시 라이브 확인.
- **10:00 정확 readiness(G0 ⑤)** — 12:47엔 READY 확인. 10:00에 D-1 미준비면 그 캐릭만 그날 제외(다음날 정상). 빈도 잦으면 발송 시각을 10:30~11:00로 조정(상수 1곳).
- **종합랭킹 exp 갱신 타이밍** — Δ는 랭킹 exp 반영 시점 의존. 비활동일 0, 갱신일에 반영(스파이크상 일 단위 정상). 배치 지연이 관측되면 "최근 7일 합" 보조 지표 백로그.
- **그래프 라인 스파게티** — 등록자 많으면(>10) 라인 겹침. 친구 그룹 소규모 전제. 초과 시 상위 N(최근 활동순) 제한 백로그.
- **단일 인스턴스 전제** — 스냅샷은 DB라 무관하나 잡 중복 실행 방지는 `max_instances=1` 의존(현 단일 인스턴스, deploy-and-scaling-plan 참조).

## 스코프 밖 (보류)

- 레벨→누적 EXP 테이블 / `character/basic` 폴백 — Q6에서 ranking 단일 소스로 확정(미등재는 제외).
- 옵트아웃·개인별 알림 — Q10에서 전원 포함 확정.
- `/경험치` 기간 인자(14/30일) — Q12에서 고정 7일 확정.
- 주간/월간 요약·MVP 뱃지·연속 출석 — 백로그.
- 누적 raw 숫자·조 단위 포맷 — Q2에서 전체순위로 대체.
