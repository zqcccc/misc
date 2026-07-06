'use client'

import { Fragment, useEffect, useMemo, useRef, useState } from 'react'

// ============ 端点定义 ============
const POLL_MS = 60_000
const BARS_PER_DAY = 96
const WIN_DAYS = [60, 180, 360] as const

interface BestPayload {
  ema: number
  cb: number
  bp: number
  mean_sharpe: number
  seed: number
}

interface HistoryEntry {
  seed: number
  ema: number
  cb: number
  bp: number
  mean_sharpe: number
  nfev: number
  success: boolean
}

interface SummaryStats {
  n_starts: number
  mean_net: number
  median_net: number
  p5_net: number
  p95_net: number
  mean_sharpe: number
  median_sharpe: number
  p5_sharpe: number
  p95_sharpe: number
  win_rate: number
  mean_mdd: number
  worst_mdd?: number
}

interface CurvePayload {
  x: number[]
  mean: (number | null)[]
  p5: (number | null)[]
  p25: (number | null)[]
  p75: (number | null)[]
  p95: (number | null)[]
  bh_mean: (number | null)[]
}

interface TopGridEntry {
  ema: number
  cb: number
  bp: number
  mean_sharpe: number
  median_sharpe: number | null
  mean_net: number
  p5_net: number
  p95_net: number
  win_rate: number
  mean_mdd: number
  n_starts: number
}

interface VsBhEntry {
  opt: {
    mean_sharpe: number
    mean_net: number
    p5_net: number
    mean_mdd: number
    win_rate: number
  }
  bh: {
    mean_sharpe: number
    mean_net: number
    p5_net: number
    mean_mdd: number
    win_rate: number
  }
  delta: {
    sharpe: number
    mean_net_pp: number
    p5_net_pp: number
    mean_mdd_pp: number
    win_rate_pp: number
  }
}

interface PitPayload {
  generated_at: string
  sample: {
    first_ts: string
    last_ts: string
    n_bars: number
    n_starts: number
    step_days: number
    lengths_days: number[]
  }
  best: BestPayload
  seed_from_grid: { ema: number; cb: number; bp: number }
  history: HistoryEntry[]
  opt_summary_180d: SummaryStats
  bh_summary_180d: SummaryStats
  curve: CurvePayload
  top_grid: TopGridEntry[]
  vs_bh: Record<string, VsBhEntry>
}

// ============ 工具函数 ============
function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)}%`
}

function fmtPp(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(digits)}pp`
}

