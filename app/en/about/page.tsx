import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: 'About c9cu',
  description:
    'About c9cu and onlylike.work: why this personal site exists and how research, engineering notes and self-built tools are handled.',
  alternates: {
    canonical: '/en/about',
    languages: { 'zh-Hans': '/about', en: '/en/about', 'x-default': '/about' },
  },
  openGraph: {
    title: 'About c9cu',
    description: 'First-hand practice with context, evidence and limits.',
    url: `${SITE_URL}/en/about`,
    locale: 'en_US',
  },
}

export default function EnAboutPage() {
  return (
    <main className='trust-page' lang='en'>
      <header>
        <h1>About c9cu</h1>
        <p>
          Research I have done, code I have written and tools I keep reusing deserve a long-lived
          address that does not depend on any platform timeline.
        </p>
      </header>

      <section>
        <h2>What this site is</h2>
        <p>
          onlylike.work is my personal website. It does not represent any company, media outlet,
          research institution or licensed investment adviser, and it is not written for one specific
          kind of reader. Some visitors arrive because of an engineering note, some only need an
          image tool, and some want to see how an investment strategy is actually calculated.
        </p>
        <p>
          These topics sit together not because they belong to the same industry, but because they
          come from the same person&apos;s real usage. I try to leave enough context so future readers
          can judge whether a page fits their own case.
        </p>
      </section>

      <section>
        <h2>How I publish</h2>
        <ul>
          <li>Engineering notes start from problems actually encountered, with verification steps and version context.</li>
          <li>Investment research states data sources, calculation methods, applicable scope and what cannot be proven.</li>
          <li>Tools explain whether data is uploaded, how results are produced, and what to do on failure.</li>
          <li>Old content is not presented as forever correct; clearly outdated articles are marked as historical or removed from the public index.</li>
        </ul>
      </section>

      <section>
        <h2>Where credibility comes from</h2>
        <p>
          I do not invent job titles, institutional endorsements or investment track records here.
          Credibility comes from checkable process: source code, charts, timestamps, data definitions,
          failure records and a correction channel. That is not authority, but it is more honest than
          conclusions without provenance.
        </p>
      </section>

      <nav className='trust-page-links' aria-label='Learn more'>
        <Link href='/en/standards'>Content and disclosure standards</Link>
        <Link href='/en/contact'>Contact and corrections</Link>
        <Link href='/en/privacy'>Privacy policy</Link>
        <Link href='/about'>中文版：关于 c9cu</Link>
      </nav>
    </main>
  )
}
