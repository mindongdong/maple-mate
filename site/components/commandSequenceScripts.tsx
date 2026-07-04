/**
 * CommandSequenceDemo 대본 — S6(캐릭터 등록으로 열리는 명령)·S9(API 키로 열리는 명령).
 * 작업지시서 §3 확정 대본. 임베드 카피 정본 = site/scripts/fixtures/demo/*.json 의 messages[].
 * 결과 PNG = /shots/demo-<run>.png (병렬 작업자가 생성 중 — 경로만 맞춰 둠).
 *
 * ⚠️ 드리프트 가드 오탐 방지: 파라미터 객체는 `{ p, v?, pick?, opts? }` 형태로만 쓴다.
 *    `name`/`visibility`/`label` 키를 한 리터럴에 함께 쓰지 않는다.
 *    - p    : 칩에 보일 파라미터 라벨(예: '모드', '유저1')
 *    - v    : 채워진 값(문자열). 없으면 미기입(옵션 미채움 시연)
 *    - pick : 값 채우는 장면 종류 — 'choice'(선택지 팝업) | 'member'(멤버 목록 팝업) | 'skip'(미채움)
 *    - opts : pick:'choice' 의 선택지 목록(예: 본서버/챌린저스)
 */
import * as React from 'react'
import { Eye } from 'lucide-react'

/** 디스코드 ephemeral 안내줄 — "나만 봐요"(스케줄러 결과). */
function EphemeralNote() {
  return (
    <div className="mm-tut-ephemeral">
      <Eye size={12} strokeWidth={2} aria-hidden />이 메시지는 당신만 볼 수 있어요
    </div>
  )
}

export type RunParam = {
  p: string
  v?: string
  pick?: 'choice' | 'member' | 'skip'
  opts?: string[]
}

export type Run = {
  speed: 'slow' | 'fast'
  cmd: string
  /** 팝업 설명줄(느린 실행 전용). */
  desc: string
  params: RunParam[]
  /** 'chips' = 입력 장면을 칩 목록부터 시작(대본 "칩에서 X 선택" run). */
  startAt?: 'chips'
  reply: React.ReactNode
}

/* ---- 결과 임베드 조각(픽스처 messages[] 카피 그대로) ---- */

function ShotImg({ run, alt }: { run: string; alt: string }) {
  return (
    <img
      className="mm-tut-seq-shot"
      src={`/shots/demo-${run}.png`}
      alt={alt}
      loading="lazy"
    />
  )
}

/** 리더보드 순위 한 줄 — **닉** — Lv.X (Y%) (픽스처 description 형식). */
function RankLine({ nick, lv }: { nick: string; lv: string }) {
  return (
    <>
      <b className="mm-rank-name">{nick}</b>
      <span className="mm-rank-lv"> — {lv}</span>
    </>
  )
}

/** 랭크 텍스트 임베드(경험치 리더보드 — 메달·**닉** — Lv.X (Y%)). */
function RankEmbed({
  title,
  lines,
  footer,
  run,
  alt,
}: {
  title: string
  lines: { medal: string; node: React.ReactNode }[]
  footer: string
  run: string
  alt: string
}) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">{title}</div>
      <div className="mm-rank-list">
        {lines.map((l, i) => (
          <div className="mm-rank-line" key={i}>
            <span className="mm-rank-badge">{l.medal}</span>
            <span>{l.node}</span>
          </div>
        ))}
      </div>
      <ShotImg run={run} alt={alt} />
      <div className="mm-embed-footer">{footer}</div>
    </div>
  )
}

/** 임베드 field(픽스처 fields[] — 굵은 이름 + 본문). */
type EmbedField = { h: string; body: React.ReactNode }

/** 픽스처 공통 field — "ℹ️ 계정 전체 합산". */
const FIELD_ACCOUNT_SUM: EmbedField = {
  h: 'ℹ️ 계정 전체 합산',
  body: (
    <>
      이력은 등록 캐릭터 본인 계정의 <b>전체 캐릭터(부캐 포함)</b> 를 합산한 값이에요.
    </>
  ),
}

/** 픽스처 공통 field — "ℹ️ 10성 이상 강화만 집계"(스타포스). */
const FIELD_STARFORCE_SCOPE: EmbedField = {
  h: 'ℹ️ 10성 이상 강화만 집계',
  body: (
    <>
      <b>10성 이상</b> 강화만 비교해요. 강화 당시 썬데이 이벤트도 반영했어요.
    </>
  ),
}

