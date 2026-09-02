import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: '自用工具',
  description:
    'c9cu 的研究工具与浏览器工具：说明维护状态、数据来源、处理位置和已知局限。',
  alternates: { canonical: '/tools' },
}

const tools = [
  {
    name: 'A 股策略信号与回测',
    desc: '查看最近交易日的风险状态、精选持仓与现金比例，并核对全样本和样本外回测。',
    href: '/ashare-strategy',
    kind: '研究工具',
    detail: '交易日盘后更新；展示的是模型信号和历史回测，不构成投资建议。',
  },
  {
    name: '聚宽小微盘量化持仓与回测',
    desc: '聚宽顶流小市值微利轮动策略：30 只股票最新持仓明细、市值分布、调仓历史及严谨因果回测。',
    href: '/smallcap-strategy',
    kind: '研究工具',
    detail: '严格 T+1 撮合与历史真实摩擦；包含 2024 年初流动性挤兑压力测试。',
  },
  {
    name: '利润线与估值',
    desc: '把股价、TTM EPS、利润线、估值区间与分红记录放进同一时间轴。',
    href: '/pe',
    kind: '研究工具',
    detail: '使用公开市场数据；页面标注更新时间与研究边界。',
  },
  {
    name: '图片合并',
    desc: '调整顺序后横向或纵向拼接多张图片，并选择导出格式。',
    href: '/tools/merge-images',
    kind: '本地工具',
    detail: '图片只在当前浏览器处理，不会上传到本站服务器。',
  },
  {
    name: '图片压缩',
    desc: '批量缩放 JPG、PNG、WEBP，并按质量导出或打包下载。',
    href: '/tools/compress-images',
    kind: '本地工具',
    detail: '图片只在当前浏览器处理，不会上传到本站服务器。',
  },
]

export default function ToolsHome() {
  return (
    <main className='tools-index'>
      <header>
        <h1>解决我自己反复遇到的问题。</h1>
        <p>
          这里不是随手堆出来的工具导航。每个页面都说明它在处理什么、数据从哪里来，以及哪些结论不能从结果中推出。
        </p>
      </header>

      <section aria-labelledby='tools-list-title'>
        <div className='tools-index-heading'>
          <h2 id='tools-list-title'>工具与研究看板</h2>
          <p>{tools.length} 个公开页面</p>
        </div>
        <ol className='tools-index-list'>
          {tools.map((tool, index) => (
            <li key={tool.href}>
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
              <Link className='tools-index-open' href={tool.href} aria-label={`打开${tool.name}`}>
                打开 <span aria-hidden='true'>→</span>
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <aside className='tools-index-note'>
        <h2>隐私与责任</h2>
        <p>
          图片工具使用浏览器能力在本地完成计算；研究工具的数据和算法有明确边界。本站不会把“免费”包装成无条件保证，也不会隐藏金融工具的风险提示。
        </p>
        <div>
          <Link href='/privacy'>隐私说明</Link>
          <Link href='/standards'>内容与披露原则</Link>
          <Link href='/contact'>反馈问题</Link>
        </div>
      </aside>
    </main>
  )
}
