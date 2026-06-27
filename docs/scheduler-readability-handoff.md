# 핸드오프 — 스케줄러 임베드 가독성 미세조정 (이어서)

> **목적:** 다른 세션에서 이 작업을 이어받아 **커밋·PR·배포·라이브 확인**을 마치거나, 추가 가독성 개선을 계속하기 위한 맥락 인계.
> **선행 맥락:** 스케줄러 알리미 기능 자체 = [ADR-0012](adr/0012-scheduler-reminder-per-user-dm.md), 표시 재설계(필드 파생 카테고리) = [ADR-0013](adr/0013-scheduler-field-derived-categories.md), 빌드 단위 = [scheduler-work-order.md](scheduler-work-order.md), API = [api/scheduler.md](api/scheduler.md). 이 문서는 그 위에 얹은 **표시 미세조정**이다.

## 0. 한 줄 목표

`/스케줄러`·스케줄러 알림 DM 임베드의 **가독성**을 라이브 피드백으로 다듬는다. **데이터·전달 로직은 불변, 표시(렌더)만** 손본다.

## 1. 지금 상태 (어디까지 됐나)

- `/grill-me` 그릴링으로 라이브 DM 피드백 4건을 결정화 → **구현·테스트·오프라인 렌더 검증 완료**.
- **위치 = `main` 작업 트리, 미커밋.** 별도 브랜치 **아직 안 땀**. (⚠️ §6 커밋 전략 필독 — 작업 트리에 무관한 잔존 변경이 섞여 있음.)
- **634 테스트 그린**, `ruff check` clean. 오프라인 임베드 렌더로 4건 모두 눈 확인.
- **⚠️ 아직 실제 디스코드 DM 으로는 눈으로 못 봤다.** 다음 세션 우선 작업 후보 = 배포 후 라이브 1회 확인.

## 2. 그릴링 결정 4건 (= 이번 변경의 전부)

라이브 DM 스크린샷에서 사용자가 짚은 4가지:

1. **회수 → 콘텐츠 (필드 병합).** `🎯 일일/주간 회수`(CAT_COUNT, 몬스터파크 회수형) **필드를 폐기**하고 `📋 일일 콘텐츠`·`⚔️ 주간 콘텐츠`(CAT_BINARY)에 **병합**. "회수"라는 단어가 임베드에서 전면 사라짐.
   - **왜 병합인가:** 단순 라벨 변경은 기존 `📋 일일 콘텐츠`(완료형)와 **이름 충돌**(잠복 버그 — 한 캐릭에 회수형+완료형이 동시에 있으면 "일일 콘텐츠" 필드가 2개). `content_field_value`가 이미 `🟡게이지 → ⬜미완료 → ✅완료`를 **한 본문에서** 처리하므로, `by_category(COUNT) + by_category(BINARY)` concat 한 줄로 자연 병합되고 충돌이 영구 소멸.
   - **⚠️ 중요 — 데이터 카테고리는 안 죽었다.** `CAT_COUNT`/`in_progress`/회수형 게이지 로직은 그대로다. **바뀐 건 임베드 필드 그루핑뿐**(COUNT 항목이 별도 회수 필드 대신 콘텐츠 필드 안에서 렌더). 파싱·`done`·`remaining_total` 전부 불변.
2. **헤더 `남은 N` 제거.** 필드 헤더 `라벨 — 남은 N  done/total` → `라벨 — done/total`. `남은 N`이 `done/total` 옆에서 중복이라 제거. **부제 헤드라인 `🔥 남은 숙제 N개 (done/total 완료)`는 유지**(중복 N/M 없는 콜투액션 — 사용자가 "필드 헤더에서만" 명시).
3. ~~빈 줄 세로 간격(`_SEP="\n\n"`)~~ **시도 → 즉시 철회.** "간격이 너무 크다"는 피드백으로 `_SEP="\n"`(단일 줄바꿈) 복귀. **디스코드는 `\n`(촘촘) / `\n\n`(빈 줄) 둘뿐이고 중간 간격이 불가**하므로, ⬜ 체크박스가 세로로 다소 촘촘한 건 감수하기로 확정. **이 방향은 막다른 길 — 다시 건드리지 말 것.**
4. **완료 표시 한 줄씩 `✅ 이름`.** 접힌 `✅ 완료 N개 · A · B · C…`(` · ` 런온) → 완료 항목마다 `✅ 이름` 한 줄씩(⬜ 미완료와 거울 대칭). 보스도 `✅ 이름(난이도)`. "완료/처치 N개" 카운트 줄은 제거(헤더 `done/total`에 이미 있음).
   - **설계 긴장 인지:** ADR-0013의 **todo-first**(완료=노이즈 → 한 줄 접기) 철학과 충돌. 사용자가 "완료한 게 뭔지 잘 보이게"를 우선해 명시적으로 펼치기를 택함. 완료는 미완료 **아래**에 오므로 "할 일"은 여전히 위에서 먼저 보임. 길면 `section_text`가 1024에서 `…외 N개` 클램프(완료가 뒤라 먼저 잘림 — 의도대로).

