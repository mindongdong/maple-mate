'use client'
/**
 * 인터랙티브 튜토리얼 (D7 UX 골격) — 풀스크린 오버레이 + 챕터 프로그래스바 +
 * "약 5분이면 끝" 배지 + `?step=N` 딥링크 + 키보드 ←→. X = 랜딩 복귀.
 * 스텝 정본은 data/tutorial-steps.tsx. localStorage 재개는 의도적으로 없음(D7).
 */
import * as React from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  ArrowLeft,
  ArrowRight,
  Bell,
  BookOpen,
  Clock,
  Eye,
  Lock,
  X,
} from 'lucide-react'
import { MushroomMark } from './Mushroom'
import { INVITE_URL } from '@/lib/site'
import {
  TUTORIAL_CHAPTERS,
  TUTORIAL_STEPS,
  type TutorialCommand,
  type TutorialMedia,
  type TutorialStep,
} from '@/data/tutorial-steps'

const TOTAL = TUTORIAL_STEPS.length

function clampStep(raw: string | null): number {
  const n = Number.parseInt(raw ?? '1', 10)
  if (Number.isNaN(n)) return 1
  return Math.min(Math.max(n, 1), TOTAL)
}

function usePrefersReducedMotion(): boolean {
  const [reduce, setReduce] = React.useState(false)
  React.useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduce(mq.matches)
    const onChange = (e: MediaQueryListEvent) => setReduce(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduce
}

function VisibilityLabel({ visibility }: { visibility: 'public' | 'private' }) {
  const isPublic = visibility === 'public'
  return (
    <span className={`mm-tut-vis mm-tut-vis--${visibility}`}>
      {isPublic ? (
        <Eye size={11} strokeWidth={2.5} aria-hidden />
      ) : (
        <Lock size={11} strokeWidth={2.5} aria-hidden />
      )}
      {isPublic ? '다같이 봐요' : '나만 봐요'}
    </span>
  )
}

/** 'doors' 스크린 — 열리는 명령 칩 + 공개/본인만 라벨. */
function DoorsList({ commands }: { commands: TutorialCommand[] }) {
  return (
    <ul className="mm-tut-doors">
      {commands.map((c) => (
        <li className="mm-tut-door" key={c.name}>
          <span className="mm-chip">{c.name}</span>
          {c.visibility ? <VisibilityLabel visibility={c.visibility} /> : null}
        </li>
      ))}
    </ul>
  )
}

/** 'summary' 스크린 — 공개/비공개 2버킷 총정리. 발송물(명령 아님)은 공개 버킷에 종 칩. */
function VisibilitySummary({
  commands,
  broadcasts = [],
}: {
  commands: TutorialCommand[]
  broadcasts?: string[]
}) {
  const buckets = [
    { key: 'public' as const, title: '다같이 봐요', icon: Eye },
    { key: 'private' as const, title: '나만 봐요', icon: Lock },
  ]
  return (
    <div className="mm-tut-summary">
      {buckets.map(({ key, title, icon: Icon }) => (
        <div className={`mm-tut-bucket mm-tut-bucket--${key}`} key={key}>
          <div className="mm-tut-bucket-head">
            <Icon size={15} strokeWidth={2.2} aria-hidden />
            {title}
          </div>
          <div className="mm-tut-bucket-chips">
            {commands
              .filter((c) => c.visibility === key)
              .map((c) => (
                <span className="mm-chip" key={c.name}>
                  {c.label ?? c.name}
                </span>
              ))}
            {key === 'public'
              ? broadcasts.map((b) => (
                  <span className="mm-tut-feed-chip" key={b}>
                    <Bell size={12} strokeWidth={2.2} aria-hidden />
                    {b}
                  </span>
                ))
              : null}
          </div>
        </div>
      ))}
    </div>
  )
}

function Media({ media, reduce }: { media: TutorialMedia; reduce: boolean }) {
  if (media.type === 'video' && media.src) {
    // 재생 규격(§4): 무음 루프 인라인. reduced-motion 이면 자동재생 없이 poster.
    return (
      <video
        className="mm-tut-video"
        src={media.src}
        poster={media.poster}
        autoPlay={!reduce}
        muted
        loop
        playsInline
        preload="metadata"
        controls={reduce}
      />
    )
  }
  if (media.type === 'video') return <>{media.fallback}</>
  return <>{media.node}</>
}

function ProgressBar({ step }: { step: TutorialStep }) {
  // 챕터별 세그먼트: 지나온 챕터는 가득, 현재 챕터는 챕터 내 진행률만큼.
  const stepIdx = TUTORIAL_STEPS.indexOf(step)
  return (
    <div
      className="mm-tut-progress"
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={TOTAL}
      aria-valuenow={stepIdx + 1}
      aria-label={`튜토리얼 진행 — ${step.chapter}`}
    >
      {TUTORIAL_CHAPTERS.map((chapter) => {
        const inChapter = TUTORIAL_STEPS.filter((s) => s.chapter === chapter)
        const done = inChapter.filter(
          (s) => TUTORIAL_STEPS.indexOf(s) <= stepIdx,
        ).length
        const fill = done / inChapter.length
        return (
          <span className="mm-tut-seg" key={chapter} title={chapter}>
            <span
              className="mm-tut-seg-fill"
              style={{ transform: `scaleX(${fill})` }}
            />
          </span>
        )
      })}
    </div>
  )
}

export function Tutorial() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const stepNo = clampStep(searchParams.get('step'))
  const step = TUTORIAL_STEPS[stepNo - 1]
  const isLast = stepNo === TOTAL
  const reduce = usePrefersReducedMotion()

  const go = React.useCallback(
    (n: number) => {
      const next = Math.min(Math.max(n, 1), TOTAL)
      router.replace(`/tutorial?step=${next}`, { scroll: false })
    },
    [router],
  )

  // 키보드 ←→ (D7)
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go(stepNo + 1)
      if (e.key === 'ArrowLeft') go(stepNo - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, stepNo])

  // 풀스크린 동안 배경(문서 크롬) 스크롤 잠금
  React.useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [])

  return (
    <div className="mm-tut" role="dialog" aria-label="메이트 인터랙티브 튜토리얼">
      <header className="mm-tut-top">
        <a className="mm-tut-brand" href="/">
          <MushroomMark size={22} />
          <span>메이트 튜토리얼</span>
        </a>
        <ProgressBar step={step} />
        <span className="mm-tut-badge">
          <Clock size={12} strokeWidth={2.5} aria-hidden />약 5분이면 끝
        </span>
        <a className="mm-tut-close" href="/" aria-label="튜토리얼 닫고 홈으로">
          <X size={20} strokeWidth={2} aria-hidden />
        </a>
      </header>

      <main className="mm-tut-body" key={stepNo}>
        <div className="mm-tut-kicker">
          {step.chapter} · {stepNo}/{TOTAL}
        </div>
        <h1 className="mm-tut-title">{step.title}</h1>
        {step.sub ? <p className="mm-tut-sub">{step.sub}</p> : null}

        {step.media ? (
          <div className="mm-tut-media">
            <Media media={step.media} reduce={reduce} />
          </div>
        ) : null}
        {step.layout === 'doors' ? <DoorsList commands={step.commands} /> : null}
        {step.layout === 'summary' ? (
          <VisibilitySummary
            commands={step.commands}
            broadcasts={step.broadcasts}
          />
        ) : null}
      </main>

      <footer className="mm-tut-nav">
        <button
          type="button"
          className="mm-btn-ghost mm-tut-prev"
          onClick={() => go(stepNo - 1)}
          disabled={stepNo === 1}
        >
          <ArrowLeft size={15} strokeWidth={2} aria-hidden />
          이전
        </button>

        <span className="mm-tut-count">
          {stepNo} / {TOTAL}
        </span>

        {isLast ? (
          <div className="mm-tut-finish-cta">
            <a
              className="mm-btn-primary"
              href={INVITE_URL}
              target="_blank"
              rel="noreferrer"
            >
              봇 초대하기
            </a>
            <a className="mm-btn-ghost" href="/commands">
              <BookOpen size={15} strokeWidth={2} aria-hidden />
              전체 명령어 보기
            </a>
          </div>
        ) : (
          <button
            type="button"
            className="mm-btn-primary mm-tut-next"
            onClick={() => go(stepNo + 1)}
          >
            다음
            <ArrowRight size={15} strokeWidth={2} aria-hidden />
          </button>
        )}
      </footer>
    </div>
  )
}
