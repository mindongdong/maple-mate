/** 명령 카드 + feature 그룹 (D9) — 단일 명령어 페이지에서 그룹별 카드 렌더.
 *  카드 anatomy: [칩 제목][전제조건 배지] → 1줄 설명 → 스샷(프레임) → optional 팁.
 *  인자 표 없음(디스코드 `/` UI 가 source-of-truth). */
import type { ReactNode } from 'react'
import { CommandChip } from './CommandChip'
import { Badge } from './Badge'
import { ScreenshotFrame } from './ScreenshotFrame'
import { Icon } from '@/lib/icons'
import { groupById, type Command } from '@/lib/commands'
import {
  GuideEmbed,
  SchedulerEmbed,
  AlertEmbed,
  RegisterEmbed,
} from './Embeds'

/** 봇 렌더러가 만든 진짜 PNG(site/public/shots/). 렌더 코드 변경 시
 *  site/scripts/render_demo_shots.py 재실행 → 재커밋(드리프트 0). */
function shot(file: string, alt: string): ReactNode {
  return <img src={`/shots/${file}`} alt={alt} className="mm-shot-img" />
}

/** 명령 → 결과 이미지 + 캡션. 비교·리더보드는 봇 실제 렌더러 PNG(<img>),
 *  텍스트 임베드 명령은 디스코드 임베드 CSS 목업. */
function embedFor(name: string): { node: ReactNode; caption: string } | null {
  switch (name) {
    case '가이드':
      return { node: <GuideEmbed />, caption: '/가이드 · 등록 없이 바로' }
    case '캐릭터등록':
      return { node: <RegisterEmbed title="캐릭터 등록 완료" line="홍길동전사(Lv.275)를 이 서버에 등록했어요." />, caption: '/캐릭터등록' }
    case '키등록':
      return { node: <RegisterEmbed title="키 등록 완료" line="개인 API 키를 등록했어요. 스타포스·잠재 기록을 계정 단위로 조회할 수 있어요." />, caption: '/키등록' }
    case '대표지정':
      return { node: <RegisterEmbed title="대표 캐릭터 지정" line="홍길동전사를 대표 캐릭터로 지정했어요." />, caption: '/대표지정' }
    case '캐릭터목록':
      return { node: <RegisterEmbed title="내 캐릭터" line="홍길동전사 Lv.275 (대표 · 키✓) · 불꽃아크 Lv.268 (키✓)" />, caption: '/캐릭터목록 · 본인만' }
    case '스펙':
      return { node: shot('spec.png', '스펙 비교표 — 전투력·HEXA 코어·스탯 코어'), caption: '/스펙 · 계정 전체 합산' }
    case '아이템':
      return { node: shot('item.png', '아이템 카드 — 부위별 스타포스·잠재·추가옵션'), caption: '/아이템 · 부위별 비교' }
    case '유니온':
      return { node: shot('union.png', '유니온 비교표 — 유니온·아티팩트·챔피언'), caption: '/유니온' }
    case '스타포스':
      return { node: shot('starforce.png', '스타포스 이력 비교표 — 운빨·사용 메소·건수'), caption: '/스타포스 · 10성 이상만 집계' }
    case '잠재':
      return { node: shot('potential.png', '잠재 이력 비교표 — 재설정·큐브·메소·등업'), caption: '/잠재 · 계정 전체 합산' }
    case '경험치':
      return { node: shot('exp.png', '경험치 리더보드 그래프 — 최근 7일 레벨 추이'), caption: '/경험치 · 최근 7일 레벨 추이 그래프' }
    case '스케줄러':
      return { node: <SchedulerEmbed />, caption: '/스케줄러 · 본인만' }
    case '스케줄러알림':
      return { node: <AlertEmbed title="스케줄러 숙제 알림" line="매일 정한 시각에 숙제 체크리스트를 개인 DM으로 보냅니다." sub="대상: 본인 DM · 켜기 · 끄기" />, caption: '/스케줄러알림 · 매일 정한 시각 DM' }
    case '경험치알림':
      return { node: <AlertEmbed title="경험치 리더보드 알림" line="매일 정한 시각에 리더보드를 이 채널 또는 본인 DM으로 보냅니다." />, caption: '/경험치알림' }
    case '공지알림':
      return { node: <AlertEmbed title="메이플 공지 알림" line="새 공지·업데이트가 올라오면 알려드려요." />, caption: '/공지알림' }
    case '썬데이알림':
      return { node: <AlertEmbed title="썬데이 메이플 알림" line="썬데이 메이플 이벤트가 시작되면 알려드려요." />, caption: '/썬데이알림' }
    default:
      return null
  }
}

function CommandCard({ command }: { command: Command }) {
  const embed = embedFor(command.name)
  return (
    <article className="mm-cmd-card" id={`cmd-${command.name}`}>
      <div className="mm-cmd-head">
        <CommandChip name={command.name} />
        <Badge tier={command.tier} />
      </div>
      <p className="mm-cmd-summary">{command.summary}</p>
      {embed ? (
        <ScreenshotFrame compact caption={embed.caption}>
          {embed.node}
        </ScreenshotFrame>
      ) : null}
      {command.tip ? (
        <p className="mm-cmd-tip">
          <strong>팁</strong> {command.tip}
        </p>
      ) : null}
    </article>
  )
}

export function CommandGroup({ id }: { id: string }) {
  const group = groupById(id)
  if (!group) return null
  return (
    <div className="mm-cmd-group">
      <div className="mm-cmd-group-meta">
        <span className="mm-cmd-group-icon">
          <Icon name={group.icon} size={16} strokeWidth={2} />
        </span>
        <span className="mm-cmd-group-count">{group.commands.length}개 명령</span>
      </div>
      {group.commands.map((c) => (
        <CommandCard key={c.name} command={c} />
      ))}
    </div>
  )
}
