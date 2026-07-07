// TRHRP 回测页面前后端共享类型。
// 字段与 deliverables/trhrp_backtest_all/_all.json 一一对应。

export interface TsPoint {
  d: string // 日期 "2018-01-03"
  s: number // 策略净值
  b: number // 基准净值 (买入持有)
  r: string // regime: risk_on / moderate / risk_off
  o: string // 操作: add / reduce / hold
  we: number // 股票权重 (0~1)
  dw: number // 股票权重变化 (Δ, 0~1)
  p: number // 标的收盘 (原始价格)
}

export interface MarketMeta {
  market: string
  label: string
  ticker: string
  proxy: string
  scenario: string
  currency: string
  start: string
  end: string
  days: number
  initial_capital: number
  generated_at: string
  source: string
}

export interface MarketSummary {
  label: string
  ticker: string
  group: string
  crash_mode: string
  crash_z: number
  overlay: string
  start: string
  end: string
  days: number
  strat_total: number
  bench_total: number
  excess: number
  strat_cagr: number
  bench_cagr: number
  strat_mdd: number
  bench_mdd: number
  risk_on: number
  moderate: number
  risk_off: number
  ops: number
  adds: number
  reduces: number
  rebalances: number
}

export interface MarketResult {
  meta: MarketMeta
  params: Record<string, any>
  summary: {
    strategy_total_return: number
    benchmark_total_return: number
    excess_total_return: number
    strategy_cagr: number
    benchmark_cagr: number
    excess_cagr: number
    strategy_max_drawdown: number
    benchmark_max_drawdown: number
    strategy_peak_date: string
    strategy_trough_date: string
    benchmark_peak_date: string
    benchmark_trough_date: string
    target_regime_changes: number
    rebalance_days: number
    avg_turnover_per_day: number
    strategy_total_commission: number
    strategy_commission_drag: number
    benchmark_total_commission: number
    risk_on_days: number
    moderate_days: number
    risk_off_days: number
    operation_days: number
    add_days: number
    reduce_days: number
  }
  timeseries: TsPoint[]
}

export interface OverviewPayload {
  generated_at: string
  source: string
  regime_cn: Record<string, string>
  markets: MarketSummary[]
}

export interface RangeStats {
  start: string
  end: string
  days: number
  sRet: number
  bRet: number
  excess: number
  sAnn: number
  bAnn: number
  sMdd: number
  bMdd: number
}
