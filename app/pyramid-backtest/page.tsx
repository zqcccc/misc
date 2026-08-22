'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'

interface Stats {
  name: string
  start: string
  end: string
  years: number
  total_return: number
  cagr: number
  mdd: number
  vol: number
  sharpe: number
  calmar: number | null
}

interface ResultItem {
  ticker: string
  group: string
  strat: Stats
  bh: Stats
  n_trades: number
  delta_cagr: number
  delta_mdd: number
  win: boolean
  nav: { dates: string[]; strat: number[]; bh: number[] }
  position: { dates: string[]; values: number[] }
  trades_sample: Array<{
    date: string
    action: string
    price: number
    pos: number
    reason: string
  }>
}

interface VersionData {
  label: string
  params: {
    ma_period: number
    ma_fast: number | null
    debounce: number
    step: number
    initial_pos: number
    adds: number[]
    cuts: number[]
    floor_pos: number
    max_pos: number
    cost_rate: number
  }
  n_assets: number
  n_win: number
  win_rate: number
  n_cagr_win: number
  n_mdd_win: number
  avg_delta_cagr: number
  avg_delta_mdd: number
  results: ResultItem[]
}

interface OverviewData {
  strategy: string
  default_version: string
  versions: Record<string, VersionData>
}

interface FullData extends VersionData {
  current_version: string
  available_versions: string[]
}

const ACTION_LABEL: Record<string, string> = {
  BUY: '建仓',
  ADD: '加仓',
  CUT: '减仓',
  EXIT: '清仓',
}
const ACTION_COLOR: Record<string, string> = {
  BUY: '#2563eb',
  ADD: '#dc2626',
  CUT: '#16a34a',
  EXIT: '#7c3aed',
}

const VERSION_LABEL: Record<string, string> = {
  v1: 'v1 基线',
  v2: 'v2 优化',
}
const VERSION_DESC: Record<string, string> = {
  v1: 'MA200单线 · 清仓 · 保守加仓',
  v2: '双线确认 · debounce · 地板仓 · 激进加仓',
}

