# 작업 지시서 — 경험치 리더보드 표·그래프 UX 개선

> 경험치 리더보드([#16](https://github.com/mindongdong/maple-mate/pull/16)·[#19](https://github.com/mindongdong/maple-mate/pull/19) 머지 완료) **출시 후 사용자 피드백 3건**을 반영하는 UX 개선 라운드다.
> 그릴링(`/grill-me`)으로 아래를 확정했다. 이 문서 하나로 다른 세션이 그대로 이어받아 구현한다.

---

## 0. 핸드오프 지시문 (다른 세션 시작점)

**목표:** 리더보드 순위표에서 군더더기 컬럼을 빼고 컬럼명을 다듬고, 그래프 y축을 "절대 경험치(억/조)"에서 **"7일 전 대비 레벨 진행량(%p)"** 으로 바꿔 비교·가독성을 높인다.

**시작 방법:**
1. `git checkout main && git pull` 후 `git checkout -b fix/leaderboard-ui-improvements` (main 기반).
2. 이 문서 §3 빌드 단위를 의존 순서대로 구현. 코드 패턴은 기존 [leaderboard_image.py](../maple_mate/bot/leaderboard_image.py)·[service.py](../maple_mate/leaderboard/service.py)·[broadcast.py](../maple_mate/leaderboard/broadcast.py) 그대로 따른다(다크 팔레트·한글 폰트·`asyncio.to_thread`·frozen dataclass·전달-무관 service).
3. 구현은 `executor`, 승인 패스는 별도 `code-reviewer`(같은 컨텍스트 self-approve 금지, OMC 규칙).

**완료 정의(DoD):**
- 표: 4컬럼(순위·닉네임·레벨(exp%)·**하루 경험치**), 전체 순위 컬럼 없음.
- 그래프: 7일 전 대비 진행량(%p) 부채꼴 라인, 범례에 유저별 일평균 %/일, 레벨업 톱니/마커 없음.
- `.venv/bin/ruff check maple_mate tests` clean + `.venv/bin/python -m pytest -m 'not live'` 전부 통과.
- §4 테스트 갱신 완료(특히 **백필 basic 테스트 반전**, 아래 ⚠️).
- 실데이터 미리보기 PNG 재생성(§5)로 눈 확인.

**복붙용 킥오프 프롬프트:**
> `docs/leaderboard-ui-improvements-work-order.md` 를 SSOT 로 읽고, 경험치 리더보드 표·그래프 UX 개선을 구현해줘. main 기반 `fix/leaderboard-ui-improvements` 브랜치에서 §3 빌드 단위를 의존 순서로 구현하고, §4 테스트를 갱신(백필 basic 테스트 반전 포함)한 뒤 `ruff` + `pytest -m 'not live'` 그린까지 반복. 마이그레이션은 불필요(exp_rate·character_level 컬럼 이미 존재). 커밋·PR 전 별도 code-reviewer 승인 패스. 완료 후 spike/preview_leaderboard.py 로 실데이터 미리보기 PNG 재생성.

---

## 1. 배경 / 현재 상태 (as-is, 정확한 참조)

피드백(사용자 제공 이미지 검토 결과):
1. `leaderboard_table.png` 의 **전체 순위 컬럼이 불필요**.
2. `leaderboard_table.png` **"어제 획득" 컬럼명이 부적절**.
3. `leaderboard_graph.png` **y축이 비직관적**(절대 Δ 경험치 억/조, 이상치 1개가 축 지배, 레벨 다른 유저끼리 불공정). 첨부 예시(`그래프_예시.png`)는 % 기반 — 그 형식을 그대로 베끼지 말고, 현 multi-user 라인 형식을 유지하며 비교가 잘 되는 대안을 적용.

현재 코드:
- 표 [leaderboard_image.py:44-59](../maple_mate/bot/leaderboard_image.py#L44) `render_table` — `headers = ["순위","닉네임","레벨","어제 획득","전체 순위"]`, `_world_rank_text`([:37](../maple_mate/bot/leaderboard_image.py#L37))로 마지막 컬럼.
- 그래프 [leaderboard_image.py:98](../maple_mate/bot/leaderboard_image.py#L98) `render_delta_graph` — y=절대 Δ 경험치, `_nice_max`+`format_eok` 라벨. 입력 `series: dict[닉 → [(date, Δ_int|None)]]`.
- 시계열 소스 [service.py:320](../maple_mate/leaderboard/service.py#L320) `history_deltas` — `total_exp` 인접일 차(절대 Δ).
- 백필 [service.py:236](../maple_mate/leaderboard/service.py#L236) — `_fetch_one_day(..., with_exp_rate=False)` (과거일 ranking-only, exp_rate=None. [#19](https://github.com/mindongdong/maple-mate/pull/19) 지연 최적화).
- `_fetch_one_day` [service.py:~141](../maple_mate/leaderboard/service.py#L141) — `*, with_exp_rate: bool = True` 인자. True 면 `_fetch_exp_rate`(character/basic best-effort)로 exp_rate 보강.
- 스냅샷 [models.py](../maple_mate/leaderboard/models.py) `ExpSnapshot` — `character_level`(NOT NULL), `total_exp`(BigInt), `world_rank`(nullable), **`exp_rate`(Float, nullable)** 이미 존재. ⇒ **이번 개선에 스키마 변경/마이그레이션 없음.**
- `build_payload` [broadcast.py:98-104](../maple_mate/leaderboard/broadcast.py#L98) — `history_deltas` 로 series 만들어 `render_delta_graph` 호출.

관련 ADR: [ADR-0005](adr/0005-exp-leaderboard-data-source.md)(ranking/overall 단일 소스, exp%는 character/basic best-effort). 도메인 용어: [CONTEXT.md](../CONTEXT.md)(경험치 리더보드·어제 Δ·랭킹 미등재).

## 2. 확정 결정 (그릴링 결과)

| # | 항목 | 결정 |
|---|---|---|
| F1 | 전체 순위 컬럼 | **제거**. 대체 없음 → 4컬럼(순위·닉네임·레벨(exp%)·하루 경험치). `world_rank` 는 스냅샷에 계속 저장(미표시). |
| F2 | "어제 획득" 컬럼명 | **"하루 경험치"**. 값은 절대 획득량(`+9351억`, `LeaderRow.delta` = total_exp Δ) 그대로 유지. |
| F3 | 그래프 y축 지표 | **7일 전(창 시작) 대비 진행량**. 지표 = 연속 진행도 `progress = 레벨 + exp%/100`(예: 287.67) 를 **각 라인의 창 내 첫 가용일=0 으로 정규화**해 그 이후 증가분만 표시. 단위 **%p**(100%p = 1레벨). |
| F3-a | 형식 | multi-user 라인 유지. 전원 0 출발 → 부채꼴. 기울기=그라인드 속도, 끝점=7일 총 진행량. |
| F3-b | 레벨업 처리 | 연속값이라 **톱니/리셋 없음** → `Lv↑` 마커 불필요(이전 라운드 파생결정 폐기). |
| F3-c | y축 스케일 | `0 → 최대 진행량`(여백 포함) 자동. 별도 줌 트릭 불필요(전원 0 출발이라 자연 분리). |
| F3-d | 범례 | 색 칩 + 닉 + **유저별 일평균 %/일**(예: `손바 · 평균 1.3%/일`). |
| F3-e | 제목 | "최근 7일 경험치 진행량 (7일 전 대비)". |
| D1 | 데이터 | 그래프엔 일별 `(레벨, exp%)` 필요 → **백필이 날마다 character/basic 도 수집**(아래 §3-1). 매일 잡은 이미 D-1 basic 수집 중(변화 없음). |

**파생 결정(질문 없이 확정):**
- **베이스라인:** 각 라인은 창(최근 7일) 내 **첫 데이터 보유일을 0** 으로. 보통 D-7, 결손 시 그 유저의 첫 가용일(불균형 가능 — 완전 백필 시 전원 D-7 정렬). 데이터 0개 유저는 그래프에서 제외.
- **단위 표기:** %p. 다레벨 상승으로 100%p 초과 가능(예: `+230%`) — 라벨은 그대로 % 로(축 자동 스케일이 흡수). 끝점/축이 너무 크면 정수 % 반올림.
- **일평균 계산:** 창 구간 총 진행 %p ÷ 데이터 있는 일수(gap). progress 가 연속이라 레벨업도 자연 합산.
- **표 "하루 경험치":** 계속 `total_exp` Δ(절대, 억/만, `_delta_text`). 그래프(%) 와 다른 보완 렌즈. `history_deltas` 는 표/`build_rows` 경로에서 계속 쓰이지 않음 — 표 Δ 는 `LeaderRow.delta`(build_rows 산출). `history_deltas` 자체는 그래프에서 제거되며 **다른 사용처 없으면 삭제 가능**(확인 후 정리).

## 3. 빌드 단위 (의존 순서)

### 1. `service.py` — 데이터 파이프라인
- `backfill`: `_fetch_one_day(..., with_exp_rate=True)` 로 되돌린다(과거일도 character/basic 수집 → 일별 exp_rate 채움). ⚠️ **백필 넥슨 콜 약 2배**(N명×8일×2콜, 앱키 0.25s 버킷, defer 로 커버, 길드당 1회성) — [#19](https://github.com/mindongdong/maple-mate/pull/19) 지연 최적화의 의도적 일부 되돌림. `with_exp_rate` 인자는 다른 호출자 없으면 vestigial → 제거 또는 유지(판단).
- 신규 `async def history_progress(session_factory, guild_id, nicknames, today, *, days=7) -> dict[str, list[tuple[date, float | None]]]` — 닉 → [(날짜, `progress=레벨+exp%/100`|None)]. 표시 구간 `today-(days-1)..today`. 각 날 progress 는 그날 스냅샷의 `character_level + (exp_rate/100)`; `exp_rate`(또는 스냅샷) 없으면 None. (`history_deltas` 의 7일 창 로직 참고하되 Δ 가 아닌 절대 progress 반환 — 정규화·일평균은 렌더러가.)
- `history_deltas` 가 그래프 외 사용처 없으면 제거(표는 `build_rows` 의 `LeaderRow.delta` 사용).
- *검증: history_progress 가 (레벨,exp%)→progress 환산·결손 None·전원 닉 포함을 단위테스트. 픽스처 스파이크값 재현.*

### 2. `leaderboard_image.py` — 표 렌더
- `render_table`: `headers`/`aligns`/`table_rows` 에서 **전체 순위 제거** → `["순위","닉네임","레벨","하루 경험치"]`, aligns `["center","left","left","right"]`. 헤더 "어제 획득"→**"하루 경험치"**. `_world_rank_text` 삭제(미사용).
- *검증: 4컬럼·헤더명 단위테스트.*

### 3. `leaderboard_image.py` — 그래프 렌더 (재작성)
- `render_delta_graph` → `render_progress_graph(series, ref_date)` (의미 변경, 이름 변경 권장). 입력 `series: dict[닉 → [(date, progress|None)]]`.
  - 각 라인: 창 내 첫 non-None progress 를 baseline 으로 빼서 `(progress-baseline)*100` = %p 로 변환(0 출발). None 구간 선 끊김.
  - y축: 0 → `_nice_max(max %p)`(기존 `_nice_max` 재사용), 라벨 `+N%`(정수). x축 날짜 MM/DD.
  - 범례: 닉 + 일평균 %/일 = `끝점 %p ÷ (데이터 gap 수)` 또는 총 진행/일수. `_draw_legend` 확장.
  - 제목 "최근 7일 경험치 진행량 (7일 전 대비)". 빈/단일 유저 가드 유지. **레벨업 마커 없음.**
- *검증: 정규화(0 출발)·%p 변환·빈/단일 유저·일평균 표기 스모크 + 값 단위테스트.*

### 4. `broadcast.py` — 배선
- `build_payload`: 그래프 series 소스를 `history_deltas` → `history_progress` 로 교체, `render_delta_graph` → `render_progress_graph` 호출. 표 경로(build_rows·render_table)는 그대로.
- *검증: 기존 build_payload/job 테스트 통과(필요시 series 형태 갱신).*

### 5. 테스트 갱신 (§4)

## 4. 테스트 계획

- ⚠️ **반전 필수:** [tests/test_leaderboard_service.py:418](../tests/test_leaderboard_service.py#L418) `test_backfill_fetches_ranking_only_skips_basic` — 백필이 이제 basic 을 **호출함**. 테스트를 "backfill 이 ranking+basic 둘 다 호출, 적재 exp_rate 채워짐"으로 반전(`_RecordingNexon.basic_calls` 가 8회).
- 표 테스트(`tests/test_leaderboard_image.py`·`test_leaderboard_commands.py`의 라벨 단언): 컬럼 4개·"하루 경험치"·전체순위 없음으로 갱신. `LeaderRow(world_rank=...)` 픽스처는 둬도 무방(미표시).
- 그래프 테스트: 신규 `render_progress_graph` 스모크(빈/단일/정규화 0출발/None구간) + `history_progress` 변환·일평균 단위테스트(스파이크 (레벨,exp%) 픽스처).
- 회귀: `pytest -m 'not live'` 전부 통과, ruff clean. 마이그레이션 없음 → alembic 변경 없음.

## 5. 검증 / 미리보기

- 실데이터 미리보기 스크립트 [spike/preview_leaderboard.py](../spike/preview_leaderboard.py)(gitignore) 가 실제 렌더 함수를 호출해 `/tmp/leaderboard_*.png` 생성. 이번 변경 후 **이 스크립트도 신규 `render_progress_graph` + `history_progress` 형태로 갱신**해 재생성(`PYTHONPATH=. .venv/bin/python spike/preview_leaderboard.py`). 손바·라딘라면(spike/.env) 실데이터로 표 4컬럼·진행량 그래프 눈 확인.
- 라이브: 배포 후 `/경험치` 로 디스코드 실제 출력 1회 확인(등재 2명 이상 전제).

## 6. 잔류 / 주의

- **백필 지연 2배**(D1) — 친구 그룹 규모에선 허용(defer·1회성). 대규모 길드면 백로그.
- **%p > 100 표기** — 저렙 다레벨 상승 시. 축 자동 스케일이 흡수하나 라벨이 `+200%` 식으로 커질 수 있음(정상).
- **베이스라인 불균형** — 일부 유저가 D-7 스냅샷 결손 시 그 유저만 첫 가용일=0 → 관측 구간이 짧아 비교가 약간 불공정. 완전 백필 시 해소.
- **그래프 ↔ 표 단위 혼재** — 표 "하루 경험치"=절대(억/만), 그래프=%p. 의도된 보완 관계(표=구체 획득량, 그래프=레벨 진행 비교). 혼동되면 후속 라운드에서 표도 %p 병기 검토.
- `history_deltas` 정리 여부는 그래프 전환 후 사용처 grep 으로 확정.

## 7. 스코프 밖 (보류)

- 예시(`그래프_예시.png`)의 단일유저 막대·툴팁·예상 레벨업 날짜 형태 — multi-user 라인 유지 결정으로 제외.
- 표 "하루 경험치" %p 전환 — 이번엔 절대량 유지로 확정(F2).
- 절대 레벨 진행도(287.67) 표시 — 기준시점 대비 정규화로 확정(F3).
