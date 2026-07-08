// TRHRP 回测页面前后端共享类型。
// 字段与 deliverables/trhrp_backtest_all/_all.json 一一对应。

/** regime 代码 -> 中文标签 的映射 (如 risk_on -> "风险开启") */
export type RegimeCn = Record<string, string>

export interface TsPoint {
  d: string // 日期 "2018-01-03"
  s: number // 策略净值
  b: number // 基准净值 (买入持有)
  c: number // 纯择时净值 (equity 权重同策略, 其余全 SGOV)
  e: number // 极致纯择时净值 (risk_on=满仓, risk_off=空仓, moderate=半仓, 其余 SGOV)
  ro: number // risk-on满仓净值 (risk_on=满仓, moderate/risk_off 全部 SGOV 空仓)
  v: number | null // vol_21 年化波动率 (0~1, 早期可能为 null)
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
  timing_total: number
  extreme_total: number
  ronly_total: number
  bench_total: number
  excess: number
  timing_excess: number
  extreme_excess: number
  ronly_excess: number
  strat_cagr: number
  bench_cagr: number
  strat_mdd: number
  timing_mdd: number
  extreme_mdd: number
  ronly_mdd: number
  bench_mdd: number
  risk_on: number
  moderate: number
  risk_off: number
  ops: number
  adds: number
  reduces: number
  rebalances: number
  // —— 当前/接下来风险偏好 + 明日操作 (回测快照推演, 见 scripts/trhrp_backtest_live.py) ——
  last_date?: string | null
  current_regime?: string | null
  current_operation?: string | null
  current_equity_weight?: number | null
  regime_outlook?: string | null
  next_regime?: string | null
  next_operation?: string | null
  outlook_note?: string | null
  outlook_dist?: number | null
}

export interface MarketResult {
  meta: MarketMeta
  params: Record<string, any>
  summary: {
    strategy_total_return: number
    benchmark_total_return: number
    timing_total_return: number
    extreme_total_return: number
    ronly_total_return: number
    excess_total_return: number
    timing_excess_total_return: number
    extreme_excess_total_return: number
    ronly_excess_total_return: number
    strategy_cagr: number
    benchmark_cagr: number
    timing_cagr: number
    extreme_cagr: number
    ronly_cagr: number
    excess_cagr: number
    strategy_max_drawdown: number
    benchmark_max_drawdown: number
    timing_max_drawdown: number
    extreme_max_drawdown: number
    ronly_max_drawdown: number
    strategy_peak_date: string
    strategy_trough_date: string
    benchmark_peak_date: string
    benchmark_trough_date: string
    timing_peak_date: string
    timing_trough_date: string
    extreme_peak_date: string
    extreme_trough_date: string
    ronly_peak_date: string
    ronly_trough_date: string
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
    // —— 风险偏好推演字段 (与 MarketSummary 对应) ——
    last_date?: string | null
    current_regime?: string | null
    current_operation?: string | null
    current_equity_weight?: number | null
    regime_outlook?: string | null
    next_regime?: string | null
    next_operation?: string | null
    outlook_note?: string | null
    outlook_dist?: number | null
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
  tRet: number // 纯择时收益(区间): equity 权重同策略, 其余全 SGOV
  eRet: number // 极致纯择时收益(区间): risk_on=满仓, risk_off=空仓, moderate=半仓
  rRet: number // risk-on满仓收益(区间): risk_on=满仓, moderate/risk_off 全部空仓
  excess: number // 策略 - 标的
  tExcess: number // 策略 - 纯择时 (即 GLD 防御腿的区间增益)
  eExcess: number // 策略 - 极致纯择时 (温和调仓相对激进切换的增益)
  rExcess: number // 策略 - risk-on满仓 (温和调仓相对二元满仓的增益)
  sAnn: number
  bAnn: number
  tAnn: number
  eAnn: number
  rAnn: number
  sMdd: number
  bMdd: number
  tMdd: number
  eMdd: number
  rMdd: number
}
