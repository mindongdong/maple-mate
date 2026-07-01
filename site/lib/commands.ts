import data from '@/data/commands.json'

export type Tier = 'free' | 'character' | 'apikey'

export interface Command {
  name: string
  tier: Tier
  summary: string
  tip?: string
}
export interface Group {
  id: string
  title: string
  icon: string
  commands: Command[]
}
export interface TierMeta {
  label: string
  icon: string
  tone: 'green' | 'indigo' | 'amber'
}

export const GROUPS = data.groups as Group[]
export const TIERS = data.tiers as Record<Tier, TierMeta>

export function groupById(id: string): Group | undefined {
  return GROUPS.find((g) => g.id === id)
}
