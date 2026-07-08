// TRHRP 回测图表的 ECharts option 构建 + 区间统计计算。
// 原样移植自 scripts/build_trhrp_dashboard.py 的 render/renderStat/updateRangeStats,
// 从原生 HTML 看板搬到 Next 客户端组件。
import type { TsPoint, MarketResult, RangeStats, RegimeCn } from './types'

const BAND: Record<string, string> = {
  risk_on: 'rgba(46,125,50,0.07)',
  moderate: 'rgba(250,200,40,0.09)',
  risk_off: 'rgba(229,57,53,0.07)',
}
const REGIME_COLOR: Record<string, string> = {
  risk_on: '#2e7d32',
  moderate: '#b58900',
  risk_off: '#d32f2f',
}
const OP_CN: Record<string, string> = {
  add: '加仓',
  reduce: '减仓',
  hold: '持有',
}

const isDark = () =>
  typeof document !== 'undefined' &&
  document.documentElement.classList.contains('dark')

/** 图表文字配色: 跟随页面 light/dark 主题, 保证图例/坐标轴在两种模式下都清晰 */
function themeColors(d: boolean) {
  return {
    legend: d ? '#cbd5e1' : '#334155',
    axis: d ? '#94a3b8' : '#64748b',
    nameGreen: d ? '#4ade80' : '#2e7d32',
    nameBlue: d ? '#60a5fa' : '#1565c0',
    // markLine 参考线标签: 暗色下用更亮的同色系, 否则压在深底上看不清
    lineRed: d ? '#ef5350' : '#b71c1c',
    lineOrange: d ? '#ffb74d' : '#ef6c00',
    lineGreen: d ? '#66bb6a' : '#2e7d32',
  }
}

export function pct(x: number): string {
  return (x * 100).toFixed(1) + '%'
}
export function signed(x: number): string {
  return (x >= 0 ? '+' : '') + (x * 100).toFixed(1) + '%'
}

/** 把连续相同 regime 的时段合并成 markArea 区间 */
export function bandRuns(ts: TsPoint[]) {
  const runs: any[] = []
  let cur: any = null
  ts.forEach((pt, i) => {
    if (!cur || pt.r !== cur.r) {
      if (cur) {
        cur.end = ts[i - 1].d
        runs.push(cur)
      }
      cur = { r: pt.r, start: pt.d }
    }
  })
  if (cur) {
    cur.end = ts[ts.length - 1].d
    runs.push(cur)
  }
  return runs.map((r) => [
    { xAxis: r.start, itemStyle: { color: BAND[r.r] || 'transparent' } },
    { xAxis: r.end },
  ])
}

function axisTooltip(regimeCn: RegimeCn) {
  return {
    trigger: 'axis',
    axisPointer: { type: 'cross' },
    confine: true,
    formatter: function (params: any) {
      const line = params.find(
        (p: any) =>
          p.seriesName === '策略净值' || p.seriesName === '标的价格(归一)',
      )
      if (!line || !line.data || typeof line.data !== 'object') return ''
      const d = line.data
      const dt = d.value[0]
      const rc = REGIME_COLOR[d.r] || '#555'
      let h = `<div style="font-weight:600;margin-bottom:4px">${dt}</div>`
      h += `<span style="color:${rc};font-weight:600">${
        regimeCn[d.r] || d.r
      }</span> `
      h += `<b>操作:</b> ${OP_CN[d.o] || d.o}`
      if (d.o !== 'hold') h += ` (Δ股票仓位 ${(d.dw * 100).toFixed(0)}pp)`
      h += `<br/><b>主策略净值:</b> ${d.s.toFixed(3)} &nbsp; <b>基准:</b> ${d.b.toFixed(
        3,
      )} &nbsp; <b>股现择时:</b> ${d.c != null ? d.c.toFixed(3) : '—'} &nbsp; <b>极值仓位:</b> ${d.e != null ? d.e.toFixed(3) : '—'} &nbsp; <b>risk-on满仓:</b> ${d.ro != null ? d.ro.toFixed(3) : '—'}`
      h += `<br/><b>股票权重:</b> ${(d.we * 100).toFixed(0)}% &nbsp; <b>标的(归一):</b> ${d.p.toFixed(
        3,
      )} &nbsp; <b>vol21:</b> ${d.v != null ? (d.v * 100).toFixed(1) + '%' : '—'}`
      return h
    },
  }
}

