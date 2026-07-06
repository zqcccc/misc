export interface InstrumentConfig {
  ema_span: number
  confirm_bars: number
  breakout_pct: number
  rsi_span: number
  rsi_over: number
  rsi_under: number
  part_ratio: number
  cool_bars: number
  tp_enabled: boolean
}

export interface InstrumentStats {
  bars: number
  first_ts: string
  last_ts: string
  strategy_return: number
  hold_return: number
  final_equity: number
  final_hold: number
  max_drawdown: number
  reversals: number
  opens: number
  tps: number
  win_rate: number
}

export interface InstrumentSeries {
  price: [number, number][]
  ema: [number, number][]
  equity: [number, number][]
  hold: [number, number][]
}

export interface TradeEvent {
  t: string
  price: number
  old_dir: number
  new_dir: number
  reason: 'open' | 'reversal' | 'end'
  net: number
}

export interface TpEvent {
  t: string
  price: number
  dir: number
  net: number
  size_ratio: number
}

export interface PosSegment {
  t0: string
  t1: string
  pos: number
}

export interface CurrentState {
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

export interface TradeLogEvent {
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

export interface ForwardEquity {
  events: TradeLogEvent[]
  equity_curve: [number, number][]
  current_equity: number
  total_return: number
  realized_capital: number
  init_ts: string | null
}

export interface InstrumentPayload {
  name: string
  display_name: string
  symbol: string
  config: InstrumentConfig
  sample_note: string
  stats: InstrumentStats
  series: InstrumentSeries
  trades: TradeEvent[]
  tps: TpEvent[]
  pos_segments: PosSegment[]
  current: CurrentState
  forward?: ForwardEquity
}

export interface OverviewPayload {
  generated_at: string
  instruments: InstrumentPayload[]
}
