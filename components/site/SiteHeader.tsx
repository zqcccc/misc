import Link from 'next/link'
import ThemeButton from './ThemeButton'

const links = [
  { href: '/', label: '首页' },
  { href: '/#work', label: '作品' },
  { href: '/#notes', label: '文章' },
  { href: '/tools', label: '工具' },
  { href: '/about', label: '关于' },
]

export default function SiteHeader() {
  return (
    <header className='site-header'>
      <a className='skip-link' href='#main-content'>
        跳到正文
      </a>
      <div className='site-header-inner'>
        <Link className='site-wordmark' href='/' aria-label='c9cu 首页'>
          <span aria-hidden='true' className='site-wordmark-mark'>
            c9
          </span>
          <span>cu</span>
        </Link>

        <nav className='site-nav site-nav-desktop' aria-label='主导航'>
          {links.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </nav>

        <div className='site-header-actions'>
          <ThemeButton />
          <details className='site-mobile-menu'>
            <summary aria-label='打开导航菜单'>
              <svg viewBox='0 0 24 24' aria-hidden='true'>
                <path d='M4 7h16M4 12h16M4 17h16' />
              </svg>
            </summary>
            <nav className='site-nav site-nav-mobile' aria-label='移动端导航'>
              {links.map((link) => (
                <Link key={link.href} href={link.href}>
                  {link.label}
                </Link>
              ))}
            </nav>
          </details>
        </div>
      </div>
    </header>
  )
}
