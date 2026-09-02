"""
对比原始策略与 EP004 增强版策略，并执行全套 EP004 严格评估:
1. 样本内/样本外/全样本表现
2. Alpha/Beta 归因与显著性检验 (t-stat, p-value)
3. 极端熊市压力测试 (Bear Market Stress Test, 如 2022 年大盘 -21.6%)
4. Deflated Sharpe Ratio (DSR) 检验
5. 蒙特卡洛 5000 次 Block Bootstrap (prob of profit)
"""

import os
import json
import numpy as np
import pandas as pd
from scripts.ashare_quant.data_feed import load_all_universe, UNIVERSE, BENCHMARK_SYMBOL
from scripts.ashare_quant.engine import BacktestEngine, calculate_performance_metrics
from scripts.ashare_quant.strategy import AdaptiveLeaderStrategy
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy
from scripts.ashare_quant.ep004_evaluator import (
    decompose_alpha_beta,
    compute_deflated_sharpe,
    run_monte_carlo_block_bootstrap
)


def run_strategy(all_data, strat_cls, strat_params, start_date="2019-01-01", end_date="2026-02-27"):
    engine = BacktestEngine(initial_capital=1_000_000.0)
    strategy = strat_cls(**strat_params)

    bm_df = all_data[BENCHMARK_SYMBOL]
    all_dates = bm_df["date"].dt.strftime("%Y-%m-%d").tolist()
    
    start_idx = next(i for i, d in enumerate(all_dates) if d >= start_date)
    warmup_idx = max(0, start_idx - 70)

    prepped = {}
    for sym, df in all_data.items():
        sub = df.copy()
        sub["date_str"] = sub["date"].dt.strftime("%Y-%m-%d")
        prepped[sym] = sub

    equity_records = []
    positions_history = []

    for i in range(warmup_idx, len(all_dates)):
        cur_d = all_dates[i]
        if cur_d > end_date:
            break
        in_window = (i >= start_idx)

        if in_window and i > warmup_idx:
            prev_d = all_dates[i - 1]
            daily_bars = {}
            prev_closes = {}
            for sym, df in prepped.items():
                cur_rows = df[df["date_str"] == cur_d]
                prev_rows = df[df["date_str"] == prev_d]
                if not cur_rows.empty:
                    daily_bars[sym] = {
                        "open": float(cur_rows["open"].iloc[0]),
                        "high": float(cur_rows["high"].iloc[0]),
                        "low": float(cur_rows["low"].iloc[0]),
                        "close": float(cur_rows["close"].iloc[0]),
                    }
                if not prev_rows.empty:
                    prev_closes[sym] = float(prev_rows["close"].iloc[0])

            engine.execute_pending_orders(cur_d, daily_bars, prev_closes)

        # 截至当日历史切片 (无未来数据)
        slice_map = {}
        daily_closes = {}
        for sym, df in prepped.items():
            h = df[df["date_str"] <= cur_d]
            if not h.empty:
                slice_map[sym] = h
                daily_closes[sym] = float(h["close"].iloc[-1])

        if in_window:
            strategy.on_bar_close(cur_d, slice_map, engine)
            bm_close = daily_closes.get(BENCHMARK_SYMBOL, 1.0)
            rec = engine.end_of_day_settlement(cur_d, daily_closes, bm_close)
            equity_records.append({
                "date": cur_d,
                "equity": rec["total_equity"],
                "cash": rec["cash"],
                "benchmark": bm_close,
                "num_positions": len(engine.positions),
            })
            pos_info = [
                {
                    "symbol": s,
                    "name": UNIVERSE.get(s, s),
                    "shares": p.shares,
                    "price": daily_closes.get(s, p.cost_price),
                    "value": p.shares * daily_closes.get(s, p.cost_price),
                    "weight": (p.shares * daily_closes.get(s, p.cost_price)) / rec["total_equity"]
                }
                for s, p in engine.positions.items()
            ]
            positions_history.append({
                "date": cur_d,
                "holdings": pos_info,
                "cash_weight": rec["cash"] / rec["total_equity"]
            })

    eq_df = pd.DataFrame(equity_records)
    eq_df["strategy_net_value"] = eq_df["equity"] / 1_000_000.0
    eq_df["benchmark_net_value"] = eq_df["benchmark"] / eq_df["benchmark"].iloc[0]
    
    eq_vals = eq_df["equity"].values
    running_max = np.maximum.accumulate(eq_vals)
    eq_df["drawdown"] = (eq_vals - running_max) / running_max
    
    bm_vals = eq_df["benchmark"].values
    bm_max = np.maximum.accumulate(bm_vals)
    eq_df["benchmark_drawdown"] = (bm_vals - bm_max) / bm_max

    metrics = calculate_performance_metrics(eq_df, benchmark_col="benchmark")

    # 交易列表
    trades_pnl = []
    buy_map = {}
    for t in engine.trades:
        if t.action == "BUY":
            buy_map[t.symbol] = t.price
        elif t.action == "SELL" and t.symbol in buy_map:
            pnl = (t.price / buy_map[t.symbol]) - 1.0
            trades_pnl.append(pnl)

    win_cnt = sum(1 for p in trades_pnl if p > 0)
    win_rate = win_cnt / len(trades_pnl) if trades_pnl else 0.0
    wins = [p for p in trades_pnl if p > 0]
    losses = [abs(p) for p in trades_pnl if p <= 0]
    pl_ratio = (np.mean(wins) / np.mean(losses)) if losses and wins else 0.0
    years = len(eq_df) / 250.0
    total_cost_turnover = sum(abs(t.total_cost) for t in engine.trades)
    turnover = (total_cost_turnover / 1_000_000.0) / years

    metrics.update({
        "win_rate": float(win_rate),
        "profit_loss_ratio": float(pl_ratio),
        "total_trades": len(trades_pnl),
        "annual_turnover": float(turnover),
    })

    # EP004 评估分析
    strat_daily_rets = np.diff(eq_df["strategy_net_value"]) / eq_df["strategy_net_value"].iloc[:-1]
    bm_daily_rets = np.diff(eq_df["benchmark_net_value"]) / eq_df["benchmark_net_value"].iloc[:-1]

    alpha_decomp = decompose_alpha_beta(strat_daily_rets, bm_daily_rets)
    dsr_result = compute_deflated_sharpe(strat_daily_rets, n_trials=30)
    mc_result = run_monte_carlo_block_bootstrap(trades_pnl, iters=5000, block_size=6)

    # 极端熊市压力测试: 截取 2022 年 (A股核心资产与大盘大熊市)
    eq_df["year"] = pd.to_datetime(eq_df["date"]).dt.year
    sub_2022 = eq_df[eq_df["year"] == 2022]
    bear_2022 = {}
    if not sub_2022.empty:
        s_2022 = sub_2022["equity"].iloc[-1] / sub_2022["equity"].iloc[0] - 1.0
        b_2022 = sub_2022["benchmark"].iloc[-1] / sub_2022["benchmark"].iloc[0] - 1.0
        mdd_2022 = float(np.min(sub_2022["drawdown"]))
        bear_2022 = {
            "strategy_return": s_2022,
            "benchmark_return": b_2022,
            "alpha": s_2022 - b_2022,
            "max_drawdown": mdd_2022,
        }

    # 逐年表现
    yearly = []
    for y, g in eq_df.groupby("year"):
        sy = g["equity"].iloc[-1] / g["equity"].iloc[0] - 1.0
        by = g["benchmark"].iloc[-1] / g["benchmark"].iloc[0] - 1.0
        yearly.append({
            "year": int(y),
            "strategy_return": float(sy),
            "benchmark_return": float(by),
            "alpha": float(sy - by),
            "strategy_mdd": float(np.min(g["drawdown"])),
        })

    return {
        "metrics": metrics,
        "yearly": yearly,
        "alpha_decomp": alpha_decomp,
        "dsr": dsr_result,
        "monte_carlo": mc_result,
        "bear_stress_test": bear_2022,
        "equity_curve": eq_df[["date", "strategy_net_value", "benchmark_net_value", "drawdown", "benchmark_drawdown", "cash", "num_positions"]].to_dict(orient="records"),
        "positions_history": positions_history,
        "trades": [
            {
                "id": t.trade_id, "symbol": t.symbol, "name": UNIVERSE.get(t.symbol, t.symbol),
                "action": t.action, "shares": t.shares, "price": round(t.price, 2),
                "date": t.trade_date, "fee": round(t.fee, 2), "reason": t.reason
            }
            for t in engine.trades
        ]
    }


