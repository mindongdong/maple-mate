# 튜토리얼 6·9 스크린 디스코드 CSS 애니메이션 작업 지시서

> `/tutorial` 6번째("캐릭터 등록으로 열리는 명령들")·9번째("API 키로 열리는 명령들") 스크린의
> 미디어를 실녹화 영상(폐기) 대신 **디스코드 메시지 스타일 CSS 애니메이션**으로 교체한다.
> 실제 봇을 쓰는 듯한 느낌 — 파라미터가 무엇이 있고 어떻게 채우는지 보이도록 느리게,
> 전송 직전엔 방문자가 직접 전송 버튼을 누르는 인터랙티브 게이트.
> grill 세션(2026-07-04)에서 모든 갈림길 결정 완료.
>
> **먼저 읽을 것:** 이 문서 → [tutorial-work-order.md](./tutorial-work-order.md)(스텝 구조) →
> [website-handoff.md](./website-handoff.md)(site/ 함정·검증 루틴).

---

## 0. 요약

- **무엇을:** `tutorial-steps.tsx` 스크린 6·9의 media를 `type: 'anim'`으로 교체.
  신규 컴포넌트 `CommandSequenceDemo`가 대본(script) props를 받아 두 스크린을 렌더.
- **느낌:** 스크린 1 `DiscordDemo`(순차 등장·타이핑 도트·루프) + 스크린 3 `SlashDemo`
  (명령 팝업 UI)를 합친 것 — 입력창에 `/` 타이핑 → 명령 팝업 → 파라미터 칩 → 값 채움 →
  **전송 버튼 게이트(클릭 대기)** → 봇 타이핑 → 결과 PNG.
- **결과물:** 봇 렌더러 진짜 PNG(기존 shots 재사용 + 변형 4종 신규 생성).
- **봇 코드 무변경, 사이트 전용 단일 PR.**

## 1. 사용자 요청 원문 요지

- 메인페이지(랜딩 히어로)에 이미 구현한 디스코드 대화 디자인을 그대로 차용.
- 스크린 3("채팅창에 / 만 입력하면 시작돼요") 애니메이션도 차용해 **실사용 느낌** 극대화.
- 튜토리얼인 만큼 **명령어 파라미터가 무엇이 있고 어떻게 채우는지 보이게 속도를 느리게**.
- 시나리오: 모든 기능을 한 번씩. 대상 지정 파라미터가 있는 명령은 무인자 실행 → 대상 지정
  실행 순서로. 그 외 파라미터는 필수만 입력하되, 옵션은 안 채워도 되고 채워도 됨을 보여줄 것.
- (후속 추가) 파라미터가 다 채워지면 **전송 버튼을 누르라고 떠서** 방문자가 직접 누르면
  봇 결과물이 뜨는 인터랙티브 구성.

## 2. 확정 결정 (grill 2026-07-04, 10건)

