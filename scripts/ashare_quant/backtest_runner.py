"""
A股量化策略回测运行器与 EP004 深度评估集成 (数据截止 2026-09-02)
===================================================================
区间划分:
- 全样本 (Full Sample): 2019-01-01 ~ 2026-09-02
- 历史样本内 (In-Sample): 2019-01-01 ~ 2023-12-31
- 样本外盲测 (Out-of-Sample): 2024-01-01 ~ 2026-02-27
- 最新绝密测试段 (Ultra-Recent OOS): 2026-03-01 ~ 2026-09-02 (近半年最新行情检验)
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any

from scripts.ashare_quant.data_feed import (
    load_all_universe,
    UNIVERSE,
    BENCHMARK_SYMBOL,
    BENCHMARK_NAME
)
from scripts.ashare_quant.engine import BacktestEngine, calculate_performance_metrics
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy
from scripts.ashare_quant.ep004_evaluator import (
    decompose_alpha_beta,
    compute_deflated_sharpe,
    run_monte_carlo_block_bootstrap
)

DELIVERABLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "deliverables")
os.makedirs(DELIVERABLES_DIR, exist_ok=True)
OUT_JSON = os.path.join(DELIVERABLES_DIR, "ashare_strategy_backtest.json")


def run_single_backtest(
    all_data: Dict[str, pd.DataFrame],
    strategy_params: dict,
    start_date: str = "2019-01-01",
    end_date: str = "2026-09-02",
    initial_capital: float = 1_000_000.0,
) -> Dict[str, Any]:
    engine = BacktestEngine(initial_capital=initial_capital)
    strategy = RelativeStrengthAlphaStrategy(**strategy_params)

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
    eq_df["strategy_net_value"] = eq_df["equity"] / initial_capital
    eq_df["benchmark_net_value"] = eq_df["benchmark"] / eq_df["benchmark"].iloc[0]
    
    eq_vals = eq_df["equity"].values
    running_max = np.maximum.accumulate(eq_vals)
    eq_df["drawdown"] = (eq_vals - running_max) / running_max
    
    bm_vals = eq_df["benchmark"].values
    bm_max = np.maximum.accumulate(bm_vals)
    eq_df["benchmark_drawdown"] = (bm_vals - bm_max) / bm_max

    metrics = calculate_performance_metrics(eq_df, benchmark_col="benchmark")

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
    turnover = (total_cost_turnover / initial_capital) / years

    metrics.update({
        "win_rate": float(win_rate),
        "profit_loss_ratio": float(pl_ratio),
        "total_trades": len(trades_pnl),
        "annual_turnover": float(turnover),
    })

    strat_daily_rets = np.diff(eq_df["strategy_net_value"]) / eq_df["strategy_net_value"].iloc[:-1]
    bm_daily_rets = np.diff(eq_df["benchmark_net_value"]) / eq_df["benchmark_net_value"].iloc[:-1]

    alpha_decomp = decompose_alpha_beta(strat_daily_rets, bm_daily_rets)
    dsr_result = compute_deflated_sharpe(strat_daily_rets, n_trials=30)
    mc_result = run_monte_carlo_block_bootstrap(trades_pnl, iters=5000, block_size=6)

    # 2022 熊市压力测试
    eq_df["year"] = pd.to_datetime(eq_df["date"]).dt.year
    sub_2022 = eq_df[eq_df["year"] == 2022]
    bear_2022 = {}
    if not sub_2022.empty:
        s_2022 = sub_2022["equity"].iloc[-1] / sub_2022["equity"].iloc[0] - 1.0
        b_2022 = sub_2022["benchmark"].iloc[-1] / sub_2022["benchmark"].iloc[0] - 1.0
        mdd_2022 = float(np.min(sub_2022["drawdown"]))
        bear_2022 = {
            "strategy_return": float(s_2022),
            "benchmark_return": float(b_2022),
            "alpha": float(s_2022 - b_2022),
            "max_drawdown": float(mdd_2022),
        }

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


def main():
    print("=" * 70)
    print("开始执行 A 股量化策略回测与最新数据测试 (截止 2026-09-02)")
    print("=" * 70)

    all_data = load_all_universe()

    cfg_top3 = {
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

    # 1. 全样本 (2019-01-01 ~ 2026-09-02)
    print("\n>>> 运行: 全样本 (2019-01-01 ~ 2026-09-02)...")
    res_full = run_single_backtest(all_data, cfg_top3, "2019-01-01", "2026-09-02")

    # 2. 样本内 (2019-01-01 ~ 2023-12-31)
    print("\n>>> 运行: 历史样本内 (2019-01-01 ~ 2023-12-31)...")
    res_is = run_single_backtest(all_data, cfg_top3, "2019-01-01", "2023-12-31")

    # 3. 2024~2026 样本外 (2024-01-01 ~ 2026-02-27)
    print("\n>>> 运行: 样本外盲测 (2024-01-01 ~ 2026-02-27)...")
    res_oos = run_single_backtest(all_data, cfg_top3, "2024-01-01", "2026-02-27")

    # 4. 【核心关注】最新绝密测试段 (2026-03-01 ~ 2026-09-02)
    print("\n>>> 运行: 最新绝密测试段 (Ultra-Recent OOS: 2026-03-01 ~ 2026-09-02)...")
    res_recent = run_single_backtest(all_data, cfg_top3, "2026-03-01", "2026-09-02")

    payload = {
        "metadata": {
            "title": "A股核心赛道龙头截面相对强弱 Alpha 策略 (EP004 增强版)",
            "benchmark": "沪深300ETF (510300.SS)",
            "universe_size": len(UNIVERSE),
            "universe": UNIVERSE,
            "latest_date": "2026-09-02",
            "backtest_range": "2019-01-01 ~ 2026-09-02",
            "ep004_evaluation": {
                "alpha_decomposition": res_full["alpha_decomp"],
                "deflated_sharpe": res_full["dsr"],
                "monte_carlo_bootstrap": res_full["monte_carlo"],
                "bear_stress_test_2022": res_full["bear_stress_test"],
                "ultra_recent_oos": {
                    "start_date": "2026-03-01",
                    "end_date": "2026-09-02",
                    "metrics": res_recent["metrics"],
                    "alpha_decomp": res_recent["alpha_decomp"],
                }
            },
        },
        "full_sample_top3": {
            "metrics": res_full["metrics"],
            "yearly_stats": res_full["yearly"],
            "equity_curve": res_full["equity_curve"],
            "recent_positions": res_full["positions_history"][-20:],
            "recent_trades": res_full["trades"][-50:],
        },
        "in_sample": {
            "metrics": res_is["metrics"],
            "yearly_stats": res_is["yearly"],
            "alpha_decomp": res_is["alpha_decomp"],
        },
        "out_of_sample": {
            "metrics": res_oos["metrics"],
            "yearly_stats": res_oos["yearly"],
            "alpha_decomp": res_oos["alpha_decomp"],
            "equity_curve": res_oos["equity_curve"],
        },
        "ultra_recent_oos": {
            "metrics": res_recent["metrics"],
            "yearly_stats": res_recent["yearly"],
            "alpha_decomp": res_recent["alpha_decomp"],
            "equity_curve": res_recent["equity_curve"],
        }
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] 最新回测数据更新完成，写入: {OUT_JSON}")


if __name__ == "__main__":
    main()
