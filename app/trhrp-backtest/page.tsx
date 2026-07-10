'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { useOverview, useMarketResult, useConnectedCharts } from './hooks'
import type { MarketResult, MarketSummary, RangeStats } from './types'
import { signed, pct, fmtPrice } from './chart-options'

const REFRESH_MS = 60_000

function fmtPct(v: number | undefined | null, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(digits)}%`
}

function clsColor(x: number): string {
  if (x > 0.0001) return '!text-[var(--pos)]'
  if (x < -0.0001) return '!text-[var(--neg)]'
  return ''
}

// 最大回撤按严重程度着色(热力): 回撤越深红色越浓, 深档文本转白保证可读。
// 仅用于表格 MDD 列(fmt: 'pct'); 与最优总收益/性价比高亮的字体色互不冲突(二者落在收益列)。
const MDD_TIERS: [number, string, boolean][] = [
  [0.1, 'rgba(229,57,53,0.07)', false],
  [0.2, 'rgba(229,57,53,0.15)', false],
  [0.35, 'rgba(229,57,53,0.27)', false],
  [0.55, 'rgba(229,57,53,0.43)', true],
  [Infinity, 'rgba(229,57,53,0.64)', true],
]
function mddSeverityStyle(absPct: number): CSSProperties | undefined {
  if (!absPct || absPct < 0.0001) return undefined
  for (const [thr, bg, white] of MDD_TIERS) {
    if (absPct < thr)
      return white ? { background: bg, color: '#fff' } : { background: bg }
  }
  return undefined
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
      ? '!text-[var(--pos)]'
      : tone === 'neg'
        ? '!text-[var(--neg)]'
        : ''
  return (
    <div className="bg-[var(--surface-2)] border border-transparent rounded-lg px-3 py-2.5 flex flex-col gap-0.5 hover:bg-[var(--surface-hover)] hover:border-[color:var(--border-trhrp)] transition">
      <div className="text-[10.5px] font-medium text-[var(--sub-2)] uppercase tracking-[0.06em]">
        {label}
      </div>
      <div
        className={`text-[18px] font-semibold tracking-tight text-[var(--ink)] tabular-nums leading-tight ${valueCls}`}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[11px] text-[var(--sub-2)] tabular-nums">{sub}</div>
      )}
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
  // —— 搜索: 按 label / ticker 模糊匹配, 不区分大小写 ——
  const [query, setQuery] = useState('')
  // —— Regime 筛选 tab: 全部 / 偏好(risk_on) / 中性(moderate) / 规避(risk_off) / 优质(quality) ——
  const [regimeFilter, setRegimeFilter] = useState<
    'all' | 'risk_on' | 'moderate' | 'risk_off' | 'quality'
  >('all')
  // —— 折叠的分组集合 (默认空集 = 全部展开) ——
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set())

  // 先按搜索词 + regime 筛选, 再按 marketGroup 分组
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return markets.filter((m) => {
      if (
        q &&
        !m.label.toLowerCase().includes(q) &&
        !m.ticker.toLowerCase().includes(q)
      )
        return false
      if (regimeFilter === 'quality') {
        if (!m.quality) return false
      } else if (regimeFilter !== 'all') {
        if (m.current_regime !== regimeFilter) return false
      }
      return true
    })
  }, [markets, query, regimeFilter])

  const groups = useMemo(() => {
    const g: Record<string, MarketSummary[]> = {}
    filtered.forEach((m) => {
      ;(g[m.group] = g[m.group] || []).push(m)
    })
    return g
  }, [filtered])

  const toggleGroup = (grp: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(grp)) next.delete(grp)
      else next.add(grp)
      return next
    })
  }

  const REGIME_TABS: { key: typeof regimeFilter; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'risk_on', label: '偏好' },
    { key: 'moderate', label: '中性' },
    { key: 'risk_off', label: '规避' },
    { key: 'quality', label: '优质' },
  ]

  return (
    <>
      {/* 搜索框 + regime 筛选 tab: 仅桌面端显示 (移动端是横向 tab 条, 不放搜索) */}
      <div className="sticky top-0 z-[2] bg-[var(--surface)] px-3 pt-2 pb-2 border-b border-[color:var(--border-trhrp)] max-md:hidden">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索标的..."
          className="w-full rounded-md border border-[color:var(--border-trhrp)] bg-[var(--surface-2)] px-2.5 py-1.5 text-[12.5px] text-[var(--ink-2)] placeholder:text-[var(--sub-2)] focus:outline-none focus:border-[color:var(--accent-trhrp)] transition"
        />
        <div className="flex items-center gap-1 mt-2 flex-wrap">
          {REGIME_TABS.map((t) => {
            const on = regimeFilter === t.key
            return (
              <button
                key={t.key}
                onClick={() => setRegimeFilter(t.key)}
                className={`px-2 py-[2px] rounded text-[11px] font-medium border transition cursor-pointer ${
                  on
                    ? 'bg-[var(--accent-trhrp)] text-white border-transparent'
                    : 'bg-transparent text-[var(--sub)] border-[color:var(--border-trhrp)] hover:bg-[var(--surface-hover)]'
                }`}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </div>
      {Object.entries(groups).map(([grp, items]) => {
        const isCollapsed = collapsed.has(grp)
        return (
          <div key={grp}>
            {/* 分组标题: 可点击折叠/展开, 右侧显示该组数量 */}
            <button
              onClick={() => toggleGroup(grp)}
              className="w-full flex items-center justify-between gap-2 px-4 pt-3.5 pb-1.5 text-[10.5px] font-semibold text-[var(--sub-2)] uppercase tracking-[0.08em] max-md:hidden hover:text-[var(--ink-2)] transition cursor-pointer"
              title={isCollapsed ? '点击展开' : '点击折叠'}
            >
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block text-[9px] transition-transform"
                  style={{
                    transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                  }}
                >
                  ▼
                </span>
                {grp}
              </span>
              <span className="text-[var(--sub-2)] normal-case font-normal tracking-normal">
                {items.length}
              </span>
            </button>
            {!isCollapsed &&
              items.map((m) => {
                const isActive = m.label === active
                // 右侧数字: risk-on满仓 相对 基准(buy&hold) 的超额 = ronly_total − bench_total
                const ronlyVsBase = (m.ronly_total ?? 0) - (m.bench_total ?? 0)
                const excessCls = clsColor(ronlyVsBase)
                const rc = m.current_regime
                const rcBg = rc ? REGIME_BG[rc] : '#9e9e9e'
                const no = m.next_operation
                const nextOpArrow = no && no !== 'hold' ? OP_ARROW[no] : null
                const nextOpColor = no && no !== 'hold' ? OP_COLOR[no] : undefined
                const is7x24 = m.trading_hours === '7x24'
                // 7×24 连续交易: 信号即时生效, 无 T+1; 传统市场: T 日收盘信号 T+1 生效
                const nextLabel = is7x24 ? '最新信号(即时生效)' : '预计明日'
                const title = [
                  `risk-on满仓超额(满仓−基准): ${fmtPct(ronlyVsBase)}`,
                  `当前风险偏好: ${regimeCnLabel(rc, regimeCn)}`,
                  `最新操作: ${OP_LABEL[m.current_operation || 'hold'] || '—'}`,
                  m.next_regime
                    ? `${nextLabel}: ${regimeCnLabel(m.next_regime, regimeCn)} / ${OP_LABEL[no || 'hold']}`
                    : '',
                  is7x24 ? '交易时段: 7×24 连续 (信号即时生效, 无 T+1 延迟)' : '',
                  m.outlook_note ? `预警: ${m.outlook_note}` : '',
                  m.last_date ? `数据截至 ${m.last_date}` : '',
                  m.quality ? '优质标的' : '',
                ]
                  .filter(Boolean)
                  .join('\n')
                return (
                  <button
                    key={m.label}
                    onClick={() => onSelect(m.label)}
                    className={`flex items-center justify-between gap-2 w-full pl-3 pr-4 py-[7px] border-l-[3px] border-l-transparent bg-transparent text-[var(--ink-2)] text-[13px] text-left cursor-pointer hover:bg-[var(--surface-hover)] transition max-md:w-auto max-md:shrink-0 max-md:border-l-0 max-md:border-b-2 max-md:border-b-transparent max-md:px-2.5 max-md:py-1.5 ${
                      isActive
                        ? 'bg-[var(--accent-trhrp)]/10 border-l-[color:var(--accent-trhrp)] text-[var(--accent-strong)] font-semibold max-md:border-l-0 max-md:border-b-2 max-md:border-b-[color:var(--accent-trhrp)]'
                        : ''
                    }`}
                    title={title}
                    style={isActive ? {
                      background: 'color-mix(in srgb, var(--accent-trhrp) 14%, transparent)',
                      borderLeftColor: 'var(--accent-trhrp)',
                    } : { gap: 6 }}
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
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <span
                        style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          minWidth: 0,
                        }}
                      >
                        {m.label}
                      </span>
                      {/* 优质标的: label 后跟小 tag */}
                      {m.quality && (
                        <span
                          title="优质标的"
                          style={{
                            flexShrink: 0,
                            fontSize: 10,
                            lineHeight: 1,
                            padding: '2px 4px',
                            borderRadius: 3,
                            background: 'color-mix(in srgb, var(--accent-trhrp) 16%, transparent)',
                            color: 'var(--accent-strong)',
                            fontWeight: 600,
                          }}
                        >
                          优质
                        </span>
                      )}
                      {is7x24 && (
                        <span
                          title="7×24 连续交易, 信号即时生效无 T+1 延迟"
                          style={{
                            flexShrink: 0,
                            fontSize: 9,
                            fontWeight: 700,
                            color: '#fff',
                            background: '#00838f',
                            padding: '0 3px',
                            borderRadius: 3,
                            lineHeight: '14px',
                            letterSpacing: '0.02em',
                          }}
                        >
                          7×24
                        </span>
                      )}
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
                        className={`text-[11.5px] tabular-nums text-[var(--sub-2)] shrink-0 ${
                          isActive ? 'text-[var(--accent-strong)]' : excessCls
                        }`}
                      >
                        {fmtPct(ronlyVsBase, 0)}
                      </span>
                    </span>
                  </button>
                )
              })}
          </div>
        )
      })}
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
    { k: '主策略最大回撤', v: pct(rs.sMdd), cls: '!text-[var(--neg)]' },
    { k: '股现择时最大回撤', v: pct(rs.tMdd), cls: '!text-[var(--neg)]' },
    { k: '极值仓位最大回撤', v: pct(rs.eMdd), cls: '!text-[var(--neg)]' },
    { k: 'risk-on满仓最大回撤', v: pct(rs.rMdd), cls: '!text-[var(--neg)]' },
    { k: '标的最大回撤', v: pct(rs.bMdd), cls: '!text-[var(--neg)]' },
    { k: '主策略年化', v: fmtPct(rs.sAnn), cls: clsColor(rs.sAnn) },
    { k: '股现择时年化', v: fmtPct(rs.tAnn), cls: clsColor(rs.tAnn) },
    { k: '极值仓位年化', v: fmtPct(rs.eAnn), cls: clsColor(rs.eAnn) },
    { k: 'risk-on满仓年化', v: fmtPct(rs.rAnn), cls: clsColor(rs.rAnn) },
    { k: '标的年化', v: fmtPct(rs.bAnn), cls: clsColor(rs.bAnn) },
  ]
  return (
    <div className="bg-gradient-to-r from-[var(--accent-bg)] to-[var(--surface)] border border-[color:var(--accent-border)] border-l-[3px] border-l-[color:var(--accent-trhrp)] rounded-[10px] px-4 py-3.5">
      <h3 className="text-[13px] font-semibold text-[var(--ink)] m-0 mb-2.5 flex items-center gap-1.5">
        <span style={{ color: 'var(--accent-trhrp)' }}>●</span>
        区间收益统计（拖动下方缩放条选择区间）
      </h3>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-x-4 gap-y-2.5">
        {cards.map((c) => (
          <div key={c.k} className="flex flex-col gap-px">
            <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em]">
              {c.k}
            </div>
            <div
              className={`text-[13.5px] font-semibold tabular-nums text-[var(--ink)] ${c.cls}`}
            >
              {c.v}
            </div>
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
  // 7×24 连续交易 (crypto): 信号于日 K 收盘即时生效, 无 T+1 延迟;
  // 传统市场: T 日收盘信号, T+1 开盘生效.
  const is7x24 = summary.trading_hours === '7x24'
  const badge = (r: string | null | undefined) =>
    r ? (
      <span
        className="text-white px-2.5 py-0.5 rounded-md text-[13px] font-semibold inline-block whitespace-nowrap"
        style={{ background: REGIME_BG[r] }}
      >
        {regimeCnLabel(r, regimeCn)}
      </span>
    ) : (
      <span className="bg-slate-400 text-white px-2.5 py-0.5 rounded-md text-[13px] font-semibold inline-block">
        —
      </span>
    )

  // —— 最新一日信号分量 (驱动当前 regime 的原始信号) ——
  // vol: 当日 21 日年化波动率; vol_p60: 波动率 60 分位 (risk_off 触发线);
  // vol_med: 波动率中位数 (risk_on 触发线); mom: 21 日动量.
  const vol = summary.latest_vol
  const volP60 = summary.latest_vol_p60
  const volMed = summary.latest_vol_med
  const mom = summary.latest_mom
  const hasSignal =
    vol != null || volP60 != null || volMed != null || mom != null
  const fmtVol = (v: number | null | undefined) =>
    v == null ? '—' : `${(v * 100).toFixed(1)}%`
  // vol 落点色: vol > vol_p60 红(规避区), vol <= vol_med 绿(偏好区), 否则黄(中性)
  const volZoneColor = (() => {
    if (vol == null) return undefined
    if (volP60 != null && vol > volP60) return REGIME_BG.risk_off
    if (volMed != null && vol <= volMed) return REGIME_BG.risk_on
    return REGIME_BG.moderate
  })()
  // mom 色: >0 绿(上行), <0 红(下行)
  const momColor =
    mom == null
      ? undefined
      : mom > 0.0001
        ? REGIME_BG.risk_on
        : mom < -0.0001
          ? REGIME_BG.risk_off
          : REGIME_BG.moderate
  // vol vs 阈值差 (pp), 用来直观显示距离 risk_off 触发线多远
  const ppVsP60 =
    vol != null && volP60 != null ? (vol - volP60) * 100 : null

  // —— 切换条件分解 (解释 outlook_dist "距触发 X%" 的来源) ——
  // risk_off 触发 = vol>p60 且 mom<0; risk_on 触发 = vol≤中位数 且 mom>0.
  // 距离 = max(各条件的归一化 gap): 已满足条件 gap<0(负, 不构成约束),
  //        未满足条件 gap>0(正, 是瓶颈). 取 max → 瓶颈条件决定距离.
  const outlookState = summary.regime_outlook // 'stable'|'watch_risk_off'|'watch_risk_on'|'unknown'
  const watchTarget =
    outlookState === 'watch_risk_off'
      ? 'risk_off'
      : outlookState === 'watch_risk_on'
        ? 'risk_on'
        : null
  type CondStatus = {
    label: string
    met: boolean
    detail: string
    gap: number | null // 归一化距离, 负=已超阈值, 正=还差这么远
    binding: boolean // 是否瓶颈(决定 outlook_dist 的那个)
  }
  const conds: CondStatus[] = []
  if (watchTarget === 'risk_off' && vol != null && volP60 != null && mom != null) {
    const volGap = (volP60 - vol) / volP60 // >0=未满足(vol<p60), <0=已满足(vol>p60)
    const momGap = mom // >0=未满足(mom>0), <0=已满足(mom<0)
    const dist = Math.max(volGap, momGap)
    conds.push({
      label: 'vol > p60',
      met: vol > volP60,
      detail: `vol ${fmtVol(vol)} ${vol > volP60 ? '>' : '≤'} p60 ${fmtVol(volP60)}（${ppVsP60! >= 0 ? '+' : ''}${ppVsP60!.toFixed(1)}pp）`,
      gap: volGap,
      binding: Math.abs(volGap - dist) < 1e-9,
    })
    conds.push({
      label: 'mom < 0',
      met: mom < 0,
      detail: `mom ${fmtPct(mom, 1)} ${mom < 0 ? '<' : '≥'} 0`,
      gap: momGap,
      binding: Math.abs(momGap - dist) < 1e-9,
    })
  } else if (watchTarget === 'risk_on' && vol != null && volMed != null && mom != null) {
    const volGap = (vol - volMed) / volMed // >0=未满足(vol>中位), <0=已满足
    const momGap = -mom // >0=未满足(mom<0), <0=已满足(mom>0)
    const dist = Math.max(volGap, momGap)
    const ppVsMed = (vol - volMed) * 100
    conds.push({
      label: 'vol ≤ 中位数',
      met: vol <= volMed,
      detail: `vol ${fmtVol(vol)} ${vol <= volMed ? '≤' : '>'} 中位数 ${fmtVol(volMed)}（${ppVsMed >= 0 ? '+' : ''}${ppVsMed.toFixed(1)}pp）`,
      gap: volGap,
      binding: Math.abs(volGap - dist) < 1e-9,
    })
    conds.push({
      label: 'mom > 0',
      met: mom > 0,
      detail: `mom ${fmtPct(mom, 1)} ${mom > 0 ? '>' : '≤'} 0`,
      gap: momGap,
      binding: Math.abs(momGap - dist) < 1e-9,
    })
  }

  return (
    <div className="bg-[var(--surface)] border border-[color:var(--border-trhrp)] rounded-xl px-4 py-4 shadow-[var(--shadow-md)] min-w-0 max-w-full">
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <h3 className="text-sm font-semibold text-[var(--ink)] tracking-tight m-0 inline-flex items-center gap-2 flex-wrap">
          风险偏好状态（回测快照推演）
          {is7x24 ? (
            <span
              title="该标的为 7×24 连续交易, 信号于日 K 收盘即时生效, 无 T+1 延迟"
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: '#fff',
                background: '#00838f',
                padding: '1px 6px',
                borderRadius: 4,
                letterSpacing: '0.02em',
              }}
            >
              7×24 即时生效
            </span>
          ) : (
            <span
              title="该标的为日内收盘市场, T 日收盘信号 T+1 开盘生效"
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: 'var(--sub-2)',
                background: 'var(--surface-2)',
                border: '1px solid var(--border-trhrp)',
                padding: '1px 6px',
                borderRadius: 4,
                letterSpacing: '0.02em',
              }}
            >
              T+1 次日生效
            </span>
          )}
        </h3>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-5 gap-y-3 mt-0.5">
        <div className="flex flex-col gap-1">
          <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
            {is7x24 ? '当前生效' : '今日生效'}
          </div>
          <div className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap">
            {badge(cur)}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
            最新操作
          </div>
          <div
            className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap"
            style={{ color: OP_COLOR[curOp] }}
          >
            {OP_ARROW[curOp]} {OP_LABEL[curOp]}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
            {is7x24 ? '最新信号' : '预计下一风险偏好'}
            <span className="text-[10px] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[5px] ml-1 font-normal normal-case tracking-normal">
              {is7x24 ? '即时生效' : '预计'}
            </span>
          </div>
          <div className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap">
            {badge(next)}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
            {is7x24 ? '最新信号操作' : '预计明日操作'}
            <span className="text-[10px] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[5px] ml-1 font-normal normal-case tracking-normal">
              {is7x24 ? '即时生效' : '预计'}
            </span>
          </div>
          <div
            className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap"
            style={{ color: OP_COLOR[nextOp] }}
          >
            {OP_ARROW[nextOp]} {OP_LABEL[nextOp]}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
            数据截至
          </div>
          <div className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap">
            {summary.last_date || '—'}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
            当前股票仓位
          </div>
          <div className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap">
            {summary.current_equity_weight != null
              ? `${(summary.current_equity_weight * 100).toFixed(0)}%`
              : '—'}
          </div>
        </div>
      </div>

      {hasSignal && (
        <>
          <div
            style={{
              marginTop: 14,
              paddingTop: 12,
              borderTop: '1px dashed var(--border-trhrp)',
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: 'var(--sub-2)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: 8,
              }}
            >
              最新信号分量（截至 {summary.last_date || '—'}，驱动上方风险偏好判定）
            </div>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-5 gap-y-3 mt-0.5">
              <div className="flex flex-col gap-1">
                <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
                  当前波动率 vol
                  <span className="text-[10px] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[5px] ml-1 font-normal normal-case tracking-normal">
                    vol_21 年化
                  </span>
                </div>
                <div className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap">
                  <span
                    style={{
                      color: '#fff',
                      background: volZoneColor || '#9e9e9e',
                      padding: '2px 10px',
                      borderRadius: 6,
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    {fmtVol(vol)}
                  </span>
                  {ppVsP60 != null && (
                    <span
                      style={{
                        fontSize: 11,
                        color: ppVsP60 > 0 ? 'var(--neg)' : 'var(--sub-2)',
                      }}
                    >
                      vs p60 {ppVsP60 >= 0 ? '+' : ''}
                      {ppVsP60.toFixed(1)}pp
                    </span>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
                  波动率 p60
                  <span className="text-[10px] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[5px] ml-1 font-normal normal-case tracking-normal">
                    risk_off 触发线
                  </span>
                </div>
                <div
                  className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap"
                  style={{ color: 'var(--neg)' }}
                >
                  {fmtVol(volP60)}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
                  波动率中位数
                  <span className="text-[10px] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[5px] ml-1 font-normal normal-case tracking-normal">
                    risk_on 触发线
                  </span>
                </div>
                <div
                  className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap"
                  style={{ color: 'var(--pos)' }}
                >
                  {fmtVol(volMed)}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <div className="text-[10.5px] text-[var(--sub-2)] uppercase tracking-[0.05em] inline-flex items-center">
                  动量 mom
                  <span className="text-[10px] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[5px] ml-1 font-normal normal-case tracking-normal">
                    21 日
                  </span>
                </div>
                <div className="text-sm font-semibold text-[var(--ink)] inline-flex items-center gap-1.5 flex-wrap">
                  <span
                    style={{
                      color: '#fff',
                      background: momColor || '#9e9e9e',
                      padding: '2px 10px',
                      borderRadius: 6,
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    {mom == null ? '—' : fmtPct(mom, 1)}
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-2 text-[11px] leading-relaxed text-[var(--sub-2)]" style={{ marginTop: 6 }}>
              判定规则：vol &gt; p60 且 mom &lt; 0 → 风险规避；vol ≤ 中位数 且 mom
              &gt; 0 → 风险偏好；其余 → 中性。vol 色块按当前落点着色（绿=偏好区 /
              黄=中性区 / 红=规避区），mom 色块按涨跌着色。
            </div>

            {conds.length > 0 && (
              <div
                style={{
                  marginTop: 10,
                  padding: '8px 12px',
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border-trhrp)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              >
                <div style={{ marginBottom: 6, color: 'var(--sub)' }}>
                  切换至「{regimeCnLabel(watchTarget, regimeCn)}」条件分解
                  <span style={{ color: 'var(--sub-2)', marginLeft: 6 }}>
                    （距触发约 {(summary.outlook_dist ?? 0) * 100 | 0}%，瓶颈条件见 ▼ 标记）
                  </span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: '4px 16px',
                  }}
                >
                  {conds.map((c) => (
                    <div
                      key={c.label}
                      style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <span
                        style={{
                          color: '#fff',
                          background: c.met ? 'var(--pos)' : 'var(--neg)',
                          padding: '1px 6px',
                          borderRadius: 4,
                          fontSize: 10,
                          fontWeight: 700,
                          minWidth: 18,
                          textAlign: 'center',
                        }}
                      >
                        {c.met ? '✓' : '✗'}
                      </span>
                      <span style={{ color: 'var(--ink-2)', fontWeight: 500 }}>
                        {c.label}
                      </span>
                      {c.binding && (
                        <span
                          style={{
                            color: 'var(--warn)',
                            fontSize: 11,
                            fontWeight: 700,
                          }}
                          title="此条件未满足且是瓶颈，决定了上方「距触发」的百分比"
                        >
                          ▼ 瓶颈
                        </span>
                      )}
                      <span style={{ color: 'var(--sub)', fontSize: 11 }}>
                        {c.detail}
                      </span>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 6, fontSize: 11, color: 'var(--sub-2)' }}>
                  触发需<b>两个条件同时满足</b>。距离 = max(各条件归一化差距)：
                  已满足条件差距为负（不构成约束），未满足条件差距为正（是瓶颈）。
                  所以「距触发 X%」= 最不紧迫的那个未满足条件还差多少。
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {summary.outlook_note && (
        <div
          className={
            isUnknown
              ? 'mt-2 text-[11px] leading-relaxed text-[var(--sub-2)]'
              : 'mt-2.5 text-xs leading-relaxed text-[var(--warn)] bg-[var(--warn-bg)] border border-[color:var(--warn)] rounded-lg px-3 py-2'
          }
        >
          {summary.outlook_note}
        </div>
      )}
      <div className="mt-2 text-[11px] leading-relaxed text-[var(--sub-2)]">
        说明：回测为历史快照，无明日行情，故“{is7x24 ? '最新信号' : '预计'}”项为按最新收盘信号黏性外推、非实时交易指令；仅当最新信号临近切换阈值（10%
        缓冲）才向前推一档。{is7x24
          ? '该标的为 7×24 连续交易，信号于日 K 收盘即时生效，无 T+1 延迟。'
          : '该标的为日内收盘市场，T 日收盘信号 T+1 开盘生效。'}
        风险偏好色：绿=偏好·黄=中性·红=规避（语义色，非涨跌）；操作色：红=加仓·绿=减仓（A股惯例）。
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
    <div
      className="bg-[var(--surface-2)] border border-[color:var(--border-trhrp)] border-l-[3px] border-l-[color:var(--sub-2)] rounded-lg px-4 py-3 text-xs leading-[1.7] text-[var(--sub)] [&_b]:text-[var(--ink-2)] [&_b]:font-semibold [&_strong]:text-[var(--ink-2)] [&_strong]:font-semibold"
      style={{ marginTop: 12 }}
    >
      <b>{meta.label}（{meta.ticker}）策略参数{hasOverride ? ' · 含自定义覆盖' : ''}</b>
      {hasOverride && (
        <span className="text-[var(--neg)] font-semibold" style={{ marginLeft: 6 }}>
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
    // MDD 列(pct)改用热力背景着色, 见下方 cellStyle, 此处不再铺红字
    return ''
  }
  // 最佳收益(最高总收益): 在「全部 5 个总收益列(含基准)」中取最大, 仅橙色字体标出、不加 ★
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
  // 最佳策略 = 最高性价比策略: 只在 4 个「策略」变体(主策略/股现择时/极值仓位/risk-on满仓)中取最优,
  // 不含基准(buy&hold 不算策略)。用一枚金色 ★ 标出。
  // 判定口径 = 总收益 ÷ |最大回撤| (Calmar 式风险收益比) 最高, 且必须优于买入持有.
  // 若 4 个策略的 Calmar 均不如 BH, 则不标记最佳策略(矮子里拔将军会误导).
  const STRATEGY_KEYS: (keyof MarketSummary)[] = [
    'strat_total',
    'timing_total',
    'extreme_total',
    'ronly_total',
  ]
  const STRATEGY_TO_MDD: Record<string, keyof MarketSummary> = {
    strat_total: 'strat_mdd',
    timing_total: 'timing_mdd',
    extreme_total: 'extreme_mdd',
    ronly_total: 'ronly_mdd',
  }
  // 最佳策略(最高性价比): 4 个策略变体中 Calmar 最高, 且该 Calmar 须 > BH 的 Calmar → 金色 ★
  const bestRiskKeysFor = (m: TableView): Set<keyof TableView> => {
    const calmar = (totKey: keyof MarketSummary, mddKey: keyof MarketSummary) => {
      const tot = Number(m[totKey]) || 0
      const mdd = Math.abs(Number(m[mddKey]) || 0)
      return mdd > 1e-9 ? tot / mdd : Number.NEGATIVE_INFINITY
    }
    const vals = STRATEGY_KEYS.map((k) => calmar(k, STRATEGY_TO_MDD[k as string]))
    const max = Math.max(...vals)
    const benchCalmar = calmar('bench_total', 'bench_mdd')
    const set = new Set<keyof MarketSummary>()
    // 只有当最佳策略的 Calmar 严格优于 BH 时才标记
    if (max > Number.NEGATIVE_INFINITY && max > benchCalmar) {
      STRATEGY_KEYS.forEach((k, i) => {
        if (Math.abs(vals[i] - max) < 1e-6) set.add(k)
      })
    }
    return set
  }
  // —— 排序状态: sortKey=null 时按 group 升序再按 label 升序 (默认) ——
  const [sortKey, setSortKey] = useState<keyof TableView | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  // 数值类 fmt 按数值排, text 按字符串排
  const NUMERIC_FMT = new Set<string>(['pct', 'signed', 'int'])

  // 预计算每行的 viewOf + best/bestRisk 集合, 仅在 data.markets 变化时重算
  // (避免每次 render 对 187 行 × 9 字段重复计算)
  const rows = useMemo(() => {
    return markets.map((m) => {
      const v = viewOf(m)
      return { v, best: bestKeysFor(v), risk: bestRiskKeysFor(v) }
    })
    // viewOf/bestKeysFor/bestRiskKeysFor 为纯函数, 仅依赖 markets 数据, 故只盯 markets
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markets])

  // 排序后的行 (默认: group 升序 → label 升序)
  const sortedRows = useMemo(() => {
    const arr = [...rows]
    const colByKey = new Map(cols.map((c) => [c.key, c]))
    arr.sort((a, b) => {
      if (sortKey === null) {
        if (a.v.group !== b.v.group) return a.v.group < b.v.group ? -1 : 1
        return a.v.label < b.v.label ? -1 : 1
      }
      const col = colByKey.get(sortKey)
      const va = a.v[sortKey]
      const vb = b.v[sortKey]
      let r: number
      if (col && NUMERIC_FMT.has(col.fmt)) {
        r = (Number(va) || 0) - (Number(vb) || 0)
      } else {
        const sa = String(va)
        const sb = String(vb)
        r = sa < sb ? -1 : sa > sb ? 1 : 0
      }
      return sortDir === 'asc' ? r : -r
    })
    return arr
  }, [rows, sortKey, sortDir, NUMERIC_FMT])

  const onSort = (key: keyof TableView) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      const col = cols.find((c) => c.key === key)
      // 数值列首次点击默认降序 (看最优), 文本列默认升序
      setSortKey(key)
      setSortDir(col && NUMERIC_FMT.has(col.fmt) ? 'desc' : 'asc')
    }
  }
  return (
    <div className="bg-[var(--surface)] border border-[color:var(--border-trhrp)] rounded-xl shadow-[var(--shadow-md)] overflow-hidden min-w-0 max-w-full">
      <div className="px-4 pt-3 pb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-[var(--ink)] m-0">全市场汇总</h3>
        <span className="text-[11.5px] text-[var(--sub-2)]">
          点击行跳转到该标的图表 ·{' '}
          <span
            style={{
              color: 'var(--best-ink)',
              fontWeight: 700,
            }}
          >
            最佳收益(最高总收益)
          </span>
          （橙色字体，无 ★）·{' '}
          <span
            style={{
              color: 'var(--best-star)',
              fontWeight: 700,
            }}
          >
            ★ 最佳策略
        </span>
        （金色 ★：4 策略变体中 Calmar 最高且优于买入持有；若均不如 BH 则不标）·{' '}
        基准(buy&amp;hold) 仅参与「最佳收益」排名，不参与「最佳策略」（买入持有不算策略）·{' '}
          <strong>所有「超额」列均为相对基准(buy&amp;hold) 的超额收益</strong>
          （主策略/股现择时/极值仓位/risk-on满仓 各自 − 基准）·{' '}
          <span
            style={{
              background: 'rgba(229,57,53,0.18)',
              padding: '0 5px',
              borderRadius: 3,
            }}
          >
            最大回撤列按严重程度深浅红着色
          </span>
        </span>
      </div>
      <div className="overflow-auto max-h-[72vh]">
        <table className="w-full border-separate border-spacing-0 text-[12.5px]">
          <thead>
            <tr>
              {cols.map((c, idx) => {
                const on = sortKey === c.key
                return (
                  <th
                    key={c.key as string}
                    onClick={() => onSort(c.key)}
                    className={`sticky top-0 z-[3] bg-[var(--surface-2)] text-[var(--sub)] font-medium uppercase text-[10.5px] tracking-[0.05em] px-3 py-2 border-b border-[color:var(--border-strong)] whitespace-nowrap shadow-[0_2px_4px_-2px_rgba(15,23,42,0.12)] cursor-pointer select-none hover:text-[var(--ink-2)] transition ${
                      idx < 2 ? 'text-left' : 'text-right'
                    }`}
                    title="点击排序"
                  >
                    <span className="inline-flex items-center gap-1">
                      {c.label}
                      {on && (
                        <span
                          className="text-[9px]"
                          style={{ color: 'var(--accent-trhrp)' }}
                        >
                          {sortDir === 'asc' ? '▲' : '▼'}
                        </span>
                      )}
                    </span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map(({ v, best, risk }) => (
              <tr
                key={v.label}
                onClick={() => onSelect(v.label)}
                className={`cursor-pointer transition-colors hover:bg-[var(--surface-hover)] ${
                  v.label === active
                    ? '!bg-[var(--accent-bg)] shadow-[inset_2px_0_0_var(--accent-trhrp)]'
                    : ''
                }`}
                // 虚拟滚动: 让浏览器跳过不可见行的渲染 (行数多时显著降低绘制成本)
                style={{
                  contentVisibility: 'auto',
                  containIntrinsicSize: '34px',
                }}
              >
                {cols.map((c, idx) => {
                  const isBest = best.has(c.key)
                  const isRisk = risk.has(c.key)
                  const alignCls = idx < 2 ? 'text-left' : 'text-right'
                  const inkCls =
                    idx === 0
                      ? 'font-semibold text-[var(--ink)]'
                      : 'text-[var(--ink-2)]'
                  const tabularCls = idx < 2 ? '' : 'tabular-nums'
                  const tdBase = `px-3 py-[7px] border-b border-[color:var(--border-trhrp)] whitespace-nowrap ${alignCls} ${inkCls} ${tabularCls}`.replace(
                    /\s+/g,
                    ' ',
                  ).trim()
                  const cellCls = [
                    tdBase,
                    isBest ? '' : clsFor(v, c),
                    isBest ? '!text-[var(--best-ink)] !font-bold' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')
                  const cellStyle =
                    c.fmt === 'pct'
                      ? mddSeverityStyle(Math.abs(Number(v[c.key]) || 0))
                      : undefined
                  return (
                    <td
                      key={c.key as string}
                      className={cellCls}
                      style={cellStyle}
                    >
                      {/* 标的列(idx 0): 优质标的名称后跟小 tag */}
                      {idx === 0 && v.quality && (
                        <span
                          title="优质标的"
                          style={{
                            fontSize: 10,
                            lineHeight: 1,
                            padding: '1px 4px',
                            marginLeft: 4,
                            borderRadius: 3,
                            background: 'color-mix(in srgb, var(--accent-trhrp) 16%, transparent)',
                            color: 'var(--accent-strong)',
                            fontWeight: 600,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          优质
                        </span>
                      )}
                      {fmtVal(v, c)}
                      {isRisk && (
                        <span className="text-[var(--best-star)] font-bold">
                          {' ★'}
                        </span>
                      )}
                    </td>
                  )
                })}
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
  // 记住上次选中的标的, 刷新页面后仍停留在该标的而非列表第一个。
  const STORAGE_KEY = 'trhrp-backtest:activeLabel'
  const [activeLabel, setActiveLabel] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    try {
      return window.localStorage.getItem(STORAGE_KEY) || null
    } catch {
      return null
    }
  })
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

  // activeLabel 变化时持久化到 localStorage
  const selectLabel = useCallback((label: string) => {
    setActiveLabel(label)
    try {
      window.localStorage.setItem(STORAGE_KEY, label)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    if (!data || !data.markets.length) return
    // 存储的标的已不在列表里(被下线) → 回退到第一个
    if (!activeLabel || !data.markets.some((m) => m.label === activeLabel)) {
      selectLabel(data.markets[0].label)
    }
  }, [data, activeLabel, selectLabel])

  if (state === 'loading' && !data) {
    return (
      <div className="my-20 mx-auto max-w-[560px] text-center text-[var(--sub)] text-sm">
        加载回测数据中…
      </div>
    )
  }
  if (state === 'error' && !data) {
    return (
      <div className="my-20 mx-auto max-w-[560px] bg-[var(--surface)] border border-[color:var(--border-trhrp)] border-l-[3px] border-l-[color:var(--neg)] rounded-[10px] px-7 py-6 shadow-[var(--shadow-lg)]">
        <h1 className="text-lg font-semibold text-[var(--neg)] m-0 mb-2">
          数据加载失败
        </h1>
        <p className="text-[var(--sub)] text-[13px] mb-4 leading-relaxed">
          {error}
        </p>
        <button
          onClick={refresh}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[color:var(--accent-trhrp)] bg-[var(--accent-trhrp)] text-white text-[13px] font-medium cursor-pointer hover:bg-[var(--accent-strong)] active:translate-y-px focus-visible:outline-2 focus-visible:outline-[var(--accent-trhrp)] focus-visible:outline-offset-2 transition"
        >
          重试
        </button>
      </div>
    )
  }
  if (!data || !activeLabel) return null

  const sm = result?.summary
  // 标的最新价 + 区间涨跌 (来自 timeseries 首尾原始价格 p)
  const tsArr = result?.timeseries
  const lastPt = tsArr && tsArr.length ? tsArr[tsArr.length - 1] : undefined
  const firstPt = tsArr && tsArr.length ? tsArr[0] : undefined
  const lastPrice = lastPt?.p
  const priceChg =
    lastPrice != null && firstPt?.p ? lastPrice / firstPt.p - 1 : null
  const lastPoll = new Date().toLocaleTimeString('zh-CN', {
    hour12: false,
  })

  // 当前选中标的的概要信息 (result.meta 未就绪时回退到 overview markets)
  const meta = result?.meta
  const ovMarket = data.markets.find((m) => m.label === activeLabel)
  const curLabel = meta?.label || activeLabel || ''
  const curTicker = meta?.ticker || ovMarket?.ticker || ''
  const curGroup = meta?.market || ovMarket?.group || ''
  const curProxy = meta?.proxy || ''
  const is7x24 = (sm?.trading_hours || ovMarket?.trading_hours) === '7x24'

  return (
    <div
      className="min-h-[100dvh] bg-[var(--page-bg)] text-[var(--ink)]"
      style={{ fontFeatureSettings: "'tnum' 1, 'cv11' 1" }}
    >
      <header className="bg-[var(--header-bg)] border-b border-[color:var(--header-border)] px-6 py-3.5 flex items-center justify-between gap-4 sticky top-0 z-20 backdrop-blur">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className="w-[3px] h-[26px] rounded-sm bg-gradient-to-b from-[var(--accent-trhrp)] to-cyan-500 shrink-0"
            aria-hidden
          />
          <div>
            <h1 className="text-[17px] font-semibold tracking-tight text-slate-100 leading-tight m-0">
              TRHRP 多市场回测 · 策略 vs 买入持有
            </h1>
            <div className="mt-[3px] text-xs text-[var(--header-sub)] tabular-nums">
              {generatedAt
                ? `数据生成于 ${generatedAt.slice(0, 19).replace('T', ' ')} UTC`
                : ''}
              {` · 自动刷新 ${REFRESH_MS / 1000}s（上次 ${lastPoll}）`}
            </div>
          </div>
        </div>
        <button
          onClick={refresh}
          className="inline-flex items-center gap-1.5 px-3.5 py-[7px] rounded-lg border border-slate-400/25 bg-slate-400/10 text-slate-200 text-[13px] font-medium cursor-pointer hover:bg-slate-400/16 hover:border-slate-400/40 active:translate-y-px focus-visible:outline-2 focus-visible:outline-[var(--accent-trhrp)] focus-visible:outline-offset-2 transition"
        >
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

      <div className="flex items-start min-h-[calc(100dvh-64px)] max-md:flex-col">
        <aside className="sticky top-16 h-[calc(100dvh-64px)] w-56 shrink-0 overflow-y-auto bg-[var(--surface)] border-r border-[color:var(--border-trhrp)] py-2 pb-6 max-md:static max-md:top-0 max-md:h-auto max-md:w-full max-md:border-r-0 max-md:border-b max-md:border-[color:var(--border-trhrp)] max-md:flex max-md:overflow-x-auto max-md:px-3 max-md:py-2 max-md:gap-1 max-md:shrink-0">
          <Sidebar
            markets={data.markets}
            active={activeLabel}
            onSelect={selectLabel}
            regimeCn={data?.regime_cn || {}}
          />
        </aside>

        <main className="flex-1 min-w-0 max-w-full overflow-hidden flex flex-col gap-3 px-3 pb-8 pt-3 sm:gap-4 sm:px-6 sm:pb-10 sm:pt-5">
          {/* 当前标的标识栏: 让用户一眼看清详情区看的是哪个标的 */}
          <div className="flex items-baseline gap-3 flex-wrap px-1">
            <h2 className="text-[22px] font-bold tracking-tight text-[var(--ink)] m-0 leading-tight">
              {curLabel}
            </h2>
            <span className="text-[13px] font-medium text-[var(--sub)] tabular-nums">
              {curTicker}
            </span>
            {curGroup && (
              <span
                className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-[var(--sub-2)] border border-[color:var(--border-trhrp)] rounded px-[7px] py-[2px]"
              >
                {curGroup}
              </span>
            )}
            {is7x24 && (
              <span
                title="7×24 连续交易, 信号即时生效无 T+1 延迟"
                style={{
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: '#fff',
                  background: '#00838f',
                  padding: '1px 7px',
                  borderRadius: 4,
                  letterSpacing: '0.02em',
                }}
              >
                7×24
              </span>
            )}
            {curProxy && (
              <span className="text-[11px] text-[var(--sub-2)]">
                · {curProxy}
              </span>
            )}
            <span className="text-[11.5px] text-[var(--sub-2)] tabular-nums ml-auto">
              {meta ? `${meta.start} ~ ${meta.end?.slice(0, 4)} · ${meta.days} 天` : ''}
            </span>
          </div>

          {sm && (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2">
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
                label={`最新价${sm?.last_date ? ` ${sm.last_date.slice(5)}` : ''}`}
                value={fmtPrice(lastPrice)}
                sub={priceChg != null ? `区间 ${fmtPct(priceChg)}` : undefined}
                tone={priceChg != null ? (priceChg >= 0 ? 'pos' : 'neg') : 'plain'}
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

          <RangeStatsPanel rs={rangeStats} />

          <div className="rounded-xl border border-[color:var(--border-trhrp)] bg-[var(--surface)] shadow-md p-2 sm:p-4">
            {resultLoading && !result && (
              <div className="text-xs text-[var(--sub-2)] py-1 pb-2">
                加载标的序列…
              </div>
            )}
            <div ref={mainRef} className="w-full h-[360px] sm:h-[520px]" />
            <div className="text-xs text-[var(--sub)] leading-relaxed mt-2 [&_b]:text-[var(--ink-2)] [&_b]:font-semibold">
              <b>绿带</b>=风险偏好 · <b>黄带</b>=中性 · <b>红带</b>=风险规避；▲红=加仓，
              ▼绿=减仓（落在归一价曲线上）。左轴净值、右轴归一价。
              <b style={{ color: '#ef6c00' }}>橙虚线</b>=股现择时净值（equity 权重同主策略，其余全现金 SGOV，不含 GLD 防御腿）；
              <b style={{ color: '#6a1b9a' }}>紫点线</b>=极值仓位（把股现择时的连续仓位推到极值：risk_on=满仓 / moderate=半仓 / risk_off=空仓，非标的全 SGOV）；
              <b style={{ color: '#00838f' }}>青虚线</b>=risk-on满仓（仅 risk_on 满仓 equity，moderate/risk_off 全部现金 SGOV 空仓，二元择时）。
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--border-trhrp)] bg-[var(--surface)] shadow-md p-2 sm:p-4">
            <div className="flex items-baseline justify-between gap-3 mb-2">
              <h3 className="text-sm font-semibold text-[var(--ink)] tracking-tight m-0">
                股票仓位 % 与波动率%（与上方联动缩放）
              </h3>
            </div>
            <div ref={weightRef} className="w-full h-[150px] sm:h-[200px]" />
            <div className="text-xs text-[var(--sub)] leading-relaxed mt-2 [&_b]:text-[var(--ink-2)] [&_b]:font-semibold">
              紫线 = 每日股票仓位（左轴）；<b style={{ color: '#00838f' }}>青线</b>=vol21 年化波动率（右轴）；
              虚线参考
              <b style={{ color: 'var(--neg)' }}> 清仓 0%</b> /
              <b style={{ color: 'var(--warn)' }}> risk_off 下限 20%</b> /
              <b style={{ color: 'var(--pos)' }}> risk_on 80%</b>。
              vol 飙升即触发 risk_off 的核心信号。
            </div>
          </div>

          {result && <SignalParamsNote params={result.params} meta={result.meta} />}

          <SummaryTable
            markets={data.markets}
            active={activeLabel}
            onSelect={selectLabel}
          />

          <div className="bg-[var(--surface-2)] border border-[color:var(--border-trhrp)] border-l-[3px] border-l-[color:var(--sub-2)] rounded-lg px-4 py-3 text-xs leading-[1.7] text-[var(--sub)] [&_b]:text-[var(--ink-2)] [&_b]:font-semibold [&_strong]:text-[var(--ink-2)] [&_strong]:font-semibold">
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

          <div className="bg-[var(--surface-2)] border border-[color:var(--border-trhrp)] border-l-[3px] border-l-[color:var(--sub-2)] rounded-lg px-4 py-3 text-xs leading-[1.7] text-[var(--sub)] [&_b]:text-[var(--ink-2)] [&_b]:font-semibold [&_strong]:text-[var(--ink-2)] [&_strong]:font-semibold">
            <b>口径与数据说明：</b>
            FX 约定：全部按 USD 计价。策略与基准同币种，相对价值（超额/回撤改善）不受影响；
            A/H 标的绝对收益含轻微汇率漂移（港股近似无，人民币有）。操作点 = 股票仓位变动（加仓▲/减仓▼），
            来自当前 monitor/trhrp_strategy 口径（高波动资产 relative_zscore 重校准 + 分组 z 叠加）。
            <br />
            <span className="text-[var(--neg)] font-semibold">数据修正：</span>
            原 SGOV_combined.csv 已损坏（价格反复锯齿、单日 ±12% 数百次），已全部 22 标的改用干净的
            <b> SHY.csv</b> 作短债防御腿（等价替代，覆盖 2018–2026）。
            此前 risk_off 期间净值的异常暴跌/尖刺均因此坏数据，现已消除。
          </div>
        </main>
      </div>
    </div>
  )
}
