import type { Metadata } from 'next'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

const MAIL_SUBJECT = encodeURIComponent('onlylike.work 广告合作')

export const metadata: Metadata = {
  title: '广告合作',
  description: '在 onlylike.work 的文章页投放赞助广告：广告位、接受的广告类型和联系方式。',
  alternates: { canonical: '/advertise' },
  openGraph: {
    title: 'onlylike.work 广告合作',
    description: '文章页赞助广告位、接受的广告类型和联系方式。',
    url: `${SITE_URL}/advertise`,
  },
}

export default function AdvertisePage() {
  return (
    <main className='trust-page'>
      <header>
        <h1>广告合作</h1>
        <p>
          onlylike.work 的读者主要关心投资研究、量化回测、前端与运维工程实践。如果你的产品对这些读者有用，可以在这里投放赞助广告。
        </p>
      </header>

      <section>
        <h2>广告位</h2>
        <ul>
          <li>文章页正文上方；</li>
          <li>文章页正文下方，评论区之前。</li>
        </ul>
        <p>
          广告以图片加链接的形式展示，统一标注“赞助”和赞助商名称，链接带 <code>rel=&quot;sponsored&quot;</code>。投研看板和工具页面不放广告。
        </p>
      </section>

      <section>
        <h2>接受的广告</h2>
        <ul>
          <li>开发者工具、云服务、VPS、数据服务和 API；</li>
          <li>行情数据、回测平台、研究工具等投资研究基础设施；</li>
          <li>技术书籍、课程和会议。</li>
        </ul>
      </section>

      <section>
        <h2>不接受的广告</h2>
        <p>
          荐股、代客理财、收益承诺、博彩、无牌照金融业务、网络代理与规避类工具。
        </p>
      </section>

      <section>
        <h2>价格与联系</h2>
        <p>
          按月计费，价格取决于广告位和投放时长。请发送邮件至
          <a href={`mailto:${SITE_EMAIL}?subject=${MAIL_SUBJECT}`}>{SITE_EMAIL}</a>
          ，说明产品、希望的广告位和投放时间，我会回复近期的访问数据和报价。
        </p>
      </section>
    </main>
  )
}
