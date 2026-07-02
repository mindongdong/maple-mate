/**
 * 디스코드 임베드 목업 (실데이터 금지 → 데모용 가짜 닉/수치).
 * 비교·리더보드 결과는 봇 실제 렌더러 PNG(site/public/shots/)로 대체했고, 여기 남은 건
 * PNG 가 없는 텍스트 임베드 명령(가이드·스케줄러·정기 알림·등록 결과)과 랜딩 히어로 목업뿐.
 *
 * 임베드 내부의 메달 이모지(🥇🥈🥉)·체크(⬜✅)는 "디스코드 화면"을 표현하므로 허용.
 * 사이트 크롬(네비·배지·노트)의 Lucide 통일 정책(D13)과 구분된다.
 */
import * as React from 'react'
import { Trophy, History } from 'lucide-react'

/** 경험치 리더보드 — 레벨 추이 바(순위키 = 레벨, exp%). 랜딩 히어로 목업 전용. */
type Row = { name: string; level: number; pct: number; medal?: 'gold' | 'silver' | 'bronze' }
const LEADERBOARD: Row[] = [
  { name: '홍길동전사', level: 275, pct: 92, medal: 'gold' },
  { name: '불꽃아크', level: 268, pct: 80, medal: 'silver' },
  { name: '바람궁수', level: 261, pct: 71, medal: 'bronze' },
  { name: '이글루법사', level: 255, pct: 62 },
  { name: '캐논슈터', level: 249, pct: 54 },
  { name: '나이트로드', level: 243, pct: 47 },
  { name: '플레임위자드', level: 238, pct: 40 },
]

const MEDAL: Record<string, string> = { gold: '🥇', silver: '🥈', bronze: '🥉' }

export function LeaderboardEmbed({ rows = 7 }: { rows?: number }) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">
        <Trophy size={13} strokeWidth={2.5} aria-hidden />
        경험치 리더보드 — Top {rows}
      </div>
      {LEADERBOARD.slice(0, rows).map((r, i) => (
        <div className="mm-bar-row" key={r.name}>
          <span className="mm-bar-rank" style={r.medal ? undefined : { color: '#72767d' }}>
            {r.medal ? MEDAL[r.medal] : i + 1}
          </span>
          <span className="mm-bar-name">{r.name}</span>
          <span className="mm-bar-bg">
            <span
              className={`mm-bar-fill${r.medal ? ` ${r.medal}` : ''}`}
              style={{ width: `${r.pct}%` }}
            />
          </span>
          <span className="mm-bar-level">Lv.{r.level}</span>
        </div>
      ))}
      <div className="mm-embed-footer">2026-07-01 기준 · /경험치</div>
    </div>
  )
}

/** 스케줄러 숙제 DM — todo-first(숫자만, 미완료 전부 나열). */
export function SchedulerEmbed() {
  return (
    <div className="mm-embed mm-embed--orange">
      <div className="mm-embed-title mm-embed-title--orange">
        <History size={12} strokeWidth={2.5} aria-hidden />
        오늘의 숙제 — 홍길동전사
      </div>
      <div className="mm-todo-row"><span className="mm-todo-check">⬜</span>에픽던전 · 무릉도장</div>
      <div className="mm-todo-row"><span className="mm-todo-check done">✅</span><span className="done">일일 보스 3</span></div>
      <div className="mm-todo-row"><span className="mm-todo-check">⬜</span>주간 보스 <span style={{ color: '#72767d' }}>· 5/8 처치</span></div>
      <div className="mm-todo-row"><span className="mm-todo-check">⬜</span>길드 미션 P · 플래그 · 수로</div>
      <div className="mm-todo-sub">매일 정한 시각에 DM · 등록 캐릭터 전부</div>
    </div>
  )
}

/** 가이드 — 6그룹 요약(등록 없이 바로 · ephemeral). */
export function GuideEmbed() {
  const groups: [string, string][] = [
    ['📝 등록·관리', '/캐릭터등록 · /키등록 · /대표지정 · /캐릭터목록'],
    ['⚔️ 스펙·장비', '/스펙 · /아이템 · /유니온'],
    ['📜 이력', '/스타포스 · /잠재'],
    ['📈 리더보드', '/경험치'],
    ['🗓 스케줄러 숙제', '/스케줄러 · /스케줄러알림'],
    ['🔔 알림 설정', '/경험치알림 · /공지알림 · /썬데이알림'],
  ]
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">메이트 가이드</div>
      {groups.map(([h, line]) => (
        <div style={{ marginBottom: 7 }} key={h}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#5ec8c8' }}>{h}</div>
          <div style={{ fontSize: 10, color: '#b0bac8', fontFamily: 'var(--font-mono)' }}>{line}</div>
        </div>
      ))}
      <div className="mm-embed-footer">ephemeral · 본인에게만 표시 · /가이드</div>
    </div>
  )
}

/** 정기 알림 구독 확인 — 채널/개인 DM 공통(경험치·공지·썬데이). */
export function AlertEmbed({ title, line }: { title: string; line: string }) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">{title}</div>
      <div style={{ fontSize: 12, color: '#dcddde' }}>{line}</div>
      <div className="mm-todo-sub">대상: 채널 또는 본인 DM · 켜기 · 끄기</div>
    </div>
  )
}

/** 등록·관리 결과(캐릭터등록/키등록/대표지정/캐릭터목록). */
export function RegisterEmbed({ title, line }: { title: string; line: string }) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">{title}</div>
      <div style={{ fontSize: 12, color: '#dcddde' }}>{line}</div>
      <div className="mm-todo-sub">본인에게만 표시(ephemeral)</div>
    </div>
  )
}
