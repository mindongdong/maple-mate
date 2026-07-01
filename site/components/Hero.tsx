/**
 * 랜딩 히어로 — hero-3 "따뜻 강조" 컨셉(D8) 구현.
 * §4 리파인 백로그 반영:
 *  1) 버섯 = 스샷 상단 중앙 걸침 → 우상단 코너 빼꼼(임베드 타이틀 안 가림).
 *  2) 스티키 nav = 항상-오렌지 → Nextra 중립/blur 네비 사용(밴드는 히어로 섹션 한정).
 *  4) 모바일 스택 = 카피+CTA 먼저, 미디어 아래(DOM 순서 그대로, order 역전 없음).
 *  5) H1 = 워드마크 텍스트만(마크는 네비 락업·큰 버섯이 마스코트 존재감 담당).
 */
import { ArrowRight } from 'lucide-react'
import { MushroomFull } from './Mushroom'
import { ScreenshotFrame } from './ScreenshotFrame'
import { LeaderboardEmbed } from './Embeds'
import { INVITE_URL, SITE_TAGLINE } from '@/lib/site'

function DiscordGlyph() {
  // 브랜드 로고(Lucide 미수록) — D13 "UI 아이콘" 정책의 예외.
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M20.317 4.37a19.79 19.79 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.74 19.74 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.1 13.1 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.3 12.3 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.84 19.84 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z" />
    </svg>
  )
}

export function Hero() {
  return (
    <section className="mm-hero-band">
      <div className="mm-hero">
        <div className="mm-hero-left">
          <h1 className="mm-hero-wordmark">메이트</h1>
          <div className="mm-hero-divider" />
          <p className="mm-hero-tagline">{SITE_TAGLINE}</p>
          <p className="mm-hero-desc">
            캐릭터를 한 번 등록해두면 유니온·스펙·경험치를 바로 확인하고,
            친구·길드원과 리더보드로 순위를 겨뤄요. 스타포스·잠재 지출은
            메소·운빨로 비교하고, 일일·주간·보스 숙제는 스케줄러가 개인 DM으로
            챙겨줍니다.
          </p>
          <div className="mm-hero-cta">
            <a className="mm-btn-primary" href={INVITE_URL} target="_blank" rel="noreferrer">
              <DiscordGlyph />
              봇 초대하기
            </a>
            <a className="mm-btn-ghost" href="/getting-started">
              5분 시작
              <ArrowRight size={15} strokeWidth={2} aria-hidden />
            </a>
          </div>
        </div>

        <div className="mm-hero-right">
          <MushroomFull size={96} className="mm-hero-mushroom" aria-hidden />
          <ScreenshotFrame caption="경험치 리더보드 · 실제 디스코드 임베드">
            <LeaderboardEmbed rows={7} />
          </ScreenshotFrame>
        </div>
      </div>
    </section>
  )
}
