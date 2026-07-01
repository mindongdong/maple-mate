# 웹사이트 스크린샷 재캡처 런북

> website-docs-plan 결정 7·미디어 제약: **데모 서버에서 재캡처**한 스크린샷만 사용(실 친구 닉/캐릭명 = 개인정보 → 금지).
> 현재 사이트는 각 명령의 디스코드 임베드를 **CSS 목업 컴포넌트**로 렌더 중(데모용 가짜 닉·수치).
> 실 스샷이 준비되면 아래 절차로 교체한다.

## 왜 목업부터인가

- 실데이터 스샷은 개인정보라 그대로 못 쓴다. 시드 데이터 데모 서버가 있어야 안전한 캡처가 가능.
- 그동안 사이트가 비지 않도록, `site/components/Embeds.tsx` 가 실제 임베드 룩(다크 카드 +
  좌측 컬러 바)을 재현한 고충실 목업을 렌더한다. 테마 인식·크리스프·개인정보 0.

## 캡처 대상 (명령 → 임베드)

| 명령 | 컴포넌트(교체 대상) | 캡처 화면 |
|---|---|---|
| /경험치 | `LeaderboardEmbed` | Top 10 리더보드 + 7일 그래프 PNG |
| /스펙 | `SpecEmbed` | 스펙 요약 임베드 |
| /아이템 | `ItemEmbed` | 부위별 장비 임베드 |
| /유니온 | `UnionEmbed` | 유니온 임베드 |
| /스타포스 | `StarforceEmbed` | 이력 비교 표 |
| /잠재 | `PotentialEmbed` | 이력 비교 표 |
| /스케줄러 · /스케줄러알림 | `SchedulerEmbed` | 숙제 체크리스트 DM |
| /가이드 | `GuideEmbed` | 6그룹 가이드 |
| /캐릭터등록·키등록·대표지정·캐릭터목록 | `RegisterEmbed` | 등록 결과 |
| /경험치알림·공지알림·썬데이알림 | `AlertEmbed` | 구독 확인 |

## 절차

1. **데모 서버 준비**: 시드 계정으로 캐릭터 등록(예: `홍길동전사` 등 가상 닉), 키 등록, 스냅샷 며칠 누적.
   실 유저 닉/캐릭명이 프레임 안에 절대 들어가지 않게 한다.
2. **캡처**: 디스코드에서 각 명령 실행 → 임베드만 잘라 PNG 저장. 다크 테마 권장(임베드 정본).
3. **배치**: `site/public/shots/` 에 `leaderboard.png`, `spec.png` … 로 저장.
4. **교체**: `site/components/CommandGroup.tsx` 의 `embedFor()` 와 `site/components/Hero.tsx` 에서
   임베드 컴포넌트를 `<img>` 로 바꾼다. `ScreenshotFrame` 은 그대로 두고 children 만 교체:
   ```tsx
   // before
   <ScreenshotFrame compact caption="/스펙 · 계정 전체 합산"><SpecEmbed /></ScreenshotFrame>
   // after
   <ScreenshotFrame compact caption="/스펙 · 계정 전체 합산">
     <img src="/shots/spec.png" alt="/스펙 결과 예시" />
   </ScreenshotFrame>
   ```
5. **틴트 프레임 유지**: `ScreenshotFrame`(D10)의 테마 인식 backdrop·그림자는 유지 → 실 스샷도 브랜드 프레임 안에 앉는다.

## OG 이미지 재생성

OG(`site/public/og.png`)는 마스코트-forward 정적 이미지다. 소스 = `site/scripts/og.html`.
```bash
# 1200×630 캡처 (Pretendard 로드를 위해 virtual-time-budget 지정)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --hide-scrollbars --window-size=1200,630 \
  --virtual-time-budget=3500 \
  --screenshot=site/public/og.png "file://$PWD/site/scripts/og.html"
```
도메인 확정 후 `NEXT_PUBLIC_SITE_URL` 을 갱신하면 OG 절대경로가 그 도메인으로 맞춰진다.
