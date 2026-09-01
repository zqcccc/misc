import type { Metadata } from 'next'
import Link from 'next/link'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '内容与披露原则',
  description: 'c9cu 对内容来源、更新、更正、金融研究、自动化、联盟链接和广告的公开说明。',
  alternates: { canonical: '/standards' },
  openGraph: {
    title: '内容与披露原则',
    description: '内容来源、更新、更正、金融研究和商业关系的公开说明。',
    url: `${SITE_URL}/standards`,
  },
}

export default function StandardsPage() {
  return (
    <main className='trust-page'>
      <header>
        <h1>内容与披露原则</h1>
        <p>这不是一份漂亮话清单，而是 onlylike.work 判断一项内容是否应该继续公开的最低标准。</p>
      </header>

      <section>
        <h2>作者与来源</h2>
        <p>
          站内原创文章默认作者为 c9cu。引用外部资料时，应尽量链接到原始文档、项目或数据来源；只复述别人结论而没有新增经验、分析或验证的内容，不应作为独立文章发布。
        </p>
      </section>

      <section>
        <h2>日期、更新与更正</h2>
        <p>
          发布日期表示文章最初形成的时间，不代表内容今天仍然有效。涉及软件版本、政策、价格或市场数据时，应在适当位置注明数据截至日或最后验证时间。超过三年的工程文章会提示可能过时。
        </p>
        <p>
          发现实质错误时，我会修正文稿；如果错误会改变原结论，应说明更正。你可以通过
          <a href={`mailto:${SITE_EMAIL}`}>电子邮件</a>提交问题。
        </p>
      </section>

      <section id='financial'>
        <h2>金融研究声明</h2>
        <p>
          站内估值、回测、市场状态和资产配置内容仅用于记录个人研究过程，不构成投资建议、证券推荐、收益承诺或招揽。历史数据与回测不能保证未来结果；数据可能延迟、缺失或存在供应商差异。
        </p>
        <p>
          任何投资决定都应由读者结合自身目标、风险承受能力和独立资料作出。工具输出不能替代持牌专业人士的意见。
        </p>
      </section>

      <section>
        <h2>自动化与人工判断</h2>
        <p>
          网站会使用程序生成图表、刷新数据和执行批量计算。自动化结果应提供数据口径与计算说明；如果生成式 AI 对一篇内容的事实表达有实质参与，会在适合的位置说明，最终发布责任仍由 c9cu 承担。
        </p>
      </section>

      <section>
        <h2>联盟链接、广告与利益关系</h2>
        <p>
          如果页面包含可能产生佣金的联盟链接，会在链接附近明确标注。广告不会被包装成站内导航、下载按钮或研究结论。商业关系不会换取未披露的正面评价。
        </p>
      </section>

      <section>
        <h2>退出公开内容</h2>
        <p>
          重复测试稿、未完成页面、无法安全维护的功能，以及可能协助绕过访问限制或引发其他合规风险的旧教程，不再进入导航、站点地图和公开文章系统。
        </p>
      </section>

      <nav className='trust-page-links' aria-label='相关页面'>
        <Link href='/about'>关于 c9cu</Link>
        <Link href='/privacy'>隐私政策</Link>
        <Link href='/contact'>联系与更正</Link>
      </nav>
    </main>
  )
}
