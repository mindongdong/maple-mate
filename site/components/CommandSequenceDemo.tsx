'use client'
/**
 * S6·S9 튜토리얼 미디어 — "봇을 실제로 쓰는" 느낌의 명령 시퀀스 애니.
 * DiscordDemo(순차 등장·타이핑 도트·루프) + SlashDemo(/ 명령 팝업)를 합친 상태머신.
 *
 * - 느린 실행: / 타이핑 → 명령 팝업 → 선택 → 파라미터 칩(전체 목록) → 값 채움 →
 *   전송 버튼 게이트(클릭 대기, 10s 후 자동) → 봇 타이핑 → 결과 임베드+PNG.
 * - 빠른 실행: 입력 장면 없이 메시지 등장 → 봇 타이핑 → 결과.
 * - 루프: 마지막 결과 3s 멈춤 → 처음부터.
 * - prefers-reduced-motion: 애니·게이트 없이 정적 전체 표시(패널 overflow 클립).
 *
 * 룩 재사용: 채팅 = hero.css `.mm-chat-*` + tutorial.css `.mm-tut-media .mm-chat*` 오버라이드,
 * 팝업 = `.mm-tut-popup*`, 입력바 = `.mm-tut-input`. 게이트·칩은 tutorial.css `.mm-tut-seq-*`.
 *
 * ⚠️ 드리프트 가드(check-command-drift.mjs·test_website_command_drift.py)는 tutorial-steps.tsx
 *    만 정규식으로 읽는다(이 파일은 스캔 대상 아님). 그래도 오탐 방지를 위해 대본 데이터에
 *    `{ name: ..., visibility: ..., label: ... }` 리터럴 패턴을 쓰지 않는다 — 파라미터 키는
 *    p(칩 라벨)·v(선택값)·pick·opts 로 둔다.
 */
import * as React from 'react'
import { Hash, SendHorizontal } from 'lucide-react'
import { MushroomMark } from './Mushroom'
import {
  S6_SCRIPT,
  S9_SCRIPT,
  type Run,
  type RunParam,
} from './commandSequenceScripts'

/* ---- 국면 타이밍(ms) — 작업지시서 §2 결정 5 ---- */
const T = {
  popup: 1200, // 팝업 노출
  chips: 2000, // 파라미터 칩 전체 목록
  fill: 1500, // 값 하나 선택
  gate: 10000, // 게이트 자동 전송(미클릭)
  botSlow: 1000, // 느린 봇 타이핑 도트
  dwellSlow: 3500, // 느린 결과 멈춤
  botFast: 500, // 빠른 봇 타이핑 도트
  dwellFast: 1100, // 빠른 결과 멈춤
  loopHold: 3000, // 마지막 결과 뒤 멈춤
} as const

type Phase =
  | 'typing-slash'
  | 'popup'
  | 'select-cmd'
  | 'chips'
  | 'fill'
  | 'await-send'
  | 'sent'
  | 'bot-typing'
  | 'result'

