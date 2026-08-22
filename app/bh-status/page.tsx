'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

/**
 * B&H Enhancement 看盘: 各标的在 ADAPTIVE v38 策略下的当前状态.
 *
 * 数据源: /api/bh-status (读 deliverables/bh_enhancement/bh_status.json)
 * 刷新:   /api/bh-status?refresh=1 触发 Python 重算 (~5s)
 */

type AssetStatus = {
  label: string
  ticker: string
  group: 'crypto' | 'us_eq' | 'us_lev'
  last_date: string
  last_close: number
  daily_ret_pct: number
  current_lev: number
  selected_sub: string
  bh_cagr_pct: number
  adapt_cagr_pct: number
  alpha_pp: number
  bh_nav: number
  adapt_nav: number
  cum_excess_pct: number
  recent_levs: number[]
  recent_op: 'add' | 'reduce' | 'hold'
  last_op_date: string | null
  last_op_from: number | null
  last_op_to: number | null
  days_since_op: number | null
  days_at_lev: number
  regime: 'high_lev' | 'mid_lev' | 'base_lev'
  backtest_years: number
}

type Summary = {
  generated_at: string
  total: number
  wins: number
  losses: number
  win_rate_pct: number
  mean_alpha_pp: number
  lev_distribution: Record<string, number>
  op_distribution: Record<string, number>
  regime_distribution: Record<string, number>
}

type Payload = { summary: Summary; results: AssetStatus[] }

const REFRESH_MS = 60_000

// 资产分组元数据
const GROUP_META: Record<
  string,
  { name: string; color: string; desc: string }
> = {
  crypto: {
    name: 'Crypto',
    color: '#f59e0b',
    desc: '7×24 永续 · funding 8% · 固定 SAL_PLUS',
  },
  us_eq: {
    name: 'US Equity',
    color: '#3b82f6',
    desc: '美股个股 · 7 子策略 warmup 选 · lev_cost 5%',
  },
  us_lev: {
    name: 'US Lev ETF',
    color: '#ef4444',
    desc: '3x 杠杆 ETF · 固定 VTL_F1 · 波动率靶向',
  },
}

// regime 配色 (语义色, 非涨跌)
const REGIME_META: Record<
  string,
  { label: string; color: string; bg: string }
> = {
  high_lev: {
    label: '高杠杆进攻',
    color: '#065f46',
    bg: '#ecfdf5',
  },
  mid_lev: {
    label: '中等杠杆',
    color: '#92400e',
    bg: '#fffbeb',
  },
  base_lev: {
    label: '基础仓位',
    color: '#1e40af',
    bg: '#eff6ff',
  },
}

// 操作语义
const OP_META: Record<
  string,
  { label: string; arrow: string; color: string }
> = {
  add: { label: '加仓', arrow: '▲', color: '#dc2626' },
  reduce: { label: '减仓', arrow: '▼', color: '#059669' },
  hold: { label: '持有', arrow: '—', color: '#6b7280' },
}

function fmtNum(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  return v.toFixed(digits)
}

function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(digits)}%`
}

function fmtSignedPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(digits)}pp`
}

function clsForNum(v: number): string {
  if (v > 0.01) return 'text-emerald-600 font-semibold'
  if (v < -0.01) return 'text-red-600 font-semibold'
  return 'text-slate-500'
}

// lev 颜色: 1.0x 蓝, 1.5x 黄, 2.0x+ 绿(进攻)
function levColor(lev: number): string {
  if (lev >= 2.0) return '#059669' // 高杠杆 - 绿(进攻)
  if (lev >= 1.4) return '#d97706' // 中杠杆 - 黄
  return '#1e40af' // 基础 - 蓝
}

function levBg(lev: number): string {
  if (lev >= 2.0) return '#ecfdf5'
  if (lev >= 1.4) return '#fffbeb'
  return '#eff6ff'
}

