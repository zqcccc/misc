import type { Metadata } from 'next'
import { SITE_EMAIL, SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '隐私政策',
  description: 'onlylike.work 实际收集的数据、浏览器本地处理、匿名访问统计和联系信息说明。',
  alternates: { canonical: '/privacy' },
  openGraph: {
    title: 'onlylike.work 隐私政策',
    description: '说明网站实际收集的数据以及访客可以怎样选择。',
    url: `${SITE_URL}/privacy`,
  },
}

export default function PrivacyPage() {
  return (
    <main className='trust-page'>
      <header>
        <h1>隐私政策</h1>
        <p>生效日期：2026 年 9 月 1 日。这里只描述 onlylike.work 目前实际发生的数据处理。</p>
      </header>

      <section>
        <h2>基本原则</h2>
        <p>
          onlylike.work 是 c9cu 维护的个人网站。网站不会出售访客个人信息，也不会要求你注册账户、提供支付资料或绑定社交账号才能阅读公开内容和使用主要工具。
        </p>
      </section>

      <section>
        <h2>服务器日志</h2>
        <p>
          为了传输网页、排查故障和防止滥用，网站服务器与网络服务提供商可能短期处理请求时间、页面地址、IP 地址、浏览器类型、响应状态等常见技术日志。这些数据不用于建立个人档案。
        </p>
      </section>

      <section id='analytics'>
        <h2>匿名访问统计</h2>
        <p>
          Google Analytics 只有在你点击“允许匿名统计”后才会加载。它可能使用 Cookie 或类似技术记录页面访问、设备类别和大致地区等信息，并启用 IP 匿名化。选择“仅必要功能”不会影响网站阅读或工具使用。
        </p>
        <p>
          你的选择保存在浏览器本地键值 <code>c9cu-analytics-consent</code> 中。清除 onlylike.work 的站点数据后，网站会再次询问。
        </p>
      </section>

      <section>
        <h2>浏览器本地数据</h2>
        <p>
          深浅主题偏好保存在浏览器的 <code>theme</code> 键中。图片合并、压缩等工具在浏览器本地处理你选择的文件；这些图片不会为了完成工具功能而上传到 onlylike.work 服务器。
        </p>
      </section>

      <section>
        <h2>评论与第三方服务</h2>
        <p>
          部分文章可能加载 Cusdis 评论组件。只有当你主动使用评论功能时，相关内容和技术信息才会由该第三方处理。外部链接、数据供应商和嵌入服务适用各自的隐私政策，onlylike.work 无法控制其数据处理。
        </p>
      </section>

      <section>
        <h2>邮件联系</h2>
        <p>
          当你主动发送邮件时，我会收到你提供的邮箱地址和邮件内容，仅用于阅读、回复、处理更正或解决问题。请不要发送账户密码、身份证件、支付资料等不必要的敏感信息。
        </p>
      </section>

      <section>
        <h2>保留、删除与选择</h2>
        <p>
          技术日志只在维护和安全所需的合理期限内保留。你可以通过浏览器拒绝或删除本地存储和 Cookie。若希望查询或删除通过邮件、评论主动提供的信息，请联系
          <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>；是否能够删除也取决于适用法律和第三方服务能力。
        </p>
      </section>

      <section>
        <h2>政策更新与联系</h2>
        <p>
          网站功能或第三方服务变化时，这份政策会相应更新并修改生效日期。对隐私处理有疑问，可以发送邮件至
          <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>。
        </p>
      </section>
    </main>
  )
}
