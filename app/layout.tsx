import './globals.css'

export const metadata = {
  title: {
    template: "%s | ZQC's Blog",
    default: "ZQC's Blog", // a default is required when creating a template
  },
  description: "welcome to ZQC's personal blog, nice to meet you",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html>
      <body className="dark:bg-[#282c35] dark:text-[hsla(0,0%,100%,.88)]">{children}</body>
    </html>
  )
}
