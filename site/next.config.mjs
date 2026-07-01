import nextra from 'nextra'

// 문서·위키 우선 사이트. 검색(Pagefind)은 MVP 범위 밖 → 비활성(후속 도입).
const withNextra = nextra({
  defaultShowCopyCode: true,
  search: false,
})

export default withNextra({
  reactStrictMode: true,
  // KO 전용: i18n 미설정 (website-docs-plan 미니결정)
})
