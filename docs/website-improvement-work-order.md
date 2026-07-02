# 메이트 웹사이트 개선 작업 지시서 (다음 세션용)

> 이미 구축·머지된 웹사이트(`site/`)를 **콘텐츠·이미지·디자인 측면에서 개선**하는 작업 지시서.
> grill 세션(2026-07-01)에서 사용자와 4개 요청을 결정 트리로 확정한 결과다.
>
> **먼저 읽을 것:** 이 문서 → [website-handoff.md](./website-handoff.md)(구조·함정·배포) → [website-design-decisions.md](./website-design-decisions.md)(D1–D14, 단 아래 §8 개정 반영).

---

## 0. 요약

- 사용자 요청 4건: ① 개념 페이지 제거·분산 ② 실제 이미지 출력물 반영 ③ 개인정보/저작권 문구 정리 + 사이트 전반 간결화 ④ 박스 디자인 탈-클로드(좌측 색바 제거).
- grill로 **모든 갈림길을 결정 완료**(§2). 이 문서는 그 결정 + 파일 단위 작업 목록이다.
- 가장 큰 작업은 **② 방법 2**: 봇의 **실제 렌더러를 가짜 닉 픽스처로 호출해 진짜 PNG를 생성**하고 사이트에 `<img>`로 박는 것. 렌더러가 전부 순수 함수라 구현 난이도는 낮음(§4).
- 공개 게이팅은 기존 그대로: 봇 #36 배포 이후 홍보.

---

## 1. 배경 — 사용자 요청 원문 요지

1. **개념 페이지 삭제.** 개념 페이지 정보는 시작하기·명령어에 간략·직관적으로 분산.
2. **실제 결과물 반영.** 디스코드 캡처본이 아니라, "그 기능이 만드는 이미지 출력물" 형태를 검토해 웹에 반영. 지금은 대략적 예시만 있고 구체적 결과물이 없음.
3. **개인정보/저작권 정리.** "비공식 커뮤니티 봇" 표현이 부정확 → 넥슨 OpenAPI 조항상 필요한 것만. 사이트 전반에서 군더더기 제거, 핵심만 간결하게.
4. **탈-클로드 박스 디자인.** 박스 좌측의 색깔 띠가 클로드 특징 → 깔끔하고 클로드스럽지 않게.

---

## 2. 확정 결정 (grill 결과)

### ① 개념 페이지
- **개념 페이지(`content/concepts.mdx`) 통째 삭제.** 내용의 80%가 이미 시작하기/명령어에 중복.
- **챌린저스 서버 모드** = 유일한 고유 조각 → **명령어 인트로에 한 문장**으로 격하(별도 섹션·콜아웃 없음).
- **"스펙류/이력류" 조어는 사이트 전면에서 제거.** 메이플 유저면 다 아는 내용이라 조어 불필요. 평범한 말("스타포스·잠재 기록" 등)로 교체. ※ 그룹명 "이력"은 일반어라 유지.
- **API 키 "왜 필요한가"** = 시작하기 키등록 단계에 한 줄만("남의 이력을 몰래 보는 게 아니라 내 이력을 서버에서 함께 견주는 용도"). **보관·암호화 세부는 개인정보 페이지로 일원화.**

### ② 실제 이미지 출력 — **방법 2 채택**
- **봇의 실제 렌더러를 가짜 닉 픽스처로 호출 → 진짜 PNG 생성 → `site/public/shots/`에 커밋 → 웹은 `<img>`.**
  - 디스코드 메시지 캡처본이 아니라 "기능이 만드는 이미지 출력물" 그 자체. 실 유저 데이터 없음(가짜 닉). Vercel은 정적 PNG만 서빙(빌드에 파이썬 불필요). 렌더 코드 변경 시 스크립트 재실행 → 드리프트 0.
- **대상 6종 + 인원:**
  | 명령 | 출력 | 인원 |
  |---|---|---|
  | `/경험치` | 선 그래프 PNG + 순위 리스트 임베드 | **5명** |
  | `/스펙` | 비교표 PNG | **3명** |
  | `/유니온` | 비교표 PNG | **3명** |
  | `/스타포스` | 비교표 PNG | **3명** |
  | `/잠재` | 비교표 PNG | **3명** |
  | `/아이템` | 아이템 카드 PNG | **3명** |
