import { NextResponse } from 'next/server'
import fs from 'node:fs/promises'
import path from 'node:path'

const CACHE_DIR = path.join(process.cwd(), 'scripts', '_cache_xag_ema_monitor')
const OVERVIEW_FILE = path.join(CACHE_DIR, 'backtest_overview.json')

export const dynamic = 'force-dynamic'
export const revalidate = 0

// ============================================================
// 类型 (与前端 types.ts 对齐, 但这里只用到子集)
// ============================================================
interface CurrentState {
  last_closed?: string
  live_price?: number
  ema?: number
  rsi?: number
  position?: number
  pos_size?: number
  entry_price?: number
  entry_time?: string
  unreal_pct?: number
  tp_count?: number
  bars_since_tp?: number
  cool_left?: number
  cool_passed?: boolean
  timestamp?: string
}

interface TradeLogEvent {
  ts: string
  type: 'init' | 'reversal' | 'partial_tp'
  instrument?: string
  dir?: number
  old_dir?: number
  new_dir?: number
  price: number
  entry?: number
  rsi?: number | null
  pos_size?: number
  pos_size_before?: number
  pos_size_after?: number
  size_ratio?: number
  gross?: number
  net?: number
  cost?: number
  capital_before?: number
  capital_after?: number
}

interface InstrumentPayload {
  name: string
  display_name: string
  symbol: string
  config: Record<string, number | boolean>
  sample_note: string
  stats: Record<string, number | string>
  series: {
    price: [number, number][]
    ema: [number, number][]
    equity: [number, number][]
    hold: [number, number][]
  }
  trades: Array<{
    t: string
    price: number
    old_dir: number
    new_dir: number
    reason: string
    net: number
  }>
  tps: Array<{
    t: string
    price: number
    dir: number
    net: number
    size_ratio: number
  }>
  pos_segments: Array<{ t0: string; t1: string; pos: number }>
  current: CurrentState
  // 前向净值 (从 trade_log 计算)
  forward?: {
    events: TradeLogEvent[]
    equity_curve: [number, number][]
    current_equity: number
    total_return: number
    realized_capital: number
    init_ts: string | null
  }
}

interface OverviewPayload {
  generated_at: string
  instruments: InstrumentPayload[]
}

// ============================================================
// 工具
// ============================================================
async function readJson<T>(file: string): Promise<T | null> {
  try {
    const raw = await fs.readFile(file, 'utf-8')
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

async function readJsonl(file: string): Promise<TradeLogEvent[]> {
  try {
    const raw = await fs.readFile(file, 'utf-8')
    const events: TradeLogEvent[] = []
    for (const line of raw.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        events.push(JSON.parse(trimmed) as TradeLogEvent)
      } catch {
        // 跳过坏行
      }
    }
    return events
  } catch {
    return []
  }
}

function toMs(iso: string | undefined | null): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : t
}

/** 对齐到 15m K 线收盘网格 (trade_log 的 ts 是 daemon 检测时刻, 偏几秒) */
function alignTo15m(ms: number): number {
  const FIFTEEN_MIN_MS = 15 * 60 * 1000
  return Math.floor(ms / FIFTEEN_MIN_MS) * FIFTEEN_MIN_MS
}

/**
 * 计算前向净值曲线.
 * - init: capital = 1.0
 * - reversal: capital *= (1 + pos_size_before * net)
 * - partial_tp: capital *= (1 + pos_size_before * size_ratio * net)
 * - 当前净值 = capital * (1 + pos_size_current * unrealized_pnl)
 */
function computeForwardEquity(events: TradeLogEvent[], current: CurrentState) {
  if (!events || events.length === 0) {
    return {
      events: [],
      equity_curve: [] as [number, number][],
      current_equity: 1.0,
      total_return: 0.0,
      realized_capital: 1.0,
      init_ts: null as string | null,
    }
  }

  // 回填 capital (与 Python reconcile_capital 一致)
  // 同时把 ts 对齐到 15m K 线收盘网格, 使事件点精确落在价格曲线上
  let capital = 1.0
  const filled: TradeLogEvent[] = events.map((e) => {
    const rawMs = toMs(e.ts)
    const alignedMs = rawMs != null ? alignTo15m(rawMs) : null
    const alignedTs = alignedMs != null ? new Date(alignedMs).toISOString() : e.ts
    const ev = { ...e, ts: alignedTs, capital_before: capital }
    if (e.type === 'init') {
      ev.capital_after = capital
    } else if (e.type === 'reversal') {
      const posSizeBefore = e.pos_size_before ?? 0
      const net = e.net ?? 0
      capital = capital * (1 + posSizeBefore * net)
      ev.capital_after = capital
    } else if (e.type === 'partial_tp') {
      const posSizeBefore = e.pos_size_before ?? 0
      const sizeRatio = e.size_ratio ?? 0
      const net = e.net ?? 0
      capital = capital * (1 + posSizeBefore * sizeRatio * net)
      ev.capital_after = capital
    } else {
      ev.capital_after = capital
    }
    return ev
  })

  // 净值曲线
  const equity_curve: [number, number][] = []
  for (const e of filled) {
    const ms = toMs(e.ts)
    if (ms != null) {
      equity_curve.push([ms, e.capital_after ?? 1.0])
    }
  }

  // 当前含浮动的净值
  const lastCapital = filled[filled.length - 1]?.capital_after ?? 1.0
  const pos = current.position ?? 0
  const posSize = current.pos_size ?? 0
  const entry = current.entry_price ?? 0
  const live = current.live_price ?? 0
  let currentEquity = lastCapital
  if (pos !== 0 && posSize > 0 && entry > 0 && live > 0) {
    const unreal = (pos * (live - entry)) / entry
    currentEquity = lastCapital * (1 + posSize * unreal)
  }

  // 追加当前实时点
  const lastClosedMs = toMs(current.last_closed)
  if (lastClosedMs != null) {
    equity_curve.push([lastClosedMs, currentEquity])
  }

  const initTs = filled.find((e) => e.type === 'init')?.ts ?? null
  return {
    events: filled,
    equity_curve,
    current_equity: currentEquity,
    total_return: currentEquity - 1.0,
    realized_capital: lastCapital,
    init_ts: initTs,
  }
}

