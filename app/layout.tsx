import Script from 'next/script'
import type { Metadata } from 'next'
import { Toaster } from 'sonner'
import AnalyticsConsent from '@/components/site/AnalyticsConsent'
import EzoicRouteHandler from '@/components/site/EzoicRouteHandler'
import SiteFooter from '@/components/site/SiteFooter'
import SiteHeader from '@/components/site/SiteHeader'
import { EZOIC_ENABLED } from '@/lib/ads'
import {
  SITE_DESCRIPTION,
  SITE_EMAIL,
  SITE_NAME,
  SITE_OG_IMAGE,
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
    url: SITE_URL,
    // 各页面没单独声明 images 时，Next 会把 app/opengraph-image.tsx
    // 生成的地址填进来，社交平台因此总能拿到一张封面。
    images: [SITE_OG_IMAGE],
  },
  twitter: {
    card: 'summary_large_image',
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: [SITE_OG_IMAGE],
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
        {EZOIC_ENABLED && (
          <>
            {/* Ezoic 要求同意管理平台(CMP)先于广告脚本加载 */}
            <Script
              id='ezoic-cmp'
              src='https://cmp.gatekeeperconsent.com/min.js'
              strategy='beforeInteractive'
              data-cfasync='false'
            />
            <Script
              id='ezoic-cmp-2'
              src='https://the.gatekeeperconsent.com/cmp.min.js'
              strategy='beforeInteractive'
              data-cfasync='false'
            />
            <script async src='//www.ezojs.com/ezoic/sa.min.js' />
            <script async src='//ezoicanalytics.com/analytics.js' />
          </>
        )}
      </head>
      <body>
        <script
          type='application/ld+json'
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@type': 'Person',
              name: SITE_NAME,
              url: SITE_URL,
              email: `mailto:${SITE_EMAIL}`,
              description: SITE_DESCRIPTION,
              sameAs: [`${SITE_URL}/about`, `${SITE_URL}/contact`],
            }),
          }}
        />
        <SiteHeader />
        <div id='main-content' tabIndex={-1}>
          {children}
        </div>
        <SiteFooter />
        <Toaster richColors position='top-center' />
        <AnalyticsConsent />
        {EZOIC_ENABLED && <EzoicRouteHandler />}
      </body>
    </html>
  )
}