export default function PyramidBacktestPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [data, setData] = useState<FullData | null>(null)
  const [version, setVersion] = useState('v2')
  const [selected, setSelected] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadOverview = useCallback(async () => {
    try {
      const res = await fetch('/api/pyramid-backtest?overview=1', { cache: 'no-store' })
      if (!res.ok) return
      const json = await res.json()
      setOverview(json)
    } catch {}
  }, [])

  const loadVersion = useCallback(async (ver: string) => {
    try {
      const res = await fetch(`/api/pyramid-backtest?version=${ver}`, { cache: 'no-store' })
      if (!res.ok) {
        const j = await res.json().catch(() => ({}))
        throw new Error(j.message || `HTTP ${res.status}`)
      }
      const json = await res.json()
      setData(json)
      if (!selected && json.results?.length) {
        setSelected(json.results[0].ticker)
      }
    } catch (e: any) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [selected])

  useEffect(() => {
    loadOverview()
    loadVersion(version)
  }, [loadOverview, loadVersion, version])

  const current = useMemo(
    () => data?.results.find((r) => r.ticker === selected) ?? null,
    [data, selected],
  )

  const switchVersion = (v: string) => {
    setVersion(v)
    setLoading(true)
  }

  if (loading && !data) {
    return <div style={{ padding: 40, color: 'var(--sub)' }}>加载回测数据中...</div>
  }

  if (error && !data) {
    return (
      <div style={{ padding: 40 }}>
        <div style={{ color: 'var(--neg)', marginBottom: 12 }}>{error}</div>
        <div style={{ color: 'var(--sub)', fontFamily: 'var(--font-mono)' }}>
          请运行: python3 scripts/pyramid_backtest.py
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
      <Header data={data} version={version} onSwitch={switchVersion} available={overview?.versions} />
      {overview && <VersionCompare overview={overview} />}
      <SummaryCards data={data} />
      <ResultsTable data={data} selected={selected} onSelect={setSelected} />
      {current && <DetailChart item={current} />}
      {current && <PositionChart item={current} />}
      {current && <TradesTable item={current} />}
    </div>
  )
}

function Header({
  data,
  version,
  onSwitch,
  available,
}: {
  data: FullData
  version: string
  onSwitch: (v: string) => void
  available?: Record<string, VersionData>
}) {
  const p = data.params
  const versions = available ? Object.keys(available) : [version]
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          金字塔加仓/减仓策略回测
        </h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {versions.map((v) => (
            <button
              key={v}
              onClick={() => onSwitch(v)}
              style={{
                padding: '6px 14px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: v === version ? 'var(--foreground)' : 'var(--bg-secondary)',
                color: v === version ? 'var(--background)' : 'var(--foreground)',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {VERSION_LABEL[v] || v}
            </button>
          ))}
        </div>
      </div>
      <div style={{ color: 'var(--sub)', fontSize: 13, lineHeight: 1.7 }}>
        {VERSION_DESC[version]}
        {' · '}
        MA{p.ma_period}
        {p.ma_fast ? `+MA${p.ma_fast}双线` : '单线'}
        {' · '}初始{(p.initial_pos * 100).toFixed(0)}%
        {' · '}台阶{(p.step * 100).toFixed(0)}%
        {' · '}加仓[{p.adds.map((x) => (x * 100).toFixed(0) + '%').join(', ')}]
        {' · '}减仓[{p.cuts.map((x) => (x * 100).toFixed(0) + '%').join(', ')}]
        {' · '}地板仓{(p.floor_pos * 100).toFixed(0)}%
        {p.debounce > 0 ? ` · 确认${p.debounce}天` : ''}
        {' · '}最大{(p.max_pos * 100).toFixed(0)}%
        {' · '}成本{(p.cost_rate * 1e4).toFixed(1)}bps
      </div>
    </div>
  )
}

function VersionCompare({ overview }: { overview: OverviewData }) {
  const v1 = overview.versions['v1']
  const v2 = overview.versions['v2']
  if (!v1 || !v2) return null

  const dc = (v2.avg_delta_cagr - v1.avg_delta_cagr).toFixed(2)
  const dm = (v2.avg_delta_mdd - v1.avg_delta_mdd).toFixed(2)

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
        marginBottom: 20,
        padding: 14,
        borderRadius: 10,
        border: '1px solid var(--border)',
        background: 'var(--bg-secondary)',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--sub)', gridColumn: '1 / -1' }}>
        v1 → v2 优化效果
      </div>
      <CompareItem label="平均 ΔCAGR" v1={`${v1.avg_delta_cagr}pp`} v2={`${v2.avg_delta_cagr}pp`} delta={`${dc > '0' ? '+' : ''}${dc}pp`} good={parseFloat(dc) > 0} />
      <CompareItem label="平均 ΔMDD" v1={`${v1.avg_delta_mdd}pp`} v2={`${v2.avg_delta_mdd}pp`} delta={`${parseFloat(dm) > 0 ? '+' : ''}${dm}pp`} good={parseFloat(dm) > 0} />
      <CompareItem label="收益胜 B&H" v1={`${v1.n_cagr_win}/${v1.n_assets}`} v2={`${v2.n_cagr_win}/${v2.n_assets}`} delta={`${v2.n_cagr_win - v1.n_cagr_win > 0 ? '+' : ''}${v2.n_cagr_win - v1.n_cagr_win}`} good={v2.n_cagr_win > v1.n_cagr_win} />
      <CompareItem label="双赢标的" v1={`${v1.n_win} (${v1.win_rate}%)`} v2={`${v2.n_win} (${v2.win_rate}%)`} delta={`${v2.n_win - v1.n_win > 0 ? '+' : ''}${v2.n_win - v1.n_win}`} good={v2.n_win >= v1.n_win} />
    </div>
  )
}

function CompareItem({
  label,
  v1,
  v2,
  delta,
  good,
}: {
  label: string
  v1: string
  v2: string
  delta: string
  good: boolean
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
      <span style={{ color: 'var(--sub)', minWidth: 80 }}>{label}</span>
      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--sub-2)' }}>{v1}</span>
      <span style={{ color: 'var(--sub-2)' }}>→</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{v2}</span>
      <span style={{ fontFamily: 'var(--font-mono)', color: good ? 'var(--pos)' : 'var(--neg)', fontWeight: 600 }}>
        {delta}
      </span>
    </div>
  )
}

