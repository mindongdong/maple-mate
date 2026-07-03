import { Suspense } from 'react'
import type { Metadata } from 'next'
import { Tutorial } from '@/components/Tutorial'
import '../tutorial.css'

export const metadata: Metadata = {
  title: '튜토리얼',
  description:
    '봇 초대부터 캐릭터·API 키 등록까지 — 메이트 사용법을 약 5분 만에 화면으로 따라가 보세요.',
}

// useSearchParams(?step=N 딥링크)를 쓰는 클라이언트 컴포넌트라 Suspense 경계 필요.
export default function TutorialPage() {
  return (
    <Suspense fallback={null}>
      <Tutorial />
    </Suspense>
  )
}
