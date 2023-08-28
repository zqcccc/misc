import Script from 'next/script'
import './globals.css'

export const metadata = {
  title: {
    template: "%s | ZQC's Blog",
    default: "ZQC's Blog", // a default is required when creating a template
  },
  description: "welcome to ZQC's personal blog, nice to meet you",
  colorScheme: 'light dark',
  keywords: ['Next.js', 'React', 'JavaScript', 'blog', 'zqc', 'onlylike.work'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang='zh-Hans'>
      <body className='dark:bg-[#282c35] dark:text-[hsla(0,0%,100%,.88)]'>
        {children}
      </body>
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
    </html>
  )
}
