import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: {
    default: 'c9cu · Research, Engineering and Self-built Tools',
    template: '%s · c9cu',
  },
  description:
    'English edition of onlylike.work: first-hand investment research, engineering notes and browser tools by c9cu, with methods, evidence and limitations.',
  alternates: {
    canonical: '/en',
    languages: {
      'zh-Hans': '/',
      en: '/en',
      'x-default': '/',
    },
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'c9cu',
    url: `${SITE_URL}/en`,
  },
}

const enLinks = [
  { href: '/en', label: 'Home' },
  { href: '/en/tools', label: 'Tools' },
  { href: '/en/about', label: 'About' },
  { href: '/en/standards', label: 'Standards' },
  { href: '/en/privacy', label: 'Privacy' },
  { href: '/en/contact', label: 'Contact' },
]

export default function EnLayout({ children }: { children: React.ReactNode }) {
  return (
    <div lang='en'>
      <nav
        aria-label='English section'
        style={{
          borderBottom: '1px solid var(--site-line)',
          background: 'var(--site-panel)',
        }}
      >
        <div
          style={{
            width: 'min(1180px, calc(100% - 40px))',
            margin: '0 auto',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '6px 20px',
            alignItems: 'center',
            padding: '10px 0',
            fontSize: 13,
          }}
        >
          <span style={{ color: 'var(--site-muted)', fontWeight: 700 }}>English</span>
          {enLinks.map((link) => (
            <Link key={link.href} href={link.href} style={{ color: 'var(--site-link)', fontWeight: 650 }}>
              {link.label}
            </Link>
          ))}
          <Link href='/' style={{ marginLeft: 'auto', color: 'var(--site-muted)' }}>
            中文版
          </Link>
        </div>
      </nav>
      {children}
    </div>
  )
}
