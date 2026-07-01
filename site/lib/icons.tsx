/** JSON 의 아이콘 문자열 → Lucide 컴포넌트 매핑 (D13 라인 아이콘 통일). */
import {
  Unlock,
  User,
  KeyRound,
  UserPlus,
  Swords,
  History,
  Trophy,
  CalendarCheck,
  Bell,
  type LucideIcon,
} from 'lucide-react'

export const ICONS: Record<string, LucideIcon> = {
  unlock: Unlock,
  user: User,
  key: KeyRound,
  'user-plus': UserPlus,
  swords: Swords,
  history: History,
  trophy: Trophy,
  'calendar-check': CalendarCheck,
  bell: Bell,
}

export function Icon({
  name,
  size = 16,
  strokeWidth = 2,
}: {
  name: string
  size?: number
  strokeWidth?: number
}) {
  const C = ICONS[name] ?? Unlock
  return <C size={size} strokeWidth={strokeWidth} aria-hidden />
}
