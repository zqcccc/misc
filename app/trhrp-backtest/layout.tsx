import type { Metadata } from 'next'
import FinancialNotice from '@/components/site/FinancialNotice'
import { SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: 'TRHRP 历史回测档案',
  description: 'TRHRP 多市场状态识别、仓位切换、收益与回撤的历史研究快照；数据已停止自动刷新。',
  alternates: { canonical: '/trhrp-backtest' },
  openGraph: {
    title: 'TRHRP 历史回测档案',
    description: '多市场状态识别、仓位切换、收益和回撤的历史研究快照，已停止自动刷新。',
    url: `${SITE_URL}/trhrp-backtest`,
  },
}

export default function TrhrpLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <aside className='archive-notice' aria-label='历史档案状态'>
        <strong>历史研究档案</strong>
        <p>TRHRP 的实时监控和定时数据服务已经下线。页面保留的是历史回测结果，不再自动刷新，请先核对页面中的数据截至日。</p>
      </aside>
      {children}
      <FinancialNotice title='TRHRP 回测的使用边界' />
    </>
  )
}
