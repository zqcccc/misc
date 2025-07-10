import Script from 'next/script'
import './globals.css'

export const metadata = {
  description: "welcome to ZQC's personal website, nice to meet you",
  keywords: ['Next.js', 'React', 'JavaScript', 'blog', 'zqc', 'onlylike.work'],
  other: {
    'google-adsense-account': 'ca-pub-6426066570730708',
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
        <Script id="theme-init" strategy="beforeInteractive">
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
      <body>{children}</body>
      <Script id='ms_clarity' type='text/javascript'>
        {`(function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "s8lmijoo3v");`}
      </Script>
      <Script
        async
        src='https://www.googletagmanager.com/gtag/js?id=G-4DLMMFXJMP'
      ></Script>
      <Script id='google-analytics'>
        {`
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());

        gtag('config', 'G-4DLMMFXJMP');
        `}
      </Script>
      <Script
        crossOrigin='anonymous'
        async
        src='https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6426066570730708'
      ></Script>
    </html>
  )
}