| # | 갈림길 | 결정 |
|---|---|---|
| 1 | 시나리오 분량 | **느린 풀 시퀀스 페어는 스크린당 대표 1개**, 나머지 명령은 빠른 실행(메시지→결과만). 전 명령 칩 커버 유지 |
| 2 | 느린 대표 명령 | S6 = **/경험치 3회**(무인자→`모드:챌린저스`→`유저1` 지정) · S9 = **/스타포스 2회**(무인자→`대상1` 지정) |
| 3 | 입력 재현 깊이 | **풀 시퀀스** — `/` 타이핑→명령 팝업→선택→파라미터 칩(전체 목록)→값 채움(choice/멤버 선택)→전송. 빠른 실행은 입력 장면 없음 |
| 4 | 결과물 표현 | **봇 렌더러 진짜 PNG** — `render_demo_shots.py` 확장해 변형 4종 신규 생성, 응답 = CSS 임베드 + 첨부 PNG 룩 |
| 5 | 타이밍 | 느린 단계: 팝업 1.2s·칩 목록 2s·값 선택 1.5s·봇 도트 1s·결과 3.5s (1회≈9~10s). 빠른 실행 1회≈2.2s. 루프 끝 3s 멈춤. **S6 루프≈45s·S9≈30s** |
| 6 | 인터랙티브 게이트 | **느린 실행 전부** 전송 버튼(➤ 펄스+힌트) 클릭 대기, **미클릭 10초 후 자동 전송**(루프 정지 방지). 빠른 실행은 자동 |
| 7 | 목업 데이터 | (후속 확장) **시나리오 전 명령을 QA 하네스로 실제 실행**(로컬 도커 실DB + 실넥슨 API)해 렌더러 입력·임베드를 캡처, 실닉·실ID **가명화 완료** JSON 픽스처 = `site/scripts/fixtures/demo/*.json` (11런, 2026-07-04 추출·커밋됨) |
| 8 | 컴포넌트 구조 | **신규 파일 `site/components/CommandSequenceDemo.tsx`** — DiscordDemo는 무변경(랜딩 회귀 위험 0), `.mm-chat-*`·팝업 룩 재사용 |
| 9 | 잔재 정리 | `.claude/skills/remotion-best-practices/` + `docs/plug-in-open.mp4` **둘 다 삭제**(폐기된 실녹화 계획 잔재, 둘 다 미추적이라 로컬 삭제로 끝) |
| 10 | 카피 정합 | 무인자 문구 = **"본인 포함 랜덤 최대 10명"**(PR #58/#59, ADR-0008 개정). 핸드오프 §4의 "레벨 상위 10명"은 구식 — 사용 금지 |

## 3. 확정 대본

### 스크린 6 (7회 실행 · 느린 3 + 빠른 4)

| # | 속도 | 입력 | 응답 |
|---|---|---|---|
| 1 | 느림 | `/` 타이핑→팝업→**/경험치** 선택→칩 `[유저1~5·모드]` 표시→**안 채우고** 게이트→전송 | Top10 임베드(CSS) + `exp.png` — 옵션은 안 채워도 됨 |
| 2 | 느림 | 칩에서 `모드` 선택→선택지 `본서버/챌린저스`→**챌린저스**→게이트→전송 | 챌린저스 리더보드 임베드 + `exp-challengers.png`(신규) |
| 3 | 느림 | 칩에서 `유저1` 선택→멤버 목록→**@지훈**→게이트→전송 | 지정 유저 그래프 `exp-target.png`(신규) |
| 4 | 빠름 | `/스펙 유저1:@수아 유저2:@지훈 유저3:@민준` | `spec.png` (유저1 필수 표현) |
| 5 | 빠름 | `/아이템 부위:무기` | `item.png` (필수 파라미터만) |
| 6 | 빠름 | `/유니온` | `union.png` |
| 7 | 빠름 | `/내캐릭터 스펙` | `mychar-spec.png`(신규) |

### 스크린 9 (4회 실행 · 느린 2 + 빠른 2)

| # | 속도 | 입력 | 응답 |
|---|---|---|---|
| 1 | 느림 | `/` 타이핑→팝업→**/스타포스** 선택→칩 `[기간·시작일·종료일·대상1~5]`→안 채우고 게이트→전송 | 랜덤 10명 운지수 `starforce.png` |
| 2 | 느림 | 칩에서 `대상1`→멤버 목록→**@수아**→게이트→전송 | `starforce-target.png`(신규) |
| 3 | 빠름 | `/잠재 기간:최근30일` | `potential.png` (옵션 채워도 됨 예시) |
| 4 | 빠름 | `/스케줄러` | `scheduler.png` + 👁 "이 메시지는 당신만 볼 수 있어요"(EphemeralNote) |

공통: 루프 = 마지막 결과 3s 멈춤 → 처음부터. 표의 `*.png`는 §4-2의 픽스처 기반
재생성본(demo-*)을 의미. 캐스트 = 유저 지훈·수아·민준 + 캐릭터 가명(본서버:
홍길동전사·불꽃아크·바람궁수·이글루법사·캐논슈터·나이트로드 / 챌린저스: 번개해적·
달빛기사·눈꽃마법사) — 픽스처에 이미 이 가명으로 박혀 있음.

## 4. 설계

### 4-1. `CommandSequenceDemo.tsx` (신규)

- **대본 타입(개념):** `run = { speed: 'slow'|'fast', cmd, params: [{ name, value?, pick?: 'choice'|'member'|'skip' }], reply: ReactNode }` — S6·S9 대본은 이 파일 안(또는 인접 상수)에 두되, ⚠️ `{ name: ..., visibility: ..., label: ... }` 리터럴 패턴 금지(§5-1).
- **상태머신(느린 실행):** `typing-slash → popup → select-cmd → chips → fill(반복) → await-send(게이트, 10s 타임아웃) → sent → bot-typing → result-dwell → 다음 run`. 빠른 실행은 `sent → bot-typing(0.5s) → result-dwell(1.1s)`만.
- **게이트:** 입력바 우측 ➤ 버튼 펄스 + "눌러서 전송해 보세요" 힌트. 클릭 즉시 전송, 10초 경과 시 자동. `aria-hidden` 장식 패널이지만 버튼만은 실제 `<button>`(키보드 접근).
- **prefers-reduced-motion:** 애니·게이트 없이 **정적 전체 표시**(DiscordDemo 패턴 — 패널 overflow 클립으로 마지막 대화만 보임).
- **룩 재사용:** 채팅 = `.mm-chat-*`(hero.css) + `.mm-tut-media .mm-chat*` 오버라이드(tutorial.css), 팝업 = SlashDemo의 `.mm-tut-popup*`, 입력바 = `.mm-tut-input`. 대화가 길어 높이 460px·페이드 마스크 값 재조정 가능성 있음(§5-2).

### 4-2. 데모 PNG — 실데이터 픽스처 기반 전량 생성 (`render_demo_shots.py` 확장)

**시나리오 11런의 결과 PNG 전부**를 `site/scripts/fixtures/demo/<run>.json`에서 복원해 생성한다
(기존 shots PNG 재사용 아님 — 결정 7 확장으로 데모 애니의 결과물은 전부 실데이터 기반).

- 픽스처 = 실행 당시 **렌더러에 들어간 인자 그대로**: `renders[].args`(dataclass는
  `__type` 마커 — ItemCard·Homework 등으로 재구성, `__bytes_b64`는 base64 디코드(아이콘 PNG),
  날짜는 ISO 문자열) + `messages[]`(임베드 dict·content·ephemeral — CSS 임베드 카피의 정본).
- 렌더러 매핑: exp_* → `render_progress_graph` · spec/union/starforce/potential/mychar →
  `render_table_image`(comparison 경유 headers·rows·aligns) · item_weapon →
  `render_item_cards` · scheduler → `render_scheduler_card`(캐릭 3장 캡처 중 1장만 사용).
- 파일명·위치는 구현 재량(권장: `site/public/shots/demo-<run>.png`). 생성 후 커밋
  (빌드에 파이썬 불필요 원칙 유지). 기존 shots 7종은 다른 페이지가 쓰므로 무변경.
- 추출 스크립트 = `spike/extract_demo_fixtures.py` — **spike/는 gitignore라 추출 원본
  머신에만 존재**. 픽스처 재추출은 도커+실키가 있는 원본 머신에서만 가능(작업 세션에서는 불필요).

### 4-3. `tutorial-steps.tsx` 변경

- 스크린 6·9의 `media`만 `{ type: 'anim', node: <CommandSequenceDemo script={...} /> }`로 교체.
  chips·visibility·sub 카피는 무변경. 다른 영상 슬롯 5종(스크린 2·3·5·7·8)도 무변경.

## 5. 함정 (핸드오프 §5 계승 + 이번 세션 추가)

1. **드리프트 가드**가 `tutorial-steps.tsx`를 정규식으로 읽음 — 명령 객체 리터럴 형식·키 순서
   불변, 데모 대본 코드에 이 패턴 금지(CommandSequenceDemo 쪽 tsx는 스캔 대상 아님).
2. `.mm-chat-body`는 히어로 공용 — 랜딩을 건드리지 말고 `.mm-tut-media .mm-chat*`
   오버라이드로만. 새 팝업·입력바·게이트 스타일은 `.mm-tut-*`에.
3. 기존 shots PNG(spec·exp·starforce·scheduler)는 이번에 채팅 버블 안 첨부 이미지로
   **계속 사용** — ShotCollage에서 빠져도 삭제 금지(getting-started.mdx·CommandGroup도 사용).
   ShotCollage 컴포넌트 자체도 스크린 2가 계속 사용하므로 유지.
4. 픽스처는 이미 가명화 완료(실닉·실ID·ocid 누수 검사 통과). **새로 데이터를 추출하거나
   실닉을 다시 들여오지 말 것** — 사이트 실데이터 금지 원칙. 픽스처의 가명을 그대로 사용.
5. 미커밋 잡파일(README.md·log.txt·기댓값/ 등) 존재 — 스테이징 외과적으로.
   로컬 :3000 prod 서버 주의 — 서빙 중 `.next` 위에 dev 금지, 검증은 재빌드+재시작.
6. 결정 9의 삭제 2건은 **미추적**이라 커밋 불요 — `rm`만.

## 6. 검증

1. `cd site && npm run build && node scripts/check-command-drift.mjs`
2. 레포 루트 pytest 전체(사이트 드리프트 테스트 포함)
3. 헤드리스 크롬 `--virtual-time-budget` 단계별 캡처 — 팝업/칩/게이트/결과 각 국면 +
   게이트 10s 자동 전송 확인(CDP 클릭으로 수동 전송도 1회) + 모바일 500px
4. reduced-motion 에뮬레이션 1샷(정적 표시)
5. 라이트/다크 테마 눈확인

## 7. 커밋·PR

- 단일 PR(사이트 전용): 한국어 conventional·squash 관행. 논리 커밋 분리 권장 —
  ① 렌더 스크립트 확장+신규 PNG ② CommandSequenceDemo+steps 교체+css ③ 문서(as-built).
- 머지 후 Vercel 자동배포로 완결(봇 재배포 불필요).
