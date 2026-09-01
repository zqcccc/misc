import Link from 'next/link'
import { SITE_EMAIL } from '@/lib/site'

export default function SiteFooter() {
  return (
    <footer className='site-footer'>
      <div className='site-footer-inner'>
        <div className='site-footer-statement'>
          <strong>c9cu</strong>
          <p>只公开亲自做过、愿意解释过程，也愿意承认局限的东西。</p>
        </div>
        <nav aria-label='页脚导航'>
          <Link href='/about'>关于</Link>
          <Link href='/contact'>联系</Link>
          <Link href='/standards'>内容与披露</Link>
          <Link href='/privacy'>隐私</Link>
          <a href={`mailto:${SITE_EMAIL}`}>邮件</a>
        </nav>
        <p className='site-footer-meta'>
          © {new Date().getFullYear()} c9cu · onlylike.work
        </p>
      </div>
    </footer>
  )
}
