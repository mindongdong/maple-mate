/**
 * 메이트 마스코트 — icon_2 기반 래스터(주황버섯 갓+얼굴, 배경 투명). D2 두 폼:
 *  - <MushroomFull>  풀 렌더(히어로 / OG / 빈 상태) — 큰 크기.
 *  - <MushroomMark>  작은 마크(로고 락업 / 파비콘 / 인라인).
 * 둘 다 동일 자산 `/mascot.png` 를 크기만 달리 렌더 → 한 캐릭터 일관성.
 * (원본 icon_2.png 의 흰 배경을 flood-fill 로 제거해 warm-wash·다크에도 얹힘.)
 */
import * as React from 'react'

type Props = React.ImgHTMLAttributes<HTMLImageElement> & { size?: number }

export function MushroomFull({ size = 120, alt = '메이트 버섯 마스코트', style, ...rest }: Props) {
  return (
    <img
      src="/mascot.png"
      width={size}
      height={size}
      alt={alt}
      style={{ objectFit: 'contain', ...style }}
      {...rest}
    />
  )
}

export function MushroomMark({ size = 28, style, ...rest }: Props) {
  return (
    <img
      src="/mascot.png"
      width={size}
      height={size}
      alt=""
      aria-hidden
      style={{ objectFit: 'contain', display: 'block', ...style }}
      {...rest}
    />
  )
}