## 3. As-built 렌더 (현재 출력)

회수형(몬파)+완료형(에픽던전) 일일 + 보스 섞인 캐릭 기준:

```
📝 일일 퀘스트 — 2/3
⬜ 카르시온 복구 지원
✅ 오디움 일대 탐사
✅ 도원경 오염 정화
----
📋 일일 콘텐츠 — 1/2              ← 회수(몬파)+완료형(에픽던전) 병합, '회수' 라벨 없음
🟡 몬스터파크 `2/14`
✅ 에픽 던전 : 하이마운틴
----
🗡 주간 보스 — 1/5  (처치 8/12)    ← 헤더에 '남은 N' 없음
⬜ 스우(익스트림)
⬜ 카링(이지)
⬜ 최초의 대적자(노멀)
⬜ 찬란한 흉성(노멀)
✅ 검은 마법사(하드)              ← 완료 보스도 한 줄씩 + 난이도
```

부제(불변): `Lv.285 · 스카니아` / `🔥 남은 숙제 7개 (5/12 완료)`.

## 4. 정확한 변경 내역 (파일·함수)

`git diff --stat` (스케줄러 관련만): broadcast.py / service.py / test_scheduler_embed.py / test_scheduler_service.py — 4 files, +43 / −61.

**`maple_mate/scheduler/broadcast.py`**
- `_content_field` 헤더: `f"{label} — 남은 {total-done}  {done}/{total}"` → `f"{label} — {done}/{total}"`.
- `_boss_field` 헤더: 동일하게 `남은 N` 제거(`(처치 c/12)` 부가는 유지).
- `build_embed`: `🎯 일일 회수`·`🎯 주간 회수` 필드 호출 **삭제**. 일일 콘텐츠 = `by_category(daily, CAT_COUNT) + by_category(daily, CAT_BINARY)`, 주간 콘텐츠 = `by_category(weekly, CAT_BINARY) + by_category(weekly, CAT_COUNT)`.

**`maple_mate/scheduler/service.py`**
- `_SEP = "\n"` (변경 없음 — `\n\n` 시도 후 복귀).
- `content_field_value`: 완료 블록 `✅ 완료 N개 · {join_clamp(...)}` 한 줄 → `for c in done: lines.append(f"✅ {truncate(c.name)}")` 한 줄씩.
- `boss_cycle_value`: 완료 블록 `✅ 처치 N개 · {join_clamp(...)}` → 한 줄씩. 신규 헬퍼 `_boss_line(box, b)`(`⬜`/`✅` 공용, 난이도 괄호 포함)로 미처치·처치 루프 공유.
- **삭제(고아):** `join_clamp` 함수 + `_DONE_BUDGET` 상수 (완료/처치 한 줄 접기 전용이었음 → per-line 전환으로 미사용). surgical-changes 규칙.

**테스트** (`tests/test_scheduler_embed.py`, `tests/test_scheduler_service.py`)
- 임베드: `🎯 일일 회수` 단언 → `📋 일일 콘텐츠`(병합), 헤더 `남은 N` 제거 단언(`"남은" not in f.name`), 완료 `✅ 완료 1개 · 리멘` → `✅ 리멘`.
- 서비스: `content_field_value`/`boss_cycle_value` per-line 단언, `test_content_field_value_all_done_per_line`(이름 변경)=`"✅ a\n✅ b"`, 보스 `✅ 자쿰(카오스)`. `join_clamp` import·`test_join_clamp_collapses_overflow` **삭제**. `section_text` 단언은 `"a\nb\nc"` 그대로.

