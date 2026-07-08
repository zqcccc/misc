'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useOverview, useMarketResult, useConnectedCharts } from './hooks'
import type { MarketResult, MarketSummary, RangeStats } from './types'
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

// 风险偏好语义色 (与图表图例一致): 绿=风险偏好/进攻, 黄=中性, 红=风险规避. 非涨跌色.
const REGIME_BG: Record<string, string> = {
  risk_on: '#2e7d32',
  moderate: '#f9a825',
  risk_off: '#c62828',
}
// 操作跟随图表 A股惯例: 加仓=红/up, 减仓=绿/down
const OP_LABEL: Record<string, string> = { add: '加仓', reduce: '减仓', hold: '持有' }
const OP_ARROW: Record<string, string> = { add: '▲', reduce: '▼', hold: '—' }
const OP_COLOR: Record<string, string> = {
  add: '#c62828',
  reduce: '#2e7d32',
  hold: 'var(--sub)',
}
function regimeCnLabel(
  regime: string | null | undefined,
  cn: Record<string, string>,
): string {
  if (!regime) return '—'
  return cn[regime] || regime
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
  regimeCn,
}: {
  markets: MarketSummary[]
  active: string
  onSelect: (label: string) => void
  regimeCn: Record<string, string>
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
            // 右侧数字: risk-on满仓 相对 基准(buy&hold) 的超额 = ronly_total − bench_total
            const ronlyVsBase = (m.ronly_total ?? 0) - (m.bench_total ?? 0)
            const excessCls = clsColor(ronlyVsBase)
            const rc = m.current_regime
            const rcBg = rc ? REGIME_BG[rc] : '#9e9e9e'
            const no = m.next_operation
            const nextOpArrow = no && no !== 'hold' ? OP_ARROW[no] : null
            const nextOpColor = no && no !== 'hold' ? OP_COLOR[no] : undefined
            const title = [
              `risk-on满仓超额(满仓−基准): ${fmtPct(ronlyVsBase)}`,
              `当前风险偏好: ${regimeCnLabel(rc, regimeCn)}`,
              `最新操作: ${OP_LABEL[m.current_operation || 'hold'] || '—'}`,
              m.next_regime
                ? `预计明日: ${regimeCnLabel(m.next_regime, regimeCn)} / ${OP_LABEL[no || 'hold']}`
                : '',
              m.outlook_note ? `预警: ${m.outlook_note}` : '',
              m.last_date ? `数据截至 ${m.last_date}` : '',
            ]
              .filter(Boolean)
              .join('\n')
            return (
              <button
                key={m.label}
                onClick={() => onSelect(m.label)}
                className={`${s.symBtn} ${isActive ? s.symBtnActive : ''}`}
                title={title}
                style={{ gap: 6 }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: rcBg,
                    flexShrink: 0,
                    boxShadow: '0 0 0 1px rgba(0,0,0,0.12) inset',
                  }}
                />
                <span
                  style={{
                    flex: 1,
                    minWidth: 0,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {m.label}
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    flexShrink: 0,
                  }}
                >
                  {nextOpArrow && (
                    <span
                      style={{
                        color: nextOpColor,
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      {nextOpArrow}
                    </span>
                  )}
                  <span
                    className={`${s.symExcess} ${
                      isActive ? s.symExcessActive : excessCls
                    }`}
                  >
                    {fmtPct(ronlyVsBase, 0)}
                  </span>
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
    { k: '主策略收益(区间)', v: fmtPct(rs.sRet), cls: clsColor(rs.sRet) },
    { k: '股现择时收益(区间)', v: fmtPct(rs.tRet), cls: clsColor(rs.tRet) },
    { k: '极值仓位收益(区间)', v: fmtPct(rs.eRet), cls: clsColor(rs.eRet) },
    { k: 'risk-on满仓收益(区间)', v: fmtPct(rs.rRet), cls: clsColor(rs.rRet) },
    { k: '标的收益(区间)', v: fmtPct(rs.bRet), cls: clsColor(rs.bRet) },
    { k: '主策略超额(主策略−标的)', v: fmtPct(rs.excess), cls: clsColor(rs.excess) },
    {
      k: 'GLD防御腿增益(主策略−股现择时)',
      v: fmtPct(rs.tExcess),
      cls: clsColor(rs.tExcess),
    },
    {
      k: '温和调仓增益(主策略−极值仓位)',
      v: fmtPct(rs.eExcess),
      cls: clsColor(rs.eExcess),
    },
    {
      k: '二元择时增益(主策略−risk-on满仓)',
      v: fmtPct(rs.rExcess),
      cls: clsColor(rs.rExcess),
    },
    { k: '主策略最大回撤', v: pct(rs.sMdd), cls: s.neg },
    { k: '股现择时最大回撤', v: pct(rs.tMdd), cls: s.neg },
    { k: '极值仓位最大回撤', v: pct(rs.eMdd), cls: s.neg },
    { k: 'risk-on满仓最大回撤', v: pct(rs.rMdd), cls: s.neg },
    { k: '标的最大回撤', v: pct(rs.bMdd), cls: s.neg },
    { k: '主策略年化', v: fmtPct(rs.sAnn), cls: clsColor(rs.sAnn) },
    { k: '股现择时年化', v: fmtPct(rs.tAnn), cls: clsColor(rs.tAnn) },
    { k: '极值仓位年化', v: fmtPct(rs.eAnn), cls: clsColor(rs.eAnn) },
    { k: 'risk-on满仓年化', v: fmtPct(rs.rAnn), cls: clsColor(rs.rAnn) },
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

function RiskStatusPanel({
  summary,
  regimeCn,
}: {
  summary: MarketResult['summary']
  regimeCn: Record<string, string>
}) {
  if (!summary) return null
  const cur = summary.current_regime
  const next = summary.next_regime
  const curOp = summary.current_operation || 'hold'
  const nextOp = summary.next_operation || 'hold'
  const outlook = summary.regime_outlook
  const isUnknown = outlook === 'unknown'
  const badge = (r: string | null | undefined) =>
    r ? (
      <span className={s.riskBadge} style={{ background: REGIME_BG[r] }}>
        {regimeCnLabel(r, regimeCn)}
      </span>
    ) : (
      <span className={s.riskBadgeMuted}>—</span>
    )
  return (
    <div className={s.card}>
      <div className={s.cardHeader}>
        <h3 className={s.cardTitle}>风险偏好状态（回测快照推演）</h3>
      </div>
      <div className={s.riskGrid}>
        <div className={s.riskCell}>
          <div className={s.riskKey}>当前风险偏好</div>
          <div className={s.riskVal}>{badge(cur)}</div>
        </div>
        <div className={s.riskCell}>
          <div className={s.riskKey}>最新操作</div>
          <div className={s.riskVal} style={{ color: OP_COLOR[curOp] }}>
            {OP_ARROW[curOp]} {OP_LABEL[curOp]}
          </div>
        </div>
        <div className={s.riskCell}>
          <div className={s.riskKey}>
            预计下一风险偏好<span className={s.riskTag}>预计</span>
          </div>
          <div className={s.riskVal}>{badge(next)}</div>
        </div>
        <div className={s.riskCell}>
          <div className={s.riskKey}>
            预计明日操作<span className={s.riskTag}>预计</span>
          </div>
          <div className={s.riskVal} style={{ color: OP_COLOR[nextOp] }}>
            {OP_ARROW[nextOp]} {OP_LABEL[nextOp]}
          </div>
        </div>
        <div className={s.riskCell}>
          <div className={s.riskKey}>数据截至</div>
          <div className={s.riskVal}>{summary.last_date || '—'}</div>
        </div>
        <div className={s.riskCell}>
          <div className={s.riskKey}>当前股票仓位</div>
          <div className={s.riskVal}>
            {summary.current_equity_weight != null
              ? `${(summary.current_equity_weight * 100).toFixed(0)}%`
              : '—'}
          </div>
        </div>
      </div>
      {summary.outlook_note && (
        <div className={isUnknown ? s.riskNote : s.riskWarn}>
          {summary.outlook_note}
        </div>
      )}
      <div className={s.riskNote}>
        说明：回测为历史快照，无明日行情，故“预计”项为按最新收盘信号黏性外推、非实时交易指令；仅当最新信号临近切换阈值（10%
        缓冲）才向前推一档。风险偏好色：绿=偏好·黄=中性·红=规避（语义色，非涨跌）；操作色：红=加仓·绿=减仓（A股惯例）。
      </div>
    </div>
  )
}

/** 把 signal_params 渲染成"策略参数"注释卡片。默认参数标灰, 非默认参数高亮。 */
function SignalParamsNote({
  params,
  meta,
}: {
  params: MarketResult['params']
  meta: MarketResult['meta']
}) {
  const sp = params?.signal_params
  if (!sp) return null

  // 默认值 (与 strategies_trhrp.json signal_params 全局一致)
  const DEFAULTS: Record<string, number | string> = {
    mom_window: 21,
    vol_window: 21,
    vol_p60_rolling_window: 252,
    vol_median_rolling_window: 126,
    zscore_rolling_window: 252,
    zscore_min_periods: 126,
    crash_trigger_vol: 0.3,
    trading_days_per_year: 252,
    crash_zscore: 2.5,
  }

  const rows: { k: string; label: string; val: string; isOverride: boolean }[] = [
    { k: 'crash_mode', label: '崩盘判定模式', val: String(sp.crash_mode ?? 'absolute'), isOverride: false },
    { k: 'crash_zscore', label: '崩盘 z 阈值', val: String(sp.crash_zscore ?? 2.5), isOverride: Number(sp.crash_zscore) !== 2.5 },
    { k: 'vol_p60_rolling_window', label: '波动率 p60 窗口', val: String(sp.vol_p60_rolling_window), isOverride: Number(sp.vol_p60_rolling_window) !== 252 },
    { k: 'vol_median_rolling_window', label: '波动率中位数窗口', val: String(sp.vol_median_rolling_window), isOverride: Number(sp.vol_median_rolling_window) !== 126 },
    { k: 'zscore_rolling_window', label: 'z-score 窗口', val: String(sp.zscore_rolling_window), isOverride: Number(sp.zscore_rolling_window) !== 252 },
    { k: 'zscore_min_periods', label: 'z-score 最小周期', val: String(sp.zscore_min_periods), isOverride: Number(sp.zscore_min_periods) !== 126 },
    { k: 'mom_window', label: '动量窗口', val: String(sp.mom_window), isOverride: Number(sp.mom_window) !== 21 },
    { k: 'vol_window', label: '波动率窗口', val: String(sp.vol_window), isOverride: Number(sp.vol_window) !== 21 },
  ]

  const hasOverride = rows.some((r) => r.isOverride)
  const overlay = params?.overlay
  const scenario = params?.scenario
  const commission = params?.commission_mode
  const overlayText = overlay
    ? `有（买≤${overlay.buy_z} / 卖≥${overlay.sell_z} / Δ${overlay.delta} / 窗口${overlay.window}）`
    : '无'

  return (
    <div className={s.note} style={{ marginTop: 12 }}>
      <b>{meta.label}（{meta.ticker}）策略参数{hasOverride ? ' · 含自定义覆盖' : ''}</b>
      {hasOverride && (
        <span className={s.negKey} style={{ marginLeft: 6 }}>
          ⚠ 该标的用了非默认窗口（上市不足 252 天，缩短窗口让 regime 可计算）
        </span>
      )}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: '4px 16px',
          marginTop: 8,
        }}
      >
        {rows.map((r) => (
          <div key={r.k} style={{ fontSize: 11 }}>
            <span style={{ color: 'var(--sub)' }}>{r.label}：</span>
            <span
              style={{
                color: r.isOverride ? 'var(--warn, #f57c00)' : 'var(--ink-2)',
                fontWeight: r.isOverride ? 600 : 400,
              }}
            >
              {r.val}
              {r.isOverride && (
                <span style={{ color: 'var(--sub)', fontSize: 10 }}>
                  {' '}
                  (默认 {DEFAULTS[r.k]})
                </span>
              )}
            </span>
          </div>
        ))}
        <div style={{ fontSize: 11 }}>
          <span style={{ color: 'var(--sub)' }}>叠加规则：</span>
          <span style={{ color: 'var(--ink-2)' }}>{overlayText}</span>
        </div>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: 'var(--sub)' }}>调仓场景：</span>
          <span style={{ color: 'var(--ink-2)' }}>{scenario}</span>
        </div>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: 'var(--sub)' }}>佣金模式：</span>
          <span style={{ color: 'var(--ink-2)' }}>{commission}</span>
        </div>
      </div>
      {hasOverride && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--sub)' }}>
          说明：该标的上市时间较短，历史数据不足 252 天，全局默认窗口会导致
          vol_p60 / vol_med / vol_z 全部 NaN，regime 恒为 moderate 无法择时。
          故缩短滚动窗口到 63 天、z-score 最小周期到 42 天，让短历史也能算出三档 regime。
          待数据积累到 252 天后可删除 <code>signal_overrides</code> 字段切回默认。
        </div>
      )}
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
  // 视图类型: 在 MarketSummary 基础上补充各变体相对基准的超额列
  type TableView = MarketSummary & {
    timing_excess_vb: number
    extreme_excess_vb: number
    ronly_excess_vb: number
  }
  const cols: {
    label: string
    key: keyof TableView
    fmt: 'pct' | 'signed' | 'int' | 'text'
  }[] = [
    { label: '标的', key: 'label', fmt: 'text' },
    { label: '代码', key: 'ticker', fmt: 'text' },
    { label: '主策略总收益', key: 'strat_total', fmt: 'signed' },
    { label: '股现择时总收益', key: 'timing_total', fmt: 'signed' },
    { label: '极值仓位总收益', key: 'extreme_total', fmt: 'signed' },
    { label: 'risk-on满仓总收益', key: 'ronly_total', fmt: 'signed' },
    { label: '基准总收益(buy&hold)', key: 'bench_total', fmt: 'signed' },
    { label: '主策略超额(主策略−基准)', key: 'excess', fmt: 'signed' },
    { label: '股现择时超额(股现择时−基准)', key: 'timing_excess_vb', fmt: 'signed' },
    { label: '极值仓位超额(极值仓位−基准)', key: 'extreme_excess_vb', fmt: 'signed' },
    { label: 'risk-on满仓超额(risk-on满仓−基准)', key: 'ronly_excess_vb', fmt: 'signed' },
    { label: '主策略CAGR', key: 'strat_cagr', fmt: 'signed' },
    { label: '主策略MDD', key: 'strat_mdd', fmt: 'pct' },
    { label: '股现择时MDD', key: 'timing_mdd', fmt: 'pct' },
    { label: '极值仓位MDD', key: 'extreme_mdd', fmt: 'pct' },
    { label: 'risk-on满仓MDD', key: 'ronly_mdd', fmt: 'pct' },
    { label: '基准MDD', key: 'bench_mdd', fmt: 'pct' },
    { label: '偏好天', key: 'risk_on', fmt: 'int' },
    { label: '中性天', key: 'moderate', fmt: 'int' },
    { label: '规避天', key: 'risk_off', fmt: 'int' },
    { label: '加仓', key: 'adds', fmt: 'int' },
    { label: '减仓', key: 'reduces', fmt: 'int' },
  ]
  // 把各变体相对基准(buy&hold)的超额算出来, 供下方列引用
  const viewOf = (m: MarketSummary): TableView => ({
    ...m,
    timing_excess_vb:
      (Number(m.timing_total) || 0) - (Number(m.bench_total) || 0),
    extreme_excess_vb:
      (Number(m.extreme_total) || 0) - (Number(m.bench_total) || 0),
    ronly_excess_vb:
      (Number(m.ronly_total) || 0) - (Number(m.bench_total) || 0),
  })
  const fmtVal = (m: TableView, c: (typeof cols)[number]) => {
    const v = m[c.key]
    if (c.fmt === 'signed') return fmtPct(v as number)
    if (c.fmt === 'pct') return pct(v as number)
    if (c.fmt === 'int') return String(v)
    return String(v)
  }
  const clsFor = (m: TableView, c: (typeof cols)[number]) => {
    if (c.fmt === 'signed') return clsColor(m[c.key] as number)
    if (c.fmt === 'pct')
      return (m[c.key] as number) < -0.0001 ? s.neg : ''
    return ''
  }
  // 每行最高总收益: 在 5 个总收益列中取最大, 用于 ★ 高亮
  const RETURN_KEYS: (keyof MarketSummary)[] = [
    'strat_total',
    'timing_total',
    'extreme_total',
    'bench_total',
    'ronly_total',
  ]
  const bestKeysFor = (m: TableView): Set<keyof TableView> => {
    const vals = RETURN_KEYS.map((k) => Number(m[k]) || 0)
    const max = Math.max(...vals)
    const set = new Set<keyof MarketSummary>()
    RETURN_KEYS.forEach((k, i) => {
      if (Math.abs(vals[i] - max) < 1e-9) set.add(k)
    })
    return set
  }
  // 每行性价比最高: 总收益 ÷ |最大回撤| (Calmar 式风险收益比),
  // 在 5 个总收益列中取最大, 用于 ◆ 高亮。无波动/Sharpe 字段, 这是可计算的最合理风险调整指标。
  const RETURN_TO_MDD: Record<string, keyof MarketSummary> = {
    strat_total: 'strat_mdd',
    timing_total: 'timing_mdd',
    extreme_total: 'extreme_mdd',
    bench_total: 'bench_mdd',
    ronly_total: 'ronly_mdd',
  }
  const bestRiskKeysFor = (m: TableView): Set<keyof TableView> => {
    const vals = RETURN_KEYS.map((k) => {
      const tot = Number(m[k]) || 0
      const mdd = Math.abs(Number(m[RETURN_TO_MDD[k as string]]) || 0)
      return mdd > 1e-9 ? tot / mdd : Number.NEGATIVE_INFINITY
    })
    const max = Math.max(...vals)
    const set = new Set<keyof MarketSummary>()
    RETURN_KEYS.forEach((k, i) => {
      if (max > Number.NEGATIVE_INFINITY && Math.abs(vals[i] - max) < 1e-6)
        set.add(k)
    })
    return set
  }
  return (
    <div className={s.tableWrap}>
      <div className={s.tableHead}>
        <h3 className={s.tableTitle}>全市场汇总</h3>
        <span className={s.tableHint}>
          点击行跳转到该标的图表 ·{' '}
          <span style={{ color: 'var(--risk-star)', fontWeight: 700 }}>
            ★
          </span>{' '}
          性价比最高（总收益 ÷ |最大回撤|，主策略/股现择时/极值仓位/risk-on满仓/基准 五者取最大）·{' '}
          <strong style={{ color: 'var(--best-ink)' }}>最高总收益</strong>
          （琥珀色字）·{' '}
          <strong>所有「超额」列均为相对基准(buy&amp;hold) 的超额收益</strong>
          （主策略/股现择时/极值仓位/risk-on满仓 各自 − 基准）
        </span>
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
            {markets.map((m) => {
              const v = viewOf(m)
              const best = bestKeysFor(v)
              const risk = bestRiskKeysFor(v)
              return (
                <tr
                  key={m.label}
                  onClick={() => onSelect(m.label)}
                  className={
                    m.label === active ? s.tableRowActive : undefined
                  }
                >
                  {cols.map((c) => {
                    const isBest = best.has(c.key)
                    const isRisk = risk.has(c.key)
                    const cellCls = [
                      clsFor(v, c),
                      isBest ? s.bestReturn : '',
                      isRisk ? s.bestRisk : '',
                    ]
                      .filter(Boolean)
                      .join(' ')
                    return (
                      <td key={c.key as string} className={cellCls}>
                        {fmtVal(v, c)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
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
            regimeCn={data?.regime_cn || {}}
          />
        </aside>

        <main className={s.main}>
          {sm && (
            <div className={s.statbar}>
              <StatCard
                label='主策略总收益'
                value={signed(sm.strategy_total_return)}
                tone={sm.strategy_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='基准总收益'
                value={signed(sm.benchmark_total_return)}
                tone={sm.benchmark_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='主策略超额'
                value={signed(sm.excess_total_return)}
                tone={sm.excess_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='risk-on满仓总收益'
                value={signed(sm.ronly_total_return)}
                tone={sm.ronly_total_return >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='主策略 CAGR'
                value={signed(sm.strategy_cagr)}
                tone={sm.strategy_cagr >= 0 ? 'pos' : 'neg'}
              />
              <StatCard
                label='主策略最大回撤'
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

          {sm && (
            <RiskStatusPanel
              summary={sm}
              regimeCn={data?.regime_cn || {}}
            />
          )}

          <div className={s.card}>
            {resultLoading && !result && (
              <div className={s.loadingHint}>加载标的序列…</div>
            )}
            <div ref={mainRef} style={{ width: '100%', height: 520 }} />
            <div className={s.legend}>
              <b>绿带</b>=风险偏好 · <b>黄带</b>=中性 · <b>红带</b>=风险规避；▲红=加仓，
              ▼绿=减仓（落在归一价曲线上）。左轴净值、右轴归一价。
              <b style={{ color: '#ef6c00' }}>橙虚线</b>=股现择时净值（equity 权重同主策略，其余全现金 SGOV，不含 GLD 防御腿）；
              <b style={{ color: '#6a1b9a' }}>紫点线</b>=极值仓位（把股现择时的连续仓位推到极值：risk_on=满仓 / moderate=半仓 / risk_off=空仓，非标的全 SGOV）；
              <b style={{ color: '#00838f' }}>青虚线</b>=risk-on满仓（仅 risk_on 满仓 equity，moderate/risk_off 全部现金 SGOV 空仓，二元择时）。
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

          {result && <SignalParamsNote params={result.params} meta={result.meta} />}

          <RangeStatsPanel rs={rangeStats} />

          <SummaryTable
            markets={data.markets}
            active={activeLabel}
            onSelect={setActiveLabel}
          />

          <div className={s.note}>
            <b>策略家族说明（均基于同一套风险偏好择时信号：risk_on / moderate / risk_off）：</b>
            <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
              <li>
                <b>主策略（标的 + 黄金 + 现金）</b>：完整 TRHRP。在「标的(个股/ETF) / 黄金(GL
                D) / 现金(SGOV)」三者间轮动，risk_off 时切到黄金做防御腿。图中绿线。
              </li>
              <li>
                <b>股现择时（标的 + 现金）</b>：与主策略相同的权益仓位，但非权益部分全部持现金（无黄金防御腿）。用于隔离「择时信号」本身的贡献。图中橙虚线。
              </li>
              <li>
                <b>极值仓位（满 / 半 / 空）</b>：把股现择时的连续仓位推到极值——risk_on
                满仓(100%)、moderate 半仓(50%)、risk_off 空仓(0%)，非标的全部现金。最激进的仓位映射。图中紫点线。
              </li>
              <li>
                <b>risk-on满仓（余皆现金）</b>：二元择时——仅 risk_on 时满仓进标的，moderate /
                risk_off 全部现金。最简单粗暴的「该不该在场内」判断。图中青虚线。
              </li>
            </ul>
          </div>

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