function usePrefersReducedMotion(): boolean {
  const [reduce, setReduce] = React.useState(false)
  React.useEffect(() => {
    setReduce(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  }, [])
  return reduce
}

/* ---- 디스코드 조각 ---- */

function UserLine({ text }: { text: string }) {
  return (
    <div className="mm-chat-line mm-chat-msg">
      <span className="mm-chat-av" style={{ background: '#e0a030' }}>
        지
      </span>
      <div className="mm-chat-content">
        <div className="mm-chat-meta">
          <span className="mm-chat-name" style={{ color: '#e0a030' }}>
            지훈
          </span>
        </div>
        <span className="mm-chat-cmd">{text}</span>
      </div>
    </div>
  )
}

function BotLine({ children }: { children: React.ReactNode }) {
  return (
    <div className="mm-chat-line mm-chat-msg">
      <span className="mm-chat-av mm-chat-av--bot">
        <MushroomMark size={22} />
      </span>
      <div className="mm-chat-content">
        <div className="mm-chat-meta">
          <span className="mm-chat-name mm-chat-name--bot">메이트</span>
          <span className="mm-chat-tag">봇</span>
        </div>
        <div className="mm-chat-reply">{children}</div>
      </div>
    </div>
  )
}

function BotTyping() {
  return (
    <div className="mm-chat-line mm-chat-msg">
      <span className="mm-chat-av mm-chat-av--bot">
        <MushroomMark size={22} />
      </span>
      <div className="mm-chat-content">
        <div className="mm-chat-meta">
          <span className="mm-chat-name mm-chat-name--bot">메이트</span>
          <span className="mm-chat-tag">봇</span>
        </div>
        <div className="mm-chat-dots">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  )
}

/** 명령 팝업(느린 실행 입력 장면). 첫 항목이 실행할 명령. */
function CommandPopup({ run }: { run: Run }) {
  return (
    <div className="mm-tut-popup mm-tut-seq-popup">
      <div className="mm-tut-popup-head">메이트 명령어</div>
      <div className="mm-tut-popup-item is-active">
        <span className="mm-tut-popup-cmd">/{run.cmd}</span>
        <span className="mm-tut-popup-desc">{run.desc}</span>
        <span className="mm-tut-popup-bot">
          <MushroomMark size={15} /> 메이트
        </span>
      </div>
    </div>
  )
}

/** 멤버 목록 팝업 캐스트(작업지시서 §3 — 지훈·수아·민준). */
const MEMBERS = [
  { n: '지훈', c: '#e0a030' },
  { n: '수아', c: '#5865f2' },
  { n: '민준', c: '#3ba55d' },
]

/** run 의 pick 파라미터 목록(채우는 장면 순서 기준). */
function pickParamsOf(run: Run): RunParam[] {
  return run.params.filter((prm) => prm.pick && prm.pick !== 'skip')
}

/**
 * fill 국면 값 선택 팝업 — pick:'choice' 는 선택지 목록(본서버/챌린저스),
 * pick:'member' 는 멤버 목록(지훈·수아·민준). 선택될 항목이 하이라이트된다.
 */
function ValuePicker({ prm }: { prm: RunParam }) {
  const target = prm.v?.replace(/^@/, '')
  const isMember = prm.pick === 'member'
  return (
    <div className="mm-tut-popup mm-tut-seq-popup mm-tut-seq-pick">
      <div className="mm-tut-popup-head">
        {prm.p} — {isMember ? '멤버 선택' : '선택지'}
      </div>
      {isMember
        ? MEMBERS.map((m) => (
            <div
              key={m.n}
              className={`mm-tut-popup-item${m.n === target ? ' is-active' : ''}`}
            >
              <span className="mm-tut-seq-mav" style={{ background: m.c }}>
                {m.n[0]}
              </span>
              <span className="mm-tut-seq-mname">{m.n}</span>
            </div>
          ))
        : (prm.opts ?? []).map((o) => (
            <div
              key={o}
              className={`mm-tut-popup-item${o === target ? ' is-active' : ''}`}
            >
              <span className="mm-tut-seq-mname">{o}</span>
            </div>
          ))}
    </div>
  )
}

/**
 * 입력바 — 명령·파라미터 칩·게이트 전송 버튼.
 * typing-slash·popup 국면은 "/" + 캐럿만(타이핑 중), select-cmd 부터 명령명이 채워진다.
 * filled = 지금까지 값이 채워진 pick 파라미터 수(fill 반복 진행도).
 */
function InputBar({
  run,
  phase,
  filled,
  picking,
  onSend,
}: {
  run: Run
  phase: Phase
  filled: number
  picking?: RunParam
  onSend?: () => void
}) {
  const typing = phase === 'typing-slash' || phase === 'popup'
  const showChips = phase === 'chips' || phase === 'fill' || phase === 'await-send'
  const gate = phase === 'await-send'
  const pickParams = pickParamsOf(run)
  return (
    <div className="mm-tut-input mm-tut-seq-input">
      <div className="mm-tut-seq-inputline">
        {typing ? (
          <>
            <span className="mm-tut-input-slash">/</span>
            <span className="mm-tut-caret" aria-hidden />
          </>
        ) : (
          <span className="mm-tut-seq-cmd">/{run.cmd}</span>
        )}
        {showChips ? (
          <span className="mm-tut-seq-chips">
            {run.params.map((prm) => {
              // ⚠️ 채움 판정은 pick 순서 기준(배열 인덱스 아님) —
              //    pick 파라미터가 목록 뒤쪽이어도 fill 진행에 맞춰 채워진다.
              const pickIdx = pickParams.indexOf(prm)
              const done = prm.v != null && pickIdx !== -1 && pickIdx < filled
              const cls = `mm-tut-seq-chip${done ? ' is-filled' : ''}${
                prm === picking ? ' is-picking' : ''
              }`
              return (
                <span key={prm.p} className={cls}>
                  {prm.p}
                  {done ? <b>: {prm.v}</b> : null}
                </span>
              )
            })}
          </span>
        ) : typing ? null : (
          <span className="mm-tut-caret" aria-hidden />
        )}
      </div>
      <button
        type="button"
        className={`mm-tut-seq-send${gate ? ' is-armed' : ''}`}
        onClick={gate ? onSend : undefined}
        tabIndex={gate ? 0 : -1}
        aria-label="전송"
      >
        <SendHorizontal size={16} strokeWidth={2.4} aria-hidden />
      </button>
      {gate ? (
        <span className="mm-tut-seq-hint" aria-hidden>
          눌러서 전송해 보세요
        </span>
      ) : null}
    </div>
  )
}

/* ---- 상태머신 ---- */

type Snapshot = {
  phase: Phase
  runIndex: number
  filled: number
  /** 지금까지 대화 로그에 쌓인, 이번 사이클에서 완료된 run들의 인덱스. */
  history: number[]
}

/** run 의 시작 국면 — 빠른 실행은 sent, 느린 실행은 typing-slash(startAt:'chips' 면 칩부터). */
function startPhaseOf(run: Run): Phase {
  if (run.speed === 'fast') return 'sent'
  return run.startAt === 'chips' ? 'chips' : 'typing-slash'
}

function resetSnapshot(runs: Run[]): Snapshot {
  return { phase: startPhaseOf(runs[0]), runIndex: 0, filled: 0, history: [] }
}

export function CommandSequenceDemo({
  script,
  channel = '메이플-길드',
}: {
  script: 'S6' | 'S9'
  channel?: string
}) {
  const runs = script === 'S6' ? S6_SCRIPT : S9_SCRIPT
  const reduce = usePrefersReducedMotion()
  const [snap, setSnap] = React.useState<Snapshot>(() => resetSnapshot(runs))
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  // 게이트 전송(클릭 또는 10s 자동) — 다음 국면(sent)으로.
  const advanceFromGate = React.useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    setSnap((s) => (s.phase === 'await-send' ? { ...s, phase: 'sent' } : s))
  }, [])

  React.useEffect(() => {
    if (reduce) return // 정적 표시(아래 렌더에서 전량 표시)
    if (timer.current) clearTimeout(timer.current)

    const run = runs[snap.runIndex]
    const isLastRun = snap.runIndex >= runs.length - 1

    const step = (next: Snapshot, delay: number) => {
      timer.current = setTimeout(() => setSnap(next), delay)
    }

    const nextRun = (): Snapshot => {
      const done = [...snap.history, snap.runIndex]
      if (isLastRun) return resetSnapshot(runs) // 루프 리셋
      const ni = snap.runIndex + 1
      return { phase: startPhaseOf(runs[ni]), runIndex: ni, filled: 0, history: done }
    }

    if (run.speed === 'fast') {
      switch (snap.phase) {
        case 'sent':
          step({ ...snap, phase: 'bot-typing' }, 550) // 메시지 등장 뒤 짧은 텀
          break
        case 'bot-typing':
          step({ ...snap, phase: 'result' }, T.botFast)
          break
        case 'result':
          step(nextRun(), isLastRun ? T.loopHold : T.dwellFast)
          break
        default:
          // 방어: 빠른 실행은 항상 sent 로 시작
          setSnap({ ...snap, phase: 'sent' })
      }
      return () => {
        if (timer.current) clearTimeout(timer.current)
      }
    }

    // ---- 느린 실행 ----
    const pickCount = pickParamsOf(run).length
    switch (snap.phase) {
      case 'typing-slash':
        step({ ...snap, phase: 'popup' }, 650)
        break
      case 'popup':
        step({ ...snap, phase: 'select-cmd' }, T.popup)
        break
      case 'select-cmd':
        step({ ...snap, phase: 'chips' }, 500)
        break
      case 'chips':
        // 채울 값이 있으면 fill 반복, 없으면 곧장 게이트.
        step(
          pickCount > 0
            ? { ...snap, phase: 'fill', filled: 0 }
            : { ...snap, phase: 'await-send' },
          T.chips,
        )
        break
      case 'fill': {
        const nextFilled = snap.filled + 1
        step(
          nextFilled >= pickCount
            ? { ...snap, phase: 'await-send', filled: nextFilled }
            : { ...snap, phase: 'fill', filled: nextFilled },
          T.fill,
        )
        break
      }
      case 'await-send':
        // 게이트: 10초 뒤 자동 전송(클릭 시 advanceFromGate 가 먼저 발화).
        step({ ...snap, phase: 'sent' }, T.gate)
        break
      case 'sent':
        step({ ...snap, phase: 'bot-typing' }, 550)
        break
      case 'bot-typing':
        step({ ...snap, phase: 'result' }, T.botSlow)
        break
      case 'result':
        step(nextRun(), isLastRun ? T.loopHold : T.dwellSlow)
        break
    }

    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [snap, runs, reduce])

  // ---- reduced-motion: 전체 정적 표시(마지막 대화만 클립으로 보임) ----
  if (reduce) {
    return (
      <div className="mm-chat mm-tut-seq" aria-hidden>
        <div className="mm-chat-head">
          <Hash size={15} strokeWidth={2.5} />
          <span>{channel}</span>
        </div>
        <div className="mm-chat-body">
          {runs.map((run, i) => (
            <React.Fragment key={i}>
              <UserLine text={userText(run)} />
              <BotLine>{run.reply}</BotLine>
            </React.Fragment>
          ))}
        </div>
      </div>
    )
  }

  const run = runs[snap.runIndex]
  // fill 국면에서 지금 값을 고르는 pick 파라미터(선택 팝업·칩 하이라이트 대상).
  const picking =
    run.speed === 'slow' && snap.phase === 'fill'
      ? pickParamsOf(run)[snap.filled]
      : undefined
  const showInputScene =
    run.speed === 'slow' &&
    (snap.phase === 'typing-slash' ||
      snap.phase === 'popup' ||
      snap.phase === 'select-cmd' ||
      snap.phase === 'chips' ||
      snap.phase === 'fill' ||
      snap.phase === 'await-send')
  const showUser =
    snap.phase === 'sent' || snap.phase === 'bot-typing' || snap.phase === 'result'
  const showTyping = snap.phase === 'bot-typing'
  const showResult = snap.phase === 'result'

  return (
    <div className="mm-chat mm-tut-seq" aria-hidden>
      <div className="mm-chat-head">
        <Hash size={15} strokeWidth={2.5} />
        <span>{channel}</span>
      </div>
      <div className="mm-chat-body">
        {/* 직전 완료 run 1건을 배경 맥락으로 남겨 "대화가 이어지는" 느낌 */}
        {snap.history.length > 0 ? (
          <>
            <UserLine text={userText(runs[snap.history[snap.history.length - 1]])} />
            <BotLine>{runs[snap.history[snap.history.length - 1]].reply}</BotLine>
          </>
        ) : null}

        {showUser ? <UserLine text={userText(run)} /> : null}
        {showTyping ? <BotTyping /> : null}
        {showResult ? <BotLine>{run.reply}</BotLine> : null}
      </div>

      {run.speed === 'slow' && (snap.phase === 'popup' || snap.phase === 'select-cmd') ? (
        <CommandPopup run={run} />
      ) : null}
      {picking ? <ValuePicker prm={picking} /> : null}

      {showInputScene ? (
        <InputBar
          run={run}
          phase={snap.phase}
          filled={snap.filled}
          picking={picking}
          onSend={advanceFromGate}
        />
      ) : null}
    </div>
  )
}

/** 유저 채팅에 표시할 명령 문자열(채운 값 병기). */
function userText(run: Run): string {
  const filled = run.params.filter((p) => p.v != null)
  if (filled.length === 0) return `/${run.cmd}`
  return `/${run.cmd} ${filled.map((p) => `${p.p}:${p.v}`).join(' ')}`
}
