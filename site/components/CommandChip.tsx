/** 인라인 명령 칩 (D7) — Pretendard pill, 틸 틴트, `/` 접두. 모노 아님.
 *  디스코드 슬래시 UI 멘탈모델 + 한글 완벽 가독. */
export function CommandChip({ name }: { name: string }) {
  return <span className="mm-chip">{name}</span>
}
