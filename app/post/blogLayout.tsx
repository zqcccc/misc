import './style.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className='article-shell'>{children}</div>
  )
}
