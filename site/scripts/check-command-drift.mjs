#!/usr/bin/env node
/**
 * commands.json 구조 검증 (사이트측 sanity check).
 * 봇 트리와의 진짜 드리프트 가드는 pytest(tests/test_website_command_drift.py)가 담당한다.
 * 여기서는 JSON 파싱·필수 필드·tier 유효성·이름 중복,
 * 그리고 튜토리얼 스텝(data/tutorial-steps.tsx)이 참조하는 명령 이름의 실재만 본다.
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

// ---- 튜토리얼 스텝 명령 참조 검증 (data/tutorial-steps.tsx) ----
// 명령 객체는 name(·visibility·label 선택, 이 순서) 리터럴 고정(파일 상단 주석).
// label 은 칩 표시 전용이라 여기선 캡처만 하고 검증하지 않는다.
// /가이드 는 사이트 카드에서 뺀 명령(_SITE_EXEMPT)이지만 튜토리얼에선 언급 허용.
const TUTORIAL_EXEMPT = new Set(['가이드'])
const tutorialSrc = readFileSync(
  join(here, '..', 'data', 'tutorial-steps.tsx'),
  'utf8',
)
const cmdRe =
  /\{\s*name:\s*'([^']+)'(?:\s*,\s*visibility:\s*'([^']+)')?(?:\s*,\s*label:\s*'[^']+')?\s*\}/g
const tutorialRefs = [...tutorialSrc.matchAll(cmdRe)]
if (tutorialRefs.length === 0) {
  errors.push('tutorial-steps.tsx 에서 명령 참조를 못 읽음 — 리터럴 형식이 깨졌는지 확인')
}
for (const [, name, visibility] of tutorialRefs) {
  if (!seen.has(name) && !TUTORIAL_EXEMPT.has(name)) {
    errors.push(`tutorial-steps.tsx 가 commands.json 에 없는 명령을 참조: /${name}`)
  }
  if (visibility && visibility !== 'public' && visibility !== 'private') {
    errors.push(`tutorial-steps.tsx /${name} visibility 불명: ${visibility}`)
  }
}

if (errors.length) {
  console.error('commands.json 검증 실패:')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log(
  `commands.json OK — ${seen.size}개 명령, ${data.groups.length}개 그룹 · ` +
    `tutorial-steps ${tutorialRefs.length}개 명령 참조 검증`,
)
