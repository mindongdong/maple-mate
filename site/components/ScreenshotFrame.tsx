/**
 * 스크린샷 틴트 backdrop 프레임 (D10). 테마 인식(CSS 토큰).
 * children = 실 스샷 <img> 또는 디스코드 임베드 목업.
 * 실데이터 금지 → 현재는 CSS 임베드 목업. 재캡처 후 <img>로 교체.
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
