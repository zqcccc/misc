'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useOverview, useMarketResult, useConnectedCharts } from './hooks'
import type { MarketSummary, RangeStats } from './types'
import { signed, pct } from './chart-options'

const REFRESH_MS = 60_000

function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)}%`
}

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: 'green' | 'red' | 'purple' | 'gray'
}) {
  const colorMap = {
    green: 'text-emerald-600 dark:text-emerald-400',
    red: 'text-rose-600 dark:text-rose-400',
    purple: 'text-purple-600 dark:text-purple-400',
    gray: 'text-gray-700 dark:text-gray-200',
  }
  const color = accent ? colorMap[accent] : colorMap.gray
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] px-3 py-2">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-base font-semibold ${color}`}>{value}</div>
      {sub && (
        <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          {sub}
        </div>
      )}
    </div>
  )
}

function MarketTabs({
  markets,
  active,
  onSelect,
}: {
  markets: MarketSummary[]
  active: string
  onSelect: (label: string) => void
}) {
  // 按 group 分组
  const groups = useMemo(() => {
    const g: Record<string, MarketSummary[]> = {}
    markets.forEach((m) => {
      ;(g[m.group] = g[m.group] || []).push(m)
    })
    return g
  }, [markets])

  return (
    <div className="flex flex-col gap-3">
      {Object.entries(groups).map(([grp, items]) => (
        <div key={grp}>
          <div className="text-xs text-gray-400 dark:text-gray-500 mb-1">
            {grp}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {items.map((m) => {
              const isActive = m.label === active
              const ex = m.excess
              const accent =
                ex > 0.001
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : ex < -0.001
                    ? 'text-rose-600 dark:text-rose-400'
                    : 'text-gray-500 dark:text-gray-400'
              return (
                <button
                  key={m.label}
                  onClick={() => onSelect(m.label)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition border ${
                    isActive
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white dark:bg-[#282c35] text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-700 hover:bg-blue-50 dark:hover:bg-[#363c48]'
                  }`}
                >
                  <span>{m.label}</span>
                  <span
                    className={`ml-1.5 text-xs ${
                      isActive ? 'text-blue-100' : accent
                    }`}
                  >
                    {fmtPct(ex, 0)}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function RangeStatsPanel({ rs }: { rs: RangeStats | null }) {
  if (!rs) return null
  const cls = (x: number) =>
    x >= 0
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-rose-600 dark:text-rose-400'
  const cards = [
    { k: '区间', v: `${rs.start} ~ ${rs.end}`, cls: 'text-gray-800 dark:text-gray-100' },
    { k: '区间天数', v: `${rs.days} 天`, cls: 'text-gray-800 dark:text-gray-100' },
    { k: '策略收益(区间)', v: fmtPct(rs.sRet), cls: cls(rs.sRet) },
    { k: '标的收益(区间)', v: fmtPct(rs.bRet), cls: cls(rs.bRet) },
    { k: '超额(策略−标的)', v: fmtPct(rs.excess), cls: cls(rs.excess) },
    { k: '策略最大回撤(区间)', v: pct(rs.sMdd), cls: cls(rs.sMdd) },
    { k: '标的最大回撤(区间)', v: pct(rs.bMdd), cls: cls(rs.bMdd) },
    { k: '策略年化(区间)', v: fmtPct(rs.sAnn), cls: cls(rs.sAnn) },
    { k: '标的年化(区间)', v: fmtPct(rs.bAnn), cls: cls(rs.bAnn) },
  ]
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3">
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
        区间收益统计（拖动下方缩放条选择区间）
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {cards.map((c) => (
          <div key={c.k}>
            <div className="text-xs text-gray-500 dark:text-gray-400">{c.k}</div>
            <div className={`text-sm font-medium ${c.cls}`}>{c.v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SummaryTable({
  markets,
  active,
  onSelect,
}: {
  markets: MarketSummary[]
  active: string
  onSelect: (label: string) => void
}) {
  const cols: { label: string; key: keyof MarketSummary; fmt: 'pct' | 'signed' | 'int' | 'text' }[] = [
    { label: '标的', key: 'label', fmt: 'text' },
    { label: '代码', key: 'ticker', fmt: 'text' },
    { label: '策略总收益', key: 'strat_total', fmt: 'signed' },
    { label: '基准总收益', key: 'bench_total', fmt: 'signed' },
    { label: '超额', key: 'excess', fmt: 'signed' },
    { label: '策略CAGR', key: 'strat_cagr', fmt: 'signed' },
    { label: '策略MDD', key: 'strat_mdd', fmt: 'pct' },
    { label: '基准MDD', key: 'bench_mdd', fmt: 'pct' },
    { label: '偏好天', key: 'risk_on', fmt: 'int' },
    { label: '中性天', key: 'moderate', fmt: 'int' },
    { label: '规避天', key: 'risk_off', fmt: 'int' },
    { label: '加仓', key: 'adds', fmt: 'int' },
    { label: '减仓', key: 'reduces', fmt: 'int' },
  ]
  const fmtVal = (m: MarketSummary, c: (typeof cols)[number]) => {
    const v = m[c.key]
    if (c.fmt === 'signed') return fmtPct(v as number)
    if (c.fmt === 'pct') return pct(v as number)
    if (c.fmt === 'int') return String(v)
    return String(v)
  }
  const clsFor = (m: MarketSummary, c: (typeof cols)[number]) => {
    if (c.fmt === 'signed')
      return (m[c.key] as number) >= 0
        ? 'text-emerald-600 dark:text-emerald-400'
        : 'text-rose-600 dark:text-rose-400'
    if (c.fmt === 'pct')
      return (m[c.key] as number) < 0
        ? 'text-rose-600 dark:text-rose-400'
        : 'text-gray-700 dark:text-gray-200'
    return 'text-gray-700 dark:text-gray-200'
  }
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3 overflow-x-auto">
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
        全市场汇总（点击行跳转）
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            {cols.map((c) => (
              <th key={c.key as string} className="py-1.5 pr-3 whitespace-nowrap">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {markets.map((m) => (
            <tr
              key={m.label}
              onClick={() => onSelect(m.label)}
              className={`cursor-pointer border-b border-gray-100 dark:border-gray-800 hover:bg-blue-50 dark:hover:bg-[#363c48] ${
                m.label === active ? 'bg-blue-50 dark:bg-[#2f3a4d]' : ''
              }`}
            >
              {cols.map((c) => (
                <td
                  key={c.key as string}
                  className={`py-1.5 pr-3 whitespace-nowrap font-medium ${clsFor(m, c)}`}
                >
                  {fmtVal(m, c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function TrhrpBacktestPage() {
  const { data, state, error, generatedAt, refresh } = useOverview(REFRESH_MS)
  const [activeLabel, setActiveLabel] = useState<string | null>(null)
  const { result, loading: resultLoading } = useMarketResult(
    activeLabel,
    generatedAt,
  )
  const [rangeStats, setRangeStats] = useState<RangeStats | null>(null)

  const mainRef = useRef<HTMLDivElement>(null)
  const weightRef = useRef<HTMLDivElement>(null)
  useConnectedCharts(
    mainRef,
    weightRef,
    result,
    data?.regime_cn || {},
    setRangeStats,
  )

  // 默认选中第一个标的
  useEffect(() => {
    if (data && !activeLabel && data.markets.length) {
      setActiveLabel(data.markets[0].label)
    }
  }, [data, activeLabel])

  if (state === 'loading' && !data) {
    return (
      <div className="max-w-6xl mx-auto my-10 p-8 text-center text-gray-500 dark:text-gray-400">
        加载回测数据中...
      </div>
    )
  }
  if (state === 'error' && !data) {
    return (
      <div className="max-w-6xl mx-auto my-10 p-8 rounded-xl shadow-lg bg-white dark:bg-[#282c35]">
        <h1 className="text-2xl font-bold mb-4 text-rose-600 dark:text-rose-400">
          数据加载失败
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mb-4">{error}</p>
        <button
          onClick={refresh}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          重试
        </button>
      </div>
    )
  }
  if (!data || !activeLabel) return null

  const s = result?.summary
  const lastPoll = new Date().toLocaleTimeString('zh-CN', { hour12: false })

  return (
    <div className="max-w-6xl mx-auto my-6 px-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            TRHRP 多市场回测 · 策略 vs 买入持有
          </h1>
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            回测数据生成于: {generatedAt?.slice(0, 19).replace('T', ' ')} UTC
            {` · 自动刷新 ${REFRESH_MS / 1000}s (上次: ${lastPoll})`}
          </div>
        </div>
        <button
          onClick={refresh}
          className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          刷新
        </button>
      </div>

      {/* 品种选择 */}
      <div className="mb-4">
        <MarketTabs
          markets={data.markets}
          active={activeLabel}
          onSelect={setActiveLabel}
        />
      </div>

      {/* 统计卡片 */}
      {s && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
          <StatCard
            label="策略总收益"
            value={signed(s.strategy_total_return)}
            accent={s.strategy_total_return >= 0 ? 'green' : 'red'}
          />
          <StatCard
            label="基准总收益"
            value={signed(s.benchmark_total_return)}
            accent={s.benchmark_total_return >= 0 ? 'green' : 'red'}
          />
          <StatCard
            label="超额收益"
            value={signed(s.excess_total_return)}
            accent={s.excess_total_return >= 0 ? 'green' : 'red'}
          />
          <StatCard
            label="策略CAGR"
            value={signed(s.strategy_cagr)}
            accent={s.strategy_cagr >= 0 ? 'green' : 'red'}
          />
          <StatCard
            label="策略最大回撤"
            value={pct(s.strategy_max_drawdown)}
            accent="red"
          />
          <StatCard
            label="基准最大回撤"
            value={pct(s.benchmark_max_drawdown)}
            accent="red"
          />
          <StatCard
            label="加仓 / 减仓日"
            value={`${s.add_days} / ${s.reduce_days}`}
            accent="gray"
          />
          <StatCard
            label="调仓日"
            value={`${s.rebalance_days}`}
            accent="gray"
          />
          <StatCard
            label="偏好/中性/规避 天"
            value={`${s.risk_on_days}/${s.moderate_days}/${s.risk_off_days}`}
            accent="gray"
          />
          <StatCard
            label="区间 / 天数"
            value={`${result?.meta.start}~${result?.meta.end.slice(0, 4)}`}
            sub={`${result?.meta.days} 天`}
            accent="gray"
          />
        </div>
      )}

      {/* 主图 + 仓位子图（联动缩放） */}
      <div className="mb-4 space-y-3">
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3">
          {resultLoading && !result && (
            <div className="text-xs text-gray-400 py-2">加载标的序列...</div>
          )}
          <div ref={mainRef} style={{ width: '100%', height: 560 }} />
          <div className="legend text-xs text-gray-500 dark:text-gray-400 mt-1">
            绿带=风险偏好 / 黄带=中性 / 红带=风险规避；▲红=加仓，▼绿=减仓（落在归一价曲线上）。
            左轴净值、右轴归一价。
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">
            股票仓位 %（0–100% · 与上方联动缩放）
          </div>
          <div ref={weightRef} style={{ width: '100%', height: 200 }} />
          <div className="legend text-xs text-gray-500 dark:text-gray-400 mt-1">
            紫线 = 每日股票仓位；虚线参考
            <b className="text-rose-700 dark:text-rose-400"> 清仓 0%</b> /
            <b className="text-orange-600 dark:text-orange-400"> risk_off 下限 20%</b> /
            <b className="text-emerald-700 dark:text-emerald-400"> risk_on 80%</b>
            。这是判断“是否清仓”的唯一准绳。
          </div>
        </div>
      </div>

      {/* 区间收益统计 */}
      <div className="mb-4">
        <RangeStatsPanel rs={rangeStats} />
      </div>

      {/* 全市场汇总表 */}
      <div className="mb-4">
        <SummaryTable
          markets={data.markets}
          active={activeLabel}
          onSelect={setActiveLabel}
        />
      </div>

      {/* 修正说明 */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3 mb-4 text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
        <span className="font-medium text-gray-800 dark:text-gray-200">
          口径与数据说明:{' '}
        </span>
        FX 约定：全部按 USD 计价。策略与基准同币种，相对价值（超额/回撤改善）不受影响；
        A/H 标的绝对收益含轻微汇率漂移（港股近似无，人民币有）。操作点 = 股票仓位变动（加仓▲/减仓▼），
        来自当前 monitor/trhrp_strategy 口径（高波动资产 relative_zscore 重校准 + 分组 z 叠加）。
        <br />
        <b className="text-rose-700 dark:text-rose-400">数据修正：</b>
        原 SGOV_combined.csv 已损坏（价格反复锯齿、单日 ±12% 数百次），已全部 22 标的改用干净的
        <b> SHY.csv</b> 作短债防御腿（等价替代，覆盖 2018–2026）。
        此前 risk_off 期间净值的异常暴跌/尖刺均因此坏数据，现已消除。
      </div>
    </div>
  )
}
