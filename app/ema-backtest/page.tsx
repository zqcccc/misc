'use client'

import { useEffect, useMemo, useState } from 'react'
import { useOverview, useChart } from './hooks'
import { buildChartOption } from './chart-options'
import type { InstrumentPayload } from './types'

const POLL_MS = 30_000

function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)}%`
}

function fmtNum(v: number | undefined | null, digits = 4): string {
  if (v == null || Number.isNaN(v)) return '-'
  return v.toFixed(digits)
}

function StatCard({ label, value, sub, accent }: {
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
      {sub && <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function InstrumentTabs({ instruments, active, onSelect }: {
  instruments: InstrumentPayload[]
  active: string
  onSelect: (name: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {instruments.map((inst) => {
        const isActive = inst.name === active
        const pos = inst.current.position ?? 0
        const posEmoji = pos === 1 ? '🟢' : pos === -1 ? '🔴' : '⚪'
        const fwdRet = inst.forward?.total_return ?? 0
        const accent = fwdRet > 0.001 ? 'text-emerald-600 dark:text-emerald-400'
          : fwdRet < -0.001 ? 'text-rose-600 dark:text-rose-400'
          : 'text-gray-500 dark:text-gray-400'
        const livePrice = inst.current.live_price
        const priceStr = livePrice != null
          ? (livePrice >= 1000 ? livePrice.toFixed(1) : livePrice >= 1 ? livePrice.toFixed(2) : livePrice.toFixed(4))
          : null
        return (
          <button
            key={inst.name}
            onClick={() => onSelect(inst.name)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition border ${
              isActive
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white dark:bg-[#282c35] text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-700 hover:bg-blue-50 dark:hover:bg-[#363c48]'
            }`}
          >
            <span>{posEmoji}</span>
            <span className="ml-1">{inst.name}</span>
            {priceStr && (
              <span className={`ml-1.5 text-xs ${isActive ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'}`}>
                @{priceStr}
              </span>
            )}
            <span className={`ml-1.5 text-xs ${isActive ? 'text-blue-100' : accent}`}>
              {fwdRet >= 0 ? '+' : ''}{(fwdRet * 100).toFixed(1)}%
            </span>
          </button>
        )
      })}
    </div>
  )
}

