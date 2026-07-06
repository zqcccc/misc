'use client'

import type { InstrumentPayload } from '../types'

interface ThemeColors {
  isDark: boolean
  axisLabel: string
  splitLine: string
  axisLine: string
  legend: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  price: string
  ema: string
  equity: string
  hold: string
  longOpen: string
  shortOpen: string
  tp: string
  longBg: string
  shortBg: string
  flatBg: string
  nowLine: string
  entryLine: string
  forward: string
  realTp: string
  realReversal: string
}

function getThemeColors(): ThemeColors {
  const isDark = document.documentElement.classList.contains('dark')
  return {
    isDark,
    axisLabel: isDark ? '#64748b' : '#94a3b8',
    splitLine: isDark ? 'rgba(255,255,255,0.04)' : '#f1f5f9',
    axisLine: isDark ? 'rgba(255,255,255,0.06)' : '#e2e8f0',
    legend: isDark ? '#94a3b8' : '#64748b',
    tooltipBg: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)',
    tooltipBorder: isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0',
    tooltipText: isDark ? '#e2e8f0' : '#1e293b',
    price: isDark ? '#cbd5e1' : '#475569',
    ema: isDark ? '#60a5fa' : '#3b82f6',
    equity: isDark ? '#34d399' : '#10b981',
    hold: isDark ? '#64748b' : '#94a3b8',
    longOpen: '#ef4444',
    shortOpen: '#3b82f6',
    tp: '#f97316',
    longBg: isDark ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.06)',
    shortBg: isDark ? 'rgba(59, 130, 246, 0.08)' : 'rgba(59, 130, 246, 0.06)',
    flatBg: isDark ? 'rgba(148, 163, 184, 0.04)' : 'rgba(148, 163, 184, 0.03)',
    nowLine: '#fbbf24',
    entryLine: '#a78bfa',
    forward: '#a855f7',
    realTp: '#dc2626',
    realReversal: '#7c3aed',
  }
}

function toMs(iso: string | undefined): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : t
}

/**
 * 构造 echarts option: 双 grid (上图价格+EMA+买卖点, 下图净值 vs 买入持有)
 * 共享 x 轴 dataZoom. 在 "最新收盘" 处画一条垂直 nowLine 标记当前监控位置.
 */
