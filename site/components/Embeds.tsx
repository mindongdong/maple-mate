/**
 * 디스코드 임베드 목업 (실데이터 금지 → 데모용 가짜 닉/수치).
 * 실제 임베드 룩(다크 카드 + 좌측 컬러 바)을 재현한 고충실 플레이스홀더.
 * 데모 서버 재캡처 PNG 로 교체 예정(docs/website-screenshot-capture.md).
 *
 * 임베드 내부의 메달 이모지(🥇🥈🥉)·체크(⬜✅)는 "디스코드 화면"을 표현하므로 허용.
 * 사이트 크롬(네비·배지·콜아웃)의 Lucide 통일 정책(D13)과 구분된다.
 */
import * as React from 'react'
import { Trophy, Swords, History, Star } from 'lucide-react'

/** 경험치 리더보드 — 레벨 추이 바(순위키 = 레벨, exp%). rows 로 Top-N 조절. */
type Row = { name: string; level: number; pct: number; medal?: 'gold' | 'silver' | 'bronze' }
const LEADERBOARD: Row[] = [
  { name: '홍길동전사', level: 275, pct: 92, medal: 'gold' },
  { name: '불꽃아크', level: 268, pct: 80, medal: 'silver' },
  { name: '바람궁수', level: 261, pct: 71, medal: 'bronze' },
  { name: '이글루법사', level: 255, pct: 62 },
  { name: '캐논슈터', level: 249, pct: 54 },
  { name: '나이트로드', level: 243, pct: 47 },
  { name: '플레임위자드', level: 238, pct: 40 },
  { name: '눈의여왕', level: 232, pct: 34 },
  { name: '달빛나이트', level: 227, pct: 28 },
  { name: '별빛도적', level: 221, pct: 22 },
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

/** 스펙 요약 — 전투력·주스탯·크뎀 등 칩 나열. */
export function SpecEmbed() {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">
        <Swords size={13} strokeWidth={2.5} aria-hidden />
        홍길동전사의 스펙
      </div>
      <div className="mm-spec-row">
        <span className="mm-spec-item">전투력 <span className="val gold">6,421,538</span></span>
        <span className="mm-spec-item">주스탯 <span className="val">87,432</span></span>
        <span className="mm-spec-item">공격력 <span className="val">3,251</span></span>
      </div>
      <div className="mm-spec-row">
        <span className="mm-spec-item">크리티컬 확률 <span className="val">100%</span></span>
        <span className="mm-spec-item">크리티컬 데미지 <span className="val orange">88%</span></span>
        <span className="mm-spec-item">방어율 무시 <span className="val">95.4%</span></span>
      </div>
      <div className="mm-spec-row">
        <span className="mm-spec-item">아케인 포스 <span className="val gold">1,020</span></span>
        <span className="mm-spec-item">유니온 <span className="val">Lv.9</span></span>
        <span className="mm-spec-item">HEXA <span className="val">Lv.6</span></span>
      </div>
      <div className="mm-embed-footer">계정 전체 합산 · /스펙</div>
    </div>
  )
}

/** 아이템 — 부위별 스타포스·잠재. */
export function ItemEmbed() {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">
        <Swords size={13} strokeWidth={2.5} aria-hidden />
        홍길동전사의 장비
      </div>
      <div className="mm-spec-row">
        <span className="mm-spec-item">무기 <span className="val gold">★22</span></span>
        <span className="mm-spec-item">모자 <span className="val gold">★17</span></span>
        <span className="mm-spec-item">상의 <span className="val">★17</span></span>
      </div>
      <div className="mm-spec-row">
        <span className="mm-spec-item">잠재 <span className="val orange">레전드리</span></span>
        <span className="mm-spec-item">에디셔널 <span className="val">유니크</span></span>
        <span className="mm-spec-item">세트 <span className="val">보스 5셋</span></span>
      </div>
      <div className="mm-embed-footer">부위별 비교 · /아이템</div>
    </div>
  )
}

/** 유니온 — 레벨·조각·레이더. */
export function UnionEmbed() {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">
        <Trophy size={13} strokeWidth={2.5} aria-hidden />
        홍길동전사의 유니온
      </div>
      <div className="mm-union">
        <div className="mm-union-item"><span className="val">Lv.9</span>유니온 레벨</div>
        <div className="mm-union-item"><span className="val">+82</span>조각 STR</div>
        <div className="mm-union-item"><span className="val">+78</span>조각 DEX</div>
        <div className="mm-union-item"><span className="val">+4,800</span>최대 HP</div>
        <div className="mm-union-item"><span className="val">+20%</span>버프 지속</div>
        <div className="mm-union-item"><span className="val">SSS</span>아티팩트</div>
      </div>
      <div className="mm-embed-footer">2026-07-01 기준 · /유니온</div>
    </div>
  )
}

/** 스타포스 이력 비교 — 강화 수·지출·운빨. */
export function StarforceEmbed() {
  return (
    <div className="mm-embed mm-embed--orange">
      <div className="mm-embed-title mm-embed-title--orange">
        <Star size={12} strokeWidth={2.5} fill="currentColor" aria-hidden />
        스타포스 이력 비교
      </div>
      <table className="mm-cmp">
        <thead>
          <tr><th>이름</th><th>강화 수</th><th>총 지출</th><th>운빨</th></tr>
        </thead>
        <tbody>
          <tr><td><span className="name">홍길동전사</span></td><td>142건</td><td><span className="cost">3.8억</span></td><td><span className="luck">상위 23%</span></td></tr>
          <tr><td><span className="name">불꽃아크</span></td><td>98건</td><td><span className="cost">2.1억</span></td><td><span className="luck">상위 8%</span></td></tr>
          <tr><td><span className="name">바람궁수</span></td><td>215건</td><td><span className="cost">6.7억</span></td><td><span className="luck amber">상위 61%</span></td></tr>
        </tbody>
      </table>
      <div className="mm-embed-footer">★11성 이상만 집계 · 이벤트 보정 반영 · /스타포스</div>
    </div>
  )
}

/** 잠재 이력 비교 — 재설정·큐브·메소·등업. */
export function PotentialEmbed() {
  return (
    <div className="mm-embed mm-embed--orange">
      <div className="mm-embed-title mm-embed-title--orange">
        <History size={12} strokeWidth={2.5} aria-hidden />
        잠재 이력 비교
      </div>
      <table className="mm-cmp">
        <thead>
          <tr><th>이름</th><th>재설정</th><th>사용 메소</th><th>등업</th></tr>
        </thead>
        <tbody>
          <tr><td><span className="name">홍길동전사</span></td><td>312회</td><td><span className="cost">5.2억</span></td><td><span className="luck">잠재 3 · 에디 1</span></td></tr>
          <tr><td><span className="name">불꽃아크</span></td><td>188회</td><td><span className="cost">2.9억</span></td><td><span className="luck amber">잠재 1</span></td></tr>
        </tbody>
      </table>
      <div className="mm-embed-footer">계정 전체 합산 · /잠재</div>
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
