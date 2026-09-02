import type { Metadata } from 'next'
import type { ReactNode } from 'react'

export const metadata: Metadata = {
  title: 'A 股策略信号与回测',
  description:
    '查看 A 股核心赛道龙头策略最近交易日的风险状态、精选持仓与现金比例，以及全样本和样本外回测。',
  alternates: { canonical: '/ashare-strategy' },
}

export default function AShareStrategyLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children
}