function SummaryCards({ data }: { data: FullData }) {
  const cards = [
    { label: '回测标的', value: String(data.n_assets), sub: '美股 + crypto' },
    {
      label: '双赢标的',
      value: String(data.n_win),
      sub: `占比 ${data.win_rate}%`,
      tone: data.win_rate > 30 ? 'pos' : data.win_rate > 10 ? 'plain' : 'neg',
    },
    {
      label: '收益胜 B&H',
      value: String(data.n_cagr_win),
      sub: `/${data.n_assets}`,
      tone: data.n_cagr_win > data.n_assets / 2 ? 'pos' : 'neg',
    },
    {
      label: '回撤胜 B&H',
      value: String(data.n_mdd_win),
      sub: `/${data.n_assets}`,
      tone: data.n_mdd_win > data.n_assets / 2 ? 'pos' : 'neg',
    },
    {
      label: '平均 ΔCAGR',
      value: `${data.avg_delta_cagr > 0 ? '+' : ''}${data.avg_delta_cagr}pp`,
      sub: 'vs Buy & Hold',
      tone: data.avg_delta_cagr > 0 ? 'pos' : 'neg',
    },
    {
      label: '平均 ΔMDD',
      value: `${data.avg_delta_mdd > 0 ? '+' : ''}${data.avg_delta_mdd}pp`,
      sub: '正值=回撤改善',
      tone: data.avg_delta_mdd > 0 ? 'pos' : 'neg',
    },
  ]
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 12,
        marginBottom: 24,
      }}
    >
      {cards.map((c) => (
        <div
          key={c.label}
          style={{
            background: 'var(--bg-secondary)',
            borderRadius: 10,
            padding: '14px 16px',
            border: '1px solid var(--border)',
          }}
        >
          <div style={{ color: 'var(--sub)', fontSize: 12, marginBottom: 4 }}>{c.label}</div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: c.tone === 'pos' ? 'var(--pos)' : c.tone === 'neg' ? 'var(--neg)' : 'inherit',
            }}
          >
            {c.value}
          </div>
          {c.sub && <div style={{ color: 'var(--sub-2)', fontSize: 11 }}>{c.sub}</div>}
        </div>
      ))}
    </div>
  )
}

