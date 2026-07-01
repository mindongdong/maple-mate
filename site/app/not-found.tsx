import { NotFoundPage } from 'nextra-theme-docs'

export default function NotFound() {
  return (
    <NotFoundPage content="홈으로 돌아가기" labels="404">
      <h1>페이지를 찾을 수 없어요</h1>
      <p>주소가 바뀌었거나 없는 페이지예요.</p>
    </NotFoundPage>
  )
}
