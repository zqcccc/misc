import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import FinancialNotice from '@/components/site/FinancialNotice'

export const metadata: Metadata = {
  title: '聚宽小微盘策略持仓详情与回测看板',
  description:
    '聚宽社区小市值微利轮动量化策略，展示最新 30 只持仓明细、市值分布、历史调仓记录与因果回测数据。',
  alternates: { canonical: '/smallcap-strategy' },
}

export default function SmallCapStrategyLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <>
      {children}
      <FinancialNotice title='小微盘策略看板的数据边界' />
    </>
  )
}
