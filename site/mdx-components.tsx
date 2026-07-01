import { useMDXComponents as getThemeComponents } from 'nextra-theme-docs'
import { CommandChip } from '@/components/CommandChip'

const themeComponents = getThemeComponents()

// 인라인 `/한글명` 코드는 명령 칩(D7)으로 렌더. 인자 있는 `/유니온 [캐릭터명]`,
// 코드블록, `.env`·URL 등은 규칙에 안 걸려 Nextra 기본 code 스타일 유지.
const COMMAND_RE = /^\/[가-힣]+$/

function Code(props: React.ComponentProps<'code'>) {
  const { children } = props
  if (typeof children === 'string' && COMMAND_RE.test(children)) {
    return <CommandChip name={children.slice(1)} />
  }
  const Base = (themeComponents.code ?? 'code') as React.ElementType
  return <Base {...props} />
}

export function useMDXComponents(
  components?: Record<string, React.ComponentType>,
) {
  return {
    ...themeComponents,
    code: Code,
    ...components,
  }
}
