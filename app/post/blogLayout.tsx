import Link from 'next/link'
import HeaderControls from './HeaderControls'
import './style.css'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className='my-0 mx-auto py-10 px-5 max-w-2xl'>
      <header className='flex justify-between items-center mb-12'>
        <Link href='/post'>
          <h1 className='cursor-pointer text-5xl font-black'>
            ZQC&apos;s Blog
          </h1>
        </Link>
        <HeaderControls />
      </header>
      {children}
    </div>
  )
}
