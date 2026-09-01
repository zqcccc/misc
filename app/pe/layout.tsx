import type { Metadata } from 'next'
import FinancialNotice from '@/components/site/FinancialNotice'
import { SITE_URL } from '@/lib/site'

export const metadata: Metadata = {
  title: '利润线与估值工具',
  description: '查看股价、TTM EPS 利润线、估值参考线、历史分红和公司分析；页面同时说明数据口径与局限。',
  alternates: { canonical: '/pe' },
  openGraph: {
    title: '利润线与估值工具',
    description: '把价格、利润和估值放在同一条可检查的时间轴上。',
    url: `${SITE_URL}/pe`,
  },
}

export default function ProfitLineLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <FinancialNotice title='利润线工具的数据边界' />
    </>
  )
}
