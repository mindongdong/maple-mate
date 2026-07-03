/**
 * 디스코드 임베드 목업 (실데이터 금지 → 데모용 가짜 닉/수치).
 * 비교·리더보드·스케줄러 결과는 봇 실제 렌더러 PNG(site/public/shots/)로 대체했고, 여기 남은 건
 * PNG 가 없는 텍스트 임베드 명령(가이드·정기 알림·등록 결과)과 랜딩 히어로 목업뿐.
 *
 * 임베드 내부의 메달 이모지(🥇🥈🥉)·체크(⬜✅)는 "디스코드 화면"을 표현하므로 허용.
 * 사이트 크롬(네비·배지·노트)의 Lucide 통일 정책(D13)과 구분된다.
 */
import * as React from 'react'

/** 경험치 리더보드 — 실제 /경험치 임베드와 동일한 순위 텍스트(메달 · **닉** — Lv.X (Y%)).
 *  실제 임베드엔 진행 바가 없으므로 바 없이 텍스트로만. 랜딩 히어로 목업 전용. */
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

export function LeaderboardEmbed({ rows = 5 }: { rows?: number }) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">📈 경험치 리더보드</div>
      <div className="mm-rank-list">
        {LEADERBOARD.slice(0, rows).map((r, i) => (
          <div className="mm-rank-line" key={r.name}>
            <span className="mm-rank-badge">{r.medal ? MEDAL[r.medal] : `${i + 1}.`}</span>
            <span>
              <b className="mm-rank-name">{r.name}</b>
              <span className="mm-rank-lv"> — Lv.{r.level} ({r.pct}%)</span>
            </span>
          </div>
        ))}
      </div>
      <div className="mm-embed-footer">기준: 오늘(07/01) 현재 · NEXON Open API</div>
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

/** 정기 알림 구독 확인 — 경험치·공지·썬데이(채널/개인 DM)와 스케줄러알림(본인 DM). */
export function AlertEmbed({
  title,
  line,
  sub = '대상: 채널 또는 본인 DM · 켜기 · 끄기',
}: {
  title: string
  line: string
  sub?: string
}) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">{title}</div>
      <div style={{ fontSize: 12, color: '#dcddde' }}>{line}</div>
      <div className="mm-todo-sub">{sub}</div>
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
