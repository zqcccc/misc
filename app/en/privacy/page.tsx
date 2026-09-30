import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description:
    'What onlylike.work actually collects: server logs, local-only processing, opt-in anonymous analytics and contact information.',
  alternates: {
    canonical: '/en/privacy',
    languages: { 'zh-Hans': '/privacy', en: '/en/privacy', 'x-default': '/privacy' },
  },
  openGraph: {
    title: 'onlylike.work Privacy Policy',
    description: 'What this site actually collects and what choices visitors have.',
    url: `${SITE_URL}/en/privacy`,
    locale: 'en_US',
  },
}

export default function EnPrivacyPage() {
  return (
    <main className='trust-page' lang='en'>
      <header>
        <h1>Privacy Policy</h1>
        <p>Effective date: September 1, 2026. This page only describes data processing that actually happens on onlylike.work.</p>
      </header>

      <section>
        <h2>Basic principle</h2>
        <p>
          onlylike.work is a personal website maintained by c9cu. The site does not sell visitor
          personal information, nor does it require account registration, payment details or social
          login to read public content or use the main tools.
        </p>
      </section>

      <section>
        <h2>Server logs</h2>
        <p>
          To deliver pages, debug failures and prevent abuse, the server and network providers may
          briefly process common technical logs such as request time, page URL, IP address, browser
          type and response status. This data is not used to build personal profiles.
        </p>
      </section>

      <section id='analytics'>
        <h2>Anonymous analytics</h2>
        <p>
          Google Analytics loads only after you click “Allow anonymous analytics”. It may use cookies
          or similar technologies to record page views, device categories and approximate regions,
          with IP anonymisation enabled. Choosing “essential only” does not affect reading or tool
          usage.
        </p>
        <p>
          Your choice is stored in the browser local key <code>c9cu-analytics-consent</code>.
          Clearing site data for onlylike.work will ask you again.
        </p>
      </section>

      <section>
        <h2>Browser-local data</h2>
        <p>
          The light/dark theme preference is stored in the browser <code>theme</code> key. Image
          merge and compression tools process the files you select locally in the browser; these
          images are not uploaded to onlylike.work servers to complete the tool function.
        </p>
      </section>

      <section>
        <h2>Comments and third-party services</h2>
        <p>
          Some articles may load the Cusdis comment widget. Related content and technical information
          is only processed by that third party when you actively use comments. External links, data
          vendors and embedded services follow their own privacy policies, which onlylike.work cannot
          control.
        </p>
      </section>

      <section>
        <h2>Email contact</h2>
        <p>
          When you email me, I receive the address and content you provide, only for reading,
          replying, handling corrections or fixing problems. Please do not send passwords, ID
          documents, payment details or other unnecessary sensitive information.
        </p>
      </section>

      <section>
        <h2>Retention, deletion and choices</h2>
        <p>
          Technical logs are kept only for a reasonable period needed for maintenance and security.
          You can refuse or delete local storage and cookies in your browser. To enquire about or
          delete information you proactively provided by email or comments, contact{' '}
          <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>; whether deletion is possible also
          depends on applicable law and third-party capabilities.
        </p>
      </section>

      <section>
        <h2>Updates and contact</h2>
        <p>
          When site features or third-party services change, this policy is updated accordingly with
          a new effective date. For privacy questions, email{' '}
          <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>.
        </p>
      </section>

      <nav className='trust-page-links' aria-label='Related pages'>
        <Link href='/en/about'>About c9cu</Link>
        <Link href='/en/standards'>Content and disclosure standards</Link>
        <Link href='/privacy'>中文版：隐私政策</Link>
      </nav>
    </main>
  )
}
