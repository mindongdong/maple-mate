/**
 * 스크린샷 프레임 (뉴트럴 · 테마 인식 CSS 토큰).
 * children = 봇 렌더러 PNG(<img>, 비교·리더보드) 또는 디스코드 임베드 CSS 목업(텍스트 임베드).
 */
import * as React from 'react'

export function ScreenshotFrame({
  children,
  caption,
  compact = false,
}: {
  children: React.ReactNode
  caption?: React.ReactNode
  compact?: boolean
}) {
  return (
    <figure className={compact ? 'mm-shot mm-shot--sm' : 'mm-shot'}>
      {children}
      {caption ? (
        <figcaption className="mm-shot-caption">{caption}</figcaption>
      ) : null}
    </figure>
  )
}