function CurrentStatePanel({ inst }: { inst: InstrumentPayload }) {
  const cur = inst.current
  const pos = cur.position ?? 0
  const dirStr = pos === 1 ? '做多' : pos === -1 ? '做空' : '空仓'
  const posEmoji = pos === 1 ? '🟢' : pos === -1 ? '🔴' : '⚪'
  const unreal = cur.unreal_pct ?? 0
  const entryTime = cur.entry_time
  const fwd = inst.forward

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{posEmoji}</span>
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            当前持仓: {dirStr} {Math.round((cur.pos_size ?? 0) * 100)}%
          </span>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          最新收盘: {cur.last_closed?.slice(0, 16).replace('T', ' ') || '-'} UTC
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">现价</div>
          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {fmtNum(cur.live_price)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">入场价 / 时间</div>
          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {fmtNum(cur.entry_price)}
            {entryTime && (
              <span className="ml-1 text-xs text-gray-400">
                {entryTime.slice(5, 16).replace('T', ' ')}
              </span>
            )}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">浮动盈亏</div>
          <div className={`text-sm font-medium ${unreal >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
            {fmtPct(unreal)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">RSI / EMA</div>
          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {(cur.rsi ?? 0).toFixed(1)} / {fmtNum(cur.ema)}
          </div>
        </div>
      </div>
      {fwd && fwd.events.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              前向净值 (自 {fwd.init_ts?.slice(0, 10)} 起, {fwd.events.length} 事件)
            </span>
            <span className={`text-sm font-semibold ${
              fwd.total_return >= 0 ? 'text-purple-600 dark:text-purple-400' : 'text-rose-600 dark:text-rose-400'
            }`}>
              累计 {fmtPct(fwd.total_return)} (含浮盈)
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function TradeLogPanel({ inst }: { inst: InstrumentPayload }) {
  const events = inst.forward?.events ?? []
  if (events.length === 0) {
    return null
  }
  const reversed = [...events].reverse()
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-4">
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
        真实操作日志 ({events.length})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
              <th className="py-1.5 pr-3">时间</th>
              <th className="py-1.5 pr-3">类型</th>
              <th className="py-1.5 pr-3">价格</th>
              <th className="py-1.5 pr-3">仓位变化</th>
              <th className="py-1.5 pr-3">净收益</th>
              <th className="py-1.5 pr-3">资金</th>
            </tr>
          </thead>
          <tbody>
            {reversed.map((e, i) => {
              const typeLabel = e.type === 'init' ? '初始化'
                : e.type === 'reversal' ? '反手'
                : '部分止盈'
              const typeColor = e.type === 'init' ? 'text-gray-500'
                : e.type === 'reversal' ? 'text-purple-600 dark:text-purple-400'
                : 'text-orange-600 dark:text-orange-400'
              const sizeBefore = e.pos_size_before ?? e.pos_size
              const sizeAfter = e.pos_size_after ?? e.pos_size
              const sizeStr = sizeBefore != null && sizeAfter != null
                ? `${Math.round(sizeBefore * 100)}% → ${Math.round(sizeAfter * 100)}%`
                : '-'
              return (
                <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">
                    {e.ts.slice(0, 19).replace('T', ' ')}
                  </td>
                  <td className={`py-1.5 pr-3 font-medium ${typeColor}`}>{typeLabel}</td>
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">
                    {e.price.toFixed(4)}
                  </td>
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">{sizeStr}</td>
                  <td className={`py-1.5 pr-3 font-medium ${(e.net ?? 0) > 0 ? 'text-emerald-600 dark:text-emerald-400' : (e.net ?? 0) < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-gray-500'}`}>
                    {e.type === 'init' ? '-' : fmtPct(e.net)}
                  </td>
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">
                    {(e.capital_after ?? 1).toFixed(4)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ChartArea({ inst }: { inst: InstrumentPayload }) {
  const { chartNode, chartRef, chartReady } = useChart()

  useEffect(() => {
    if (!chartReady || !chartRef.current) return
    const option = buildChartOption(inst)
    chartRef.current.setOption(option, { notMerge: true })
  }, [chartReady, inst])

  // 价格摘要
  const cur = inst.current
  const livePrice = cur.live_price
  const entryPrice = cur.entry_price
  const priceSeries = inst.series.price
  let hi: number | null = null
  let lo: number | null = null
  let firstPrice: number | null = null
  if (priceSeries.length > 0) {
    for (const [, p] of priceSeries) {
      if (hi == null || p > hi) hi = p
      if (lo == null || p < lo) lo = p
    }
    firstPrice = priceSeries[0][1]
  }
  const fmtP = (n: number | null | undefined) => {
    if (n == null || Number.isNaN(n)) return '-'
    if (n >= 1000) return n.toFixed(2)
    if (n >= 1) return n.toFixed(4)
    return n.toFixed(6)
  }
  const pos = cur.position ?? 0
  const entryVsLive = livePrice != null && entryPrice != null && entryPrice > 0
    ? (livePrice - entryPrice) / entryPrice
    : null
  const totalChg = livePrice != null && firstPrice != null && firstPrice > 0
    ? (livePrice - firstPrice) / firstPrice
    : null

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3">
      {/* 价格摘要 */}
      <div className="flex flex-wrap items-end gap-x-6 gap-y-1 mb-2 px-1 text-sm">
        <div>
          <span className="text-xs text-gray-500 dark:text-gray-400">现价 </span>
          <span className="text-lg font-bold text-gray-900 dark:text-gray-100">{fmtP(livePrice)}</span>
        </div>
        {entryVsLive != null && pos !== 0 && (
          <div>
            <span className="text-xs text-gray-500 dark:text-gray-400">vs 入场 </span>
            <span className={`font-semibold ${entryVsLive >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {entryVsLive >= 0 ? '+' : ''}{(entryVsLive * 100).toFixed(2)}%
            </span>
            <span className="ml-1 text-xs text-gray-400">({fmtP(entryPrice)})</span>
          </div>
        )}
        {totalChg != null && (
          <div>
            <span className="text-xs text-gray-500 dark:text-gray-400">回测区间 </span>
            <span className={`font-semibold ${totalChg >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {totalChg >= 0 ? '+' : ''}{(totalChg * 100).toFixed(1)}%
            </span>
          </div>
        )}
        {hi != null && lo != null && (
          <div className="text-xs text-gray-500 dark:text-gray-400">
            区间高/低: <span className="text-gray-700 dark:text-gray-300">{fmtP(hi)} / {fmtP(lo)}</span>
          </div>
        )}
        {cur.ema != null && (
          <div className="text-xs text-gray-500 dark:text-gray-400">
            EMA{inst.config.ema_span}: <span className="text-gray-700 dark:text-gray-300">{fmtP(cur.ema)}</span>
          </div>
        )}
      </div>
      <div ref={chartNode} style={{ width: '100%', height: 560 }} />
    </div>
  )
}

export default function EmaBacktestPage() {
  const { data, state, error, generatedAt, refresh } = useOverview(POLL_MS)
  const [activeName, setActiveName] = useState<string>('XAG')

  const instruments = data?.instruments ?? []
  const activeInst = useMemo(
    () => instruments.find((i) => i.name === activeName) ?? instruments[0],
    [instruments, activeName],
  )

  // 初始化选中第一个品种
  useEffect(() => {
    if (instruments.length > 0 && !instruments.find((i) => i.name === activeName)) {
      setActiveName(instruments[0].name)
    }
  }, [instruments, activeName])

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
        <h1 className="text-2xl font-bold mb-4 text-rose-600 dark:text-rose-400">数据加载失败</h1>
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

  if (!data || !activeInst) {
    return null
  }

  const s = activeInst.stats
  const fwd = activeInst.forward
  const lastPoll = new Date().toLocaleTimeString('zh-CN', { hour12: false })

  return (
    <div className="max-w-6xl mx-auto my-6 px-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            EMA 反手策略 · 回测 & 实时监控
          </h1>
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            回测数据生成于: {generatedAt?.slice(0, 19).replace('T', ' ')} UTC
            {fwd?.init_ts && ` · 前向监控起始: ${fwd.init_ts.slice(0, 10)}`}
            {` · 自动刷新 ${POLL_MS / 1000}s (上次: ${lastPoll})`}
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
        <InstrumentTabs
          instruments={instruments}
          active={activeName}
          onSelect={setActiveName}
        />
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
        <StatCard
          label="策略收益 (回测)"
          value={fmtPct(s.strategy_return)}
          sub={`${s.bars} 根 K 线`}
          accent={s.strategy_return >= 0 ? 'green' : 'red'}
        />
        <StatCard
          label="买入持有"
          value={fmtPct(s.hold_return)}
          accent={s.hold_return >= 0 ? 'green' : 'red'}
        />
        <StatCard
          label="最大回撤"
          value={fmtPct(s.max_drawdown)}
          accent="red"
        />
        <StatCard
          label="反手 / 止盈 / 胜率"
          value={`${s.reversals} / ${s.tps}`}
          sub={`胜率 ${(s.win_rate * 100).toFixed(1)}%`}
        />
        <StatCard
          label="前向累计 (真实)"
          value={fwd ? fmtPct(fwd.total_return) : '-'}
          sub={fwd ? `${fwd.events.length} 次操作` : ''}
          accent={fwd && fwd.total_return >= 0 ? 'purple' : 'red'}
        />
      </div>

      {/* 当前状态 */}
      <div className="mb-4">
        <CurrentStatePanel inst={activeInst} />
      </div>

      {/* 图表 */}
      <div className="mb-4">
        <ChartArea inst={activeInst} />
      </div>

      {/* 配置说明 */}
      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3 mb-4 text-xs text-gray-600 dark:text-gray-400">
        <span className="font-medium text-gray-800 dark:text-gray-200">策略配置: </span>
        EMA{activeInst.config.ema_span} + {activeInst.config.confirm_bars}根确认 + {(activeInst.config.breakout_pct * 100).toFixed(1)}%幅度
        {activeInst.config.tp_enabled
          ? ` · RSI${activeInst.config.rsi_over}/${activeInst.config.rsi_under} 止盈${(activeInst.config.part_ratio * 100).toFixed(0)}% 冷却${activeInst.config.cool_bars}根`
          : ' · 纯反手 (不止盈)'}
        <span className="ml-2 text-gray-400">| {activeInst.sample_note}</span>
      </div>

      {/* 真实操作日志 */}
      <TradeLogPanel inst={activeInst} />
    </div>
  )
}
