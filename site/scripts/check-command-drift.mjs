#!/usr/bin/env node
/**
 * commands.json 구조 검증 (사이트측 sanity check).
 * 봇 트리와의 진짜 드리프트 가드는 pytest(tests/test_website_command_drift.py)가 담당한다.
 * 여기서는 JSON 파싱·필수 필드·tier 유효성·이름 중복만 본다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const data = JSON.parse(readFileSync(join(here, '..', 'data', 'commands.json'), 'utf8'))

const errors = []
const tiers = new Set(Object.keys(data.tiers ?? {}))
const seen = new Set()

for (const group of data.groups ?? []) {
  if (!group.id || !group.title) errors.push(`그룹 필수 필드 누락: ${JSON.stringify(group.id)}`)
  for (const cmd of group.commands ?? []) {
    if (!cmd.name) errors.push(`명령 name 누락 (그룹 ${group.id})`)
    if (!cmd.summary) errors.push(`/${cmd.name} summary 누락`)
    if (!tiers.has(cmd.tier)) errors.push(`/${cmd.name} tier 불명: ${cmd.tier}`)
    if (seen.has(cmd.name)) errors.push(`명령 이름 중복: /${cmd.name}`)
    seen.add(cmd.name)
  }
}

if (errors.length) {
  console.error('commands.json 검증 실패:')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log(`commands.json OK — ${seen.size}개 명령, ${data.groups.length}개 그룹`)
