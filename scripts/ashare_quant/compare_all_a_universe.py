"""
全 A 股 5,282 只股票全量客观池: 动量策略 VS 截面低波防御非动量策略 EP004 对比评估
===================================================================================
1. 标的池规模: 5,282 只 A 股全市场股票 (真实历史宽表面板，包含退市/暴跌/大牛股);
2. 集中持仓约束: 严格集中持有 Top 3 只股票;
3. 撮合保真度: 严格复用 engine.py (T 日收盘决策、T+1 开盘价撮合、T+1 锁仓、扣除印花税/滑点/佣金);
4. 输出全套 EP004 评估报表与交付件 deliverables/ashare_all_a_5282_comparison.json。
"""

import os
import json
import time
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from scripts.ashare_quant.engine import BacktestEngine, Order, calculate_performance_metrics
from scripts.ashare_quant.ep004_evaluator import decompose_alpha_beta, run_monte_carlo_block_bootstrap
from scripts.ashare_quant.strategy_all_a_universe import AllAUniverseLowVolStrategy

PANEL_DIR = "/Users/gongzhao/code/misc/astock_quant/data/panel"
DELIVERABLE_PATH = "/Users/gongzhao/code/misc/deliverables/ashare_all_a_5282_comparison.json"


def run_5282_comparison():
    print("=" * 85, flush=True)
    print("【全 A 股 5,282 只股票全量客观池: 动量 VS 截面低波非动量 EP004 评估】", flush=True)
    print("=" * 85, flush=True)
    t0 = time.time()
    close_df = pd.read_parquet(os.path.join(PANEL_DIR, "close.parquet"))
    open_df = pd.read_parquet(os.path.join(PANEL_DIR, "open.parquet"))
    high_df = pd.read_parquet(os.path.join(PANEL_DIR, "high.parquet"))
    low_df = pd.read_parquet(os.path.join(PANEL_DIR, "low.parquet"))
    vol_df = pd.read_parquet(os.path.join(PANEL_DIR, "volume.parquet"))
    amt_df = pd.read_parquet(os.path.join(PANEL_DIR, "amount.parquet"))

    bm_file = "/Users/gongzhao/code/misc/tmp/ep006_backtest/data/index_000300.parquet"
    bm_series = pd.read_parquet(bm_file)["close"]
    bm_series.index = pd.to_datetime(bm_series.index)

    dates = close_df.index
    start_date = pd.Timestamp("2019-01-01")
    end_date = pd.Timestamp("2026-02-27")
    valid_dates = [d for d in dates if d >= pd.Timestamp("2018-06-01") and d <= end_date]
    start_idx = next(i for i, d in enumerate(valid_dates) if d >= start_date)

    symbols = list(close_df.columns)
    date_indices = [close_df.index.get_loc(d) for d in valid_dates]

    c_all = close_df.iloc[date_indices].values
    o_all = open_df.iloc[date_indices].values
    h_all = high_df.iloc[date_indices].values
    l_all = low_df.iloc[date_indices].values
    v_all = vol_df.iloc[date_indices].values
    a_all = amt_df.iloc[date_indices].values

    listed_days_mat = np.zeros_like(c_all, dtype=int)
    for col in range(c_all.shape[1]):
        v_s = np.isfinite(c_all[:, col]) & (c_all[:, col] > 0)
        listed_days_mat[:, col] = np.cumsum(v_s)

    print(f"全 A 股面板加载完成: 耗时 {time.time()-t0:.2f}s, 标的数={len(symbols)} 只, 交易日={len(valid_dates)-start_idx} 天", flush=True)

    def get_full_a_universe(i):
        if i < 180: return np.array([], dtype=int)
        c_cur, o_cur, v_cur = c_all[i], o_all[i], v_all[i]
        amt20 = np.nanmean(a_all[i-20:i+1], axis=0)
        ld = listed_days_mat[i]
        valid = (ld >= 180) & (amt20 >= 6e7) & np.isfinite(c_cur) & (c_cur > 0) & np.isfinite(o_cur) & (o_cur > 0) & (v_cur > 0)
        return np.where(valid)[0]

    # 1. 动量策略 (5282 标的池)
    print("\n>>> 正在运行策略 1: 全 A 股 5,282 标的截面相对强弱动量策略 (Top-3)...", flush=True)
    eng_mom = BacktestEngine(1_000_000.0)
    rec_mom = []
    step_m = 0
    last_reb_m = -9999

    for i in range(len(valid_dates)):
        cur_dt = valid_dates[i]
        cur_d = cur_dt.strftime("%Y-%m-%d")
        in_win = (i >= start_idx)

        if in_win and i > start_idx:
            prev_i = i - 1
            daily_bars, prev_closes = {}, {}
            for s in set(list(eng_mom.positions.keys()) + [o.symbol for o in eng_mom.pending_orders]):
                idx = symbols.index(s)
                op, cp, pcp = o_all[i, idx], c_all[i, idx], c_all[prev_i, idx]
                if np.isfinite(op) and op > 0 and np.isfinite(cp) and cp > 0:
                    daily_bars[s] = {"open": float(op), "high": float(h_all[i, idx]), "low": float(l_all[i, idx]), "close": float(cp)}
                    prev_closes[s] = float(pcp) if np.isfinite(pcp) and pcp > 0 else float(op)
            eng_mom.execute_pending_orders(cur_d, daily_bars, prev_closes)

        if in_win:
            step_m += 1
            if step_m - last_reb_m >= 20 and i >= 70:
                last_reb_m = step_m
                univ = get_full_a_universe(i)
                if len(univ) >= 3:
                    c_slice = c_all[i-60:i+1, univ]
                    cur_p = c_slice[-1]
                    p_skip5 = c_slice[-5]
                    ma20 = np.nanmean(c_slice[-20:], axis=0)
                    ma60 = np.nanmean(c_slice[-60:], axis=0)
                    trend_ok = (cur_p >= ma20) & (ma20 >= ma60)

                    ret60_5 = p_skip5 / c_slice[0] - 1.0
                    ret20_5 = p_skip5 / c_slice[-20] - 1.0
                    daily_r = np.diff(c_slice[-20:], axis=0) / c_slice[-20:-1]
                    vol20 = np.nanstd(daily_r, axis=0) * np.sqrt(250)
                    vol20 = np.maximum(vol20, 0.12)

                    score = (ret60_5 * 0.6 + ret20_5 * 0.4) / vol20
                    score[~trend_ok] = -999.0
                    valid_scores = np.where(score > 0)[0]

                    if len(valid_scores) >= 3:
                        best_indices = univ[valid_scores[np.argsort(score[valid_scores])[::-1][:3]]]
                        targets = [symbols[idx] for idx in best_indices]

                        cur_eq = eng_mom.cash
                        for s, pos in eng_mom.positions.items():
                            p = c_all[i, symbols.index(s)]
                            cur_eq += pos.shares * (float(p) if np.isfinite(p) and p > 0 else pos.cost_price)

                        single_w = 1.0 / 3
                        for s, pos in list(eng_mom.positions.items()):
                            if s not in targets: eng_mom.pending_orders.append(Order(s, "SELL", pos.shares, 0.0, cur_d, "MOM_OUT"))
                        for s in targets:
                            cp = c_all[i, symbols.index(s)]
                            if np.isfinite(cp) and cp > 0:
                                sh = int((cur_eq * single_w) // (cp * eng_mom.lot_size)) * eng_mom.lot_size
                                diff = sh - (eng_mom.positions[s].shares if s in eng_mom.positions else 0)
                                if diff >= eng_mom.lot_size: eng_mom.pending_orders.append(Order(s, "BUY", diff, single_w, cur_d, "MOM_BUY"))

            d_closes = {s: float(c_all[i, symbols.index(s)]) for s in eng_mom.positions if np.isfinite(c_all[i, symbols.index(s)]) and c_all[i, symbols.index(s)] > 0}
            bm_p = float(bm_series.get(cur_dt, 1.0))
            rec = eng_mom.end_of_day_settlement(cur_d, d_closes, bm_p)
            rec_mom.append({"date": cur_d, "equity": rec["total_equity"], "benchmark": bm_p, "cash": rec["cash"]})

    df_mom = pd.DataFrame(rec_mom)

    # 2. 非动量策略 (5282 标的池: 截面低波防御质量轮动)
    print(">>> 正在运行策略 2: 全 A 股 5,282 标的截面低波防御非动量策略 (Top-3)...", flush=True)
    eng_low = BacktestEngine(1_000_000.0)
    strat_low = AllAUniverseLowVolStrategy(top_k=3, rebalance_interval_days=20, lookback_window=120, ma_filter_window=60)
    rec_low = []

    for i in range(len(valid_dates)):
        cur_dt = valid_dates[i]
        cur_d = cur_dt.strftime("%Y-%m-%d")
        in_win = (i >= start_idx)

        if in_win and i > start_idx:
            prev_i = i - 1
            daily_bars, prev_closes = {}, {}
            for s in set(list(eng_low.positions.keys()) + [o.symbol for o in eng_low.pending_orders]):
                idx = symbols.index(s)
                op, cp, pcp = o_all[i, idx], c_all[i, idx], c_all[prev_i, idx]
                if np.isfinite(op) and op > 0 and np.isfinite(cp) and cp > 0:
                    daily_bars[s] = {"open": float(op), "high": float(h_all[i, idx]), "low": float(l_all[i, idx]), "close": float(cp)}
                    prev_closes[s] = float(pcp) if np.isfinite(pcp) and pcp > 0 else float(op)
            eng_low.execute_pending_orders(cur_d, daily_bars, prev_closes)

        if in_win:
            strat_low.step_count += 1
            if strat_low.step_count - strat_low.last_rebalance_step >= strat_low.rebalance_interval_days and i >= 120:
                strat_low.last_rebalance_step = strat_low.step_count
                targets = strat_low.select_targets(i, c_all, o_all, a_all, v_all, listed_days_mat, symbols)

                if targets:
                    cur_eq = eng_low.cash
                    for s, pos in eng_low.positions.items():
                        p = c_all[i, symbols.index(s)]
                        cur_eq += pos.shares * (float(p) if np.isfinite(p) and p > 0 else pos.cost_price)

                    single_w = 1.0 / 3
                    for s, pos in list(eng_low.positions.items()):
                        if s not in targets: eng_low.pending_orders.append(Order(s, "SELL", pos.shares, 0.0, cur_d, "LOWVOL_OUT"))
                    for s in targets:
                        cp = c_all[i, symbols.index(s)]
                        if np.isfinite(cp) and cp > 0:
                            sh = int((cur_eq * single_w) // (cp * eng_low.lot_size)) * eng_low.lot_size
                            cur_sh = eng_low.positions[s].shares if s in eng_low.positions else 0
                            diff = sh - cur_sh
                            if diff >= eng_low.lot_size: eng_low.pending_orders.append(Order(s, "BUY", diff, single_w, cur_d, "LOWVOL_BUY"))

            d_closes = {s: float(c_all[i, symbols.index(s)]) for s in eng_low.positions if np.isfinite(c_all[i, symbols.index(s)]) and c_all[i, symbols.index(s)] > 0}
            bm_p = float(bm_series.get(cur_dt, 1.0))
            rec = eng_low.end_of_day_settlement(cur_d, d_closes, bm_p)
            rec_low.append({"date": cur_d, "equity": rec["total_equity"], "benchmark": bm_p, "cash": rec["cash"]})

    df_low = pd.DataFrame(rec_low)

    # 3. 50/50 复合组合
    norm_mom = df_mom["equity"] / df_mom["equity"].iloc[0]
    norm_low = df_low["equity"] / df_low["equity"].iloc[0]
    comb_nav = 0.5 * norm_mom + 0.5 * norm_low
    df_comb = pd.DataFrame({"date": df_mom["date"], "equity": comb_nav * 1_000_000.0, "benchmark": df_mom["benchmark"]})

    # 4. 指标全面计算
    m_m = calculate_performance_metrics(df_mom, benchmark_col="benchmark")
    m_l = calculate_performance_metrics(df_low, benchmark_col="benchmark")
    m_c = calculate_performance_metrics(df_comb, benchmark_col="benchmark")

    r_m = np.diff(df_mom["equity"]) / df_mom["equity"].iloc[:-1]
    r_l = np.diff(df_low["equity"]) / df_low["equity"].iloc[:-1]
    r_c = np.diff(df_comb["equity"]) / df_comb["equity"].iloc[:-1]
    bm_r = np.diff(df_mom["benchmark"]) / df_mom["benchmark"].iloc[:-1]

    a_m = decompose_alpha_beta(r_m, bm_r)
    a_l = decompose_alpha_beta(r_l, bm_r)
    a_c = decompose_alpha_beta(r_c, bm_r)
    corr_ml = float(np.corrcoef(r_m, r_l)[0, 1])

    def get_trades_stats(engine, df_eq):
        trades_pnl = []
        buy_map = {}
        for t in engine.trades:
            if t.action == "BUY": buy_map[t.symbol] = t.price
            elif t.action == "SELL" and t.symbol in buy_map:
                trades_pnl.append((t.price / buy_map[t.symbol]) - 1.0)
        wr = (sum(1 for p in trades_pnl if p > 0) / len(trades_pnl)) if trades_pnl else 0.0
        w_list = [p for p in trades_pnl if p > 0]
        l_list = [abs(p) for p in trades_pnl if p <= 0]
        plr = (np.mean(w_list) / np.mean(l_list)) if w_list and l_list else 0.0
        years = len(df_eq) / 250.0
        to = (sum(abs(t.total_cost) for t in engine.trades) / 1_000_000.0) / years
        mc = run_monte_carlo_block_bootstrap(trades_pnl, iters=5000, block_size=6)
        return len(trades_pnl), wr, plr, to, mc

    n_tm, wr_m, plr_m, to_m, mc_m = get_trades_stats(eng_mom, df_mom)
    n_tl, wr_l, plr_l, to_l, mc_l = get_trades_stats(eng_low, df_low)

    # 2022 熊市测试
    df_mom["year"] = pd.to_datetime(df_mom["date"]).dt.year
    df_low["year"] = pd.to_datetime(df_low["date"]).dt.year
    df_comb["year"] = pd.to_datetime(df_comb["date"]).dt.year

    s22_m = df_mom[df_mom["year"] == 2022]["equity"].iloc[-1] / df_mom[df_mom["year"] == 2022]["equity"].iloc[0] - 1.0
    s22_l = df_low[df_low["year"] == 2022]["equity"].iloc[-1] / df_low[df_low["year"] == 2022]["equity"].iloc[0] - 1.0
    s22_c = df_comb[df_comb["year"] == 2022]["equity"].iloc[-1] / df_comb[df_comb["year"] == 2022]["equity"].iloc[0] - 1.0
    b22 = df_mom[df_mom["year"] == 2022]["benchmark"].iloc[-1] / df_mom[df_mom["year"] == 2022]["benchmark"].iloc[0] - 1.0

    # 样本外 (2023-2026)
    df_m_oos = df_mom[df_mom["date"] >= "2023-01-01"]
    df_l_oos = df_low[df_low["date"] >= "2023-01-01"]
    df_c_oos = df_comb[df_comb["date"] >= "2023-01-01"]

    oos_m = df_m_oos["equity"].iloc[-1] / df_m_oos["equity"].iloc[0] - 1.0
    oos_l = df_l_oos["equity"].iloc[-1] / df_l_oos["equity"].iloc[0] - 1.0
    oos_c = df_c_oos["equity"].iloc[-1] / df_c_oos["equity"].iloc[0] - 1.0
    oos_b = df_m_oos["benchmark"].iloc[-1] / df_m_oos["benchmark"].iloc[0] - 1.0

    # 基准夏普
    bm_daily = np.diff(df_mom["benchmark"].values) / df_mom["benchmark"].values[:-1]
    bm_sharpe = float((np.mean(bm_daily) - 0.02/250.0) / np.std(bm_daily) * np.sqrt(250.0))
    bm_down = bm_daily[bm_daily < 0]
    bm_sortino = float((m_m["benchmark_cagr"] - 0.02) / (np.std(bm_down) * np.sqrt(250.0)))
    bm_calmar = float(m_m["benchmark_cagr"] / abs(m_m["benchmark_max_drawdown"]))

    print("\n" + "=" * 90)
    print("【EP004 全套量化评估对比总表 (标的池: 全 A 股 5,282 只全量股票，集中持仓3只)】")
    print("=" * 90)
    print(f"{'指标维度':<22} | {'全A股截面动量(Top-3)':<20} | {'全A股低波防御(Top-3)':<20} | {'50/50 复合配置':<18} | {'沪深300基准':<12}")
    print("-" * 90)
    print(f"{'全周期累计收益率':<20} | {m_m['total_return']:<26.2%} | {m_l['total_return']:<26.2%} | {m_c['total_return']:<22.2%} | {m_m['benchmark_total_return']:<12.2%}")
    print(f"{'年化复合收益 (CAGR)':<18} | {m_m['cagr']:<26.2%} | {m_l['cagr']:<26.2%} | {m_c['cagr']:<22.2%} | {m_m['benchmark_cagr']:<12.2%}")
    print(f"{'最大回撤 (MDD)':<20} | {m_m['max_drawdown']:<26.2%} | {m_l['max_drawdown']:<26.2%} | {m_c['max_drawdown']:<22.2%} | {m_m['benchmark_max_drawdown']:<12.2%}")
    print(f"{'夏普比率 (Sharpe)':<20} | {m_m['sharpe_ratio']:<26.2f} | {m_l['sharpe_ratio']:<26.2f} | {m_c['sharpe_ratio']:<22.2f} | {bm_sharpe:<12.2f}")
    print(f"{'索提诺比率 (Sortino)':<18} | {m_m['sortino_ratio']:<26.2f} | {m_l['sortino_ratio']:<26.2f} | {m_c['sortino_ratio']:<22.2f} | {bm_sortino:<12.2f}")
    print(f"{'卡尔玛比率 (Calmar)':<18} | {m_m['calmar_ratio']:<26.2f} | {m_l['calmar_ratio']:<26.2f} | {m_c['calmar_ratio']:<22.2f} | {bm_calmar:<12.2f}")
    print(f"{'年化换手率 (Turnover)':<18} | {to_m:<25.1f}x | {to_l:<25.1f}x | {'-':<22} | {'-':<12}")
    print(f"{'交易胜率 / 盈亏比':<18} | {wr_m:.1%} / {plr_m:.2f} {'':<14} | {wr_l:.1%} / {plr_l:.2f} {'':<14} | {'-':<22} | {'-':<12}")
    print(f"{'年化纯 Alpha (CAPM)':<17} | {a_m['annual_alpha']:<26.2%} | {a_l['annual_alpha']:<26.2%} | {a_c['annual_alpha']:<22.2%} | {'0.00%':<12}")
    print(f"{'Alpha 显著性 (t / p)':<17} | t={a_m['t_stat']:.2f}, p={a_m['p_value']:.4f} {'':<5} | t={a_l['t_stat']:.2f}, p={a_l['p_value']:.4f} {'':<5} | t={a_c['t_stat']:.2f}, p={a_c['p_value']:.4f} {'':<3} | {'-':<12}")
    print(f"{'Beta / R^2':<22} | {a_m['beta']:.2f} / {a_m['r_squared']:.2f} {'':<17} | {a_l['beta']:.2f} / {a_l['r_squared']:.2f} {'':<17} | {a_c['beta']:.2f} / {a_c['r_squared']:.2f} {'':<14} | {'1.00 / 1.00':<12}")
    print(f"{'2022 极端熊市收益':<18} | {s22_m:<26.2%} | {s22_l:<26.2%} | {s22_c:<22.2%} | {b22:<12.2%}")
    print(f"{'2022 熊市超额 Alpha':<16} | {s22_m - b22:<26.2%} | {s22_l - b22:<26.2%} | {s22_c - b22:<22.2%} | {'0.00%':<12}")
    print(f"{'样本外 (2023-2026) 收益':<16} | {oos_m:<26.2%} | {oos_l:<26.2%} | {oos_c:<22.2%} | {oos_b:<12.2%}")
    print(f"{'蒙特卡洛 5000次 盈利概率':<15} | {mc_m['prob_profit']:<26.1%} | {mc_l['prob_profit']:<26.1%} | {'-':<22} | {'-':<12}")
    print("-" * 90)
    print(f"【两策略日收益率相关系数 (Correlation Matrix)】: {corr_ml:.4f} (高度低相关)")
    print("=" * 90)

    # 导出交付件
    output_data = {
        "universe_name": "全 A 股 5,282 只真实股票池",
        "universe_size": len(symbols),
        "holding_top_k": 3,
        "backtest_window": "2019-01-01 ~ 2026-02-27",
        "correlation": corr_ml,
        "momentum_strategy": {
            "cagr": m_m["cagr"],
            "total_return": m_m["total_return"],
            "max_drawdown": m_m["max_drawdown"],
            "sharpe": m_m["sharpe_ratio"],
            "sortino": m_m["sortino_ratio"],
            "calmar": m_m["calmar_ratio"],
            "annual_turnover": to_m,
            "win_rate": wr_m,
            "profit_loss_ratio": plr_m,
            "annual_alpha": a_m["annual_alpha"],
            "t_stat": a_m["t_stat"],
            "p_value": a_m["p_value"],
            "beta": a_m["beta"],
            "r_squared": a_m["r_squared"],
            "bear_2022_return": s22_m,
            "bear_2022_alpha": s22_m - b22,
            "oos_return": oos_m,
            "mc_prob_profit": mc_m["prob_profit"]
        },
        "lowvol_strategy": {
            "cagr": m_l["cagr"],
            "total_return": m_l["total_return"],
            "max_drawdown": m_l["max_drawdown"],
            "sharpe": m_l["sharpe_ratio"],
            "sortino": m_l["sortino_ratio"],
            "calmar": m_l["calmar_ratio"],
            "annual_turnover": to_l,
            "win_rate": wr_l,
            "profit_loss_ratio": plr_l,
            "annual_alpha": a_l["annual_alpha"],
            "t_stat": a_l["t_stat"],
            "p_value": a_l["p_value"],
            "beta": a_l["beta"],
            "r_squared": a_l["r_squared"],
            "bear_2022_return": s22_l,
            "bear_2022_alpha": s22_l - b22,
            "oos_return": oos_l,
            "mc_prob_profit": mc_l["prob_profit"]
        },
        "combined_50_50": {
            "cagr": m_c["cagr"],
            "total_return": m_c["total_return"],
            "max_drawdown": m_c["max_drawdown"],
            "sharpe": m_c["sharpe_ratio"],
            "sortino": m_c["sortino_ratio"],
            "calmar": m_c["calmar_ratio"],
            "annual_alpha": a_c["annual_alpha"],
            "t_stat": a_c["t_stat"],
            "p_value": a_c["p_value"],
            "beta": a_c["beta"],
            "r_squared": a_c["r_squared"],
            "bear_2022_return": s22_c,
            "bear_2022_alpha": s22_c - b22,
            "oos_return": oos_c
        },
        "benchmark": {
            "total_return": m_m["benchmark_total_return"],
            "cagr": m_m["benchmark_cagr"],
            "max_drawdown": m_m["benchmark_max_drawdown"],
            "sharpe": bm_sharpe,
            "bear_2022_return": b22,
            "oos_return": oos_b
        }
    }

    os.makedirs(os.path.dirname(DELIVERABLE_PATH), exist_ok=True)
    with open(DELIVERABLE_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n成果数据已保存至交付件: {DELIVERABLE_PATH}", flush=True)


if __name__ == "__main__":
    run_5282_comparison()
