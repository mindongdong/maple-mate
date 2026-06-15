# 작업 결과 (As-built) — 경험치 리더보드 표 폐기·레벨 추이 그래프

- **일자:** 2026-06-15
- **PR:** [#21](https://github.com/mindongdong/maple-mate/pull/21) (브랜치 `fix/leaderboard-ui-improvements`, main 기반)
- **관련:** [ADR-0006](adr/0006-exp-leaderboard-graph-only-matplotlib.md)(결정·대안·결과), [ADR-0005](adr/0005-exp-leaderboard-data-source.md)(데이터 소스 — 유지), [leaderboard-ui-improvements-work-order.md](leaderboard-ui-improvements-work-order.md)(1차 작업지시서 — 표시층은 본 라운드로 대체), [CONTEXT.md](../CONTEXT.md)(용어 갱신)

리더보드 출시 후 사용자 피드백을 **2라운드**로 반영했다. 1차는 작업지시서대로 표를 다듬고 그래프를 정규화 %p로 바꿨고, **2차에서 사용자 결정으로 표를 폐기하고 그래프 하나(matplotlib·절대 레벨 축)로 재설계**했다. 최종 산출물은 2차 기준이다.

## 1. 최종 산출물 (무엇이 나가나)

`/경험치`·매일 10시 발송 = **최근 7일 레벨 추이 그래프 PNG 1장**(등재 2명 이상일 때).

- **Y축 = 절대 연속 레벨** `character_level + exp%/100`(예: 287.69). 정규화 없음.
- **각 점에 `Lv.287 (69%)` 라벨** — 그날의 실제 레벨·경험치%.
- **범례에 유저별 일평균 %/일** = (끝−처음 가용 레벨)×100 ÷ 사이 일수(성장 속도).
- 데이터 0개 유저 제외, `None` 구간 선 끊김, 레벨업 마커 없음(연속값), 전원 데이터 없으면 안내 문구.
- 다크 팔레트·한글 폰트는 표 렌더(`table_image`)와 공유.

## 2. 1차 작업지시서와의 차이 (피벗)

| 항목 | 1차 작업지시서(계획) | 2차 최종(출시) |
|---|---|---|
| 표 | 4컬럼(순위·닉·레벨·하루 경험치)으로 정리 | **폐기** — 그래프만 |
| 그래프 Y축 | 7일 전 대비 진행량(%p) 정규화 부채꼴 | **절대 연속 레벨**(287→291) |
| 점 라벨 | 없음 | **모든 점에 `Lv.287 (69%)`** |
| 렌더 | PIL `ImageDraw` 직접 | **matplotlib**(OO `Figure`+`FigureCanvasAgg`) |
| 하루 경험치(절대 억) | 표에 유지 | **표시 제외**(데이터는 적재) |

(1차 데이터 파이프라인 — `history_deltas`→`history_progress`, backfill 의 일별 `exp_rate` 수집 — 은 그대로 유지.)

## 3. 변경 파일

- `maple_mate/bot/leaderboard_image.py` — **전면 재작성.** matplotlib `render_progress_graph` + 헬퍼(`_progress_label`·`_daily_average`·`_hex`·`_font`·`_to_png`). 표 코드(`render_table`·`_level_text`·`_delta_text`·`_TABLE_*`)·구 PIL 그래프(`_nice_max`·`_normalize_progress`·`_draw_legend`) 제거.
- `maple_mate/leaderboard/broadcast.py` — `LeaderboardPayload` 그래프 단일(`table_png` 제거), `to_files` 1파일, `_build_embed` 그래프 메인 이미지·문구 갱신, `build_payload` 그래프만 렌더(등재 게이트는 `build_rows` 유지).
- `maple_mate/leaderboard/commands.py` — 명령 설명·안내 문구 갱신.
- `maple_mate/leaderboard/service.py` — 2차에선 변경 없음(1차의 `history_progress`·`build_rows`·backfill 유지).
- `pyproject.toml`·`uv.lock` — `matplotlib>=3.8`(+numpy) 추가(`uv add`).
- 테스트: `test_leaderboard_image.py`(그래프 스모크 + `_progress_label`·`_daily_average` 단위테스트, 표 테스트 제거), `test_leaderboard_commands.py`(표 라벨 테스트 제거·payload 1파일), `test_leaderboard_job.py`(가짜 `to_files` 1파일).
- `spike/preview_leaderboard.py`(gitignore) — 그래프 단독 미리보기로 갱신.

## 4. 엣지케이스 / 잔류 (그대로 두기로 결정)

- **7일 미만 신규 캐릭:** 종합 랭킹 등재 이전 날짜는 스냅샷이 없어 **첫 등장일부터 부분 라인**으로 그려진다. 길드당 백필은 1회뿐이라 기존 길드의 새 멤버는 등록 후 하루 1점씩 누적. 가용 점 1개면 범례가 `평균 0.0%/일`(측정불가가 0으로 보이는 경미한 오해). → **정상 동작, 그대로 둠.**
- **절대 레벨 축의 레벨차 민감성:** 레벨이 크게 다른 캐릭(예: 신규 150 vs 메인 287)이 끼면 Y축이 벌어져 전원 라인이 납작해지고 기울기 비교가 약화된다(정규화 %p였다면 회피했을 부분). 친구 그룹 전원 고렙이라 실관측 드물어 **그대로 두기로 결정(2026-06-15).** 빈번해지면 옵션: 정규화 %p 회귀 / 레벨차 분리(ADR-0006 결과 참조).
- **Render 한글 폰트:** 컨테이너에 `fonts-nanum`이 있어야 그래프 한글이 정상 렌더. 미설치 시 tofu(□) + import 경고 로그. 표 렌더도 같은 폰트라 기존 배포에 있으면 무손상.
- **y축 라벨 버그픽스(commit `2d64d84`):** 친구 전원이 같은 레벨일 때 정수 반올림이 287.6·287.8 을 둘 다 `Lv.288`로 뭉개 오해를 줘 → `:g` 포매터 + 기본 AutoLocator로 `Lv.287.6` 구분(실데이터 미리보기에서 발견).

## 5. 검증

- `ruff check`/`format` clean + `pytest -m 'not live'` **503 통과**.
- 1차·2차 각각 **별도 `code-reviewer` 승인 패스**(self-approve 금지) → 모두 **APPROVE**, CRITICAL/HIGH 0건. 2차 권고(폰트 미발견 경고 로그·99% 클램프·시리즈 길이 계약 주석·게이트 주석) 반영.
- `spike/preview_leaderboard.py` 실데이터 PNG 재생성 눈 확인(한글 정상·절대 레벨축·점 라벨·일평균 범례). 신규 캐릭/저렙/1점 엣지케이스도 렌더 확인.
- 마이그레이션 없음(`exp_rate`·`character_level` 컬럼 기존재).

## 6. 운영자 남은 일

1. PR #21 머지 → 배포.
2. `/경험치` 디스코드 라이브 1회 확인(등재 2명 이상).
3. ⚠️ **Render 컨테이너 한글 폰트(`fonts-nanum`) 렌더 확인** — 미설치면 그래프 한글 tofu + 경고 로그. 표 렌더가 이미 동작 중이면 동일 폰트라 OK.
