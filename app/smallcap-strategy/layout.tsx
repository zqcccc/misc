import type { Metadata } from 'next'
import type { ReactNode } from 'react'

export const metadata: Metadata = {
  title: '聚宽小微盘策略持仓详情与回测看板',
  description:
    '聚宽社区顶流小市值微利轮动量化策略，展示最新 30 只持仓明细、市值分布、历史调仓记录与严谨因果回测数据。',
  alternates: { canonical: '/smallcap-strategy' },
}

export default function SmallCapStrategyLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children
}
