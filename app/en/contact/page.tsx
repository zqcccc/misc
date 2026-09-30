import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Contact c9cu',
  description: 'Contact c9cu to report factual errors, outdated steps, data issues or site bugs.',
  alternates: {
    canonical: '/en/contact',
    languages: { 'zh-Hans': '/contact', en: '/en/contact', 'x-default': '/contact' },
  },
  openGraph: {
    title: 'Contact c9cu',
    description: 'Report factual errors, outdated steps, data issues or site bugs.',
    url: `${SITE_URL}/en/contact`,
    locale: 'en_US',
  },
}

export default function EnContactPage() {
  return (
    <main className='trust-page' lang='en'>
      <header>
        <h1>Contact c9cu</h1>
        <p>The most valuable messages are usually not “nice post”, but pointers to what is already wrong.</p>
      </header>

      <section>
        <h2>Email</h2>
        <p>
          Please write to <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>. There is no support
          team behind this site; I read and handle messages when I have time, without a fixed reply
          SLA.
        </p>
      </section>

      <section>
        <h2>When reporting an issue, please include</h2>
        <ul>
          <li>The full URL of the page with the problem;</li>
          <li>What you saw: the wrong content or unexpected behaviour;</li>
          <li>For data issues: ticker, date and the reference source you used;</li>
          <li>For tool failures: browser, device and reproducible steps.</li>
        </ul>
      </section>

      <section>
        <h2>What email cannot provide</h2>
        <p>
          I do not provide personalised investment advice, discretionary account services or return
          guarantees by email. Please do not send passwords, ID documents or payment information.
        </p>
      </section>

      <nav className='trust-page-links' aria-label='Related pages'>
        <Link href='/en/about'>About c9cu</Link>
        <Link href='/en/privacy'>Privacy policy</Link>
        <Link href='/contact'>中文版：联系 c9cu</Link>
      </nav>
    </main>
  )
}
