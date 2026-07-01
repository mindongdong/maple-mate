# 메이트 웹사이트 배포 런북 (`site/` · Nextra v4 → Vercel)

> 코드: `site/` (Next.js 15 + Nextra 4 App Router). 디자인 결정: [website-design-decisions.md](./website-design-decisions.md).
> ⚠️ **공개 조율(D5)**: 사이트는 **post-#36 상태**(권한제거·알림통일·비틱숨김)를 문서화한다.
> #36 배포가 **라이브가 된 뒤에만** 사이트를 공개하라(안 나간 기능 서술 방지). #36 은 이미 머지됨(커밋 `771db88`).

## 로컬 개발

```bash
cd site
npm install          # zod 4.1.12 로 고정됨(아래 "알려진 함정" 참조)
npm run dev          # http://localhost:3000
npm run build        # 프로덕션 빌드 검증 (배포 전 필수)
```

## Vercel 설정 (운영자 1회)

Vercel 은 이 저장소의 **하위 디렉터리** `site/` 를 루트로 배포한다.

1. Vercel 대시보드 → **Add New… → Project** → `mindongdong/maple-mate` import.
2. **Root Directory** = `site` 로 지정 (Edit → `site` 선택). ← **핵심**. 이걸 안 하면 저장소 루트(파이썬 봇)를 빌드하려다 실패.
3. **Framework Preset** = Next.js (자동 감지). Build Command / Output 은 기본값 그대로.
4. **Environment Variables** 등록:
   | 키 | 값(예) | 용도 |
   |---|---|---|
   | `NEXT_PUBLIC_SITE_URL` | `https://<확정도메인>` | OG·canonical URL 절대경로 |
   | `NEXT_PUBLIC_INVITE_URL` | `https://discord.com/oauth2/authorize?client_id=<봇ID>&scope=bot%20applications.commands` | 히어로/시작하기 초대 CTA |
   두 값은 `site/lib/site.ts` 가 읽는다. 미설정 시 플레이스홀더로 폴백(빌드는 통과하나 초대 링크가 동작 안 함).
5. Deploy.

## 커스텀 도메인 (D11·website-docs-plan 결정 8)

1. Vercel 프로젝트 → **Settings → Domains → Add** → 도메인 입력.
2. 도메인 등록기관(가비아/Cloudflare 등)에서 안내되는 **A / CNAME** 레코드 추가.
3. 전파 후 HTTPS 자동 발급 확인.
4. 도메인 확정 즉시 `NEXT_PUBLIC_SITE_URL` 를 그 값으로 갱신 → 재배포(OG 절대경로 정합).
5. 확정 도메인을 [service-launch-copy] 의 넥슨 OpenAPI 서비스 URL 로도 반영.

## 알려진 함정

- **zod 핀**: `nextra@4.6.1` 은 `zod ^4.1.12` 를 선언하지만, 최신 `zod@4.4.x` 에서 `z.custom()` 의
  `undefined` 처리가 바뀌어 Nextra `Layout` 의 `children` 스키마가 `"expected nonoptional, received undefined"`
  로 깨진다. → `site/package.json` 의 `overrides.zod = "4.1.12"` 로 고정. Nextra 상향 시 재검토.
- **검색 비활성**: MVP 는 `next.config.mjs` 에서 `search: false`(Pagefind 미도입). 후속 활성 시
  `-D pagefind` 추가 + postbuild 인덱싱.
- **스크린샷**: 명령 카드/히어로의 디스코드 임베드는 현재 **CSS 목업 플레이스홀더**(실데이터 금지 원칙 준수).
  데모 서버 재캡처 PNG 로 교체 예정 — [website-screenshot-capture.md](./website-screenshot-capture.md) 참조.

## 유입 (website-docs-plan 미니결정)

배포 후: 초대 링크 상단 노출 · koreanbots 등록 · 인벤 홍보 · Vercel Analytics(선택).