/** 主图: 策略净值 + 基准 + 归一价 + 加/减仓三角标记 + regime 背景带 */
export function buildMainOption(
  res: MarketResult,
  regimeCn: RegimeCn,
  isDarkMode: boolean = isDark(),
) {
  const ts = res.timeseries
  const p0 = ts[0].p
  const navData = ts.map((pt) => ({
    value: [pt.d, pt.s],
    r: pt.r,
    o: pt.o,
    dw: pt.dw,
    we: pt.we,
    s: pt.s,
    b: pt.b,
    c: pt.c,
    e: pt.e,
    ro: pt.ro,
    v: pt.v,
    p: pt.p / p0,
  }))
  const cashData = ts.map((pt) => ({
    value: [pt.d, pt.c],
    r: pt.r,
    o: pt.o,
    dw: pt.dw,
    we: pt.we,
    s: pt.s,
    b: pt.b,
    c: pt.c,
    e: pt.e,
    ro: pt.ro,
    v: pt.v,
    p: pt.p / p0,
  }))
  const extremeData = ts.map((pt) => ({
    value: [pt.d, pt.e],
    r: pt.r,
    o: pt.o,
    dw: pt.dw,
    we: pt.we,
    s: pt.s,
    b: pt.b,
    c: pt.c,
    e: pt.e,
    ro: pt.ro,
    v: pt.v,
    p: pt.p / p0,
  }))
  const priceData = ts.map((pt) => ({
    value: [pt.d, pt.p / p0],
    r: pt.r,
    o: pt.o,
    dw: pt.dw,
    we: pt.we,
    s: pt.s,
    b: pt.b,
    c: pt.c,
    e: pt.e,
    ro: pt.ro,
    v: pt.v,
    p: pt.p / p0,
  }))
  const ronlyData = ts.map((pt) => ({
    value: [pt.d, pt.ro],
    r: pt.r,
    o: pt.o,
    dw: pt.dw,
    we: pt.we,
    s: pt.s,
    b: pt.b,
    c: pt.c,
    e: pt.e,
    ro: pt.ro,
    v: pt.v,
    p: pt.p / p0,
  }))
  // 操作点标记必须落在归一价曲线上(同量纲), 否则会飞出轴外
  const mPrice = { add: [] as any[], red: [] as any[] }
  priceData.forEach((pt) => {
    if (pt.o === 'add') mPrice.add.push(pt)
    else if (pt.o === 'reduce') mPrice.red.push(pt)
  })
  const runs = bandRuns(ts)
  const t = themeColors(isDarkMode)

  return {
    backgroundColor: 'transparent',
    textStyle: { color: t.legend },
    tooltip: axisTooltip(regimeCn),
    legend: {
      data: [
        { name: '主策略净值', icon: 'roundRect' },
        { name: '股现择时净值', icon: 'roundRect' },
        { name: '极值仓位', icon: 'roundRect' },
        { name: 'risk-on满仓', icon: 'roundRect' },
        { name: '标的价格(归一)', icon: 'roundRect' },
        { name: '加仓', icon: 'triangle' },
        { name: '减仓', icon: 'triangle' },
      ],
      top: 0,
      itemWidth: 16,
      itemHeight: 10,
      textStyle: { color: t.legend, fontSize: 12 },
      selected: { 加仓: true, 减仓: true },
    },
    grid: { left: 58, right: 64, top: 38, bottom: 64 },
    xAxis: { type: 'time', axisLabel: { fontSize: 11, color: t.axis } },
    yAxis: [
      {
        type: 'value',
        scale: true,
        name: '净值',
        position: 'left',
        axisLabel: { fontSize: 11, color: t.axis },
        nameTextStyle: { color: t.nameGreen },
      },
      {
        type: 'value',
        scale: true,
        name: '归一价',
        position: 'right',
        axisLabel: { fontSize: 11, color: t.axis },
        nameTextStyle: { color: t.nameBlue },
        splitLine: { show: false },
      },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 24 }],
    series: [
      {
        name: '主策略净值',
        type: 'line',
        yAxisIndex: 0,
        data: navData,
        showSymbol: false,
        lineStyle: { width: 1.8, color: '#2e7d32' },
        markArea: { silent: true, data: runs },
      },
      {
        name: '股现择时净值',
        type: 'line',
        yAxisIndex: 0,
        data: cashData,
        showSymbol: false,
        lineStyle: { width: 1.4, color: '#ef6c00', type: 'dashed' },
      },
      {
        name: '极值仓位',
        type: 'line',
        yAxisIndex: 0,
        data: extremeData,
        showSymbol: false,
        lineStyle: { width: 1.4, color: '#6a1b9a', type: 'dotted' },
      },
      {
        name: 'risk-on满仓',
        type: 'line',
        yAxisIndex: 0,
        data: ronlyData,
        showSymbol: false,
        lineStyle: { width: 1.4, color: '#00838f', type: 'dashed' },
      },
      {
        name: '标的价格(归一)',
        type: 'line',
        yAxisIndex: 1,
        data: priceData,
        showSymbol: false,
        lineStyle: { width: 1.4, color: '#1565c0' },
      },
      {
        name: '加仓',
        type: 'scatter',
        yAxisIndex: 1,
        data: mPrice.add,
        tooltip: { show: false },
        symbol: 'triangle',
        symbolSize: 9,
        itemStyle: { color: '#d32f2f' },
      },
      {
        name: '减仓',
        type: 'scatter',
        yAxisIndex: 1,
        data: mPrice.red,
        tooltip: { show: false },
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 9,
        itemStyle: { color: '#388e3c' },
      },
    ],
  }
}

