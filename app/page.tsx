import type { Metadata } from 'next'
import Link from 'next/link'
import { getCachedAllPost } from './api/post/lib'
import {
  formatPostDate,
  getPostCategory,
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

const tools = [
  {
    href: '/pe',
    title: '利润线与估值',
    description: '保留股价、TTM EPS、利润线与估值区间的历史查询入口；当前仅做必要维护。',
    meta: '历史入口 · 低频维护',
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
  const recent = posts.slice(0, 10)
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
            <Link href='/smallcap-strategy'>查看微盘股策略信号</Link>
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

        <article className='home-lead-work'>
          <div className='home-lead-meta'>
            <span>策略看板</span>
            <span>交易日盘后更新</span>
          </div>
          <h2>
            <Link href='/smallcap-strategy'>A 股小微盘轮动策略</Link>
          </h2>
          <p>查看最近交易日的目标持仓、调仓记录，以及不同持股数量下的历史收益与回撤。</p>
          <Link className='home-text-link' href='/smallcap-strategy'>
            查看微盘股持仓与完整回测
            <span aria-hidden='true'>→</span>
          </Link>
        </article>
      </section>

      <section id='work' className='home-section home-work' aria-labelledby='work-title'>
        <div className='home-section-heading'>
          <h2 id='work-title'>工具入口</h2>
          <p>仍在使用的工具会说明处理位置和数据边界；低频维护的历史工具会直接标注状态。</p>
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
