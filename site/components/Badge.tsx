/** 전제조건 배지 (D5·D6) — 권한기반 아님, 온보딩 funnel(등록없이/캐릭터/API키).
 *  green=unlock · indigo=user · amber=key. Lucide 아이콘(D13). */
import { Icon } from '@/lib/icons'
import { TIERS, type Tier } from '@/lib/commands'

export function Badge({ tier }: { tier: Tier }) {
  const meta = TIERS[tier]
  return (
    <span className={`mm-badge mm-badge--${meta.tone}`}>
      <Icon name={meta.icon} size={11} strokeWidth={2.5} />
      {meta.label}
    </span>
  )
}

/** 배지 범례 — 명령어 페이지 상단. 3티어를 한 줄로 설명. */
export function BadgeLegend() {
  const order: Tier[] = ['free', 'character', 'apikey']
  return (
    <div className="mm-badge-legend">
      {order.map((t) => (
        <Badge key={t} tier={t} />
      ))}
    </div>
  )
}
