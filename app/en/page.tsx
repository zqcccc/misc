import type { Metadata } from 'next'
import Link from 'next/link'
import { getCachedAllPost } from '../api/post/lib'
import { formatPostDate, getPostCategory, SITE_CATEGORIES, SITE_URL } from '@/lib/site'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: { absolute: 'c9cu · Research, Engineering and Self-built Tools' },
  description:
    'This is the personal website of c9cu. First-hand investment research, engineering practice and self-built browser tools, with methods, evidence and limitations.',
  alternates: {
    canonical: '/en',
    languages: {
      'zh-Hans': '/',
      en: '/en',
      'x-default': '/',
    },
  },
  openGraph: {
    title: 'c9cu · Research, Engineering and Self-built Tools',
    description:
      'First-hand research, engineering notes and tools. Every claim comes with process, evidence and limits.',
    url: `${SITE_URL}/en`,
    locale: 'en_US',
  },
}

const tools = [
  {
    href: '/en/tools',
    title: 'Profit line and valuation',
    description:
      'Historical lookup for price, TTM EPS, profit lines and valuation bands. Kept as a historical entry with only necessary maintenance.',
    meta: 'Historical entry · Low-frequency maintenance',
  },
  {
    href: '/en/tools',
    title: 'Browser utilities',
    description:
      'Image merging and compression run locally in your browser. Your files are never uploaded to the server.',
    meta: 'Utilities · Local processing',
  },
]

export default async function EnHome() {
  const posts = await getCachedAllPost()
  const recent = posts.slice(0, 10)

  return (
    <main className='home-page' lang='en'>
      <section className='home-hero' aria-labelledby='en-home-title'>
        <div className='home-intro'>
          <h1 id='en-home-title'>This is the personal website of c9cu.</h1>
          <p className='home-intro-lead'>
            I keep first-hand research, engineering practice and self-built tools here. Different topics
            share one standard: explain the process, show the evidence, and write down the limits.
          </p>
          <div className='home-actions'>
            <Link href='/en/tools'>Browse tools in English</Link>
            <Link href='/en/about'>About c9cu</Link>
          </div>
          <dl className='home-principles' aria-label='Content principles'>
            <div>
              <dt>Source</dt>
              <dd>First-hand practice</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>Date-stamped, expiry risks noted</dd>
            </div>
            <div>
              <dt>Responsibility</dt>
              <dd>Methods, limits and correction channel</dd>
            </div>
          </dl>
        </div>

        <article className='home-lead-work'>
          <div className='home-lead-meta'>
            <span>Strategy board</span>
            <span>Updated after close on trading days</span>
          </div>
          <h2>
            <Link href='/smallcap-strategy'>A-share small/micro-cap rotation</Link>
          </h2>
          <p>
            Recent target positions, rebalance records, and historical returns and drawdowns under
            different position counts. The full backtest interface is currently available in Chinese.
          </p>
          <Link className='home-text-link' href='/smallcap-strategy'>
            View positions and full backtest
            <span aria-hidden='true'>→</span>
          </Link>
        </article>
      </section>

      <section id='work' className='home-section home-work' aria-labelledby='en-work-title'>
        <div className='home-section-heading'>
          <h2 id='en-work-title'>Tool entries</h2>
          <p>
            Tools that are still in use document where processing happens and where data goes.
            Historical tools under low-frequency maintenance are labelled as such.
          </p>
        </div>
        <div className='home-tool-list'>
          {tools.map((tool) => (
            <article key={tool.title}>
              <p className='home-tool-meta'>{tool.meta}</p>
              <h3>
                <Link href={tool.href}>{tool.title}</Link>
              </h3>
              <p>{tool.description}</p>
              <Link className='home-text-link' href={tool.href}>
                Open
                <span aria-hidden='true'>→</span>
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section id='notes' className='home-section home-notes' aria-labelledby='en-notes-title'>
        <div className='home-section-heading'>
          <h2 id='en-notes-title'>Recent articles and notes</h2>
          <p>
            Old articles keep their original judgement. Engineering notes older than three years carry
            an obsolescence reminder. Full article translations are in progress; titles below link to
            the Chinese originals.
          </p>
        </div>
        <div className='home-note-groups'>
          {(Object.keys(SITE_CATEGORIES) as (keyof typeof SITE_CATEGORIES)[]).map((category) => {
            const items = recent.filter((post) => getPostCategory(post) === category)
            if (!items.length) return null
            const details = SITE_CATEGORIES[category]
            return (
              <section key={category} aria-labelledby={`en-notes-${category}`}>
                <div className='home-note-group-heading'>
                  <h3 id={`en-notes-${category}`}>{category}</h3>
                  <p>{details.description}</p>
                </div>
                <ol>
                  {items.map((post) => (
                    <li key={post.path}>
                      <Link href={`/post/${post.path}`}>
                        <span>{String(post.data.title)}</span>
                        <time dateTime={String(post.data.date)}>{formatPostDate(post.data.date)}</time>
                      </Link>
                      {post.data.description && <p>{String(post.data.description)}</p>}
                    </li>
                  ))}
                </ol>
              </section>
            )
          })}
        </div>
      </section>

      <section className='home-section home-about' aria-labelledby='en-about-title'>
        <h2 id='en-about-title'>Why keep a personal website</h2>
        <div>
          <p>
            Platforms are good for publishing opinions. A personal website is better for keeping
            context. Articles and tools here do not represent any institution, nor do they pretend to
            have authority they do not have. Their value comes from checkable process and traces of
            real usage.
          </p>
          <p>
            When you read an investment study, you can check the data definitions. When you read an
            engineering note, you can jump to the original repository. When you use a tool, you can
            tell whether the result was computed on my own machine. A personal website keeps this
            evidence together with the original text, without being overwritten by recommendation
            algorithms or platform editors.
          </p>
          <p>
            It is also a reminder to myself: every article carries publication and update dates;
            finance-related content discloses data sources and what cannot be proven; tool pages state
            whether data is uploaded and whether results are reproducible. Nothing here claims to be
            “always right”, and wrong judgements are not silently rewritten.
          </p>
          <p>
            If you find factual errors, outdated steps or data issues, please contact me. I keep
            corrections instead of quietly editing old judgements into always-correct ones.
          </p>
          <div className='home-actions'>
            <Link href='/en/standards'>Content and disclosure standards</Link>
            <Link href='/en/contact'>Report an issue</Link>
          </div>
        </div>
      </section>
    </main>
  )
}
