/**
 * "5분 시작" 티저 — §4 리파인 백로그 #3(D8 흐름의 누락 섹션 보강).
 * 3기둥 → (여기) → docs 로 잇는 온보딩 브리지. 전제조건 funnel 3티어를 단계로 노출.
 */
import { ArrowRight, UserPlus, KeyRound, Unlock } from 'lucide-react'

const STEPS = [
  {
    icon: Unlock,
    tone: 'green' as const,
    label: '등록 없이 바로',
    body: '봇을 초대하면 /가이드 와 경험치·공지·썬데이 알림은 누구나 바로.',
  },
  {
    icon: UserPlus,
    tone: 'indigo' as const,
    label: '캐릭터 등록하면',
    body: '/캐릭터등록 → /대표지정 으로 스펙·유니온·경험치 리더보드까지.',
  },
  {
    icon: KeyRound,
    tone: 'amber' as const,
    label: 'API 키 등록하면',
    body: '/키등록 으로 스타포스·잠재 지출 비교와 스케줄러 숙제 DM 개방.',
  },
]

export function QuickStartTeaser() {
  return (
    <section className="mm-teaser">
      <div className="mm-teaser-inner">
        <p className="mm-eyebrow">5분이면 충분해요</p>
        <h2 className="mm-teaser-title">등록한 만큼 열립니다</h2>
        <p className="mm-teaser-sub">
          권한 설정은 필요 없어요. 필요한 만큼만 등록하면 그만큼 기능이 열립니다.
        </p>

        <ol className="mm-teaser-steps">
          {STEPS.map(({ icon: Icon, tone, label, body }, i) => (
            <li className={`mm-teaser-step mm-tone-${tone}`} key={label}>
              <span className="mm-teaser-num">{i + 1}</span>
              <span className="mm-teaser-step-icon">
                <Icon size={18} strokeWidth={2} aria-hidden />
              </span>
              <div>
                <div className="mm-teaser-step-label">{label}</div>
                <p className="mm-teaser-step-body">{body}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mm-teaser-cta">
          <a className="mm-btn-primary" href="/getting-started">
            5분 시작 가이드
            <ArrowRight size={15} strokeWidth={2} aria-hidden />
          </a>
          <a className="mm-btn-ghost" href="/commands">
            전체 명령어 보기
          </a>
        </div>
      </div>
    </section>
  )
}
