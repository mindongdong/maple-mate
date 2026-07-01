/** 사이트 전역 상수 — 링크는 배포 환경변수로 주입, 없으면 플레이스홀더.
 *  운영자: Vercel 프로젝트 환경변수에 NEXT_PUBLIC_* 를 설정하세요.
 *  (docs/website-deploy-runbook.md 참조) */

export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://maple-mate.vercel.app'

/** 봇 초대 링크(디스코드 OAuth). 클라이언트 ID 확정 후 env 로 주입. */
export const INVITE_URL =
  process.env.NEXT_PUBLIC_INVITE_URL ??
  'https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&scope=bot%20applications.commands'

export const GITHUB_URL = 'https://github.com/mindongdong/maple-mate'

export const SITE_NAME = '메이트'
export const SITE_TAGLINE = '메이플을 더 재밌게 즐기도록 돕는 친구 같은 디스코드 봇'
export const SITE_DESCRIPTION =
  '메이트는 메이플스토리를 더 재밌게 즐기도록 돕는 친구 같은 디스코드 봇입니다. ' +
  '캐릭터를 등록해 유니온·스펙·경험치를 바로 확인하고, 친구·길드원과 리더보드로 순위를 겨뤄요. ' +
  '스타포스·잠재 지출은 메소·운빨로 비교하고, 일일·주간·보스 숙제는 스케줄러가 개인 DM으로 챙겨줍니다.'