/** 표 결과 임베드(스펙·유니온·스타포스·잠재·내캐릭터) — 제목 + 대상줄 + PNG + 푸터. */
function TableEmbed({
  title,
  targets,
  fields,
  footer,
  run,
  alt,
}: {
  title: string
  targets: string
  fields?: EmbedField[]
  footer: string
  run: string
  alt: string
}) {
  return (
    <div className="mm-embed">
      <div className="mm-embed-title">{title}</div>
      <div className="mm-tut-seq-targets">👤 {targets}</div>
      <ShotImg run={run} alt={alt} />
      {fields?.map((f) => (
        <div className="mm-tut-seq-field" key={f.h}>
          <div className="mm-tut-seq-field-name">{f.h}</div>
          <div className="mm-tut-seq-field-val">{f.body}</div>
        </div>
      ))}
      <div className="mm-embed-footer">{footer}</div>
    </div>
  )
}

/** 스케줄러 결과(ephemeral · content 텍스트 + PNG 1장). */
function SchedulerEmbed() {
  return (
    <div className="mm-tut-seq-sched">
      <div className="mm-tut-seq-sched-line">바람궁수 — 남은 숙제 1개 (1/2 완료)</div>
      <ShotImg run="scheduler" alt="/스케줄러 숙제 현황 카드" />
      <EphemeralNote />
    </div>
  )
}

/* ---- 공통 칩 목록(느린 run 은 항상 전체 파라미터를 보여준다 — 대본 §3) ---- */

/** /경험치 파라미터 전체(유저1~5·모드). 채울 것만 v·pick 을 덧입힌다. */
function expParams(overrides: Record<string, RunParam> = {}): RunParam[] {
  return ['유저1', '유저2', '유저3', '유저4', '유저5', '모드'].map(
    (p) => overrides[p] ?? { p },
  )
}

/** /스타포스 파라미터 전체(기간·시작일·종료일·대상1~5). */
function starforceParams(overrides: Record<string, RunParam> = {}): RunParam[] {
  return ['기간', '시작일', '종료일', '대상1', '대상2', '대상3', '대상4', '대상5'].map(
    (p) => overrides[p] ?? { p },
  )
}

/* ============================================================
   S6 — 캐릭터 등록으로 열리는 명령 (7회: 느림 3 + 빠름 4)
   ============================================================ */

export const S6_SCRIPT: Run[] = [
  // 1. 느림 · /경험치 무인자(옵션 안 채워도 됨) → 본서버 리더보드
  {
    speed: 'slow',
    cmd: '경험치',
    desc: '레벨 추이 리더보드',
    params: expParams(),
    reply: (
      <RankEmbed
        title="📈 경험치 리더보드"
        lines={[
          { medal: '🥇', node: <RankLine nick="홍길동전사" lv="Lv.287 (95%)" /> },
          { medal: '🥈', node: <RankLine nick="불꽃아크" lv="Lv.287 (55%)" /> },
          { medal: '🥉', node: <RankLine nick="바람궁수" lv="Lv.285 (25%)" /> },
        ]}
        footer="기준: 오늘(07/04) 현재 · NEXON Open API"
        run="exp_main"
        alt="/경험치 리더보드 그래프"
      />
    ),
  },
  // 2. 느림 · 칩에서 모드 선택 → 선택지 본서버/챌린저스 → 챌린저스
  {
    speed: 'slow',
    cmd: '경험치',
    desc: '레벨 추이 리더보드',
    startAt: 'chips',
    params: expParams({
      모드: { p: '모드', v: '챌린저스', pick: 'choice', opts: ['본서버', '챌린저스'] },
    }),
    reply: (
      <RankEmbed
        title="🏆 챌린저스 경험치 리더보드"
        lines={[
          { medal: '🥇', node: <RankLine nick="번개해적" lv="Lv.280 (25%)" /> },
          { medal: '🥈', node: <RankLine nick="달빛기사" lv="Lv.280 (22%)" /> },
          { medal: '🥉', node: <RankLine nick="눈꽃마법사" lv="Lv.276 (50%)" /> },
        ]}
        footer="기준: 오늘(07/04) 현재 · NEXON Open API"
        run="exp_challengers"
        alt="/경험치 챌린저스 리더보드 그래프"
      />
    ),
  },
  // 3. 느림 · 칩에서 유저1 선택 → 멤버 목록 → @동민
  {
    speed: 'slow',
    cmd: '경험치',
    desc: '레벨 추이 리더보드',
    startAt: 'chips',
    params: expParams({
      유저1: { p: '유저1', v: '@동민', pick: 'member' },
    }),
    reply: (
      <RankEmbed
        title="📈 경험치 리더보드"
        lines={[
          { medal: '🥇', node: <RankLine nick="바람궁수" lv="Lv.285 (25%)" /> },
        ]}
        footer="기준: 오늘(07/04) 현재 · NEXON Open API"
        run="exp_target"
        alt="/경험치 지정 유저 그래프"
      />
    ),
  },
  // 4. 빠름 · /스펙 유저1:@수찬 유저2:@동민 유저3:@진혁
  {
    speed: 'fast',
    cmd: '스펙',
    desc: '전투력·스펙 비교',
    params: [
      { p: '유저1', v: '@수찬' },
      { p: '유저2', v: '@동민' },
      { p: '유저3', v: '@진혁' },
    ],
    reply: (
      <TableEmbed
        title="스펙 비교"
        targets="불꽃아크 · 홍길동전사 · 바람궁수"
        footer="최신 기준 · NEXON Open API"
        run="spec_three"
        alt="/스펙 비교 결과 카드"
      />
    ),
  },
  // 5. 빠름 · /아이템 부위:무기
  {
    speed: 'fast',
    cmd: '아이템',
    desc: '장비 아이템 비교',
    params: [{ p: '부위', v: '무기' }],
    reply: (
      <TableEmbed
        title="아이템 — 무기"
        targets="바람궁수 · 홍길동전사 · 불꽃아크"
        footer="등록자 전원(3명)을 비교했어요 · 최신 기준 · NEXON Open API"
        run="item_weapon"
        alt="/아이템 무기 비교 카드"
      />
    ),
  },
  // 6. 빠름 · /유니온
  {
    speed: 'fast',
    cmd: '유니온',
    desc: '유니온·아티팩트 비교',
    params: [],
    reply: (
      <TableEmbed
        title="유니온 비교"
        targets="불꽃아크 · 홍길동전사 · 바람궁수"
        footer="등록자 전원(3명)을 비교했어요 · 2026-07-03 기준 · NEXON Open API"
        run="union_all"
        alt="/유니온 비교 결과 카드"
      />
    ),
  },
  // 7. 빠름 · /내캐릭터 스펙
  {
    speed: 'fast',
    cmd: '내캐릭터',
    desc: '내 캐릭터끼리 비교',
    params: [{ p: '항목', v: '스펙' }],
    reply: (
      <TableEmbed
        title="내 캐릭터 스펙 비교"
        targets="동민"
        footer="최신 기준 · NEXON Open API"
        run="mychar_spec"
        alt="/내캐릭터 스펙 비교 카드"
      />
    ),
  },
]