function ResultsTable({
  data,
  selected,
  onSelect,
}: {
  data: FullData
  selected: string
  onSelect: (t: string) => void
}) {
  const sorted = [...data.results].sort((a, b) => b.delta_cagr - a.delta_cagr)
  return (
    <div
      style={{
        overflowX: 'auto',
        marginBottom: 24,
        borderRadius: 10,
        border: '1px solid var(--border)',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: 'var(--bg-secondary)' }}>
            {['标的', '分组', '策略CAGR', '策略MDD', 'Sharpe', 'B&H CAGR', 'B&H MDD', 'ΔCAGR', 'ΔMDD', '操作', '结果'].map((h) => (
              <th
                key={h}
                style={{
                  padding: '8px 10px',
                  textAlign: 'right',
                  fontWeight: 600,
                  color: 'var(--sub)',
                  borderBottom: '1px solid var(--border)',
                  whiteSpace: 'nowrap',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const isSel = r.ticker === selected
            return (
              <tr
                key={r.ticker}
                onClick={() => onSelect(r.ticker)}
                style={{ cursor: 'pointer', background: isSel ? 'var(--pos-bg)' : undefined }}
              >
                <td style={cellLeft}>{r.ticker}</td>
                <td style={{ ...cell, color: 'var(--sub)' }}>{r.group}</td>
                <td style={cell}>{r.strat.cagr.toFixed(2)}%</td>
                <td style={cell}>{r.strat.mdd.toFixed(2)}%</td>
                <td style={cell}>{r.strat.sharpe.toFixed(2)}</td>
                <td style={cell}>{r.bh.cagr.toFixed(2)}%</td>
                <td style={cell}>{r.bh.mdd.toFixed(2)}%</td>
                <td style={{ ...cell, color: r.delta_cagr > 0 ? 'var(--pos)' : 'var(--neg)', fontWeight: 600 }}>
                  {r.delta_cagr > 0 ? '+' : ''}{r.delta_cagr}pp
                </td>
                <td style={{ ...cell, color: r.delta_mdd > 0 ? 'var(--pos)' : 'var(--neg)', fontWeight: 600 }}>
                  {r.delta_mdd > 0 ? '+' : ''}{r.delta_mdd}pp
                </td>
                <td style={cell}>{r.n_trades}</td>
                <td style={cell}>
                  {r.win ? (
                    <span style={{ color: '#fff', background: 'var(--pos)', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      双赢
                    </span>
                  ) : r.delta_cagr > 0 ? (
                    <span style={{ color: 'var(--pos)', fontSize: 11 }}>收益胜</span>
                  ) : (
                    <span style={{ color: 'var(--sub-2)', fontSize: 11 }}>-</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const cell: CSSProperties = {
  padding: '7px 10px',
  textAlign: 'right',
  borderBottom: '1px solid var(--border)',
  fontFamily: 'var(--font-mono)',
  whiteSpace: 'nowrap',
}
const cellLeft: CSSProperties = { ...cell, textAlign: 'left', fontWeight: 600 }

function DetailChart({ item }: { item: ResultItem }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let disposed = false
    let chart: any

    import('echarts').then((ec) => {
      if (disposed || !ref.current) return
      chart = ec.init(ref.current)
      const nav = item.nav
      chart.setOption({
        title: { text: `${item.ticker} · 净值曲线 (初始资金 10000)`, left: 0, textStyle: { fontSize: 14, fontWeight: 600 } },
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        legend: { data: ['金字塔策略', 'Buy & Hold'], top: 28, right: 0 },
        grid: { left: 50, right: 20, top: 60, bottom: 60 },
        xAxis: { type: 'category', data: nav.dates, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(0), fontSize: 10 } },
        dataZoom: [
          { type: 'inside', start: 0, end: 100 },
          { type: 'slider', bottom: 10, height: 18 },
        ],
        series: [
          { name: '金字塔策略', type: 'line', data: nav.strat, showSymbol: false, lineStyle: { width: 2, color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
          { name: 'Buy & Hold', type: 'line', data: nav.bh, showSymbol: false, lineStyle: { width: 1.5, color: '#9ca3af', type: 'dashed' }, itemStyle: { color: '#9ca3af' } },
        ],
      })
      const onResize = () => chart?.resize()
      window.addEventListener('resize', onResize)
    })

    return () => { disposed = true; chart?.dispose?.() }
  }, [item])

  return <div ref={ref} style={{ width: '100%', height: 380, marginBottom: 20, border: '1px solid var(--border)', borderRadius: 10, padding: 8 }} />
}

function PositionChart({ item }: { item: ResultItem }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let disposed = false
    let chart: any

    import('echarts').then((ec) => {
      if (disposed || !ref.current) return
      chart = ec.init(ref.current)
      const pos = item.position
      chart.setOption({
        title: { text: `${item.ticker} · 仓位变化`, left: 0, textStyle: { fontSize: 14, fontWeight: 600 } },
        tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${(v * 100).toFixed(1)}%` },
        grid: { left: 50, right: 20, top: 50, bottom: 60 },
        xAxis: { type: 'category', data: pos.dates, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', min: 0, max: 1.2, axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%`, fontSize: 10 } },
        dataZoom: [
          { type: 'inside', start: 0, end: 100 },
          { type: 'slider', bottom: 10, height: 18 },
        ],
        series: [
          { type: 'line', data: pos.values, showSymbol: false, lineStyle: { width: 1.5, color: '#f59e0b' }, areaStyle: { color: 'rgba(245,158,11,0.12)' } },
        ],
      })
      const onResize = () => chart?.resize()
      window.addEventListener('resize', onResize)
    })

    return () => { disposed = true; chart?.dispose?.() }
  }, [item])

  return <div ref={ref} style={{ width: '100%', height: 220, marginBottom: 20, border: '1px solid var(--border)', borderRadius: 10, padding: 8 }} />
}

function TradesTable({ item }: { item: ResultItem }) {
  const trades = item.trades_sample
  return (
    <div style={{ marginBottom: 20, borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px', background: 'var(--bg-secondary)', fontWeight: 600, fontSize: 13, borderBottom: '1px solid var(--border)' }}>
        {item.ticker} · 操作记录 (前 {trades.length} 笔，共 {item.n_trades} 笔)
      </div>
      <div style={{ overflowX: 'auto', maxHeight: 360, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)' }}>
            <tr>
              {['日期', '操作', '价格', '仓位', '原因'].map((h) => (
                <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--sub)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={i}>
                <td style={tradeCell}>{t.date}</td>
                <td style={tradeCell}>
                  <span style={{ color: ACTION_COLOR[t.action] || 'inherit', fontWeight: 600 }}>
                    {ACTION_LABEL[t.action] || t.action}
                  </span>
                </td>
                <td style={{ ...tradeCell, fontFamily: 'var(--font-mono)' }}>{t.price}</td>
                <td style={{ ...tradeCell, fontFamily: 'var(--font-mono)', color: 'var(--sub)' }}>
                  {(t.pos * 100).toFixed(0)}%
                </td>
                <td style={{ ...tradeCell, color: 'var(--sub)' }}>{t.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const tradeCell: CSSProperties = {
  padding: '5px 10px',
  borderBottom: '1px solid var(--border)',
  whiteSpace: 'nowrap',
}
