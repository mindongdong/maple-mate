import { Hero } from './Hero'
import { Pillars } from './Pillars'
import { QuickStartTeaser } from './QuickStartTeaser'

// 랜딩 = 히어로(오렌지 wash 밴드) → 3기둥(쿨 베이스) → 5분 시작 티저 → docs (D8)
export function Landing() {
  return (
    <div className="mm-landing">
      <Hero />
      <Pillars />
      <QuickStartTeaser />
    </div>
  )
}
