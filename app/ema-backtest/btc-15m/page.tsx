'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { buildChartOption } from '../chart-options'
import type { InstrumentPayload, OverviewPayload } from '../types'

const POLL_MS = 60_000
// 触发 dev server HMR 重编

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

function ConfigTabs({ instruments, active, onSelect }: {
  instruments: InstrumentPayload[]
  active: string
  onSelect: (name: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {instruments.map((inst) => {
        const isActive = inst.name === active
        const nr = inst.stats.strategy_return ?? 0
        const accent = nr > 0.001 ? 'text-emerald-600 dark:text-emerald-400'
          : nr < -0.001 ? 'text-rose-600 dark:text-rose-400'
          : 'text-gray-500 dark:text-gray-400'
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
            <span>{inst.name}</span>
            <span className={`ml-1.5 text-xs ${isActive ? 'text-blue-100' : accent}`}>
              {nr >= 0 ? '+' : ''}{(nr * 100).toFixed(1)}%
            </span>
          </button>
        )
      })}
    </div>
  )
}

function TradeTable({ inst }: { inst: InstrumentPayload }) {
  const trades = inst.trades
  if (trades.length === 0) return null
  const reversed = [...trades].reverse()
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-4">
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
        交易明细 ({trades.length})
      </div>
      <div className="overflow-x-auto max-h-80 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-white dark:bg-[#282c35]">
            <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
              <th className="py-1.5 pr-3">时间</th>
              <th className="py-1.5 pr-3">类型</th>
              <th className="py-1.5 pr-3">价格</th>
              <th className="py-1.5 pr-3">方向变化</th>
              <th className="py-1.5 pr-3">净收益</th>
            </tr>
          </thead>
          <tbody>
            {reversed.map((t, i) => {
              const typeLabel = t.reason === 'open' ? '开仓' : t.reason === 'reversal' ? '反手' : '平仓'
              const typeColor = t.reason === 'open' ? 'text-gray-500'
                : t.reason === 'reversal' ? 'text-purple-600 dark:text-purple-400'
                : 'text-gray-500'
              const dirStr = (d: number) => d === 1 ? '多' : d === -1 ? '空' : '空'
              return (
                <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">
                    {t.t.slice(0, 19).replace('T', ' ')}
                  </td>
                  <td className={`py-1.5 pr-3 font-medium ${typeColor}`}>{typeLabel}</td>
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">
                    {t.price.toFixed(1)}
                  </td>
                  <td className="py-1.5 pr-3 text-gray-700 dark:text-gray-300">
                    {dirStr(t.old_dir)} → {dirStr(t.new_dir)}
                  </td>
                  <td className={`py-1.5 pr-3 font-medium ${(t.net ?? 0) > 0 ? 'text-emerald-600 dark:text-emerald-400' : (t.net ?? 0) < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-gray-500'}`}>
                    {t.reason === 'open' ? '-' : fmtPct(t.net)}
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
  const chartNode = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<any>(null)
  const [chartReady, setChartReady] = useState(false)

  useEffect(() => {
    let disposed = false
    let resizeFn = () => {}
    // dynamic import 避免 SSR 时 echarts 访问 window
    import('echarts').then((echartsMod) => {
      if (disposed || !chartNode.current) return
      chartRef.current = echartsMod.init(chartNode.current, undefined, { renderer: 'canvas' })
      resizeFn = () => chartRef.current?.resize()
      window.addEventListener('resize', resizeFn)
      resizeFn()
      setChartReady(true)
    }).catch((e) => console.error('[btc-15m] echarts load fail:', e))
    return () => {
      disposed = true
      window.removeEventListener('resize', resizeFn)
      chartRef.current?.dispose?.()
      chartRef.current = null
      setChartReady(false)
    }
  }, [])

  useEffect(() => {
    if (!chartReady || !chartRef.current) return
    // forward 字段在我们 payload 里没有, 给个空对象让 chart-options 不报错
    const instSafe = { ...inst, forward: { events: [], equity_curve: [], current_equity: 1, total_return: 0, realized_capital: 1, init_ts: null } } as InstrumentPayload
    const option = buildChartOption(instSafe)
    chartRef.current.setOption(option, { notMerge: true })
  }, [chartReady, inst])

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3">
      <div ref={chartNode} style={{ width: '100%', height: 640 }} />
    </div>
  )
}

export default function Btc15mResearchPage() {
  const [data, setData] = useState<OverviewPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeName, setActiveName] = useState<string>('')

  useEffect(() => {
    let cancelled = false
    async function fetchData() {
      try {
        const resp = await fetch('/api/ema-btc-15m', { cache: 'no-store' })
        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}))
          throw new Error(j.message || `HTTP ${resp.status}`)
        }
        const payload = (await resp.json()) as OverviewPayload
        if (cancelled) return
        setData(payload)
        if (!activeName && payload.instruments.length > 0) {
          setActiveName(payload.instruments[0].name)
        }
        setLoading(false)
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'fetch failed')
        setLoading(false)
      }
    }
    fetchData()
    const t = setInterval(fetchData, POLL_MS)
    return () => { cancelled = true; clearInterval(t) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const instruments = data?.instruments ?? []
  const activeInst = useMemo(
    () => instruments.find((i) => i.name === activeName) ?? instruments[0],
    [instruments, activeName],
  )

  if (loading && !data) {
    return (
      <div className="max-w-6xl mx-auto my-10 p-8 text-center text-gray-500 dark:text-gray-400">
        加载 BTC 15m 研究数据中...
        <div className="text-xs mt-2 text-gray-400">数据约 4MB, 应在 1 秒内完成</div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="max-w-3xl mx-auto my-10 p-8 rounded-xl shadow-lg bg-white dark:bg-[#282c35]">
        <h1 className="text-2xl font-bold mb-4 text-rose-600 dark:text-rose-400">数据加载失败</h1>
        <p className="text-gray-600 dark:text-gray-300 mb-2 text-sm">{error}</p>
        <p className="text-xs text-gray-400 mb-4">
          请先运行: <code className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">/Users/gongzhao/.workbuddy/binaries/python/envs/default/bin/python btc_ema_15m/export_research_json.py</code>
        </p>
      </div>
    )
  }

  if (!data || !activeInst) return null

  const s = activeInst.stats
  const bh = s.hold_return

  return (
    <div className="max-w-6xl mx-auto my-6 px-4">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          BTC 15m · EMA 反手策略多配置研究 (2023-01 ~ 2026-07)
        </h1>
        <a href="/ema-backtest/btc-15m/pit"
          className="px-2.5 py-1 text-xs font-medium rounded-md bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-900/60 border border-amber-300 dark:border-amber-700">
          🎯 PIT 连续优化收敛 (step8) →
        </a>
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-4">
        样本 123,032 根 15m · 反手双边成本 0.11% · 降采样到 1h 显示 · 每 60s 自动刷新
      </div>

      <div className="mb-4">
        <ConfigTabs instruments={instruments} active={activeName} onSelect={setActiveName} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
        <StatCard label="策略收益" value={fmtPct(s.strategy_return)}
          sub={`${s.bars.toLocaleString()} 根 K线`}
          accent={s.strategy_return >= 0 ? 'green' : 'red'} />
        <StatCard label="买入持有" value={fmtPct(bh)} accent={bh >= 0 ? 'green' : 'red'} />
        <StatCard label="最大回撤" value={fmtPct(s.max_drawdown)} accent="red" />
        <StatCard label="反手 / 止盈 / 胜率"
          value={`${s.reversals} / ${s.tps}`}
          sub={`胜率 ${(s.win_rate * 100).toFixed(1)}%`} />
        <StatCard label="样本时间"
          value={s.first_ts.slice(0, 10)}
          sub={`${s.last_ts.slice(0, 10)} (${(new Date(s.last_ts).getTime() - new Date(s.first_ts).getTime()) / (365*24*3600*1000)}年)`}
          accent="gray" />
      </div>

      <div className="mb-4">
        <ChartArea inst={activeInst} />
      </div>

      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3 mb-4 text-xs text-gray-600 dark:text-gray-400">
        <span className="font-medium text-gray-800 dark:text-gray-200">策略配置: </span>
        EMA{activeInst.config.ema_span} + {activeInst.config.confirm_bars}根确认
        + {(activeInst.config.breakout_pct * 100).toFixed(1)}%幅度
        {activeInst.config.tp_enabled
          ? ` · A5 长上影止盈 ${(activeInst.config.part_ratio * 100).toFixed(0)}% 冷却${activeInst.config.cool_bars}根`
          : ' · 纯反手 (不止盈)'}
        <span className="ml-2 text-gray-400">| 对齐系数 {(activeInst.config.confirm_bars / activeInst.config.ema_span).toFixed(3)}</span>
      </div>

      <TradeTable inst={activeInst} />

      <div className="mt-6 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border-l-4 border-amber-500 text-amber-700 dark:text-amber-300 text-sm">
        <b>风险提示</b>: 全样本最优 ≠ 真实可达. 长牛行情参数带强样本偏差,
        walk-forward 实测 EMA100/cb64/bp1.2% 真实可达仅 +17.75% (vs 全样本 +488%, 偏差 -470pp).
        仅供方法论研究, 不构成投资建议.
      </div>
    </div>
  )
}