// mini lev sparkline (最近 10 天)
function LevSparkline({ levs }: { levs: number[] }) {
  if (!levs || levs.length === 0) return <span className="text-slate-400">—</span>
  const max = Math.max(...levs, 2.5)
  const min = Math.min(...levs, 0.5)
  const range = max - min || 1
  const w = 80
  const h = 22
  const pts = levs
    .map((lv, i) => {
      const x = (i / (levs.length - 1 || 1)) * (w - 4) + 2
      const y = h - 2 - ((lv - min) / range) * (h - 4)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const last = levs[levs.length - 1]
  return (
    <div className="inline-flex items-center gap-1">
      <svg width={w} height={h} className="align-middle">
        <polyline
          points={pts}
          fill="none"
          stroke={levColor(last)}
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle
          cx={(w - 4) + 2}
          cy={h - 2 - ((last - min) / range) * (h - 4)}
          r="2"
          fill={levColor(last)}
        />
      </svg>
    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub?: string
  tone?: 'pos' | 'neg' | 'plain'
}) {
  const valueCls =
    tone === 'pos'
      ? 'text-emerald-600'
      : tone === 'neg'
        ? 'text-red-600'
        : 'text-slate-800'
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 flex flex-col gap-0.5 hover:bg-slate-100 transition">
      <div className="text-[10.5px] font-medium text-slate-500 uppercase tracking-wider">
        {label}
      </div>
      <div
        className={`text-[18px] font-semibold tracking-tight tabular-nums leading-tight ${valueCls}`}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[11px] text-slate-500 tabular-nums">{sub}</div>
      )}
    </div>
  )
}

function LevBadge({ lev }: { lev: number }) {
  const color = levColor(lev)
  const bg = levBg(lev)
  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[13px] font-bold tabular-nums"
      style={{ color, background: bg, border: `1px solid ${color}33` }}
    >
      {lev.toFixed(2)}x
    </span>
  )
}

function GroupBadge({ group }: { group: string }) {
  const meta = GROUP_META[group] || { name: group, color: '#6b7280' }
  return (
    <span
      className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider"
      style={{
        color: meta.color,
        background: `${meta.color}1a`,
        border: `1px solid ${meta.color}33`,
      }}
    >
      {meta.name}
    </span>
  )
}

function RegimeBadge({ regime }: { regime: string }) {
  const meta = REGIME_META[regime] || {
    label: regime,
    color: '#6b7280',
    bg: '#f3f4f6',
  }
  return (
    <span
      className="inline-block px-2 py-0.5 rounded text-[11px] font-medium"
      style={{ color: meta.color, background: meta.bg }}
    >
      {meta.label}
    </span>
  )
}

function OpBadge({ op }: { op: string }) {
  const meta = OP_META[op] || OP_META.hold
  return (
    <span
      className="inline-flex items-center gap-0.5 text-[12px] font-semibold"
      style={{ color: meta.color }}
    >
      <span>{meta.arrow}</span>
      <span>{meta.label}</span>
    </span>
  )
}

type SortKey =
  | 'label'
  | 'group'
  | 'current_lev'
  | 'alpha_pp'
  | 'bh_cagr_pct'
  | 'adapt_cagr_pct'
  | 'daily_ret_pct'
  | 'days_at_lev'
  | 'selected_sub'

