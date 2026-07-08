import Script from 'next/script'
import { Toaster } from 'sonner'
import './globals.css'

export const metadata = {
  description: "welcome to ZQC's personal website, nice to meet you",
  keywords: ['Next.js', 'React', 'JavaScript', 'blog', 'zqc', 'onlylike.work'],
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
        <Toaster richColors position='top-center' />
      </body>
    </html>
  )
}
