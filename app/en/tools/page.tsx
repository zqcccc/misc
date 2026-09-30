import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Self-built Tools',
  description:
    'Research dashboards and browser tools by c9cu: maintenance status, data sources, processing location and known limits.',
  alternates: {
    canonical: '/en/tools',
    languages: { 'zh-Hans': '/tools', en: '/en/tools', 'x-default': '/tools' },
  },
  openGraph: {
    title: 'Self-built Tools',
    description: 'What each tool does, where data comes from, and what conclusions cannot be drawn.',
    url: `${SITE_URL}/en/tools`,
    locale: 'en_US',
  },
}

const tools = [
  {
    name: 'A-share strategy signals and backtests',
    desc: 'Recent risk state, selected positions and cash ratio, with full-sample and out-of-sample backtests.',
    href: '/ashare-strategy',
    kind: 'Research tool',
    detail: 'Updated after close on trading days. Model signals and historical backtests, not investment advice.',
  },
  {
    name: 'Small/micro-cap positions and backtest',
    desc: 'A top small-cap rotation strategy: latest holdings of 30 stocks, market-cap distribution, rebalance history and causal backtest.',
    href: '/smallcap-strategy',
    kind: 'Research tool',
    detail: 'Strict T+1 matching with historical frictions; includes the early-2024 liquidity stress test.',
  },
  {
    name: 'Profit line and valuation',
    desc: 'Price, TTM EPS, profit lines, valuation bands and dividend records on one timeline.',
    href: '/pe',
    kind: 'Research tool',
    detail: 'Uses public market data. Pages state update time and research boundaries.',
  },
  {
    name: 'Merge images',
    desc: 'Reorder multiple images, stitch them horizontally or vertically, and choose the export format.',
    href: '/tools/merge-images',
    kind: 'Local tool',
    detail: 'Images are processed only in the current browser and never uploaded to this server.',
  },
  {
    name: 'Compress images',
    desc: 'Batch-resize JPG, PNG and WEBP, then export by quality or download as a ZIP.',
    href: '/tools/compress-images',
    kind: 'Local tool',
    detail: 'Images are processed only in the current browser and never uploaded to this server.',
  },
  {
    name: 'Element Scroll Capture',
    desc: 'Pick any scrollable inner container (chat logs, admin tables, code boxes), auto-scroll and stitch it into one long image.',
    href: '/tools/element-scroll-capture',
    kind: 'Chrome extension',
    detail: 'Pure frontend Manifest V3. Images stay in local memory and IndexedDB; listed on the Chrome Web Store.',
  },
]

export default function EnToolsPage() {
  return (
    <main className='tools-index' lang='en'>
      <header>
        <h1>Solving problems I keep hitting.</h1>
        <p>
          This is not a pile of tool links. Every page explains what it processes, where data comes
          from, and which conclusions cannot be drawn from its output. Interactive tool interfaces
          are currently in Chinese; the descriptions below help English readers decide what to open.
        </p>
      </header>

      <section aria-labelledby='en-tools-list-title'>
        <div className='tools-index-heading'>
          <h2 id='en-tools-list-title'>Tools and research boards</h2>
          <p>{tools.length} public pages</p>
        </div>
        <ol className='tools-index-list'>
          {tools.map((tool, index) => (
            <li key={tool.href + tool.name}>
              <span className='tools-index-number' aria-hidden='true'>
                {String(index + 1).padStart(2, '0')}
              </span>
              <div>
                <p className='tools-index-kind'>{tool.kind}</p>
                <h3><Link href={tool.href}>{tool.name}</Link></h3>
              </div>
              <div className='tools-index-copy'>
                <p>{tool.desc}</p>
                <small>{tool.detail}</small>
              </div>
              <Link className='tools-index-open' href={tool.href} aria-label={`Open ${tool.name}`}>
                Open <span aria-hidden='true'>→</span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <aside className='tools-index-note'>
        <h2>Privacy and responsibility</h2>
        <p>
          Image tools compute locally with browser capabilities; research tools carry explicit data
          and methodology boundaries. This site never packages “free” as an unconditional guarantee,
          nor hides risk warnings on financial tools.
        </p>
        <div>
          <Link href='/en/privacy'>Privacy</Link>
          <Link href='/en/standards'>Content and disclosure standards</Link>
          <Link href='/en/contact'>Report an issue</Link>
          <Link href='/tools'>中文版：自用工具</Link>
        </div>
      </aside>
    </main>
  )
}
