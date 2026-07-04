/**
 * 튜토리얼 스텝 미디어 — CSS 목업(폴백·애니) 모음.
 * 녹화 영상(🎬)이 들어오기 전 PR1 폴백 + 순수 CSS 애니(✨) 스크린을 담당한다.
 * 디스코드 룩은 hero.css(.mm-chat-*)·embeds.css(.mm-embed) 클래스를 재사용하고,
 * 튜토리얼 전용 스타일은 app/tutorial.css(.mm-tut-*)에 둔다.
 */
import * as React from 'react'
import { ArrowDown, Bell, Copy, Eye, Globe, Sun, TrendingUp } from 'lucide-react'
import { MushroomFull, MushroomMark } from './Mushroom'

/* ---- 공용 조각: 디스코드 대화 라인 ---- */

function UserCmd({ cmd }: { cmd: string }) {
  return (
    <div className="mm-chat-line">
      <span className="mm-chat-av" style={{ background: '#e0a030' }}>
        나
      </span>
      <div className="mm-chat-content">
        <div className="mm-chat-meta">
          <span className="mm-chat-name" style={{ color: '#e0a030' }}>
            지훈
          </span>
        </div>
        <span className="mm-chat-cmd">{cmd}</span>
      </div>
    </div>
  )
}

function BotReply({ children }: { children: React.ReactNode }) {
  return (
    <div className="mm-chat-line">
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

/** 디스코드 ephemeral 안내줄 — "나만 봐요"를 화면 그대로 가르치는 조각. */
function EphemeralNote() {
  return (
    <div className="mm-tut-ephemeral">
      <Eye size={12} strokeWidth={2} aria-hidden />
      이 메시지는 당신만 볼 수 있어요
    </div>
  )
}

/** 디스코드 패널 래퍼(다크 고정 — 실제 디스코드 룩). */
function DiscordPanel({ children }: { children: React.ReactNode }) {
  return <div className="mm-tut-discord">{children}</div>
}

/* ---- S3: 명령어 기초 — `/` 입력 → 자동완성 목록 ---- */

const SLASH_ITEMS = [
  { cmd: '가이드', desc: '메이트 사용법 안내' },
  { cmd: '캐릭터등록', desc: '메이플 캐릭터 등록' },
  { cmd: '스펙', desc: '전투력·스펙 비교' },
  { cmd: '경험치', desc: '레벨 추이 리더보드' },
]

export function SlashDemo() {
  return (
    <DiscordPanel>
      <div className="mm-tut-popup">
        <div className="mm-tut-popup-head">메이트 명령어</div>
        {SLASH_ITEMS.map((it, i) => (
          <div
            className={`mm-tut-popup-item${i === 0 ? ' is-active' : ''}`}
            key={it.cmd}
          >
            <span className="mm-tut-popup-cmd">/{it.cmd}</span>
            <span className="mm-tut-popup-desc">{it.desc}</span>
            <span className="mm-tut-popup-bot">
              <MushroomMark size={15} /> 메이트
            </span>
          </div>
        ))}
      </div>
      <div className="mm-tut-input">
        <span className="mm-tut-input-slash">/</span>
        <span className="mm-tut-caret" aria-hidden />
      </div>
    </DiscordPanel>
  )
}

/* ---- S4: 등록 없이 바로 — 알림 3종 미리보기 ---- */

const ALERTS = [
  {
    icon: Bell,
    label: '공지 알림',
    body: '일정 시간마다 공지를 확인해서 새로 생기면 발송해요',
  },
  { icon: TrendingUp, label: '경험치 리더보드', body: '매일 오전 10시에 자동 발송해요' },
  {
    icon: Sun,
    label: '썬데이 메이플',
    body: '매주 금요일 오전 10시 10분에 썬데이 메이플을 알려줘요',
  },
]

export function AlertsDemo() {
  return (
    <div className="mm-tut-alerts">
      {ALERTS.map(({ icon: Icon, label, body }) => (
        <div className="mm-tut-alert" key={label}>
          <span className="mm-tut-alert-icon">
            <Icon size={16} strokeWidth={2} aria-hidden />
          </span>
          <div>
            <div className="mm-tut-alert-label">{label}</div>
            <div className="mm-tut-alert-body">{body}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ---- S5: 캐릭터 등록 실행 장면 ---- */

export function RegisterDemo() {
  return (
    <DiscordPanel>
      <UserCmd cmd="/캐릭터등록 캐릭터명:메이트" />
      <BotReply>
        <div className="mm-embed">
          <div className="mm-embed-title">캐릭터 등록 완료</div>
          <div className="mm-tut-embed-body">
            <b>메이트</b> · Lv.274 · 나이트로드
            <br />
            이제 스펙·유니온·경험치 비교에서 바로 쓸 수 있어요.
          </div>
        </div>
        <EphemeralNote />
      </BotReply>
    </DiscordPanel>
  )
}

/* ---- S7: 넥슨 API 키 발급 — 브라우저 폼 목업 ---- */

// getting-started.mdx 폼 표와 동일 값(전체 7행).
const KEY_FORM_ROWS = [
  ['게임 선택', '메이플스토리'],
  ['애플리케이션 타입', '서비스 단계'],
  ['대표 언어', '한국어'],
  ['출시할 서비스명', '메이트'],
  ['서비스 소개', '스케줄러 기능 및 큐브, 스타포스 내역 조회'],
  ['개발 환경', '기타 (Pc App, 서버간 통신 등)'],
  ['URL 정보', 'https://maplemate.site/'],
]

export function KeyIssueDemo() {
  return (
    <div className="mm-tut-browser">
      <div className="mm-tut-browser-bar">
        <Globe size={12} strokeWidth={2} aria-hidden />
        openapi.nexon.com
      </div>
      <div className="mm-tut-browser-body">
        {KEY_FORM_ROWS.map(([label, value]) => (
          <div className="mm-tut-form-row" key={label}>
            <span>{label}</span>
            <b>{value}</b>
          </div>
        ))}
        <div className="mm-tut-key-row">
          <span className="mm-tut-key">live_a1b2c3••••••••••</span>
          <span className="mm-tut-copy">
            <Copy size={12} strokeWidth={2} aria-hidden />
            복사
          </span>
        </div>
      </div>
    </div>
  )
}

/* ---- S8: /키등록 실행 장면 (ephemeral 강조) ---- */

export function KeyRegisterDemo() {
  return (
    <DiscordPanel>
      <UserCmd cmd="/키등록 키:live_a1b2c3••••••••••" />
      <BotReply>
        <div className="mm-embed">
          <div className="mm-embed-title">API 키 등록 완료</div>
          <div className="mm-tut-embed-body">
            키는 암호화해서 안전하게 보관해요.
            <br />
            스타포스·잠재·스케줄러가 열렸어요!
          </div>
        </div>
        <EphemeralNote />
      </BotReply>
    </DiscordPanel>
  )
}

/* ---- S10: 대상 지정 기조 — 안 적으면 전원, 적으면 그 사람들만 ---- */

export function TargetDemo() {
  return (
    <div className="mm-tut-target">
      <div className="mm-tut-target-col">
        <span className="mm-chat-cmd">/유니온</span>
        <ArrowDown size={16} strokeWidth={2} className="mm-tut-target-arrow" aria-hidden />
        <div className="mm-tut-target-out">
          <b>본인 포함 랜덤 최대 10명</b> 비교
        </div>
      </div>
      <div className="mm-tut-target-col">
        <span className="mm-chat-cmd">/유니온 대상:@수아</span>
        <ArrowDown size={16} strokeWidth={2} className="mm-tut-target-arrow" aria-hidden />
        <div className="mm-tut-target-out">
          <b>수아</b>의 대표 캐릭터만 비교
        </div>
      </div>
    </div>
  )
}

/* ---- S2·S6·S9: 정적 스샷 콜라주(기존 shots/ PNG 재활용) ---- */

export function ShotCollage({
  shots,
}: {
  shots: { src: string; alt: string }[]
}) {
  return (
    <div className="mm-tut-collage" data-count={shots.length}>
      {shots.map((s) => (
        <img key={s.src} src={s.src} alt={s.alt} className="mm-shot-img" />
      ))}
    </div>
  )
}

/* ---- S12: 완료 — 마스코트 축하 패널 ---- */

export function FinishPanel() {
  return (
    <div className="mm-tut-finish" aria-hidden>
      <span className="mm-tut-spark mm-tut-spark--1" />
      <span className="mm-tut-spark mm-tut-spark--2" />
      <span className="mm-tut-spark mm-tut-spark--3" />
      <MushroomFull size={132} className="mm-tut-finish-mushroom" />
    </div>
  )
}