/* ============================================================
   S9 — API 키로 열리는 명령 (4회: 느림 2 + 빠름 2)
   ============================================================ */

export const S9_SCRIPT: Run[] = [
  // 1. 느림 · /스타포스 무인자 → 랜덤 대상 운빨 비교
  {
    speed: 'slow',
    cmd: '스타포스',
    desc: '스타포스 운빨 비교',
    params: starforceParams(),
    reply: (
      <TableEmbed
        title="스타포스 운빨 비교"
        targets="동민 · 수찬"
        fields={[
          {
            h: '⚠️ 조회 실패 (1명)',
            body: (
              <>
                • <b>진혁</b> — 기간 내 10성 이상 강화 기록이 없어요.
              </>
            ),
          },
          FIELD_ACCOUNT_SUM,
          FIELD_STARFORCE_SCOPE,
        ]}
        footer="키 등록자 전원(3명)을 비교했어요 · 2026-06-28 ~ 2026-07-04 · NEXON Open API"
        run="starforce_rand"
        alt="/스타포스 운빨 비교 카드"
      />
    ),
  },
  // 2. 느림 · 칩에서 대상1 선택 → 멤버 목록 → @수찬
  {
    speed: 'slow',
    cmd: '스타포스',
    desc: '스타포스 운빨 비교',
    startAt: 'chips',
    params: starforceParams({
      대상1: { p: '대상1', v: '@수찬', pick: 'member' },
    }),
    reply: (
      <TableEmbed
        title="스타포스 운빨 비교"
        targets="수찬"
        fields={[FIELD_ACCOUNT_SUM, FIELD_STARFORCE_SCOPE]}
        footer="2026-06-28 ~ 2026-07-04 · NEXON Open API"
        run="starforce_target"
        alt="/스타포스 지정 대상 카드"
      />
    ),
  },
  // 3. 빠름 · /잠재 기간:최근30일 (옵션 채워도 됨 예시)
  {
    speed: 'fast',
    cmd: '잠재',
    desc: '잠재 메소·큐브 비교',
    params: [{ p: '기간', v: '최근30일' }],
    reply: (
      <TableEmbed
        title="잠재 메소·큐브 비교"
        targets="수찬 · 진혁 · 동민"
        fields={[FIELD_ACCOUNT_SUM]}
        footer="키 등록자 전원(3명)을 비교했어요 · 2026-06-05 ~ 2026-07-04 · NEXON Open API"
        run="potential_30d"
        alt="/잠재 메소·큐브 비교 카드"
      />
    ),
  },
  // 4. 빠름 · /스케줄러 (ephemeral)
  {
    speed: 'fast',
    cmd: '스케줄러',
    desc: '숙제 현황(나만 봐요)',
    params: [],
    reply: <SchedulerEmbed />,
  },
]
