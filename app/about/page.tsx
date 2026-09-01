import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_DESCRIPTION, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '关于 c9cu',
  description: '了解 c9cu 为什么维护 onlylike.work，以及这个个人网站如何处理研究、工程笔记和自用工具。',
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
        <p>一个人做过的研究、写过的代码和反复使用的工具，值得有一个不依赖平台时间线的长期地址。</p>
      </header>

      <section>
        <h2>这个网站是什么</h2>
        <p>
          onlylike.work 是我的个人网站。它不代表公司、媒体、研究机构或持牌投资顾问，也没有刻意限定某一种读者。有人因为一篇工程笔记来到这里，也有人只是需要一个图片工具，或者想看一套投资策略是怎样计算的。
        </p>
        <p>
          这些主题之所以放在一起，不是因为它们属于同一个行业，而是因为它们都来自同一个人的真实使用过程。我会尽量留下足够的上下文，让后来的人能判断内容是否适合自己。
        </p>
      </section>

      <section>
        <h2>我怎样发布内容</h2>
        <ul>
          <li>工程笔记优先记录实际遇到的问题、验证步骤和版本背景。</li>
          <li>投资研究会说明数据来源、计算方法、适用边界和无法证明的部分。</li>
          <li>工具会解释数据是否上传、结果怎样产生，以及失败时应该怎么处理。</li>
          <li>旧内容不会假装永远正确；明显过时的文章会标记为历史记录或退出公开索引。</li>
        </ul>
      </section>

      <section>
        <h2>可信度从哪里来</h2>
        <p>
          我不会在这里编造职业头衔、机构背书或投资业绩。这个网站能提供的可信度来自可检查的过程：源码、图表、时间、数据口径、失败记录和更正入口。它们不等于权威，但比没有出处的结论更诚实。
        </p>
      </section>

      <nav className='trust-page-links' aria-label='进一步了解'>
        <Link href='/standards'>内容与披露原则</Link>
        <Link href='/contact'>联系与更正</Link>
        <Link href='/privacy'>隐私政策</Link>
      </nav>
    </main>
  )
}
