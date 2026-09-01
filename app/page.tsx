import type { Metadata } from 'next'
import Link from 'next/link'
import { getCachedAllPost } from './api/post/lib'
import {
  formatPostDate,
  getPostCategory,
  isArchivedPost,
  SITE_CATEGORIES,
  SITE_DESCRIPTION,
  SITE_TITLE,
  SITE_URL,
  type SiteCategory,
} from '@/lib/site'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: { absolute: SITE_TITLE },
  description: SITE_DESCRIPTION,
  alternates: { canonical: '/' },
  openGraph: {
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: SITE_URL,
  },
}

const FEATURED_PATHS = [
  'trhrp-strategy',
  'etf/自由现金流ETF',
  'ai/2025',
  'cursor/code',
]

const tools = [
  {
    href: '/pe',
    title: '利润线与估值',
    description: '把股价、TTM EPS、利润线、估值区间和分红记录放在一张可检查的时间轴里。',
    meta: '数据工具 · 持续维护',
  },
  {
    href: '/trhrp-backtest',
    title: 'TRHRP 历史回测档案',
    description: '保留当时的状态识别、仓位切换、回撤与长期收益；数据已停止自动刷新。',
    meta: '历史研究 · 已停止刷新',
  },
  {
    href: '/tools',
    title: '浏览器小工具',
    description: '图片合并与压缩在本地浏览器完成，文件不会上传到服务器。',
    meta: '实用工具 · 本地处理',
  },
]

export default async function Home() {
  const posts = await getCachedAllPost()
  const featured = FEATURED_PATHS.map((postPath) =>
    posts.find((post) => post.path === postPath),
  ).filter(Boolean)
  const lead = featured[0] || posts[0]
  const recent = posts.filter((post) => post.path !== lead?.path).slice(0, 10)
  const grouped = recent.reduce<Record<SiteCategory, typeof posts>>(
    (groups, post) => {
      groups[getPostCategory(post)].push(post)
      return groups
    },
    { research: [], engineering: [], reflection: [] },
  )

  return (
    <main className='home-page'>
      <section className='home-hero' aria-labelledby='home-title'>
        <div className='home-intro'>
          <h1 id='home-title'>这是 c9cu 的个人网站。</h1>
          <p className='home-intro-lead'>
            我在这里保存亲自做过的研究、工程实践和自用工具。不同主题由同一个标准连接：说明过程，给出证据，也写清局限。
          </p>
          <div className='home-actions'>
            <a href='#work'>查看代表作品</a>
            <Link href='/about'>认识 c9cu</Link>
          </div>
          <dl className='home-principles' aria-label='内容原则'>
            <div>
              <dt>来源</dt>
              <dd>第一手实践</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>标注日期与过期风险</dd>
            </div>
            <div>
              <dt>责任</dt>
              <dd>方法、局限与更正入口</dd>
            </div>
          </dl>
        </div>

        {lead && (
          <article className='home-lead-work'>
            <div className='home-lead-meta'>
              <span>{isArchivedPost(lead) ? '历史研究' : SITE_CATEGORIES[getPostCategory(lead)].label}</span>
              <time dateTime={String(lead.data.date)}>
                {formatPostDate(lead.data.date)}
              </time>
            </div>
            <h2>
              <Link href={`/post/${lead.path}`}>{lead.data.title}</Link>
            </h2>
            <p>{lead.data.description}</p>
            <Link className='home-text-link' href={`/post/${lead.path}`}>
              阅读完整方法
              <span aria-hidden='true'>→</span>
            </Link>
          </article>
        )}
      </section>

      <section id='work' className='home-section home-work' aria-labelledby='work-title'>
        <div className='home-section-heading'>
          <h2 id='work-title'>我做过并保留的东西</h2>
          <p>仍在维护和已经归档的页面都会写清状态，并解释数据从哪里来、适合回答什么问题，以及不能证明什么。</p>
        </div>
        <div className='home-tool-list'>
          {tools.map((tool) => (
            <article key={tool.href}>
              <p className='home-tool-meta'>{tool.meta}</p>
              <h3>
                <Link href={tool.href}>{tool.title}</Link>
              </h3>
              <p>{tool.description}</p>
              <Link className='home-text-link' href={tool.href}>
                打开
                <span aria-hidden='true'>→</span>
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section id='notes' className='home-section home-notes' aria-labelledby='notes-title'>
        <div className='home-section-heading'>
          <h2 id='notes-title'>最近的文章与记录</h2>
          <p>旧文章会保留当时的判断；超过三年的技术记录会在正文中提醒可能过时。</p>
        </div>
        <div className='home-note-groups'>
          {(Object.keys(SITE_CATEGORIES) as SiteCategory[]).map((category) => {
            const items = grouped[category]
            if (!items.length) return null
            const details = SITE_CATEGORIES[category]
            return (
              <section key={category} aria-labelledby={`notes-${category}`}>
                <div className='home-note-group-heading'>
                  <h3 id={`notes-${category}`}>{details.label}</h3>
                  <p>{details.description}</p>
                </div>
                <ol>
                  {items.map((post) => (
                    <li key={post.path}>
                      <Link href={`/post/${post.path}`}>
                        <span>{post.data.title}</span>
                        <time dateTime={String(post.data.date)}>
                          {formatPostDate(post.data.date)}
                        </time>
                      </Link>
                      {post.data.description && <p>{post.data.description}</p>}
                    </li>
                  ))}
                </ol>
              </section>
            )
          })}
        </div>
      </section>

      <section className='home-section home-about' aria-labelledby='home-about-title'>
        <h2 id='home-about-title'>为什么保留一个个人网站</h2>
        <div>
          <p>
            平台适合发布观点，个人网站更适合保留上下文。这里的文章和工具不代表机构意见，也不假装拥有不存在的权威；价值来自可检查的过程和真实使用痕迹。
          </p>
          <p>
            如果你发现事实错误、过期步骤或数据口径问题，可以直接联系我。我会保留更正，而不是静默把旧判断改成一直正确。
          </p>
          <div className='home-actions'>
            <Link href='/standards'>查看内容与披露原则</Link>
            <Link href='/contact'>报告问题</Link>
          </div>
        </div>
      </section>
    </main>
  )
}