/** 股票仓位子图(0-100%), 与主轴 dataZoom 联动 */
export function buildWeightOption(
  res: MarketResult,
  regimeCn: RegimeCn,
  isDarkMode: boolean = isDark(),
) {
  const ts = res.timeseries
  const p0 = ts[0].p
  const wData = ts.map((pt) => ({
    value: [pt.d, +(pt.we * 100).toFixed(1)],
    r: pt.r,
    o: pt.o,
    dw: pt.dw,
    we: pt.we,
    v: pt.v,
    s: pt.s,
    b: pt.b,
    p: pt.p / p0,
  }))
  // vol_21 年化波动率 -> 百分比, 早期 null 过滤掉(否则 echarts 会画到 0)
  const volData = ts
    .map((pt) => ({
      value: [pt.d, pt.v == null ? null : +(pt.v * 100).toFixed(2)],
      r: pt.r,
      o: pt.o,
      dw: pt.dw,
      we: pt.we,
      v: pt.v,
    }))
    .filter((pt) => pt.value[1] != null)
  const mWadd: any[] = []
  const mWred: any[] = []
  wData.forEach((pt) => {
    if (pt.o === 'add') mWadd.push(pt)
    else if (pt.o === 'reduce') mWred.push(pt)
  })
  const runs = bandRuns(ts)
  const t = themeColors(isDarkMode)

  return {
    backgroundColor: 'transparent',
    textStyle: { color: t.legend },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      confine: true,
      formatter: function (params: any) {
        const d = params[0]?.data
        if (!d || typeof d !== 'object') return ''
        const rc = REGIME_COLOR[d.r] || '#555'
        let h = `<div style="font-weight:600;margin-bottom:4px">${d.value[0]}</div>`
        h += `<span style="color:${rc};font-weight:600">${
          regimeCn[d.r] || d.r
        }</span> `
        h += `<b>操作:</b> ${OP_CN[d.o] || d.o}`
        if (d.o !== 'hold') h += ` (Δ ${(d.dw * 100).toFixed(0)}pp)`
        h += `<br/><b>股票仓位:</b> ${d.value[1].toFixed(0)}%`
        if (d.v != null) h += ` &nbsp; <b>vol21:</b> ${(d.v * 100).toFixed(1)}%`
        return h
      },
    },
    legend: {
      data: [
        { name: '股票仓位%', icon: 'roundRect' },
        { name: '波动率%', icon: 'roundRect' },
        { name: '加仓', icon: 'triangle' },
        { name: '减仓', icon: 'triangle' },
      ],
      top: 0,
      itemWidth: 16,
      itemHeight: 10,
      textStyle: { color: t.legend, fontSize: 12 },
      selected: { 加仓: true, 减仓: true },
    },
    grid: { left: 58, right: 64, top: 34, bottom: 48 },
    xAxis: { type: 'time', axisLabel: { fontSize: 11, color: t.axis } },
    yAxis: [
      {
        type: 'value',
        min: 0,
        max: 100,
        name: '仓位%',
        position: 'left',
        axisLabel: { fontSize: 11, color: t.axis },
        nameTextStyle: { color: t.legend },
      },
      {
        type: 'value',
        scale: true,
        name: 'vol%',
        position: 'right',
        axisLabel: { fontSize: 11, color: t.axis, formatter: '{value}%' },
        nameTextStyle: { color: '#00838f' },
        splitLine: { show: false },
      },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 18 }],
    series: [
      {
        name: '股票仓位%',
        type: 'line',
        step: 'end',
        yAxisIndex: 0,
        data: wData,
        showSymbol: false,
        lineStyle: { width: 1.8, color: '#6a1b9a' },
        markArea: { silent: true, data: runs },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            {
              yAxis: 0,
              lineStyle: { color: t.lineRed, type: 'dashed', width: 1.5 },
              label: {
                formatter: '清仓 0%',
                color: t.lineRed,
                fontSize: 10,
                position: 'insideEndTop',
              },
            },
            {
              yAxis: 20,
              lineStyle: { color: t.lineOrange, type: 'dashed', width: 1 },
              label: {
                formatter: 'risk_off 下限 20%',
                color: t.lineOrange,
                fontSize: 10,
                position: 'insideEndTop',
              },
            },
            {
              yAxis: 80,
              lineStyle: { color: t.lineGreen, type: 'dashed', width: 1 },
              label: {
                formatter: 'risk_on 80%',
                color: t.lineGreen,
                fontSize: 10,
                position: 'insideEndTop',
              },
            },
          ],
        },
      },
      {
        name: '波动率%',
        type: 'line',
        yAxisIndex: 1,
        data: volData,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.2, color: '#00838f' },
        areaStyle: { color: 'rgba(0,131,143,0.06)' },
      },
      {
        name: '加仓',
        type: 'scatter',
        yAxisIndex: 0,
        data: mWadd,
        tooltip: { show: false },
        symbol: 'triangle',
        symbolSize: 9,
        itemStyle: { color: '#d32f2f' },
      },
      {
        name: '减仓',
        type: 'scatter',
        yAxisIndex: 0,
        data: mWred,
        tooltip: { show: false },
        symbol: 'triangle',
        symbolRotate: 180,
        symbolSize: 9,
        itemStyle: { color: '#388e3c' },
      },
    ],
  }
}

