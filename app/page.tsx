import type { Metadata } from 'next'
import Link from 'next/link'
import { getCachedAllPost } from './api/post/lib'
import AdSlot from '@/components/site/AdSlot'
import { AD_SLOT } from '@/lib/ads'
import {
  formatPostDate,
  getPostCategory,
  SITE_CATEGORIES,
  SITE_DESCRIPTION,
  SITE_TITLE,
  SITE_URL,
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

const RECENT_POST_LIMIT = 10

const works = [
  {
    href: '/smallcap-strategy',
    title: 'A 股小微盘轮动策略',
    description: '最近交易日的目标持仓、调仓记录，以及不同持股数量下的历史收益与回撤。',
    status: '交易日盘后更新',
  },
  {
    href: '/pe',
    title: '利润线与估值',
    description: '股价、TTM EPS、利润线与估值区间的历史查询入口。',
    status: '低频维护',
  },
  {
    href: '/tools',
    title: '浏览器小工具',
    description: '图片合并与压缩在本地浏览器完成，文件不会上传到服务器。',
    status: '本地处理',
  },
]

export default async function Home() {
  const posts = await getCachedAllPost()
  const recent = posts.slice(0, RECENT_POST_LIMIT)

  return (
    <main className='home-page'>
      <h1 className='home-title'>c9cu 的个人网站</h1>

      <section id='work' className='home-section' aria-labelledby='work-title'>
        <div className='home-section-heading'>
          <h2 id='work-title'>研究看板与工具</h2>
          <Link href='/tools'>全部工具</Link>
        </div>
        <ul className='home-list'>
          {works.map((work) => (
            <li key={work.href}>
              <h3>
                <Link href={work.href}>{work.title}</Link>
              </h3>
              <p>{work.description}</p>
              <span className='home-list-aside'>{work.status}</span>
            </li>
          ))}
        </ul>
      </section>

      <AdSlot slot={AD_SLOT.HOME_MIDDLE} />

      <section id='notes' className='home-section' aria-labelledby='notes-title'>
        <div className='home-section-heading'>
          <h2 id='notes-title'>最近文章</h2>
          <span>最近 {recent.length} 篇</span>
        </div>
        <ol className='home-list'>
          {recent.map((post) => (
            <li key={post.path}>
              <h3>
                <Link href={`/post/${post.path}`}>{post.data.title}</Link>
              </h3>
              {post.data.description && <p>{post.data.description}</p>}
              <span className='home-list-aside'>
                <time dateTime={String(post.data.date)}>{formatPostDate(post.data.date)}</time>
                {SITE_CATEGORIES[getPostCategory(post)].label}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <AdSlot slot={AD_SLOT.HOME_BOTTOM} />
    </main>
  )
}
