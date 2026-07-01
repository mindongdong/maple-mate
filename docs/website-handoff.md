# 메이트 웹사이트 — 다음 세션 핸드오프 (구현 이후)

> 이 문서는 **이미 구축·머지된 웹사이트(`site/`)를 이어서 개선**하려는 다음 세션을 위한 것이다.
> (최초 *설계* 핸드오프는 [website-design-handoff.md](./website-design-handoff.md) — 그건 grill 입력 브리핑이라 역사 기록용.)
>
> 먼저 읽을 것: 이 문서 → [website-design-decisions.md](./website-design-decisions.md)(D1–D14 + §5 as-built) → [website-deploy-runbook.md](./website-deploy-runbook.md).

## 0. 30초 요약

- 홍보·문서 웹사이트가 `site/`(Next 15 + **Nextra 4.6** App Router)에 **구현·머지 완료**(PR #37, 문서반영 #38).
- 5개 페이지: 랜딩 · 시작하기 · 명령어 · 개념 · 개인정보. 라이트/다크 1급, 모바일 QA 됨.
- **디자인은 확정**(D1–D14, 재론 금지). 남은 건 대부분 **콘텐츠·에셋·배포** 개선(§7 백로그).
- 배포: Vercel 연결됨(PR 프리뷰 붙음). **Root Directory=`site`** 만 맞으면 뜬다. 공개는 **봇 #36 배포 이후**.

## 1. 로컬 실행 & 검증

```bash
cd site
npm install            # zod 4.1.12 로 고정됨(§5 함정 참조) — 반드시 lockfile 존중
npm run dev            # http://localhost:3000
npm run build          # 프로덕션 빌드(= Vercel 이 하는 것). 배포 전 항상 통과 확인
node scripts/check-command-drift.mjs   # commands.json 구조 sanity
```

**드리프트 테스트(파이썬, CI 게이트)** — 루트에서:
```bash
.venv/bin/python -m pytest tests/test_website_command_drift.py -q
```

**스크린샷 눈확인**(headless Chrome, 브라우저 도구 없이):
```bash
# 라이트
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --hide-scrollbars --window-size=1280,900 \
  --screenshot=/tmp/shot.png "http://localhost:3000/"
# 다크는 --force-dark-mode, 모바일은 --window-size=430,1600
```

- **Node**: 로컬은 25지만 Vercel/권장은 **22 LTS**. lockfileVersion 3.
- **검색 비활성**(MVP). 켜려면 `next.config.mjs` `search` + `pagefind`(-D) + postbuild 인덱싱.

## 2. 아키텍처 지도

```
site/
  next.config.mjs        # nextra({ search:false, defaultShowCopyCode }), reactStrictMode
  package.json           # ⭐ overrides.zod = "4.1.12" (안 지우기)
  mdx-components.tsx      # ⭐ 인라인 `/한글명` code → <CommandChip> 자동 변환(D7)
  app/
    layout.tsx           # Nextra <Layout> 루트: Navbar(로고=MushroomMark+메이트)·Footer·
                         #   Head(teal 색 토큰·favicon)·metadata(OG/SEO)·테마(system+토글)
    [[...mdxPath]]/page.tsx  # content/ catch-all 렌더러(importPage + Wrapper)
    not-found.tsx        # 404 (Nextra NotFoundPage) — 없으면 빌드 깨짐
    globals.css          # ⭐ 디자인 토큰(:root/.dark) + 폰트 @import + Nextra 색 오버라이드
    hero.css             # 랜딩(히어로 밴드·3기둥·티저·버튼·마스코트·모바일·모션). full-bleed 여기
    commands.css         # 명령 카드·배지·칩·그룹
    embeds.css           # 디스코드 임베드 목업 + 스샷 틴트 프레임(공용)
  content/               # ← MDX 콘텐츠(소스오브트루스는 여기, 손작성)
    _meta.ts             # 네비: index=풀레이아웃·숨김, 4섹션=type:page(상단 네비)
    index.mdx            # 랜딩 → <Landing/>
    getting-started.mdx  # Steps 온보딩 funnel + 넥슨 API 키 발급
    commands.mdx         # ## 그룹 헤딩(우측 TOC) + <CommandGroup id=.../>
    concepts.mdx         # 스펙류vs이력류·API키·챌린저스
    privacy.mdx          # Fernet 암호화·데이터 철회
  components/
    Landing / Hero / Pillars / QuickStartTeaser  # 랜딩 조립
    CommandGroup / CommandChip / Badge           # 명령어 페이지 유닛
    Embeds.tsx           # ⭐ 모든 디스코드 임베드 목업(가짜 닉) — 실 스샷 교체 대상
    ScreenshotFrame.tsx  # 틴트 프레임 래퍼(D10)
    Mushroom.tsx         # 마스코트 두 폼(Full/Mark) — 둘 다 /mascot.png 렌더
  data/commands.json     # ⭐ 명령 16개 정본(페이지 렌더 + 드리프트 테스트가 읽음)
  lib/
    site.ts              # ⭐ 카피/링크 단일 소스(SITE_TAGLINE·DESCRIPTION·INVITE_URL 등)
    commands.ts          # commands.json 타입·헬퍼(GROUPS/TIERS)
    icons.tsx            # 아이콘 문자열 → Lucide 매핑
  public/                # mascot.png·favicon.png·apple-touch-icon.png·og.png
  scripts/               # og.html(OG 소스)·check-command-drift.mjs
tests/test_website_command_drift.py   # ← 루트(파이썬 CI). 봇 트리 == commands.json
```

**어디를 고치나 (자주 하는 작업)**
- 카피/태그라인/링크 → `lib/site.ts` (한 곳).
- 색/토큰 → `app/globals.css` (`:root` + `.dark`). **AA 유지**(§4).
- 명령 추가/변경 → `data/commands.json` (+ 필요 시 `components/Embeds.tsx` 목업). 드리프트 테스트가 봇 트리와 대조.
- 페이지 문구 → `content/*.mdx`. 인라인 `/명령` 은 백틱으로 쓰면 자동 칩.
- 새 페이지 → `content/foo.mdx` + `content/_meta.ts` 항목.

## 3. 디자인 시스템 (확정 — 재론 금지)

전체는 [website-design-decisions.md](./website-design-decisions.md)(D1–D14). 핵심만:

- **2색 액센트**: 틸(기능/링크) + 오렌지(브랜드/CTA·마스코트). 골드는 데이터 모티프만.
- **전제조건 funnel 배지**(권한기반 아님): 등록없이 green / 캐릭터 indigo / API키 amber. 비틱 제외.
- **명령 칩**(Pretendard pill, 모노 아님) / 실코드만 JetBrains Mono.
- **마스코트**: `icon_2.png`(주황버섯 갓+얼굴) 기반 래스터. 두 폼(Full 큰 것 / Mark 작은 것).
- **모션 절제** + `prefers-reduced-motion` 존중. **Lucide 라인 아이콘 통일**(네이티브 이모지는 임베드 목업 안에서만).

**AA (지켜야 함)** — 토큰 바꿀 때 대비 재검증:
- 라이트: teal 링크 `#0B7C82`(≥4.5 on white/subtle) · muted `#64748B` · CTA `--cta #B85906`(흰 텍스트 4.7:1, **크기 무관**).
- 브랜드 오렌지 `#E0700A` 는 **그래픽 전용**(글자로 쓰지 말 것 — 대비 부족).
- 대비 계산은 파이썬 한 줄 스크립트로(WCAG relative luminance). 이전 세션이 전 토큰쌍 검증함.

## 4. 반드시 아는 함정

1. **zod 핀**: `nextra@4.6.1` × `zod@4.4.x` 의 `z.custom()` undefined 처리 변경 → Layout `children` 스키마가 `"expected nonoptional"` 로 깨짐. `package.json overrides.zod="4.1.12"` 로 고정. **Nextra 올릴 때 재검토**, 그전엔 제거 금지.
2. **full-bleed**: Nextra `layout:full` 도 좌우 패딩 있음 → 랜딩 섹션은 `100vw` + `calc(50% - 50vw)` 로 브레이크아웃하고, 가로 스크롤은 `globals.css` `html{overflow-x:clip}` 로 막음(`hidden` 아님 — sticky 네비 안 깨지게).
3. **드리프트 가드**: `data/commands.json` 의 명령 집합 == 봇 트리(`bot.tree.get_commands()`, 비틱 자동제외). 봇에 명령 추가/개명 시 **commands.json 도 갱신** 안 하면 CI(`uv run pytest`) 빨감. 반대로 유령 명령도 잡음.
4. **스크린샷 = CSS 목업**: 실데이터 금지 원칙. `components/Embeds.tsx` 가 가짜 닉으로 임베드를 재현. 실 스샷 교체 = [website-screenshot-capture.md](./website-screenshot-capture.md).
5. **CI 범위**: `.github/workflows/ci.yml` 은 **파이썬만**(ruff·pytest·alembic) — 사이트 빌드 안 함. 사이트 빌드는 **Vercel**이 담당. 그래서 사이트 TS/빌드 오류는 로컬 `npm run build` 로 직접 잡아야 함.
6. **커밋/PR 관례**: 커밋 메시지 **한국어·conventional**(`feat:`/`docs:`…), **attribution 없음**(사용자 설정). 흐름 = 브랜치 → 논리 커밋 → PR → **squash 머지**(`(#N)`) → 브랜치 삭제. 파이썬 신규/수정 시 `ruff format --check` 통과 확인.
7. **공개 게이팅**: 사이트는 post-#36 상태 서술. 봇 #36 이 **실제 배포/기동된 뒤** 홍보·공개(안 나간 기능 서술 방지).

## 5. 배포 상태 (Vercel)

- Vercel 이 저장소에 **연결됨**(PR 에 프리뷰 코멘트 붙음). PR #37/#38 에서 프리뷰 URL·빌드 성공 여부 확인.
- 필수: **Root Directory=`site`** (안 되면 루트 파이썬 빌드 시도→실패). Framework=Next.js(자동). Node 22.
- 환경변수: `NEXT_PUBLIC_SITE_URL`(OG 절대경로)·`NEXT_PUBLIC_INVITE_URL`(초대 CTA). 미설정 시 폴백(빌드는 됨).
- 도메인 붙이면 `NEXT_PUBLIC_SITE_URL` 갱신 후 재배포. 상세 = [website-deploy-runbook.md](./website-deploy-runbook.md).

## 6. 개선 백로그 (우선순위)

**높음 — 공개 전 실질**
- [ ] **데모 서버 실 스크린샷 재캡처** → `components/Embeds.tsx` 목업을 `<img src="/shots/...">` 로 교체(프레임 유지). 시드 계정·가짜 닉. 절차 = screenshot-capture 런북.
- [ ] **Vercel Root=`site` + env + 커스텀 도메인** 확정, OG 프리뷰(카톡/디코 공유) 실제 확인.
- [ ] **봇 초대 링크(client_id)** 확정 → `NEXT_PUBLIC_INVITE_URL`.

**중간 — 완성도**
- [ ] **검색 활성화**(Pagefind) — 문서 수 늘면 유용.
- [ ] **파비콘 16px 선명도**: 현재 래스터 다운스케일이라 16px 소프트. 필요 시 icon_2 축약 SVG 마크 별도 제작.
- [ ] **per-page OG**(현재 site-wide 1장) — 명령어/개념 등 페이지별.
- [ ] 데모 캐릭/닉 **일관성**(Embeds 전반 가짜 닉 통일), 수치 현실성 점검.
- [ ] `getting-started` 넥슨 API 키 발급 절차 — 실제 넥슨 UI 와 대조해 정확도 확인.

**낮음 — 확장**
- [ ] FAQ / 변경이력 페이지(원 계획서 "반복으로 미룸" 항목).
- [ ] 챌린저스 모드 개념 더 깊이(스크린샷 포함).
- [ ] Vercel Analytics, koreanbots 등록, 인벤 홍보(유입).
- [ ] 접근성 추가 점검(키보드 포커스·명령칩 색만 의존 여부).

## 7. 핵심 레퍼런스

- 디자인 결정: [website-design-decisions.md](./website-design-decisions.md) (D1–D14 + §3 해소 + §4 백로그해소 + §5 as-built)
- 배포: [website-deploy-runbook.md](./website-deploy-runbook.md) · 스샷: [website-screenshot-capture.md](./website-screenshot-capture.md)
- 채택 목업(시각 레퍼런스): `docs/website-mockups/hero-3.html`, `commands.html`
- **드리프트 소스오브트루스(봇)**: `maple_mate/guide/commands.py`(`/가이드` 그룹·명령) — 사이트 6그룹·문구가 여기 미러
- 카피 정본: [service-launch-copy] 메모리(넥슨 서비스 등록 + 개정 오프너)
- 프로젝트 메모리(다른 세션): `website-implementation-status` · `website-design-decisions` · `website-docs-plan`
