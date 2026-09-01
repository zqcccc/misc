import Script from 'next/script'
import type { Metadata } from 'next'
import { Toaster } from 'sonner'
import AnalyticsConsent from '@/components/site/AnalyticsConsent'
import SiteFooter from '@/components/site/SiteFooter'
import SiteHeader from '@/components/site/SiteHeader'
import {
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_TITLE,
  SITE_URL,
} from '@/lib/site'
import './globals.css'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  authors: [{ name: SITE_NAME, url: `${SITE_URL}/about` }],
  creator: SITE_NAME,
  publisher: SITE_NAME,
  keywords: ['c9cu', '个人网站', '投资研究', '工程实践', '自用工具'],
  openGraph: {
    type: 'website',
    locale: 'zh_CN',
    siteName: SITE_NAME,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
      'max-video-preview': -1,
    },
  },
}

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  colorScheme: 'light dark',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang='zh-Hans' suppressHydrationWarning>
      <head>
        <Script id='theme-init' strategy='beforeInteractive'>
          {`
            (function() {
              try {
                var theme = localStorage.getItem('theme');
                var darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
                if (!theme) {
                  theme = darkQuery.matches ? 'dark' : 'light';
                }
                document.documentElement.className = theme;
              } catch (e) {}
            })();
          `}
        </Script>
      </head>
      <body>
        <div
          hidden
          aria-hidden='true'
          dangerouslySetInnerHTML={{
            __html: `<!--
THESIS: c9cu 是第一手实践的个人档案，拒绝无作者、无上下文的模板文章列表。
OWN-WORLD: 冷白纸面、石墨文字、深蓝链接和琥珀状态标记；以细规则线和开放列表组织内容。
STORY: 访客先认识作者与写作原则，再查看代表作品、最近记录和自用工具，最后获得方法与责任说明。
FIRST VIEWPORT: 左侧是 c9cu 的身份与说明，右侧用一项大型代表作品证明研究与工具来自真实实践。
FORM: 个人档案索引，结构候选 6，seed 6398bd69。
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
-->`,
          }}
        />
        <SiteHeader />
        <div id='main-content' tabIndex={-1}>
          {children}
        </div>
        <SiteFooter />
        <Toaster richColors position='top-center' />
        <AnalyticsConsent />
      </body>
    </html>
  )
}
