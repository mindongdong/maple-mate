'use client'
/**
 * 랜딩 히어로 — 디스코드에서 메이트를 쓰는 시나리오 목업(장식성 CSS 목업).
 * 명령어 입력 → 봇 응답(경험치·유니온)이 순차적으로 쌓이는 루프. "메이플 디스코드 봇"임을
 * 직관적으로 전달하는 게 목적이라 2턴만 짧게. prefers-reduced-motion 이면 정적 표시(루프 없음).
 */
import * as React from 'react'
import { Hash } from 'lucide-react'
import { MushroomMark } from './Mushroom'
import { LeaderboardEmbed } from './Embeds'

function UnionMini() {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">유니온 비교</div>
      <div className="mm-chat-uni">
        <div><span className="mm-chat-uni-rank">🥇</span> 홍길동전사 · 유니온 <b>8,742</b> · 아티팩트 60</div>
        <div><span className="mm-chat-uni-rank">🥈</span> 불꽃아크 · 유니온 <b>8,210</b> · 아티팩트 57</div>
        <div><span className="mm-chat-uni-rank">🥉</span> 바람궁수 · 유니온 <b>7,650</b> · 아티팩트 54</div>
      </div>
      <div className="mm-embed-footer">유니온 · 아티팩트 · 챔피언 · /유니온</div>
    </div>
  )
}

type UserItem = { who: 'user'; author: string; color: string; initial: string; cmd: string }
type BotItem = { who: 'bot'; reply: React.ReactNode }
type Item = UserItem | BotItem

const SCRIPT: Item[] = [
  { who: 'user', author: '지훈', color: '#e0a030', initial: '지', cmd: '/경험치' },
  { who: 'bot', reply: <LeaderboardEmbed rows={4} /> },
  { who: 'user', author: '수아', color: '#5865f2', initial: '수', cmd: '/유니온' },
  { who: 'bot', reply: <UnionMini /> },
]

function UserRow({ item }: { item: UserItem }) {
  return (
    <>
      <span className="mm-chat-av" style={{ background: item.color }}>
        {item.initial}
      </span>
      <div className="mm-chat-content">
        <div className="mm-chat-meta">
          <span className="mm-chat-name" style={{ color: item.color }}>
            {item.author}
          </span>
        </div>
        <span className="mm-chat-cmd">{item.cmd}</span>
      </div>
    </>
  )
}

function BotHead() {
  return (
    <div className="mm-chat-meta">
      <span className="mm-chat-name mm-chat-name--bot">메이트</span>
      <span className="mm-chat-tag">봇</span>
    </div>
  )
}

export function DiscordDemo() {
  const [visible, setVisible] = React.useState(1)

  React.useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setVisible(SCRIPT.length)
      return
    }
    let n = 1
    let timer: ReturnType<typeof setTimeout>
    setVisible(1)
    const schedule = () => {
      const atEnd = n >= SCRIPT.length
      const next = atEnd ? 1 : n + 1
      // 곧 등장할 항목(SCRIPT[n])이 봇 응답이면 타이핑을 잠깐 보여주고(950ms),
      // 유저 메시지면 앞 응답을 읽을 틈(1500ms), 대화가 끝나면 멈춤(2800ms).
      const delay = atEnd ? 2800 : SCRIPT[n].who === 'bot' ? 950 : 1500
      timer = setTimeout(() => {
        n = next
        setVisible(n)
        schedule()
      }, delay)
    }
    schedule()
    return () => clearTimeout(timer)
  }, [])

  const pending = SCRIPT[visible]
  const showTyping = visible < SCRIPT.length && pending?.who === 'bot'

  return (
    <div className="mm-chat" aria-hidden>
      <div className="mm-chat-head">
        <Hash size={15} strokeWidth={2.5} />
        <span>메이플-길드</span>
      </div>
      <div className="mm-chat-body">
        {SCRIPT.slice(0, visible).map((it, i) => (
          <div className="mm-chat-line mm-chat-msg" key={i}>
            {it.who === 'user' ? (
              <UserRow item={it} />
            ) : (
              <>
                <span className="mm-chat-av mm-chat-av--bot">
                  <MushroomMark size={22} />
                </span>
                <div className="mm-chat-content">
                  <BotHead />
                  <div className="mm-chat-reply">{it.reply}</div>
                </div>
              </>
            )}
          </div>
        ))}
        {showTyping ? (
          <div className="mm-chat-line mm-chat-msg">
            <span className="mm-chat-av mm-chat-av--bot">
              <MushroomMark size={22} />
            </span>
            <div className="mm-chat-content">
              <BotHead />
              <div className="mm-chat-dots">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
