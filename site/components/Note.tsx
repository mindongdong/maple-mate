/**
 * 플랫 뉴트럴 노트 박스 — Nextra <Callout>(좌측 색 액센트 바) 대체.
 * 사방 1px 균일 보더 + 옅은 무채색 배경 + 작은 muted Lucide 아이콘. 색 액센트 없음.
 */
import * as React from 'react'
import { Info } from 'lucide-react'

export function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="mm-note">
      <Info className="mm-note-icon" size={16} strokeWidth={2} aria-hidden />
      <div className="mm-note-body">{children}</div>
    </div>
  )
}
