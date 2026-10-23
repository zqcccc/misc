import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_DESCRIPTION, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '关于 c9cu',
  description: 'c9cu 的个人网站 onlylike.work 简介，以及研究、工程笔记和自用工具的发布方式。',
  alternates: { canonical: '/about' },
  openGraph: {
    title: '关于 c9cu',
    description: SITE_DESCRIPTION,
    url: `${SITE_URL}/about`,
  },
}

export default function AboutPage() {
  return (
    <main className='trust-page'>
      <header>
        <h1>关于 c9cu</h1>
      </header>

      <section>
        <h2>这个网站是什么</h2>
        <p>
          onlylike.work 是我的个人网站，不代表公司、媒体、研究机构或持牌投资顾问。内容包括工程笔记、图片工具和投资策略研究。
        </p>
      </section>

      <section>
        <h2>我怎样发布内容</h2>
        <ul>
          <li>工程笔记优先记录实际遇到的问题、验证步骤和版本背景。</li>
          <li>投资研究会说明数据来源、计算方法、适用边界和无法证明的部分。</li>
          <li>工具会解释数据是否上传、结果怎样产生，以及失败时应该怎么处理。</li>
          <li>明显过时的文章会标记为历史记录或退出公开索引。</li>
        </ul>
      </section>

      <nav className='trust-page-links' aria-label='进一步了解'>
        <Link href='/standards'>内容与披露原则</Link>
        <Link href='/contact'>联系与更正</Link>
        <Link href='/privacy'>隐私政策</Link>
      </nav>
    </main>
  )
}
