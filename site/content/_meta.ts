// 상단 네비 = 4개 섹션(type: page). 랜딩은 풀폭·사이드바/TOC 없음·네비 숨김.
export default {
  index: {
    display: 'hidden',
    theme: {
      layout: 'full',
      sidebar: false,
      toc: false,
      breadcrumb: false,
      pagination: false,
      timestamp: false,
    },
  },
  'getting-started': { title: '시작하기', type: 'page' },
  commands: { title: '명령어', type: 'page' },
  concepts: { title: '개념', type: 'page' },
  privacy: { title: '개인정보·보안', type: 'page' },
}
