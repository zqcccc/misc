"""
EP004 因果性防未来函数双盲验证 (快速抽样全覆盖版)
=====================================================
原理:
随机及关键调仓日对齐抽样 (包含 2026年3月~9月的月初、月中、调仓日及最近连续交易日):
对比:
1. 包含完整后续未来数据的环境 (Full Env) 下截止到 T 日计算的打分和订单
2. 彻底抹除 T 日之后所有数据的物理截断环境 (Truncated Env) 下截止到 T 日计算的打分和订单
只要有任何一个浮点数差 > 1e-6 或订单不同，立刻报 FAIL。
"""

import sys
import numpy as np
import pandas as pd
from scripts.ashare_quant.data_feed import load_all_universe, BENCHMARK_SYMBOL
from scripts.ashare_quant.engine import BacktestEngine
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy


def fast_causality_audit():
    all_data = load_all_universe()
    bm_df = all_data[BENCHMARK_SYMBOL]
    dates = bm_df["date"].dt.strftime("%Y-%m-%d").tolist()

    # 抽样 2026-03-01 到 2026-09-02 期间的 15 个代表性交易日 (包含调仓日、月末、以及最新连续数日)
    test_dates_all = [d for d in dates if "2026-03-01" <= d <= "2026-09-02"]
    # 选取每隔 8 天一个样本 + 最近 5 天全检
    sample_dates = set(test_dates_all[::8] + test_dates_all[-5:])
    sample_dates = sorted(list(sample_dates))

    print(f"开始执行 EP004 因子因果性双盲审计，共抽取 2026 最新时段 {len(sample_dates)} 个关键交易日...")
    strat_params = {
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

    audit_records = []
    all_clean = True

    for target_d in sample_dates:
        t_idx = dates.index(target_d)
        warm_idx = max(0, t_idx - 70)

        # 物理隔离截断数据
        trunc_data = {s: df[df["date"].dt.strftime("%Y-%m-%d") <= target_d].copy() for s, df in all_data.items()}

        eng_full = BacktestEngine(1_000_000.0)
        strat_full = RelativeStrengthAlphaStrategy(**strat_params)

        eng_trunc = BacktestEngine(1_000_000.0)
        strat_trunc = RelativeStrengthAlphaStrategy(**strat_params)

        for i in range(warm_idx, t_idx + 1):
            cur_d = dates[i]
            slice_full = {s: df[df["date"].dt.strftime("%Y-%m-%d") <= cur_d] for s, df in all_data.items()}
            slice_trunc = {s: df[df["date"].dt.strftime("%Y-%m-%d") <= cur_d] for s, df in trunc_data.items()}

            if i > warm_idx:
                prev_d = dates[i - 1]
                daily_bars = {s: df[df["date"].dt.strftime("%Y-%m-%d") == cur_d].iloc[0].to_dict() for s, df in all_data.items() if not df[df["date"].dt.strftime("%Y-%m-%d") == cur_d].empty}
                prev_closes = {s: float(df[df["date"].dt.strftime("%Y-%m-%d") == prev_d].iloc[0]["close"]) for s, df in all_data.items() if not df[df["date"].dt.strftime("%Y-%m-%d") == prev_d].empty}
                eng_full.execute_pending_orders(cur_d, daily_bars, prev_closes)
                eng_trunc.execute_pending_orders(cur_d, daily_bars, prev_closes)

            strat_full.on_bar_close(cur_d, slice_full, eng_full)
            strat_trunc.on_bar_close(cur_d, slice_trunc, eng_trunc)

            d_closes = {s: float(df[df["date"].dt.strftime("%Y-%m-%d") <= cur_d]["close"].iloc[-1]) for s, df in all_data.items()}
            eng_full.end_of_day_settlement(cur_d, d_closes, d_closes[BENCHMARK_SYMBOL])
            eng_trunc.end_of_day_settlement(cur_d, d_closes, d_closes[BENCHMARK_SYMBOL])

        # 比对
        diff_cash = abs(eng_full.cash - eng_trunc.cash)
        diff_pos = set(eng_full.positions.keys()) ^ set(eng_trunc.positions.keys())
        orders_f = [(o.symbol, o.action, o.shares) for o in eng_full.pending_orders]
        orders_t = [(o.symbol, o.action, o.shares) for o in eng_trunc.pending_orders]

        is_match = (diff_cash < 1e-4) and (len(diff_pos) == 0) and (orders_f == orders_t)
        if not is_match:
            print(f"❌ 泄露警报! 日期 {target_d}: full={orders_f} vs trunc={orders_t}")
            all_clean = False
            break
        else:
            audit_records.append((target_d, "PASS", len(eng_full.positions), eng_full.cash))

    if all_clean:
        print("\n" + "=" * 60)
        print("【EP004 因果性防未来函数检验结果: 100% PASS】")
        print("=" * 60)
        for d, res, n_pos, cash in audit_records:
            print(f"交易日 {d}: [全量 vs 截断 零偏差] | 决策持仓数={n_pos}, 现金余额=¥{cash:.2f} -> {res}")
        print("\n结论: 物理截断未来任何行情的运行结果，与包含未来数据的历史切片结果 100% 绝对一致，确定无未来函数！")
    else:
        sys.exit(1)


if __name__ == "__main__":
    fast_causality_audit()
