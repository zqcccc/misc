import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Content and Disclosure Standards',
  description:
    'How c9cu handles sources, dates, corrections, financial research, automation, affiliate links and advertising on onlylike.work.',
  alternates: {
    canonical: '/en/standards',
    languages: { 'zh-Hans': '/standards', en: '/en/standards', 'x-default': '/standards' },
  },
  openGraph: {
    title: 'Content and Disclosure Standards',
    description: 'Sources, updates, corrections, financial research and commercial relationships.',
    url: `${SITE_URL}/en/standards`,
    locale: 'en_US',
  },
}

export default function EnStandardsPage() {
  return (
    <main className='trust-page' lang='en'>
      <header>
        <h1>Content and Disclosure Standards</h1>
        <p>This is not a list of slogans. It is the minimum bar for whether a page should stay public on onlylike.work.</p>
      </header>

      <section>
        <h2>Authorship and sources</h2>
        <p>
          Original articles are authored by c9cu by default. When external material is cited, link to
          the original document, project or data source whenever possible. Content that only repeats
          someone else&apos;s conclusions without added experience, analysis or verification should not
          be published as a standalone article.
        </p>
      </section>

      <section>
        <h2>Dates, updates and corrections</h2>
        <p>
          The publication date marks when an article was first written; it does not mean the content
          is still valid today. Where software versions, policies, prices or market data are
          involved, the data cut-off or last-verified time should be stated. Engineering articles
          older than three years carry an obsolescence reminder.
        </p>
        <p>
          When a material error is found, I fix the draft; if the error changes the original
          conclusion, the correction is explained. You can report issues by{' '}
          <a href={`mailto:${SITE_EMAIL}`}>email</a>.
        </p>
      </section>

      <section id='financial'>
        <h2>Financial research disclaimer</h2>
        <p>
          Valuation, backtest, market-state and allocation content only documents a personal research
          process. It is not investment advice, securities recommendation, return guarantee or
          solicitation. Historical data and backtests do not guarantee future results; data may be
          delayed, missing or differ across vendors.
        </p>
        <p>
          Any investment decision should be made by readers with their own goals, risk tolerance and
          independent sources. Tool outputs do not replace opinions of licensed professionals.
        </p>
      </section>

      <section>
        <h2>Automation and human judgement</h2>
        <p>
          Programs generate charts, refresh data and run batch calculations on this site. Automated
          results should come with data definitions and calculation notes. Where generative AI
          materially contributed to factual expression, it is disclosed where appropriate; final
          publishing responsibility stays with c9cu.
        </p>
      </section>

      <section>
        <h2>Affiliate links, ads and interests</h2>
        <p>
          Pages carrying potentially commission-bearing affiliate links label them next to the link.
          Advertising is never disguised as site navigation, download buttons or research
          conclusions. Commercial relationships never buy undisclosed positive reviews.
        </p>
      </section>

      <section>
        <h2>Retiring public content</h2>
        <p>
          Duplicate test drafts, unfinished pages, features that cannot be maintained safely, and old
          tutorials that could help bypass access controls or raise other compliance risks no longer
          enter navigation, sitemap or the public article system.
        </p>
      </section>

      <nav className='trust-page-links' aria-label='Related pages'>
        <Link href='/en/about'>About c9cu</Link>
        <Link href='/en/privacy'>Privacy policy</Link>
        <Link href='/en/contact'>Contact and corrections</Link>
        <Link href='/standards'>中文版：内容与披露原则</Link>
      </nav>
    </main>
  )
}