if __name__ == "__main__":
    print("加载数据...")
    all_data = load_all_universe()
    
    print("\n>>> 正在运行 EP004 增强版策略 (Top 3, 相对强弱 Alpha + 月度低换手)...")
    p_v2 = {
        "top_k": 3,
        "rebalance_interval_days": 20,
        "market_filter_ma": 60,
        "rs_window_fast": 20,
        "rs_window_slow": 60,
        "hysteresis_buffer": 0.20,
        "stop_loss_pct": 0.10,
        "trail_activation_pct": 0.15,
        "trail_pullback_pct": 0.08,
        "enable_market_filter": True,
    }
    res_v2 = run_strategy(all_data, RelativeStrengthAlphaStrategy, p_v2, "2019-01-01", "2026-02-27")
    
    print("\n>>> 正在运行 样本外盲测 (2023-01-01 ~ 2026-02-27)...")
    res_v2_oos = run_strategy(all_data, RelativeStrengthAlphaStrategy, p_v2, "2023-01-01", "2026-02-27")

    print("\n" + "=" * 80)
    print("【EP004 增强版策略核心结果】")
    print("=" * 80)
    m = res_v2["metrics"]
    a = res_v2["alpha_decomp"]
    d = res_v2["dsr"]
    mc = res_v2["monte_carlo"]
    b = res_v2["bear_stress_test"]

    print(f"累计收益率: {m['total_return']:.2%} (年化 CAGR: {m['cagr']:.2%}) | 基准累计: {m['benchmark_total_return']:.2%}")
    print(f"最大回撤: {m['max_drawdown']:.2%} | 基准最大回撤: {m['benchmark_max_drawdown']:.2%}")
    print(f"夏普比率: {m['sharpe_ratio']:.2f} | 卡尔玛比率: {m['calmar_ratio']:.2f}")
    print(f"交易胜率: {m['win_rate']:.2%} | 盈亏比: {m['profit_loss_ratio']:.2f} | 年化换手率: {m['annual_turnover']:.1f}x")
    print("-" * 80)
    print("【EP004 深度归因与统计显著性检验】")
    print(f"年化 Alpha: {a['annual_alpha']:.2%} (t-stat={a['t_stat']:.2f}, p-value={a['p_value']:.4f}) -> {'显著! (p<0.05)' if a['is_alpha_significant'] else '未达显著'}")
    print(f"Beta: {a['beta']:.2f} | R^2: {a['r_squared']:.2f} | 纯 Alpha 贡献: {a['alpha_contribution']:.2%} vs Beta 拖累: {a['beta_drag']:.2%}")
    print(f"Deflated Sharpe (DSR): {d['DSR']:.4f} -> {d['verdict']}")
    print(f"蒙特卡洛 5000 次重采样: prob(profit)={mc['prob_profit']:.1%} | P5={mc['p5']:.2f}x | P50={mc['p50']:.2f}x | P95={mc['p95']:.2f}x")
    print(f"2022 极端熊市压力测试: 策略收益 {b['strategy_return']:.2%} vs 沪深300 {b['benchmark_return']:.2%} (超额 Alpha: {b['alpha']:.2%})")
    print("=" * 80)

    # 样本外结果
    m_oos = res_v2_oos["metrics"]
    a_oos = res_v2_oos["alpha_decomp"]
    d_oos = res_v2_oos["dsr"]
    print("\n【样本外盲测 2023-2026 结果】")
    print(f"样本外收益: {m_oos['total_return']:.2%} (年化: {m_oos['cagr']:.2%}) | 沪深300: {m_oos['benchmark_total_return']:.2%}")
    print(f"样本外最大回撤: {m_oos['max_drawdown']:.2%} | 沪深300回撤: {m_oos['benchmark_max_drawdown']:.2%}")
    print(f"样本外年化 Alpha: {a_oos['annual_alpha']:.2%} (p-val={a_oos['p_value']:.4f}) | DSR: {d_oos['DSR']:.4f} ({d_oos['verdict']})")
    print("=" * 80)
