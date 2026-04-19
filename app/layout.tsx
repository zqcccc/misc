import Script from 'next/script'
import AdUnit from '@/components/AdUnit'
import { Toaster } from 'sonner'
import './globals.css'

const AD_SLOT_FOOTER = '4555521397'
const AD_CLIENT = 'ca-pub-6426066570730708'
const ADSENSE_SRC = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${AD_CLIENT}`
const CLARITY_ID = 's8lmijoo3v'

export const metadata = {
  description: "welcome to ZQC's personal website, nice to meet you",
  keywords: ['Next.js', 'React', 'JavaScript', 'blog', 'zqc', 'onlylike.work'],
  other: {
    'google-adsense-account': AD_CLIENT,
  },
}

export const viewport = {
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
        <link
          rel='preconnect'
          href='https://pagead2.googlesyndication.com'
          crossOrigin='anonymous'
        />
        <link rel='dns-prefetch' href='https://www.clarity.ms' />
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
        {children}
        <div style={{ margin: '24px auto', maxWidth: '1200px', padding: '0 16px' }}>
          <AdUnit slot={AD_SLOT_FOOTER} />
        </div>
        <Toaster richColors position='top-center' />
      </body>
      <Script
        id='adsbygoogle'
        src={ADSENSE_SRC}
        strategy='afterInteractive'
        crossOrigin='anonymous'
      />
      <Script id='ms_clarity' strategy='lazyOnload'>
        {`(function(c,l,a,r,i,t,y){
          c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
          t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
          y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
        })(window, document, "clarity", "script", "${CLARITY_ID}");`}
      </Script>
    </html>
  )
}