- **비교 명령은 여러 명 결과만** 노출(단일 임베드 생략) — 메이트의 핵심 가치가 "서버 비교"라서.
- **텍스트 임베드 명령**(스케줄러·가이드·경험치알림·공지알림·썬데이알림·등록관리 4종·스펙 단일)은 PNG가 없으므로 **CSS 임베드 목업 유지**(정확도만 손봄).
- **시작하기 페이지 대표 샷** = `/경험치` 그래프 PNG 1장(등록의 보상을 즉시 보여줌).
- **랜딩 3기둥 미니 목업** = 장식성 브랜드 일러스트라 그대로 유지(진짜 PNG는 명령어·시작하기에만).
- **데모 캐스트(가짜 닉, 전 샷 일관)**: `홍길동전사` · `불꽃아크` · `바람궁수` (+경험치 5명은 `이글루법사` · `캐논슈터` 추가). 수치는 기존 `components/Embeds.tsx` 값 계승.

### ③ 개인정보 + 간결화
- **개인정보 "저작권" 문단(`privacy.mdx` 하단) 통째 삭제.** 넥슨 약관상 필수 의무는 "출처표시"(제6조④)뿐이고, 그건 **웹 전역 푸터**([layout.tsx:74-77](../site/app/layout.tsx#L74-L77))가 이미 담당한다(게다가 푸터 문구엔 "비공식 봇" 표현이 없어 이미 깔끔). 따로 추가할 것 없음.
- **간결화 방침:** 당연한 내용을 반복하는 콜아웃/문장 삭제, 각 페이지를 핵심만 남긴 간결한 산문으로. 죽은 링크(개념) 정리.

### ④ 탈-클로드 박스 디자인
- **"클로드 티"의 정체 = 정보 박스 좌측의 색깔 액센트 바**(Anthropic 공식 문서 패턴). 사이트에선 Nextra `<Callout>`와 `.mm-cmd-tip` 두 군데.
- **콜아웃/팁 → 플랫 뉴트럴 박스**: 사방 1px 균일 보더 + 아주 옅은 무채색 배경(`--bg-subtle`) + 작은 muted Lucide 아이콘. **좌측 색바·색 액센트 전면 제거.** 색은 (필요 시) 작은 아이콘에만.
- **박스 개수 자체도 축소**(③ 간결화와 연동).
- **랜딩 3기둥 상단 색바 제거**(`border-top` 색 → 뉴트럴), 색은 아이콘에만 유지.
- **스크린샷 프레임 틸 틴트 제거** → 뉴트럴 최소 프레임(얇은 뉴트럴 보더 + 약한 그림자), 캡션 유지. (진짜 PNG가 이미 "출력물"처럼 보이므로 틴트는 군더더기.)
- **디스코드 임베드 목업 좌측바(`.mm-embed`)는 유지** — 진짜 디스코드 룩이라 없애면 오히려 디스코드처럼 안 보임.
- 팔레트(틸+오렌지 2색)·전제조건 배지·명령 카드 보더는 유지(클로드 티가 아님).

---

## 3. 작업 항목 체크리스트 (파일 단위)

### ① 개념 제거·분산
- [ ] `site/content/concepts.mdx` 삭제.
- [ ] `site/content/_meta.ts`에서 `concepts` 항목 제거.
- [ ] `site/content/getting-started.mdx`: 하단 Cards의 `/concepts` 링크 제거. 키등록 단계 문구에서 "이력류" → 평범한 말. API 키 "왜 필요한가" 한 줄 보강.
- [ ] `site/content/commands.mdx`: 인트로에 챌린저스 1줄 추가. (조어 사용 금지)
- [ ] `site/data/commands.json`: 키등록 summary "이력류" → "스타포스·잠재 기록" 류로 교체.
- [ ] `site/components/CommandGroup.tsx:31`: 키등록 임베드 문구 "이력류(계정 전체)" → 평범한 말.
- [ ] `site/content/privacy.mdx`: "이력류" 3곳(L19·L31·L34) 평범한 말로 교체.

### ② 실제 이미지 (방법 2) — §4 상세 참고
- [ ] `site/scripts/render_demo_shots.py`(신규): 픽스처 → 봇 렌더러 호출 → `site/public/shots/*.png` 덤프.
- [ ] `site/public/shots/` 에 생성 PNG 커밋(경험치·스펙·유니온·스타포스·잠재·아이템).
- [ ] `site/components/CommandGroup.tsx`: `embedFor` 6개 명령을 `<img src="/shots/...">`(ScreenshotFrame 안)로 교체. 나머지는 CSS 임베드 유지.
- [ ] `site/content/getting-started.mdx`: 경험치 그래프 PNG 1장 삽입(대표 보상 샷).
- [ ] `components/Embeds.tsx`: 교체로 안 쓰이게 된 목업(LeaderboardEmbed 등) 정리. **단 텍스트 임베드용(SchedulerEmbed·GuideEmbed·AlertEmbed·RegisterEmbed)은 유지.**

### ③ 개인정보 + 간결화
- [ ] `site/content/privacy.mdx`: "## 저작권" 문단 삭제. 반복 콜아웃·문장 정리.
- [ ] 전 페이지 훑어 군더더기 콜아웃/문장 제거(핵심만).

### ④ 탈-클로드 디자인 — §5 상세 참고
- [ ] `site/app/globals.css`: Nextra `<Callout>` 좌측바 제거·플랫 뉴트럴 오버라이드. `--screenshot-*` 토큰 뉴트럴화.
- [ ] `site/app/commands.css`: `.mm-cmd-tip` 좌측 보더 제거 → 플랫 뉴트럴.
- [ ] `site/app/embeds.css`: `.mm-shot` 프레임 뉴트럴화(틴트 제거). `.mm-embed` 좌측바는 그대로.
- [ ] `site/app/hero.css`: `.mm-pillar--*` 상단 색바 제거(아이콘 색만 유지).

### ⑤ 결정 기록 (§8)
- [ ] `docs/website-design-decisions.md`에 개정 섹션 추가.
- [ ] 메모리 `website-improvement-status`(가칭) 추가 + `MEMORY.md` 포인터.

---

## 4. 방법 2 구현 상세 — 렌더러 재사용

렌더러는 전부 **순수 함수 + 단순 입력**. DB·넥슨·디스코드 불필요. `site/scripts/render_demo_shots.py`에서 `maple_mate.bot.*`를 직접 import해 호출하고 결과 bytes를 파일로 쓴다. (레포 루트 기준 실행, `.venv` 사용.)

### 4-1. 경험치 선 그래프 — 가장 쉬움
```
maple_mate/bot/leaderboard_image.py
  render_progress_graph(series: dict[str, list[tuple[date, float|None]]], ref_date: date) -> io.BytesIO
```
- `series` = 닉 → `[(날짜, 절대레벨)]`. **절대레벨 = level + exp%/100** (선 높이 = 총 레벨). 5명 × 7일.
- 선 끝 라벨 `닉 Lv.287 (79%)`, 겹치면 세로 분산. None 구간은 선 끊김. 리스트 길이 동일 가정.
- **동반 임베드(순위 리스트)**: 형식 `{메달} **{닉}** — Lv.287 (79%)` Top5, 푸터 `기준: 오늘(MM/DD) 현재 · NEXON Open API`. 참고 `maple_mate/leaderboard/broadcast.py:_build_embed`(L86-98). → 이건 CSS 임베드로 유지하고 그래프만 PNG.

### 4-2. 비교표(스타포스·잠재·유니온) — 문자열 행만
```
maple_mate/bot/table_image.py
  render_table_image(headers: list[str], rows: list, *, aligns: list[str]|None = None) -> bytes
```
- `headers` = 문자열 리스트, `rows` = 행(리스트)들의 리스트. 셀은 **문자열** 또는 강조용 `table_image.Highlight("텍스트")`(금색). 특수셀: `NumGrid`(스펙 코어), `GradeBadges`(잠재 등업 뱃지).
- **스타포스** 컬럼/정렬(그대로 픽스처 템플릿, `maple_mate/history/commands.py:_build_table` L216-270):
  ```python
  headers = ["순위", "대상", "운빨수치", "총 사용 메소", "기준건수"]
  rows = [["1","홍길동전사", Highlight("상위 8%"), "2.1억", "98건"], ...]
  aligns = ["center","left","right","right","right"]
  ```
- **잠재** 컬럼(`maple_mate/history/potential_commands.py:_build_table` L135-190): `["순위","대상","잠재 재설정","사용 큐브","사용 메소","잠재 등업","에디 등업"]`. 등업 컬럼은 `GradeBadges`(색 뱃지) — 픽스처에서 문자열로 단순화 가능하나, 실제 룩 원하면 `GradeBadges` 사용법을 L84 dataclass에서 확인.
- **유니온** 컬럼(`maple_mate/union/commands.py:handle_union` L112 부근): `["순위","캐릭터","유니온","아티팩트","챔피언"]`.

### 4-3. 스펙 비교표 — 가장 복잡(코어/HEXA 동적 컬럼)
- `NumGrid`(코어 스킬/마스터리/강화/범용 격자) + HEXA 스탯 컬럼. 픽스처 조립 난이도 최상.
- **권장:** `maple_mate/character/commands.py:handle_spec`(L75-219)의 컬럼 구성 로직을 그대로 읽고, `NumGrid`(table_image.py:58) 필드에 맞춰 가짜 값 조립. 시간 부족하면 스펙만 대표 컬럼(전투력·어빌리티 등)으로 축약한 표로 타협 가능(단 "실제 형태 반영" 취지에선 코어 격자까지 재현이 이상적).

### 4-4. 아이템 카드
```
maple_mate/bot/item_card.py
  render_item_cards(cards: list[ItemCard]) -> bytes
  ItemCard(label, found, item_name, starforce, icon_png=None, potential, additional, add_option, upgrade, upgrade_stats)
  CardPotential(grade, options)   # grade="레전드리" 등, options=["공격력+3%", ...]
```
- `icon_png=None` 이면 아이콘 숨김(가짜 아이콘 없어도 됨). 3명 → 각자 대표 부위 카드 몇 장.

### 4-5. 폰트·워크플로우 주의
- 렌더 폰트: 로컬 맥 `AppleSDGothicNeo`(table_image.py:30 후보 목록 우선순위). 프로덕션 봇은 Linux `NanumGothic`이라 **글자 렌더가 미세하게 다를 수 있으나** 데모용 형태 재현엔 무방.
- 워크플로우: 스크립트 **로컬 실행 → PNG 커밋 → Vercel은 정적 서빙.** 봇 렌더 코드 바뀌면 스크립트 재실행 후 재커밋.
- 생성 후 **PNG를 눈으로 열어 실제 봇 출력 형태와 일치하는지 확인**(완료 기준 §7).

---

## 5. 탈-클로드 디자인 스펙

**플랫 뉴트럴 박스(콜아웃/팁 공통):**
```
- 배경: var(--bg-subtle)
- 보더: 1px solid var(--border)  ← 사방 균일, 좌측 단독 바 금지
- 라운드: var(--radius-md)
- 아이콘: 작은 Lucide, color: var(--tx-muted)  ← 색 액센트 아님
- 좌측 border-left 색바: 전면 제거
```
적용 지점:
- **Nextra `<Callout>`**: `globals.css`에서 Nextra 콜아웃 클래스의 `border-inline-start`/좌측 강조·틴트 배경을 위 스타일로 오버라이드(또는 `<Callout>` 사용을 커스텀 노트 컴포넌트로 대체). 타입별 색(info/warning) 강조 제거 — 경고도 뉴트럴 + 아이콘만.
- **`.mm-cmd-tip`**(commands.css:108-117): `border-left: 3px solid var(--teal)` 제거 → 사방 보더 뉴트럴. "팁" 라벨은 muted.
- **`.mm-shot`**(embeds.css:7-13): `--screenshot-bg` 틸 틴트 → 뉴트럴 배경/보더. `globals.css`의 `--screenshot-bg`(#F0F9F9)·`--screenshot-border`를 뉴트럴 토큰으로.
- **`.mm-pillar--teal/orange/green`**(hero.css:223-225): `border-top-color` 색 → `var(--border)`. 아이콘 색(`.mm-pillar-icon--*`)은 유지.
- **유지:** `.mm-embed` 좌측바(디스코드 룩), 명령 카드 보더/그림자, 전제조건 배지, 2색 팔레트.

검증: 토큰 바꾸면 **AA 대비 재검증**(파이썬 relative-luminance 한 줄). 라이트/다크/모바일 스크린샷 눈확인(handoff §1 절차).

---

## 6. 스코프 아웃 / 백로그

- **숙제 DM 비서(스케줄러)를 PNG로 예쁘게** — 지금은 텍스트 임베드. 웹 목업처럼 만들려면 봇이 스케줄러도 PIL PNG로 렌더해야 함(기존 이미지 인프라 재사용). **봇 쪽 기능 변경이라 이번 웹 작업과 분리.** 원하면 별도 세션에서.
  - 웹 정확성 원칙: 실제 출력이 텍스트 임베드인 동안엔 웹도 텍스트 임베드 형태로 정직하게 표시(없는 기능처럼 보이지 않게).
- 검색(Pagefind)·per-page OG·파비콘 16px·커스텀 도메인 등은 기존 [website-handoff.md](./website-handoff.md) §6 백로그 유지.

---

## 7. 완료 기준

- [ ] `site/npm run build` 통과(사이트 TS/빌드 오류는 로컬 빌드로만 잡힘 — CI는 파이썬만).
- [ ] 드리프트 테스트 통과: `.venv/bin/python -m pytest tests/test_website_command_drift.py -q`.
- [ ] `render_demo_shots.py` 실행 → `site/public/shots/*.png` 6종 생성, **각 PNG 눈으로 열어 실제 봇 출력 형태와 일치 확인**.
- [ ] 라이트/다크/모바일 스크린샷 눈확인 — 좌측 색바가 콜아웃/팁/기둥/프레임에서 **사라졌는지**, 디스코드 임베드 목업 바만 남았는지.
- [ ] 개념 페이지·죽은 링크·"스펙류/이력류" 조어·"비공식 커뮤니티 봇" 문구가 **완전히 사라졌는지** grep 확인.
- [ ] 토큰 변경분 AA 대비 재검증.

---

## 8. 결정 기록 대상 — `website-design-decisions.md` 개정 항목

다음 세션이 "확정 — 재론 금지"를 근거로 되돌리지 않도록, 아래를 개정 섹션으로 추가할 것(별도 ADR보다 D-로그 형식이 맞음):

1. **IA 개정:** 5페이지 → **4페이지**(개념 페이지 폐지). 개념 정보는 시작하기·명령어에 인라인 흡수, "스펙류/이력류" 조어는 사용자 대면에서 폐기.
2. **D10 개정:** "CSS 목업(실데이터 금지)" → **"봇 실제 렌더러를 가짜 닉 픽스처로 호출한 진짜 PNG"**. CSS 목업은 텍스트 임베드 명령에만 잔존. (실 디스코드 스크린샷 캡처 계획도 폐기 — 대신 렌더러 직접 호출.)
3. **콜아웃/프레임 디자인 개정:** 좌측 색 액센트 바 패턴 폐기(플랫 뉴트럴). 스크린샷 틸 틴트 프레임 폐기(뉴트럴). 랜딩 기둥 상단 색바 폐기. **단 디스코드 임베드 목업 좌측바는 의도적 유지**(디스코드 룩).
4. **개인정보 저작권 문단 폐지:** 출처표시는 전역 푸터가 담당(약관 제6조④ 충족).

---

## 9. 핵심 레퍼런스 (file 포인터)

- 사이트 구조·함정·배포: [website-handoff.md](./website-handoff.md)
- 봇 렌더러: `maple_mate/bot/leaderboard_image.py`(그래프) · `table_image.py`(비교표) · `item_card.py`(카드)
- 비교표 빌더(픽스처 템플릿): `maple_mate/history/commands.py:_build_table` · `history/potential_commands.py:_build_table` · `union/commands.py:handle_union` · `character/commands.py:handle_spec`
- 사이트 편집 지점: 카피 `site/lib/site.ts` · 토큰 `site/app/globals.css` · 명령 정본 `site/data/commands.json` · 콜아웃/임베드 CSS `site/app/{commands,embeds}.css`
- 드리프트 소스오브트루스(봇): `maple_mate/guide/commands.py`
</content>
</invoke>