// ============================================================
// 路由
// ============================================================

/**
 * 把真实事件的 price 对齐到价格曲线上的 close.
 * trade_log 的 price 可能来自旧缓存或四舍五入, 与曲线 close 有微小差异,
 * 导致图上事件点偏离曲线. 这里用曲线上对齐时间点的 close 替换,
 * 使事件点 y 坐标 = 曲线 y 坐标, 精确落在曲线上.
 * (净值计算不受影响, capital 已在 computeForwardEquity 里算完)
 */
function alignEventPricesToSeries(
  events: TradeLogEvent[],
  priceSeries: [number, number][],
): TradeLogEvent[] {
  if (!events || events.length === 0 || !priceSeries || priceSeries.length === 0) {
    return events
  }
  // 构建 15m 对齐 ms → close 映射
  const priceMap = new Map<number, number>()
  for (const [ms, p] of priceSeries) {
    priceMap.set(alignTo15m(ms), p)
  }
  return events.map((e) => {
    const ms = toMs(e.ts)
    if (ms == null) return e
    const alignedMs = alignTo15m(ms)
    const seriesPrice = priceMap.get(alignedMs)
    if (seriesPrice != null && seriesPrice > 0) {
      return { ...e, price: seriesPrice }
    }
    return e
  })
}

async function mergeLiveData(overview: OverviewPayload): Promise<OverviewPayload> {
  const merged = { ...overview, instruments: [...overview.instruments] }
  for (let i = 0; i < merged.instruments.length; i++) {
    const inst = merged.instruments[i]
    // 1. 实时 state_*.json (daemon 每 15m 更新)
    const live = await readJson<CurrentState>(
      path.join(CACHE_DIR, `state_${inst.name}.json`),
    )
    const current = live ? { ...inst.current, ...live } : inst.current
    // 2. trade_log_*.jsonl (真实变仓事件)
    const events = await readJsonl(path.join(CACHE_DIR, `trade_log_${inst.name}.jsonl`))
    const forward = computeForwardEquity(events, current)
    // 3. 把所有事件 price 对齐到价格曲线 close, 使图上点位精确落在曲线上
    //    覆盖: 真实事件 + 回测反手点 + 回测止盈点
    const alignedForwardEvents = alignEventPricesToSeries(forward.events, inst.series.price)
    const alignedTrades = inst.trades.map((t) => alignSingleEventPrice(t, inst.series.price))
    const alignedTps = inst.tps.map((t) => alignSingleEventPrice(t, inst.series.price))
    merged.instruments[i] = {
      ...inst,
      trades: alignedTrades,
      tps: alignedTps,
      current,
      forward: { ...forward, events: alignedForwardEvents },
    }
  }
  return merged
}

/** 对齐单个事件的 price 到价格曲线 close (用于回测 trades/tps) */
function alignSingleEventPrice<T extends { t: string; price: number }>(
  ev: T,
  priceSeries: [number, number][],
): T {
  if (!priceSeries || priceSeries.length === 0) return ev
  const ms = toMs(ev.t)
  if (ms == null) return ev
  const alignedMs = alignTo15m(ms)
  // 构建 15m 对齐 ms → close 映射 (每次调用都构建, 数据量小可接受)
  for (const [sms, p] of priceSeries) {
    if (alignTo15m(sms) === alignedMs) {
      return { ...ev, price: p }
    }
  }
  return ev
}

export async function GET() {
  const overview = await readJson<OverviewPayload>(OVERVIEW_FILE)
  if (!overview) {
    return NextResponse.json(
      {
        message:
          '回测数据未生成。请在项目根目录运行: .venv/bin/python scripts/xag_ema_export_json.py',
      },
      { status: 503 },
    )
  }

  const merged = await mergeLiveData(overview)
  return NextResponse.json(merged, {
    headers: {
      'Cache-Control': 'no-store, max-age=0',
      'x-overview-generated': overview.generated_at,
    },
  })
}
