import Script from 'next/script'
import './globals.css'

export const metadata = {
  description: "welcome to ZQC's personal website, nice to meet you",
  colorScheme: 'light dark',
  keywords: ['Next.js', 'React', 'JavaScript', 'blog', 'zqc', 'onlylike.work'],
  other: {
    'google-adsense-account': 'ca-pub-6426066570730708',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang='zh-Hans'>
      <body>{children}</body>
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
