import type { Metadata } from 'next'
import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import 'nextra-theme-docs/style.css'
import './globals.css'
import './embeds.css'
import './hero.css'
import './commands.css'
import { MushroomMark } from '@/components/Mushroom'
import {
  GITHUB_URL,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_TAGLINE,
  SITE_URL,
} from '@/lib/site'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — ${SITE_TAGLINE}`,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESCRIPTION,
    locale: 'ko_KR',
    images: ['/og.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: `${SITE_NAME} — ${SITE_TAGLINE}`,
    description: SITE_DESCRIPTION,
    images: ['/og.png'],
  },
  icons: {
    icon: [{ url: '/favicon.png', type: 'image/png', sizes: '64x64' }],
    apple: [{ url: '/apple-touch-icon.png', sizes: '180x180' }],
  },
}

const navbar = (
  <Navbar
    logo={
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 9,
          fontWeight: 800,
          fontSize: 19,
          letterSpacing: '-0.02em',
        }}
      >
        <MushroomMark size={26} />
        {SITE_NAME}
      </span>
    }
    projectLink={GITHUB_URL}
  />
)

const footer = (
  <Footer>
    <div style={{ fontSize: 13, lineHeight: 1.7 }}>
      <div style={{ fontWeight: 700 }}>
        {SITE_NAME} · {SITE_TAGLINE}
      </div>
      <div style={{ color: 'var(--tx-muted)', marginTop: 4 }}>
        메이플스토리 및 관련 자산의 저작권은 넥슨에 있습니다. 데이터는 넥슨
        오픈 API 를 통해 제공됩니다.
      </div>
    </div>
  </Footer>
)

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" dir="ltr" suppressHydrationWarning>
      <Head
        color={{
          hue: { light: 184, dark: 180 },
          saturation: { light: 82, dark: 50 },
          lightness: { light: 28, dark: 58 },
        }}
      />
      <body>
        <Layout
          navbar={navbar}
          footer={footer}
          pageMap={await getPageMap()}
          docsRepositoryBase={`${GITHUB_URL}/tree/main/site`}
          darkMode
          nextThemes={{ defaultTheme: 'system' }}
          themeSwitch={{ dark: '다크', light: '라이트', system: '시스템' }}
          sidebar={{ defaultMenuCollapseLevel: 1, toggleButton: true }}
          toc={{ float: true, title: '이 페이지', backToTop: '맨 위로' }}
          search={null}
          copyPageButton={false}
          editLink={null}
          feedback={{ content: null, labels: '' }}
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