/**
 * 解析当前可见窗口的首/末时间戳(毫秒)。
 * ECharts dataZoom 在用户缩放后会带 startValue/endValue; 否则用百分比推算。
 */
export function resolveRange(
  dz: any,
  ts: TsPoint[],
): [number, number] {
  const arr = Array.isArray(dz) ? dz : dz ? [dz] : []
  const cand = arr.find(
    (x: any) => x.startValue != null && x.endValue != null,
  )
  if (cand) return [+cand.startValue, +cand.endValue]
  const n = ts.length
  const d0 = arr[0] || {}
  const s = d0.start == null ? 0 : d0.start
  const e = d0.end == null ? 100 : d0.end
  const si = Math.max(0, Math.floor((s / 100) * (n - 1)))
  const ei = Math.min(n - 1, Math.ceil((e / 100) * (n - 1)))
  return [Date.parse(ts[si].d), Date.parse(ts[ei].d)]
}

function maxDD(vals: number[]): number {
  let peak = -Infinity
  let mdd = 0
  for (const v of vals) {
    if (v > peak) peak = v
    const dd = (v - peak) / peak
    if (dd < mdd) mdd = dd
  }
  return mdd // <= 0
}

/** 给定窗口首/末时间戳, 计算区间收益/超额/回撤/年化 */
export function computeRangeStats(
  ts: TsPoint[],
  sv: number,
  ev: number,
): RangeStats | null {
  if (!ts.length) return null
  const win = ts.filter((pt) => {
    const t = Date.parse(pt.d)
    return t >= sv && t <= ev
  })
  if (!win.length) return null
  const first = win[0]
  const last = win[win.length - 1]
  const sRet = first.s ? last.s / first.s - 1 : 0
  const bRet = first.b ? last.b / first.b - 1 : 0
  const tRet = first.c ? last.c / first.c - 1 : 0
  const eRet = first.e ? last.e / first.e - 1 : 0
  const rRet = first.ro ? last.ro / first.ro - 1 : 0
  const excess = sRet - bRet
  const tExcess = sRet - tRet
  const eExcess = sRet - eRet
  const rExcess = sRet - rRet
  const days = Math.round((Date.parse(last.d) - Date.parse(first.d)) / 86400000) + 1
  const years = days / 365
  const annF = (r: number) => (years > 0 ? Math.pow(1 + r, 1 / years) - 1 : r)
  const sAnn = annF(sRet)
  const bAnn = annF(bRet)
  const tAnn = annF(tRet)
  const eAnn = annF(eRet)
  const rAnn = annF(rRet)
  const sMdd = maxDD(win.map((p) => p.s))
  const bMdd = maxDD(win.map((p) => p.b))
  const tMdd = maxDD(win.map((p) => p.c))
  const eMdd = maxDD(win.map((p) => p.e))
  const rMdd = maxDD(win.map((p) => p.ro))
  return {
    start: first.d,
    end: last.d,
    days,
    sRet,
    bRet,
    tRet,
    eRet,
    rRet,
    excess,
    tExcess,
    eExcess,
    rExcess,
    sAnn,
    bAnn,
    tAnn,
    eAnn,
    rAnn,
    sMdd,
    bMdd,
    tMdd,
    eMdd,
    rMdd,
  }
}
