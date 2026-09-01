import type { Metadata } from 'next'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '联系 c9cu',
  description: '联系 c9cu，报告事实错误、过期步骤、数据口径问题或网站故障。',
  alternates: { canonical: '/contact' },
  openGraph: {
    title: '联系 c9cu',
    description: '报告事实错误、过期步骤、数据口径问题或网站故障。',
    url: `${SITE_URL}/contact`,
  },
}

export default function ContactPage() {
  return (
    <main className='trust-page'>
      <header>
        <h1>联系 c9cu</h1>
        <p>最有价值的来信，通常不是“写得不错”，而是指出哪里已经不对了。</p>
      </header>

      <section>
        <h2>电子邮件</h2>
        <p>
          请发送至 <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>。网站没有客服团队，我会在有空时阅读和处理，但不承诺固定回复时间。
        </p>
      </section>

      <section>
        <h2>报告问题时请尽量附上</h2>
        <ul>
          <li>出问题的完整页面地址；</li>
          <li>你看到的错误内容或异常表现；</li>
          <li>如果是数据问题，请说明标的、日期和你采用的对照来源；</li>
          <li>如果是工具故障，请说明浏览器、设备和可复现步骤。</li>
        </ul>
      </section>

      <section>
        <h2>不会通过邮件提供的服务</h2>
        <p>
          我不会通过邮件提供个性化投资建议、代客理财、账户操作或收益承诺。涉及账户密码、身份证件、支付信息等敏感数据，请不要发送。
        </p>
      </section>
    </main>
  )
}