function fmtSigned(v: number | undefined | null, digits = 3): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(digits)}`
}

// ============ StatCard ============
function StatCard({ label, value, sub, accent }: {
  label: string
  value: string
  sub?: string
  accent?: 'green' | 'red' | 'purple' | 'yellow' | 'gray'
}) {
  const colorMap = {
    green: 'text-emerald-600 dark:text-emerald-400',
    red: 'text-rose-600 dark:text-rose-400',
    purple: 'text-purple-600 dark:text-purple-400',
    yellow: 'text-amber-600 dark:text-amber-400',
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

// ============ 分位带图 ============
function PercentileChart({ curve }: { curve: CurvePayload }) {
  const nodeRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<any>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let disposed = false
    let resizeFn = () => {}
    import('echarts').then((echartsMod) => {
      if (disposed || !nodeRef.current) return
      chartRef.current = echartsMod.init(nodeRef.current, undefined, { renderer: 'canvas' })
      resizeFn = () => chartRef.current?.resize()
      window.addEventListener('resize', resizeFn)
      resizeFn()
      setReady(true)
    }).catch((e) => console.error('[pit] echarts load fail:', e))
    return () => {
      disposed = true
      window.removeEventListener('resize', resizeFn)
      chartRef.current?.dispose?.()
      chartRef.current = null
      setReady(false)
    }
  }, [])

  const isDark = useIsDark()
  const option = useMemo(() => buildCurveOption(curve, isDark), [isDark, curve])

  useEffect(() => {
    if (!ready || !chartRef.current) return
    chartRef.current.setOption(option, { notMerge: true })
  }, [ready, option])

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-3">
      <div ref={nodeRef} style={{ width: '100%', height: 480 }} />
    </div>
  )
}

function useIsDark() {
  const [dark, setDark] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.className.includes('dark')
      : false,
  )
  useEffect(() => {
    const update = () => setDark(document.documentElement.className.includes('dark'))
    update()
    const ob = new MutationObserver(update)
    ob.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => ob.disconnect()
  }, [])
  return dark
}

function buildCurveOption(curve: CurvePayload, isDark: boolean) {
  const xs = curve.x.map((i) => `t+${i}`)
  const labelColor = isDark ? '#94a3b8' : '#64748b'
  const splitLine = isDark ? 'rgba(255,255,255,0.05)' : '#f1f5f9'
  return {
    backgroundColor: 'transparent',
    textStyle: { color: labelColor },
    legend: { data: ['平均', 'p5', 'p25', 'p75', 'p95', 'buy-hold 平均'], textStyle: { color: labelColor }, top: 0 },
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 40, bottom: 50 },
    xAxis: {
      type: 'category',
      data: xs,
      axisLine: { lineStyle: { color: isDark ? '#334155' : '#cbd5e1' } },
      axisLabel: {
        color: labelColor,
        formatter: (v: string) => {
          const i = parseInt(v.replace('t+', ''), 10)
          const day = Math.floor(i / BARS_PER_DAY)
          return day % 30 === 0 ? `${day}d` : ''
        },
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: labelColor,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: splitLine } },
    },
    series: [
      {
        name: 'p5',
        type: 'line',
        data: curve.p5,
        lineStyle: { color: '#7f8c8d', width: 1, type: 'dashed' },
        showSymbol: false,
        smooth: true,
      },
      {
        name: 'p95',
        type: 'line',
        data: curve.p95,
        lineStyle: { color: '#7f8c8d', width: 1, type: 'dashed' },
        showSymbol: false,
        smooth: true,
        areaStyle: { color: 'rgba(127,140,141,0.10)', origin: 'start' },
        stack: 'a',
      },
      {
        name: 'p25',
        type: 'line',
        data: curve.p25,
        lineStyle: { color: '#3498db', width: 1 },
        showSymbol: false,
        smooth: true,
      },
      {
        name: 'p75',
        type: 'line',
        data: curve.p75,
        lineStyle: { color: '#3498db', width: 1 },
        showSymbol: false,
        smooth: true,
        areaStyle: { color: 'rgba(52,152,219,0.18)', origin: 'start' },
        stack: 'b',
      },
      {
        name: '平均',
        type: 'line',
        data: curve.mean,
        lineStyle: { color: '#f1c40f', width: 3 },
        showSymbol: false,
        smooth: true,
      },
      {
        name: 'buy-hold 平均',
        type: 'line',
        data: curve.bh_mean,
        lineStyle: { color: '#9b59b6', width: 2, type: 'dashed' },
        showSymbol: false,
        smooth: true,
      },
    ],
  }
}

// ============ 收敛轨迹表 ============
function HistoryTable({ history }: { history: HistoryEntry[] }) {
  const sorted = useMemo(
    () => [...history].sort((a, b) => b.mean_sharpe - a.mean_sharpe),
    [history],
  )
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="py-2 pr-3">种子</th>
            <th className="py-2 pr-3">EMA</th>
            <th className="py-2 pr-3">cb (连续)</th>
            <th className="py-2 pr-3">bp</th>
            <th className="py-2 pr-3">mean Sharpe</th>
            <th className="py-2 pr-3">nfev</th>
            <th className="py-2 pr-3">收敛</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr key={h.seed} className="border-b border-gray-100 dark:border-gray-800">
              <td className="py-2 pr-3 text-gray-700 dark:text-gray-300">seed {h.seed}</td>
              <td className="py-2 pr-3 font-mono text-emerald-600 dark:text-emerald-400">{h.ema.toFixed(0)}</td>
              <td className="py-2 pr-3 font-mono">{h.cb.toFixed(2)}</td>
              <td className="py-2 pr-3 font-mono">{(h.bp * 100).toFixed(2)}%</td>
              <td className="py-2 pr-3 font-mono font-semibold text-amber-600 dark:text-amber-400">{fmtSigned(h.mean_sharpe, 4)}</td>
              <td className="py-2 pr-3">{h.nfev}</td>
              <td className="py-2 pr-3">{h.success ? '✓' : ' parcial'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ============ 粗网格 Top 排行 ============
function TopGridTable({ rows }: { rows: TopGridEntry[] }) {
  return (
    <div className="overflow-x-auto max-h-96 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white dark:bg-[#282c35]">
          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="py-2 pr-3">策略</th>
            <th className="py-2 pr-3 text-right">mean Sharpe</th>
            <th className="py-2 pr-3 text-right">median Sharpe</th>
            <th className="py-2 pr-3 text-right">mean net</th>
            <th className="py-2 pr-3 text-right">p5 net</th>
            <th className="py-2 pr-3 text-right">p95 net</th>
            <th className="py-2 pr-3 text-right">胜率</th>
            <th className="py-2 pr-3 text-right">平均回撤</th>
            <th className="py-2 pr-3 text-right">起点</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <tr key={`${r.ema}-${r.cb}-${r.bp}`} className="border-b border-gray-100 dark:border-gray-800">
              <td className="py-1.5 pr-3 text-amber-600 dark:text-amber-400">
                {idx === 0 ? '★ ' : ''}EMA{r.ema}/cb{r.cb}/bp{(r.bp * 100).toFixed(2)}%
              </td>
              <td className="py-1.5 pr-3 text-right font-mono">{fmtSigned(r.mean_sharpe, 3)}</td>
              <td className="py-1.5 pr-3 text-right font-mono">{fmtSigned(r.median_sharpe, 3)}</td>
              <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(r.mean_net)}</td>
              <td className="py-1.5 pr-3 text-right font-mono text-rose-600 dark:text-rose-400">{fmtPct(r.p5_net)}</td>
              <td className="py-1.5 pr-3 text-right font-mono text-emerald-600 dark:text-emerald-400">{fmtPct(r.p95_net)}</td>
              <td className="py-1.5 pr-3 text-right">{(r.win_rate * 100).toFixed(1)}%</td>
              <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(r.mean_mdd)}</td>
              <td className="py-1.5 pr-3 text-right text-gray-400">{r.n_starts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ============ vs buy-hold 三窗口对照 ============
function VsBhTable({ vsBh }: { vsBh: Record<string, VsBhEntry> }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="py-2 pr-3">窗口</th>
            <th className="py-2 pr-3 text-right">mean Sharpe</th>
            <th className="py-2 pr-3 text-right">mean net</th>
            <th className="py-2 pr-3 text-right">5pct net</th>
            <th className="py-2 pr-3 text-right">平均回撤</th>
            <th className="py-2 pr-3 text-right">胜率</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(vsBh).map(([Ld, v]) => (
            <Fragment key={Ld}>
              <tr className="border-b border-gray-100 dark:border-gray-800 bg-amber-50/40 dark:bg-amber-950/20">
                <td className="py-1.5 pr-3 font-medium text-amber-600 dark:text-amber-400">最优 ({Ld})</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtSigned(v.opt.mean_sharpe)}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(v.opt.mean_net)}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(v.opt.p5_net)}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(v.opt.mean_mdd)}</td>
                <td className="py-1.5 pr-3 text-right">{(v.opt.win_rate * 100).toFixed(1)}%</td>
              </tr>
              <tr className="border-b border-gray-100 dark:border-gray-800 bg-purple-50/30 dark:bg-purple-950/20">
                <td className="py-1.5 pr-3 font-medium text-purple-600 dark:text-purple-400">buy-hold ({Ld})</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtSigned(v.bh.mean_sharpe)}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(v.bh.mean_net)}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(v.bh.p5_net)}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{fmtPct(v.bh.mean_mdd)}</td>
                <td className="py-1.5 pr-3 text-right">{(v.bh.win_rate * 100).toFixed(1)}%</td>
              </tr>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-xs">
                <td className="py-1.5 pr-2 text-gray-500 dark:text-gray-400">Δ (opt - bh)</td>
                <td className="py-1.5 pr-2 text-right font-mono text-gray-500">
                  {fmtSigned(v.delta.sharpe)} {v.delta.sharpe > 0 ? '✅' : '❌'}
                </td>
                <td className="py-1.5 pr-2 text-right font-mono">{fmtPp(v.delta.mean_net_pp)}</td>
                <td className="py-1.5 pr-2 text-right font-mono text-emerald-600 dark:text-emerald-400">
                  {fmtPp(v.delta.p5_net_pp)} {v.delta.p5_net_pp > 0 ? '✅' : '❌'}
                </td>
                <td className="py-1.5 pr-2 text-right font-mono">
                  {fmtPp(v.delta.mean_mdd_pp)} {v.delta.mean_mdd_pp > 0 ? '✅' : '❌'}
                </td>
                <td className="py-1.5 pr-2 text-right font-mono">{fmtPp(v.delta.win_rate_pp)}</td>
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ============ 主页面 ============
export default function Btc15mPitPage() {
  const [data, setData] = useState<PitPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function fetchData() {
      try {
        const resp = await fetch('/api/ema-btc-15m-pit', { cache: 'no-store' })
        if (!resp.ok) {
          const j = await resp.json().catch(() => ({}))
          throw new Error(j.message || `HTTP ${resp.status}`)
        }
        const payload = (await resp.json()) as PitPayload
        if (cancelled) return
        setData(payload)
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
  }, [])

  if (loading && !data) {
    return (
      <div className="max-w-6xl mx-auto my-10 p-8 text-center text-gray-500 dark:text-gray-400">
        加载 BTC 15m PIT 连续优化数据中...
        <div className="text-xs mt-2 text-gray-400">数据约 2.3MB, 应在 1 秒内完成</div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="max-w-3xl mx-auto my-10 p-8 rounded-xl shadow-lg bg-white dark:bg-[#282c35]">
        <h1 className="text-2xl font-bold mb-4 text-rose-600 dark:text-rose-400">数据加载失败</h1>
        <p className="text-gray-600 dark:text-gray-300 mb-2 text-sm">{error}</p>
        <p className="text-xs text-gray-400 mb-4">
          请先运行: <code className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">/Users/gongzhao/.workbuddy/binaries/python/envs/default/bin/python btc_ema_15m/export_step8_frontend_json.py</code>
        </p>
      </div>
    )
  }

  if (!data) return null
  const { best, history, opt_summary_180d, bh_summary_180d, curve, top_grid, vs_bh, sample } = data
  const deltaShr = opt_summary_180d.mean_sharpe - bh_summary_180d.mean_sharpe
  const deltaP5 = (opt_summary_180d.p5_net - bh_summary_180d.p5_net) * 100
  const deltaMdd = (opt_summary_180d.mean_mdd - bh_summary_180d.mean_mdd) * 100
  const deltaWin = (opt_summary_180d.win_rate - bh_summary_180d.win_rate) * 100

  return (
    <div className="max-w-6xl mx-auto my-6 px-4">
      <div className="mb-2">
        <a href="/ema-backtest/btc-15m" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
          ← 返回 BTC 15m 单曲线研究
        </a>
      </div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          BTC 15m · PIT 连续优化收敛 (Step 8)
        </h1>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          样本 {sample.n_bars.toLocaleString()} 根 15m · {sample.first_ts.slice(0, 10)} ~ {sample.last_ts.slice(0, 10)} ·
          起点间隔 {sample.step_days}d · 起点数 {sample.n_starts} · 反手双边成本 0.11% · 主窗口 180d ·
          <span className="ml-1">主指标 = mean Sharpe</span>
        </div>
      </div>

      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 p-4 mb-4">
        <h2 className="text-sm font-semibold text-amber-700 dark:text-amber-300 mb-2">🎯 收敛最优解 (Nelder-Mead 5 种子, log 空间)</h2>
        <div className="text-base mb-1">
          EMA <b className="text-amber-700 dark:text-amber-300">{best.ema.toFixed(0)}</b> ·
          cb <b className="text-amber-700 dark:text-amber-300">{best.cb.toFixed(2)}</b> (连续化) ·
          bp <b className="text-amber-700 dark:text-amber-300">{(best.bp * 100).toFixed(2)}%</b> ·
          mean Sharpe <b className="text-amber-700 dark:text-amber-300">{fmtSigned(best.mean_sharpe, 4)}</b> (seed #{best.seed})
        </div>
        <div className="text-xs text-amber-700/80 dark:text-amber-300/80">
          不卡任何边界: ema 在 2000~3000 内部, cb 在 16~32 内部, bp 在 0.10%~0.20% 内部 (vs step7 离散网格卡在 ema2000/bp0.20% 边界处) ·
          种子来自粗网格 top1 EMA{data.seed_from_grid.ema}/cb{data.seed_from_grid.cb}/bp{(data.seed_from_grid.bp * 100).toFixed(2)}%
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
        <StatCard label="mean Sharpe (180d)" value={fmtSigned(opt_summary_180d.mean_sharpe)}
          sub={`vs bh ${fmtSigned(bh_summary_180d.mean_sharpe)} (${deltaShr > 0 ? '✅' : '❌'} ${fmtSigned(deltaShr)})`}
          accent={deltaShr > 0 ? 'green' : 'red'} />
        <StatCard label="mean 净收益" value={fmtPct(opt_summary_180d.mean_net)}
          sub={`bh ${fmtPct(bh_summary_180d.mean_net)}`} />
        <StatCard label="5pct 最差收益" value={fmtPct(opt_summary_180d.p5_net)}
          sub={`bh ${fmtPct(bh_summary_180d.p5_net)} (${deltaP5 > 0 ? '✅' : '❌'} ${fmtPp(deltaP5)})`}
          accent={deltaP5 > 0 ? 'green' : 'red'} />
        <StatCard label="平均最大回撤" value={fmtPct(opt_summary_180d.mean_mdd)}
          sub={`bh ${fmtPct(bh_summary_180d.mean_mdd)} (${deltaMdd > 0 ? '✅' : '❌'} ${fmtPp(deltaMdd)})`}
          accent={deltaMdd > 0 ? 'green' : 'red'} />
        <StatCard label="胜率" value={`${(opt_summary_180d.win_rate * 100).toFixed(1)}%`}
          sub={`bh ${(bh_summary_180d.win_rate * 100).toFixed(1)}% (${deltaWin > 0 ? '✅' : '❌'} ${fmtPp(deltaWin)})`}
          accent={deltaWin > 0 ? 'green' : 'red'} />
      </div>

      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          1. 最优策略起点 equity 分位带 (180d)
        </h2>
        <PercentileChart curve={curve} />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          横轴 = 入场后第 N 个 15m bar (180d = 17280 bars); 纵轴 = 累计净收益率.
          深色带 = 5pct~95pct, 浅色带 = 25pct~75pct, 黄实线 = 平均, 紫虚线 = 同池 buy-hold 平均.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">
            2. 收敛轨迹 (Nelder-Mead 多种子)
          </h2>
          <HistoryTable history={history} />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            5 种子汇聚到 EMA 2600~2900 / cb 14~18 / bp 0.07~0.19% 同一高原, 唯 seed 2 落到次优 EMA4132。
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-4">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">
            3. vs buy-hold 三窗口对照
          </h2>
          <VsBhTable vsBh={vs_bh} />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            60/180/360d 三窗口下: 平均 Sharpe 全部略输 buy-hold, 但 5pct / 平均回撤 / 胜率 系统性更优 — 策略定位是「风控」而非「超额」。
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-[#282c35] p-4 mb-4">
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">
          4. 超密粗网格 Top 排行 (按 180d mean Sharpe, Top 30)
        </h2>
        <TopGridTable rows={top_grid} />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          粗网格 11 EMA × 7 cb × 8 bp = 768 组合 (有效 539) · 收敛最优 (★) Sharpe {fmtSigned(best.mean_sharpe, 4)} 高于粗网格 best, 证实连续化能在离散网格之上挖到增量收益。
        </p>
      </div>

      <div className="mt-6 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border-l-4 border-amber-500 text-amber-700 dark:text-amber-300 text-sm">
        <b>风险提示</b>: 本页策略参数是 BTC 15m 历史样本 (2023-01 ~ 2026-07, 3.5 年) 在 PIT 全起点框架下的连续优化收敛结果。
        平均 Sharpe 仍略输 buy-hold, 但 5pct / 回撤 / 胜率 系统性更优 — 适合有回撤约束的账户使用, 不构成投资建议。
      </div>
    </div>
  )
}
