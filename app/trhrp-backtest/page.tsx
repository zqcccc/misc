'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useOverview, useMarketResult, useConnectedCharts } from './hooks'
import type { MarketSummary, RangeStats } from './types'
import { signed, pct } from './chart-options'
import s from './page.module.css'

const REFRESH_MS = 60_000

function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)}%`
}

function clsColor(x: number): string {
  if (x > 0.0001) return s.pos
  if (x < -0.0001) return s.neg
  return ''
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
      ? s.pos
      : tone === 'neg'
        ? s.neg
        : ''
  return (
    <div className={s.stat}>
      <div className={s.statLabel}>{label}</div>
      <div className={`${s.statValue} ${valueCls}`}>{value}</div>
      {sub && <div className={s.statSub}>{sub}</div>}
    </div>
  )
}

function Sidebar({
  markets,
  active,
  onSelect,
}: {
  markets: MarketSummary[]
  active: string
  onSelect: (label: string) => void
}) {
  const groups = useMemo(() => {
    const g: Record<string, MarketSummary[]> = {}
    markets.forEach((m) => {
      ;(g[m.group] = g[m.group] || []).push(m)
    })
    return g
  }, [markets])

  return (
    <>
      {Object.entries(groups).map(([grp, items]) => (
        <div key={grp}>
          <div className={s.groupHeader}>{grp}</div>
          {items.map((m) => {
            const isActive = m.label === active
            const excessCls = clsColor(m.excess)
            return (
              <button
                key={m.label}
                onClick={() => onSelect(m.label)}
                className={`${s.symBtn} ${isActive ? s.symBtnActive : ''}`}
              >
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {m.label}
                </span>
                <span
                  className={`${s.symExcess} ${
                    isActive ? s.symExcessActive : excessCls
                  }`}
                >
                  {fmtPct(m.excess, 0)}
                </span>
              </button>
            )
          })}
        </div>
      ))}
    </>
  )
}

function RangeStatsPanel({ rs }: { rs: RangeStats | null }) {
  if (!rs) return null
  const cards = [
    {
      k: '区间',
      v: `${rs.start} ~ ${rs.end}`,
      cls: '',
    },
    { k: '区间天数', v: `${rs.days} 天`, cls: '' },
    { k: '策略收益(区间)', v: fmtPct(rs.sRet), cls: clsColor(rs.sRet) },
    { k: '纯择时收益(区间)', v: fmtPct(rs.tRet), cls: clsColor(rs.tRet) },
    { k: '极致纯择时收益(区间)', v: fmtPct(rs.eRet), cls: clsColor(rs.eRet) },
    { k: '标的收益(区间)', v: fmtPct(rs.bRet), cls: clsColor(rs.bRet) },
    { k: '超额(策略−标的)', v: fmtPct(rs.excess), cls: clsColor(rs.excess) },
    {
      k: 'GLD增益(策略−纯择时)',
      v: fmtPct(rs.tExcess),
      cls: clsColor(rs.tExcess),
    },
    {
      k: '温和增益(策略−极致)',
      v: fmtPct(rs.eExcess),
      cls: clsColor(rs.eExcess),
    },
    { k: '策略最大回撤', v: pct(rs.sMdd), cls: s.neg },
    { k: '纯择时最大回撤', v: pct(rs.tMdd), cls: s.neg },
    { k: '极致最大回撤', v: pct(rs.eMdd), cls: s.neg },
    { k: '标的最大回撤', v: pct(rs.bMdd), cls: s.neg },
    { k: '策略年化', v: fmtPct(rs.sAnn), cls: clsColor(rs.sAnn) },
    { k: '纯择时年化', v: fmtPct(rs.tAnn), cls: clsColor(rs.tAnn) },
    { k: '极致年化', v: fmtPct(rs.eAnn), cls: clsColor(rs.eAnn) },
    { k: '标的年化', v: fmtPct(rs.bAnn), cls: clsColor(rs.bAnn) },
  ]
  return (
    <div className={s.rangePanel}>
      <h3 className={s.rangeTitle}>
        <span style={{ color: 'var(--accent)' }}>●</span>
        区间收益统计（拖动下方缩放条选择区间）
      </h3>
      <div className={s.rangeGrid}>
        {cards.map((c) => (
          <div key={c.k} className={s.rangeItem}>
            <div className={s.rangeKey}>{c.k}</div>
            <div className={`${s.rangeVal} ${c.cls}`}>{c.v}</div>
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
  const cols: {
    label: string
    key: keyof MarketSummary
    fmt: 'pct' | 'signed' | 'int' | 'text'
  }[] = [
    { label: '标的', key: 'label', fmt: 'text' },
    { label: '代码', key: 'ticker', fmt: 'text' },
    { label: '策略总收益', key: 'strat_total', fmt: 'signed' },
    { label: '纯择时总收益', key: 'timing_total', fmt: 'signed' },
    { label: '极致纯择时总收益', key: 'extreme_total', fmt: 'signed' },
    { label: '基准总收益', key: 'bench_total', fmt: 'signed' },
    { label: '超额(策略−基准)', key: 'excess', fmt: 'signed' },
    { label: '择时超额(策略−纯择时)', key: 'timing_excess', fmt: 'signed' },
    { label: '极致超额(策略−极致)', key: 'extreme_excess', fmt: 'signed' },
    { label: '策略CAGR', key: 'strat_cagr', fmt: 'signed' },
    { label: '策略MDD', key: 'strat_mdd', fmt: 'pct' },
    { label: '纯择时MDD', key: 'timing_mdd', fmt: 'pct' },
    { label: '极致MDD', key: 'extreme_mdd', fmt: 'pct' },
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
    if (c.fmt === 'signed') return clsColor(m[c.key] as number)
    if (c.fmt === 'pct')
      return (m[c.key] as number) < -0.0001 ? s.neg : ''
    return ''
  }
  return (
    <div className={s.tableWrap}>
      <div className={s.tableHead}>
        <h3 className={s.tableTitle}>全市场汇总</h3>
        <span className={s.tableHint}>点击行跳转到该标的图表</span>
      </div>
      <div className={s.tableScroll}>
        <table className={s.table}>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.key as string}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => (
              <tr
                key={m.label}
                onClick={() => onSelect(m.label)}
                className={
                  m.label === active ? s.tableRowActive : undefined
                }
              >
                {cols.map((c) => (
                  <td key={c.key as string} className={clsFor(m, c)}>
                    {fmtVal(m, c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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

  useEffect(() => {
    if (data && !activeLabel && data.markets.length) {
      setActiveLabel(data.markets[0].label)
    }
  }, [data, activeLabel])

  if (state === 'loading' && !data) {
    return <div className={s.centerMsg}>加载回测数据中…</div>
  }
  if (state === 'error' && !data) {
    return (
      <div className={s.errorCard}>
        <h1 className={s.errorTitle}>数据加载失败</h1>
        <p className={s.errorMsg}>{error}</p>
        <button onClick={refresh} className={s.retryBtn}>
          重试
        </button>
      </div>
    )
  }
  if (!data || !activeLabel) return null

  const sm = result?.summary
  const lastPoll = new Date().toLocaleTimeString('zh-CN', {
    hour12: false,
  })

  return (
    <div className={s.page}>
      <header className={s.header}>
        <div className={s.brand}>
          <div className={s.brandBar} aria-hidden />
          <div>
            <h1 className={s.title}>
              TRHRP 多市场回测 · 策略 vs 买入持有
            </h1>
            <div className={s.subtitle}>
              {generatedAt
                ? `数据生成于 ${generatedAt.slice(0, 19).replace('T', ' ')} UTC`
                : ''}
              {` · 自动刷新 ${REFRESH_MS / 1000}s（上次 ${lastPoll}）`}
            </div>
          </div>
        </div>
        <button onClick={refresh} className={s.refreshBtn}>
          <svg
            width='13'
            height='13'
            viewBox='0 0 24 24'
            fill='none'
            stroke='currentColor'
            strokeWidth='2.2'
            strokeLinecap='round'
            strokeLinejoin='round'
            aria-hidden
          >
            <path d='M21 12a9 9 0 1 1-3-6.7L21 8' />
            <path d='M21 3v5h-5' />
          </svg>
          刷新
        </button>
      </header>

      <div className={s.layout}>
        <aside className={s.sidebar}>
          <Sidebar
            markets={data.markets}
            active={activeLabel}
            onSelect={setActiveLabel}
          />
        </aside>

        <main className={s.main}>
          {sm && (
            <div className={s.statbar}>
              <StatCard
                label='策略总收益'
                value={signed(sm.strategy_total_return)}
                tone={sm.strategy_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='基准总收益'
                value={signed(sm.benchmark_total_return)}
                tone={sm.benchmark_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='超额收益'
                value={signed(sm.excess_total_return)}
                tone={sm.excess_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='策略 CAGR'
                value={signed(sm.strategy_cagr)}
                tone={sm.strategy_cagr >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='策略最大回撤'
                value={pct(sm.strategy_max_drawdown)}
                tone='neg'
              />
              <StatCard
                label='基准最大回撤'
                value={pct(sm.benchmark_max_drawdown)}
                tone='neg'
              />
              <StatCard
                label='加仓 / 减仓日'
                value={`${sm.add_days} / ${sm.reduce_days}`}
              />
              <StatCard
                label='调仓日'
                value={`${sm.rebalance_days}`}
              />
              <StatCard
                label='偏好/中性/规避'
                value={`${sm.risk_on_days}/${sm.moderate_days}/${sm.risk_off_days}`}
              />
              <StatCard
                label='区间 / 天数'
                value={`${result?.meta.start ?? ''}~${result?.meta.end?.slice(0, 4) ?? ''}`}
                sub={`${result?.meta.days ?? 0} 天`}
              />
            </div>
          )}

          <div className={s.card}>
            {resultLoading && !result && (
              <div className={s.loadingHint}>加载标的序列…</div>
            )}
            <div ref={mainRef} style={{ width: '100%', height: 520 }} />
            <div className={s.legend}>
              <b>绿带</b>=风险偏好 · <b>黄带</b>=中性 · <b>红带</b>=风险规避；▲红=加仓，
              ▼绿=减仓（落在归一价曲线上）。左轴净值、右轴归一价。
              <b style={{ color: '#ef6c00' }}>橙虚线</b>=纯择时净值（equity 权重同策略，其余全 SGOV，不含 GLD 防御腿）；
              <b style={{ color: '#6a1b9a' }}>紫点线</b>=极致纯择时（risk_on=满仓 / risk_off=空仓 / moderate=半仓，非标的全 SGOV）。
            </div>
          </div>

          <div className={s.card}>
            <div className={s.cardHeader}>
              <h3 className={s.cardTitle}>股票仓位 % 与波动率%（与上方联动缩放）</h3>
            </div>
            <div ref={weightRef} style={{ width: '100%', height: 200 }} />
            <div className={s.legend}>
              紫线 = 每日股票仓位（左轴）；<b style={{ color: '#00838f' }}>青线</b>=vol21 年化波动率（右轴）；
              虚线参考
              <b style={{ color: 'var(--neg)' }}> 清仓 0%</b> /
              <b style={{ color: 'var(--warn)' }}> risk_off 下限 20%</b> /
              <b style={{ color: 'var(--pos)' }}> risk_on 80%</b>。
              vol 飙升即触发 risk_off 的核心信号。
            </div>
          </div>

          <RangeStatsPanel rs={rangeStats} />

          <SummaryTable
            markets={data.markets}
            active={activeLabel}
            onSelect={setActiveLabel}
          />

          <div className={s.note}>
            <b>口径与数据说明：</b>
            FX 约定：全部按 USD 计价。策略与基准同币种，相对价值（超额/回撤改善）不受影响；
            A/H 标的绝对收益含轻微汇率漂移（港股近似无，人民币有）。操作点 = 股票仓位变动（加仓▲/减仓▼），
            来自当前 monitor/trhrp_strategy 口径（高波动资产 relative_zscore 重校准 + 分组 z 叠加）。
            <br />
            <span className={s.negKey}>数据修正：</span>
            原 SGOV_combined.csv 已损坏（价格反复锯齿、单日 ±12% 数百次），已全部 22 标的改用干净的
            <b> SHY.csv</b> 作短债防御腿（等价替代，覆盖 2018–2026）。
            此前 risk_off 期间净值的异常暴跌/尖刺均因此坏数据，现已消除。
          </div>
        </main>
      </div>
    </div>
  )
}