export function buildChartOption(inst: InstrumentPayload): Record<string, unknown> {
  const c = getThemeColors()
  const cfg = inst.config

  // ---- 反手开仓点 (按新方向分组) ----
  const longOpens = inst.trades
    .filter((t) => t.new_dir === 1)
    .map((t) => ({ coord: [toMs(t.t), t.price], value: t }))
  const shortOpens = inst.trades
    .filter((t) => t.new_dir === -1)
    .map((t) => ({ coord: [toMs(t.t), t.price], value: t }))
  const tpPoints = inst.tps.map((t) => ({ coord: [toMs(t.t), t.price], value: t }))

  // ---- 持仓背景区段 (markArea) ----
  const posMarkAreas = inst.pos_segments.map((seg) => {
    const t0 = toMs(seg.t0)
    const t1 = toMs(seg.t1)
    if (t0 == null || t1 == null) return null
    const color = seg.pos === 1 ? c.longBg : seg.pos === -1 ? c.shortBg : c.flatBg
    return [
      { xAxis: t0, itemStyle: { color, borderColor: 'transparent' } },
      { xAxis: t1 },
    ]
  }).filter(Boolean) as Array<unknown>

  // ---- 当前位置标记 ----
  const nowMs = toMs(inst.current.last_closed)
  const livePrice = inst.current.live_price
  const entryPrice = inst.current.entry_price
  const entryMs = toMs(inst.current.entry_time)
  const position = inst.current.position ?? 0
  const lastEquity = inst.series.equity.length > 0
    ? inst.series.equity[inst.series.equity.length - 1][1]
    : null

  const dirLabel = position === 1 ? '做多' : position === -1 ? '做空' : '空仓'
  const posSizePct = Math.round((inst.current.pos_size ?? 0) * 100)
  const unrealPct = (inst.current.unreal_pct ?? 0) * 100

  // ---- 真实变仓事件 (从 trade_log, daemon 实际触发的) ----
  const forwardEvents = inst.forward?.events ?? []
  const realReversals = forwardEvents.filter((e) => e.type === 'reversal')
  const realTps = forwardEvents.filter((e) => e.type === 'partial_tp')
  const realReversalData = realReversals
    .map((e) => {
      const ms = toMs(e.ts)
      return ms != null ? ([ms, e.price] as [number, number]) : null
    })
    .filter(Boolean) as [number, number][]
  const realTpData = realTps
    .map((e) => {
      const ms = toMs(e.ts)
      return ms != null ? ([ms, e.price] as [number, number]) : null
    })
    .filter(Boolean) as [number, number][]
  const forwardEquityCurve = inst.forward?.equity_curve ?? []

  // 反手点 tooltip 格式化
  const tradeTooltipFormatter = (p: { data?: { value?: unknown } }) => {
    // p.data.value = [ts_ms, price]
    return ''
  }

  // 反手 scatter 数据: echarts 需要 [[x, y], ...]
  const longOpenData = longOpens.map((o) => o.coord)
  const shortOpenData = shortOpens.map((o) => o.coord)
  const tpData = tpPoints.map((o) => o.coord)

  // 价格图的 markLine: 当前位置垂直线 + 开仓价水平线
  const priceMarkLines: unknown[] = []
  if (nowMs != null) {
    priceMarkLines.push([
      { xAxis: nowMs, label: { formatter: '现在', color: c.nowLine, position: 'insideEndTop' } },
      { xAxis: nowMs },
    ])
  }
  if (position !== 0 && entryPrice && entryPrice > 0 && entryMs != null) {
    priceMarkLines.push([
      {
        xAxis: entryMs,
        label: { formatter: `开仓 ${dirLabel} ${posSizePct}%`, color: c.entryLine, position: 'insideStartTop' },
      },
      { xAxis: entryMs },
    ])
    priceMarkLines.push([
      { yAxis: entryPrice, label: { formatter: `入场 ${entryPrice.toFixed(4)}`, color: c.entryLine, position: 'insideEndTop' } },
      { yAxis: entryPrice },
    ])
  }

  // 净值图的 markLine: 当前位置垂直线
  const equityMarkLines: unknown[] = []
  if (nowMs != null) {
    equityMarkLines.push([
      { xAxis: nowMs, label: { formatter: '现在', color: c.nowLine, position: 'insideEndTop' } },
      { xAxis: nowMs },
    ])
  }
  if (lastEquity != null) {
    equityMarkLines.push([
      {
        yAxis: lastEquity,
        label: {
          formatter: `策略净值 ${lastEquity.toFixed(3)} (${unrealPct >= 0 ? '+' : ''}${unrealPct.toFixed(2)}%浮盈)`,
          color: c.equity,
          position: 'insideEndTop',
        },
      },
      { yAxis: lastEquity },
    ])
  }

  const baseAxis = {
    type: 'time',
    axisLine: { lineStyle: { color: c.axisLine } },
    axisLabel: { color: c.axisLabel, hideOverlap: true },
    splitLine: { show: false },
  }

  const baseYAxis = {
    type: 'value',
    scale: true,
    axisLine: { lineStyle: { color: c.axisLine } },
    axisLabel: { color: c.axisLabel },
    splitLine: { lineStyle: { color: c.splitLine } },
  }

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: [
      { left: 60, right: 30, top: 40, height: '52%' },
      { left: 60, right: 30, top: '64%', height: '32%' },
    ],
    legend: {
      top: 8,
      textStyle: { color: c.legend, fontSize: 11 },
      itemWidth: 14,
      itemHeight: 8,
      data: [
        { name: '价格', icon: 'roundRect' },
        { name: `EMA${cfg.ema_span}`, icon: 'roundRect' },
        { name: '反手开多', icon: 'triangle' },
        { name: '反手开空', icon: 'pin' },
        { name: '部分止盈', icon: 'circle' },
        { name: '真实反手', icon: 'diamond' },
        { name: '真实止盈', icon: 'circle' },
        { name: '策略净值', icon: 'roundRect' },
        { name: '买入持有', icon: 'roundRect' },
        { name: '前向净值(真实)', icon: 'roundRect' },
      ],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', link: [{ xAxisIndex: 'all' }] },
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.tooltipText, fontSize: 12 },
      formatter: (params: Array<{ axisValue: number; seriesName: string; value: number | number[] }>) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const ts = new Date(params[0].axisValue)
        const tsStr = `${ts.getUTCFullYear()}-${String(ts.getUTCMonth() + 1).padStart(2, '0')}-${String(ts.getUTCDate()).padStart(2, '0')} ${String(ts.getUTCHours()).padStart(2, '0')}:${String(ts.getUTCMinutes()).padStart(2, '0')} UTC`
        const lines = params.map((p) => {
          const v = Array.isArray(p.value) ? p.value[1] : p.value
          if (v == null) return null
          const num = typeof v === 'number' ? v : Number(v)
          return `<span style="color:${c.legend}">${p.seriesName}</span>: <b>${num.toFixed(4)}</b>`
        }).filter(Boolean)
        return `${tsStr}<br/>${lines.join('<br/>')}`
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 70,
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 8,
        height: 18,
        borderColor: c.axisLine,
        fillerColor: c.isDark ? 'rgba(59,130,246,0.15)' : 'rgba(59,130,246,0.1)',
        handleStyle: { color: '#3b82f6' },
        textStyle: { color: c.axisLabel },
        labelFormatter: (val: number) => {
          const d = new Date(val)
          return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
        },
      },
    ],
    xAxis: [baseAxis, baseAxis],
    yAxis: [
      { ...baseYAxis, name: '价格', nameTextStyle: { color: c.axisLabel, fontSize: 11 } },
      { ...baseYAxis, name: '净值', nameTextStyle: { color: c.axisLabel, fontSize: 11 } },
    ],
    series: [
      // ===== 上图: 价格 + EMA + 标记 =====
      {
        name: '价格',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: inst.series.price,
        showSymbol: false,
        symbol: 'none',
        lineStyle: { color: c.price, width: 1 },
        markArea: posMarkAreas.length > 0 ? { silent: true, data: posMarkAreas } : undefined,
        markLine: priceMarkLines.length > 0 ? {
          symbol: 'none',
          silent: true,
          lineStyle: { type: 'dashed', width: 1 },
          data: priceMarkLines,
        } : undefined,
        z: 2,
      },
      {
        name: `EMA${cfg.ema_span}`,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: inst.series.ema,
        showSymbol: false,
        symbol: 'none',
        lineStyle: { color: c.ema, width: 1, opacity: 0.85 },
        z: 3,
      },
      {
        name: '反手开多',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: longOpenData,
        symbol: 'triangle',
        symbolSize: 9,
        itemStyle: { color: c.longOpen, borderColor: '#fff', borderWidth: 0.5 },
        z: 5,
        tooltip: { formatter: () => '▲ 反手开多' },
      },
      {
        name: '反手开空',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: shortOpenData,
        symbol: 'pin',
        symbolSize: 9,
        itemStyle: { color: c.shortOpen, borderColor: '#fff', borderWidth: 0.5 },
        z: 5,
        tooltip: { formatter: () => '▼ 反手开空' },
      },
      {
        name: '部分止盈',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: tpData,
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: { color: c.tp, borderColor: '#fff', borderWidth: 0.3, opacity: 0.85 },
        z: 4,
        tooltip: { formatter: () => '● 部分止盈' },
      },
      // ===== 上图: 真实变仓标记 (从 trade_log, 加大加粗) =====
      {
        name: '真实反手',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: realReversalData,
        symbol: 'diamond',
        symbolSize: 14,
        itemStyle: { color: c.realReversal, borderColor: '#fff', borderWidth: 1.5 },
        z: 8,
        tooltip: {
          formatter: (p: { value: [number, number] }) => {
            const ev = realReversals.find((e) => toMs(e.ts) === p.value[0])
            if (!ev) return '◆ 真实反手'
            const dir = (d?: number) => (d === 1 ? '多' : d === -1 ? '空' : '空仓')
            const netPct = ((ev.net ?? 0) * 100).toFixed(2)
            const cap = (ev.capital_after ?? 1).toFixed(4)
            return `◆ 真实反手 ${dir(ev.old_dir)}→${dir(ev.new_dir)} @ ${ev.price.toFixed(4)}<br/>净收益 ${netPct}%  资金 ${cap}`
          },
        },
      },
      {
        name: '真实止盈',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: realTpData,
        symbol: 'circle',
        symbolSize: 11,
        itemStyle: { color: c.realTp, borderColor: '#fff', borderWidth: 1.2 },
        z: 7,
        tooltip: {
          formatter: (p: { value: [number, number] }) => {
            const ev = realTps.find((e) => toMs(e.ts) === p.value[0])
            if (!ev) return '● 真实止盈'
            const before = Math.round((ev.pos_size_before ?? 0) * 100)
            const after = Math.round((ev.pos_size_after ?? 0) * 100)
            const netPct = ((ev.net ?? 0) * 100).toFixed(2)
            const cap = (ev.capital_after ?? 1).toFixed(4)
            return `● 真实止盈 ${before}%→${after}% @ ${ev.price.toFixed(4)}<br/>净收益 ${netPct}%  资金 ${cap}`
          },
        },
      },
      // ===== 下图: 净值 vs 买入持有 + 前向净值 =====
      {
        name: '策略净值',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: inst.series.equity,
        showSymbol: false,
        symbol: 'none',
        lineStyle: { color: c.equity, width: 1.4 },
        markLine: equityMarkLines.length > 0 ? {
          symbol: 'none',
          silent: true,
          lineStyle: { type: 'dashed', width: 1 },
          data: equityMarkLines,
        } : undefined,
        z: 2,
      },
      {
        name: '买入持有',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: inst.series.hold,
        showSymbol: false,
        symbol: 'none',
        lineStyle: { color: c.hold, width: 1, opacity: 0.8, type: 'dashed' },
        z: 1,
      },
      {
        name: '前向净值(真实)',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: forwardEquityCurve,
        showSymbol: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: c.forward, width: 1.8 },
        itemStyle: { color: c.forward },
        z: 4,
        tooltip: {
          formatter: (p: { value: [number, number] }) => {
            const pct = ((p.value[1] - 1) * 100).toFixed(2)
            const sign = p.value[1] >= 1 ? '+' : ''
            return `前向净值: ${p.value[1].toFixed(4)} (累计 ${sign}${pct}%)`
          },
        },
      },
    ],
  }
}