## 5. 검증 상태

- `python -m pytest -q` → **634 passed**, 1 deselected.
- `python -m ruff check maple_mate/scheduler/ tests/test_scheduler_*.py` → clean.
- 오프라인 렌더 1케이스 눈 확인(§3). **라이브 디스코드 DM 미확인.**
- 재현용 렌더 스니펫은 §3 케이스를 `build_embed`에 넣어 `for f in e.fields: print(f.name, f.value)` 로 즉시 찍힌다.

## 6. ⚠️ 커밋 전략 (이 레포 고유 — 반드시 지킬 것)

작업 트리에 **이전 세션들의 무관한 미커밋/언트랙 변경이 잔존**한다 (이번 작업과 무관, **건드리지 말 것**):
- `M README.md`
- `?? docs/adr/0010-deployment-provider-portability.md`, `?? docs/provider-cutover-runbook.md`, `?? railway.json`, `?? starforce-simulator-system.md`, `?? 기댓값/`

이 레포의 확립된 패턴(메모리 `scheduler-reminder-decisions`):
1. `origin/main` 기준으로 **새 브랜치**를 딴다 (예: `feat/scheduler-readability`).
2. **스케줄러 관련 hunk만 외과적으로 스테이징** — `git add maple_mate/scheduler/broadcast.py maple_mate/scheduler/service.py tests/test_scheduler_embed.py tests/test_scheduler_service.py` (README 등 잔존 노이즈 절대 포함 금지).
3. 논리 단위 커밋(표시 변경 1 + 문서 동기화 1 권장) → push → squash PR.
4. CI(lint/test/migrations) 그린 확인 후 머지.

## 7. 남은 일 (To-Do)

- [ ] **문서 동기화** (이번 변경으로 stale — 코드와 어긋남):
  - `docs/scheduler-work-order.md` L38, L55–56, L70–71 — `🎯 일일 회수` 필드·`남은 N` 헤더·`완료 N개 · 이름` 표기 갱신.
  - `docs/adr/0013-scheduler-field-derived-categories.md` — **개정 노트 추가**(기존 2026-06-27 개정 노트와 같은 양식): ① COUNT(회수형) 필드를 콘텐츠 필드에 **표시 병합**(데이터 카테고리는 불변, 라벨 충돌 해소), ② 헤더 `남은 N` 제거(부제는 유지), ③ 완료 `✅ 이름` 한 줄씩(todo-first 완화), ④ `_SEP` 빈 줄 시도→철회. L28/L35–37/L40 표기 갱신.
  - `CONTEXT.md` L23 — **판단 필요**: 여기 "회수형(몬스터파크 n/m)"은 **도메인 데이터 카테고리** 설명이라 여전히 정확(파싱 레이어 불변). 임베드 필드명이 아니므로 **수정 불필요할 가능성 큼**. 다음 세션이 확인만.
  - `docs/api-verification-plan.md` — `🎯` 언급 있으면 점검(저우선).
- [ ] **커밋·PR** (§6 전략대로).
- [ ] **배포 반영 후 라이브 확인** — 실제 `/스케줄러` 온디맨드 + 정각 DM 1회로 4건 가독성 눈 확인.
- [ ] (선택) 추가 가독성 후보: **주간 보스 난이도별 묶기**(메모리 기존 열린 후보). 단 §2-3 빈 줄 간격은 막다른 길이라 재시도 금지.

## 8. 관련 문서·메모리

- ADR: [0012](adr/0012-scheduler-reminder-per-user-dm.md)(구독), [0013](adr/0013-scheduler-field-derived-categories.md)(필드 파생 카테고리 — **이번 변경으로 일부 stale**).
- 선행 핸드오프: [scheduler-feature-handoff.md](scheduler-feature-handoff.md), [scheduler-design-handoff.md](scheduler-design-handoff.md)(§2~4 요약형은 이미 폐기됨).
- 메모리: `scheduler-reminder-decisions`(말미에 2026-06-28 미세조정 항목 추가됨).