export default function BhStatusPage() {
  const [data, setData] = useState<Payload | null>(null)
  const [state, setState] = useState<'idle' | 'loading' | 'refreshing' | 'ready' | 'error'>('idle')
  const [error, setError] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('group')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [groupFilter, setGroupFilter] = useState<'all' | 'crypto' | 'us_eq' | 'us_lev'>('all')
  const [levFilter, setLevFilter] = useState<'all' | 'high' | 'mid' | 'base'>('all')

  const fetchData = useCallback(async (refresh = false) => {
    setState(refresh ? 'refreshing' : 'loading')
    try {
      const url = refresh ? '/api/bh-status?refresh=1' : '/api/bh-status'
      const resp = await fetch(url, { cache: 'no-store' })
      const payload = await resp.json()
      if (!resp.ok) {
        throw new Error(payload?.message || `HTTP ${resp.status}`)
      }
      setData(payload as Payload)
      setState('ready')
      setError('')
    } catch (err) {
      setState('error')
      setError(err instanceof Error ? err.message : '数据获取失败')
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // 自动刷新 (只读不触发 Python)
  useEffect(() => {
    if (state !== 'ready') return
    const timer = setInterval(() => fetchData(false), REFRESH_MS)
    return () => clearInterval(timer)
  }, [state, fetchData])

  // 筛选 + 排序
  const rows = useMemo(() => {
    if (!data) return []
    let arr = [...data.results]
    // 分组筛选
    if (groupFilter !== 'all') {
      arr = arr.filter((r) => r.group === groupFilter)
    }
    // lev 筛选
    if (levFilter !== 'all') {
      arr = arr.filter((r) => r.regime === `${levFilter}_lev`)
    }
    // 排序
    const dir = sortDir === 'asc' ? 1 : -1
    arr.sort((a, b) => {
      const va = a[sortKey]
      const vb = b[sortKey]
      if (typeof va === 'number' && typeof vb === 'number') {
        return (va - vb) * dir
      }
      return String(va).localeCompare(String(vb)) * dir
    })
    return arr
  }, [data, sortKey, sortDir, groupFilter, levFilter])

  const onSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      // 数值列首次点击默认降序
      const numeric: SortKey[] = [
        'current_lev',
        'alpha_pp',
        'bh_cagr_pct',
        'adapt_cagr_pct',
        'daily_ret_pct',
        'days_at_lev',
      ]
      setSortDir(numeric.includes(key) ? 'desc' : 'asc')
    }
  }

  const sortArrow = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' ▲' : ' ▼'
  }

  const sm = data?.summary
  const lastPoll = new Date().toLocaleTimeString('zh-CN', { hour12: false })

  if (state === 'loading' && !data) {
    return (
      <div className="my-20 mx-auto max-w-[560px] text-center text-slate-500 text-sm">
        加载策略状态中…
      </div>
    )
  }

  if (state === 'error' && !data) {
    return (
      <div className="my-20 mx-auto max-w-[560px] bg-white border border-slate-200 rounded-lg px-7 py-6 shadow-sm">
        <h1 className="text-lg font-semibold text-red-600 m-0 mb-2">
          数据加载失败
        </h1>
        <p className="text-slate-500 text-[13px] mb-4 leading-relaxed">
          {error}
        </p>
        <button
          onClick={() => fetchData(true)}
          className="px-4 py-2 rounded-lg border border-sky-700 bg-sky-700 text-white text-[13px] font-medium cursor-pointer hover:bg-sky-800 transition"
        >
          重新计算
        </button>
      </div>
    )
  }

  if (!data || !sm) return null

  // 分布统计
  const levDist = sm.lev_distribution || {}
  const opDist = sm.op_distribution || {}
  const regimeDist = sm.regime_distribution || {}
  const highCnt = regimeDist.high_lev || 0
  const midCnt = regimeDist.mid_lev || 0
  const baseCnt = regimeDist.base_lev || 0

  const cols: { key: SortKey; label: string; numeric: boolean }[] = [
    { key: 'label', label: '标的', numeric: false },
    { key: 'group', label: '分组', numeric: false },
    { key: 'current_lev', label: '当前 Lev', numeric: true },
    { key: 'selected_sub', label: '子策略', numeric: false },
    { key: 'daily_ret_pct', label: '当日涨跌', numeric: true },
    { key: 'adapt_cagr_pct', label: 'ADAPT CAGR', numeric: true },
    { key: 'bh_cagr_pct', label: 'BH CAGR', numeric: true },
    { key: 'alpha_pp', label: 'α (pp)', numeric: true },
    { key: 'days_at_lev', label: '维持天数', numeric: true },
  ]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-700 px-6 py-3.5 flex items-center justify-between gap-4 sticky top-0 z-20 backdrop-blur">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-[3px] h-[26px] rounded-sm bg-gradient-to-b from-amber-400 to-emerald-500 shrink-0" />
          <div>
            <h1 className="text-[17px] font-semibold tracking-tight text-slate-100 leading-tight m-0">
              B&H 增强策略看盘 · ADAPTIVE v38 实时状态
            </h1>
            <div className="mt-[3px] text-xs text-slate-400 tabular-nums">
              {sm.generated_at
                ? `数据生成于 ${sm.generated_at}`
                : '尚未生成数据'}
              {` · 自动刷新 ${REFRESH_MS / 1000}s（上次 ${lastPoll}）`}
            </div>
          </div>
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={state === 'refreshing'}
          className="inline-flex items-center gap-1.5 px-3.5 py-[7px] rounded-lg border border-slate-400/25 bg-slate-400/10 text-slate-200 text-[13px] font-medium cursor-pointer hover:bg-slate-400/16 hover:border-slate-400/40 active:translate-y-px disabled:opacity-50 disabled:cursor-wait transition"
        >
          {state === 'refreshing' ? (
            <>
              <svg
                className="animate-spin"
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
              </svg>
              重新计算中…
            </>
          ) : (
            <>
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
                <path d="M21 3v5h-5" />
              </svg>
              重新计算
            </>
          )}
        </button>
      </header>

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 py-5 flex flex-col gap-4">
        {/* 总览卡片 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
          <StatCard
            label="胜率"
            value={`${sm.wins}/${sm.total}`}
            sub={`${sm.win_rate_pct.toFixed(0)}% 跑赢 B&H`}
            tone={sm.win_rate_pct >= 70 ? 'pos' : 'neg'}
          />
          <StatCard
            label="平均 Alpha"
            value={`${sm.mean_alpha_pp >= 0 ? '+' : ''}${sm.mean_alpha_pp.toFixed(2)}pp`}
            sub="ADAPT - BH (CAGR)"
            tone={sm.mean_alpha_pp >= 0 ? 'pos' : 'neg'}
          />
          <StatCard
            label="高杠杆 (≥2x)"
            value={String(highCnt)}
            sub={`${midCnt} 中杠杆 · ${baseCnt} 基础仓位`}
            tone="plain"
          />
          <StatCard
            label="最近操作"
            value={`${opDist.add || 0}加/${opDist.reduce || 0}减`}
            sub={`${opDist.hold || 0} 从未调仓`}
            tone="plain"
          />
          <StatCard
            label="2.0x 仓位"
            value={String(levDist['2.0x'] || 0)}
            sub="高 Sharpe 趋势标的"
            tone="plain"
          />
          <StatCard
            label="1.0x 仓位"
            value={String(levDist['1.0x'] || 0)}
            sub="基础仓位 / 防御中"
            tone="plain"
          />
        </div>

        {/* 筛选条 */}
        <div className="bg-white border border-slate-200 rounded-lg px-3 py-2 flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-slate-500 uppercase tracking-wider mr-1">
              分组:
            </span>
            {(['all', 'crypto', 'us_eq', 'us_lev'] as const).map((g) => (
              <button
                key={g}
                onClick={() => setGroupFilter(g)}
                className={`px-2 py-[3px] rounded text-[11.5px] font-medium border transition cursor-pointer ${
                  groupFilter === g
                    ? 'bg-sky-700 text-white border-transparent'
                    : 'bg-transparent text-slate-600 border-slate-300 hover:bg-slate-100'
                }`}
              >
                {g === 'all' ? '全部' : GROUP_META[g].name}
              </button>
            ))}
          </div>
          <div className="w-px h-4 bg-slate-200" />
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-slate-500 uppercase tracking-wider mr-1">
              杠杆:
            </span>
            {(
              [
                ['all', '全部'],
                ['high', '高(≥2x)'],
                ['mid', '中(1.4-2x)'],
                ['base', '基础(1x)'],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setLevFilter(k)}
                className={`px-2 py-[3px] rounded text-[11.5px] font-medium border transition cursor-pointer ${
                  levFilter === k
                    ? 'bg-sky-700 text-white border-transparent'
                    : 'bg-transparent text-slate-600 border-slate-300 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="ml-auto text-[11px] text-slate-500 tabular-nums">
            显示 {rows.length}/{sm.total} 个标的
          </div>
        </div>

        {/* 主表格 */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-[12.5px]">
              <thead>
                <tr>
                  {cols.map((c, idx) => (
                    <th
                      key={c.key}
                      onClick={() => onSort(c.key)}
                      className={`sticky top-0 z-[3] bg-slate-100 text-slate-600 font-medium uppercase text-[10.5px] tracking-wider px-3 py-2.5 border-b border-slate-300 whitespace-nowrap cursor-pointer select-none hover:text-slate-900 transition ${
                        idx < 2 ? 'text-left' : 'text-right'
                      }`}
                      title="点击排序"
                    >
                      {c.label}
                      {sortArrow(c.key)}
                    </th>
                  ))}
                  <th className="sticky top-0 z-[3] bg-slate-100 text-slate-600 font-medium uppercase text-[10.5px] tracking-wider px-3 py-2.5 border-b border-slate-300 text-left whitespace-nowrap">
                    近 10 天 Lev
                  </th>
                  <th className="sticky top-0 z-[3] bg-slate-100 text-slate-600 font-medium uppercase text-[10.5px] tracking-wider px-3 py-2.5 border-b border-slate-300 text-left whitespace-nowrap">
                    最新操作
                  </th>
                  <th className="sticky top-0 z-[3] bg-slate-100 text-slate-600 font-medium uppercase text-[10.5px] tracking-wider px-3 py-2.5 border-b border-slate-300 text-left whitespace-nowrap">
                    Regime
                  </th>
                  <th className="sticky top-0 z-[3] bg-slate-100 text-slate-600 font-medium uppercase text-[10.5px] tracking-wider px-3 py-2.5 border-b border-slate-300 text-left whitespace-nowrap">
                    最新价 / 日期
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const opMeta = OP_META[r.recent_op] || OP_META.hold
                  return (
                    <tr
                      key={r.label}
                      className="hover:bg-slate-50 transition-colors border-b border-slate-100"
                    >
                      <td className="px-3 py-2 text-left whitespace-nowrap">
                        <div className="font-semibold text-slate-900">
                          {r.label}
                        </div>
                        <div className="text-[10.5px] text-slate-400 tabular-nums">
                          {r.ticker}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-left whitespace-nowrap">
                        <GroupBadge group={r.group} />
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <LevBadge lev={r.current_lev} />
                      </td>
                      <td className="px-3 py-2 text-left whitespace-nowrap">
                        <span className="text-[11.5px] font-medium text-slate-700">
                          {r.selected_sub}
                        </span>
                      </td>
                      <td
                        className={`px-3 py-2 text-right whitespace-nowrap tabular-nums ${clsForNum(
                          r.daily_ret_pct,
                        )}`}
                      >
                        {fmtPct(r.daily_ret_pct)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right whitespace-nowrap tabular-nums ${clsForNum(
                          r.adapt_cagr_pct,
                        )}`}
                      >
                        {fmtPct(r.adapt_cagr_pct)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right whitespace-nowrap tabular-nums ${clsForNum(
                          r.bh_cagr_pct,
                        )}`}
                      >
                        {fmtPct(r.bh_cagr_pct)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right whitespace-nowrap tabular-nums font-semibold ${clsForNum(
                          r.alpha_pp,
                        )}`}
                      >
                        {fmtSignedPct(r.alpha_pp)}
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums text-slate-600">
                        {r.days_at_lev}天
                      </td>
                      <td className="px-3 py-2 text-left whitespace-nowrap">
                        <LevSparkline levs={r.recent_levs} />
                      </td>
                      <td className="px-3 py-2 text-left whitespace-nowrap">
                        <div className="inline-flex flex-col gap-0.5">
                          <OpBadge op={r.recent_op} />
                          {r.last_op_date && r.last_op_from != null && r.last_op_to != null ? (
                            <div className="text-[10.5px] text-slate-500 tabular-nums leading-tight">
                              <span className="text-slate-400">{r.last_op_from.toFixed(1)}→</span>
                              <span className="font-medium text-slate-700">{r.last_op_to.toFixed(1)}x</span>
                              <span className="text-slate-400"> · {r.last_op_date}</span>
                              <span className="text-slate-400"> · {r.days_since_op}天前</span>
                            </div>
                          ) : (
                            <div className="text-[10.5px] text-slate-400 italic leading-tight">
                              回测期内未调仓
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-left whitespace-nowrap">
                        <RegimeBadge regime={r.regime} />
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                        <div className="text-[12px] font-medium text-slate-800">
                          {r.last_close.toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </div>
                        <div className="text-[10.5px] text-slate-400">
                          {r.last_date}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 子策略说明 */}
        <div className="bg-slate-100 border border-slate-200 border-l-[3px] border-l-slate-400 rounded-lg px-4 py-3 text-xs leading-relaxed text-slate-600">
          <b className="text-slate-800">ADAPTIVE v38 策略说明:</b>
          <ul className="mt-1.5 ml-5 list-disc space-y-1">
            <li>
              <b>crypto</b> (BTC/ETH/SOL/BNB): 固定
              <span className="font-mono text-slate-700"> SAL_PLUS</span> —
              Sharpe&gt;1.2 且 close&gt;SMA50 时 2.0x; 回撤&gt;35% 降到 1.0x
            </li>
            <li>
              <b>us_lev</b> (SOXL/TQQQ): 固定
              <span className="font-mono text-slate-700"> VTL_F1</span> —
              target_vol/realized_vol, 高波动自动降杠杆, cap 2.5x
            </li>
            <li>
              <b>us_eq</b>: 504 天 warmup 期 expanding CAGR 排序, 从 7 个子策略
              (SAL_PLUS / VTL_F1 / CL2 / DRL_LONG / DRL_SHORT / TL / UNIVERSAL)
              中选 CAGR 最高者, 排除 CAGR&gt;200% 的过拟合策略
            </li>
          </ul>
          <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] text-slate-500">
            <b>当前 Lev</b> = T+1 生效杠杆 (已 shift 1 天);
            <b> α</b> = ADAPT CAGR − BH CAGR (百分点);
            <b> 维持天数</b> = 当前 lev 连续保持天数;
            <b> 最新操作</b> = 回溯找到的最近一次杠杆变化 (非当日操作).
            <b> Regime</b>:
            <span className="text-emerald-700"> 绿=高杠杆进攻(≥2x, 借钱加仓放大收益)</span>,
            <span className="text-amber-700"> 黄=中等(1.4-2x)</span>,
            <span className="text-blue-700"> 蓝=基础仓位(1x, 不借钱等于买入持有)</span>.
            点击表头排序.
          </div>
        </div>
      </main>
    </div>
  )
}
