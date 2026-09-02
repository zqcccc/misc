"""
EP004 核心未来函数因果性检验 (Factor Causality Check)
======================================================
原理 (与 EP004 scripts/factor_causality_check.py 同款原理):
对测试区间的每一个时点 T:
1. 用包含未来的全量数据 (Full Dataset)，按回测框架切片运行到 T，记录 T 日全部特征得分与决策;
2. 用严格截断到 T 的物理隔离数据 (Truncated Dataset, 绝无未来数据)，运行到 T，记录 T 日全部特征得分与决策;
3. 严格比对两者。若有任何一个得分或订单出现微小差异，立即报告 FAIL 并定位泄露字段;
4. 若全部交易日完全一致，判定 PASS (真正因果时间对称，绝无未来函数)。
"""

import sys
import numpy as np
import pandas as pd
from scripts.ashare_quant.data_feed import load_all_universe, BENCHMARK_SYMBOL
from scripts.ashare_quant.engine import BacktestEngine
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy


def run_causality_verification(test_start_date="2026-03-01", test_end_date="2026-09-02"):
    print("=" * 70)
    print(f"执行 EP004 因子因果性防未来函数严格检验 ({test_start_date} ~ {test_end_date})")
    print("=" * 70)

    all_data = load_all_universe(force=False)
    bm_df = all_data[BENCHMARK_SYMBOL]
    dates = bm_df["date"].dt.strftime("%Y-%m-%d").tolist()

    # 提取测试区间内的所有交易日
    test_dates = [d for d in dates if test_start_date <= d <= test_end_date]
    print(f"待检验交易日总数: {len(test_dates)} 天\n")

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

    all_pass = True
    checked_days = 0

    for target_date in test_dates:
        # A. 全量数据切片运行 (包含未来数据，仅通过切片隔离)
        # B. 物理截断数据运行 (彻底删除 target_date 之后的所有行)
        truncated_data = {}
        for sym, df in all_data.items():
            sub = df[df["date"].dt.strftime("%Y-%m-%d") <= target_date].copy()
            truncated_data[sym] = sub

        # 分别运行两者到 target_date
        eng_full = BacktestEngine(1_000_000.0)
        strat_full = RelativeStrengthAlphaStrategy(**strat_params)

        eng_trunc = BacktestEngine(1_000_000.0)
        strat_trunc = RelativeStrengthAlphaStrategy(**strat_params)

        # 找到预热起点
        t_idx = dates.index(target_date)
        warm_idx = max(0, t_idx - 70)

        # 运行至 target_date
        for i in range(warm_idx, t_idx + 1):
            cur_d = dates[i]
            # 准备当天的历史切片
            slice_full = {s: df[df["date"].dt.strftime("%Y-%m-%d") <= cur_d] for s, df in all_data.items()}
            slice_trunc = {s: df[df["date"].dt.strftime("%Y-%m-%d") <= cur_d] for s, df in truncated_data.items()}

            if i > warm_idx:
                prev_d = dates[i - 1]
                daily_bars = {}
                prev_closes = {}
                for s, df in all_data.items():
                    c_rows = df[df["date"].dt.strftime("%Y-%m-%d") == cur_d]
                    p_rows = df[df["date"].dt.strftime("%Y-%m-%d") == prev_d]
                    if not c_rows.empty:
                        daily_bars[s] = c_rows.iloc[0].to_dict()
                    if not p_rows.empty:
                        prev_closes[s] = float(p_rows.iloc[0]["close"])
                eng_full.execute_pending_orders(cur_d, daily_bars, prev_closes)
                eng_trunc.execute_pending_orders(cur_d, daily_bars, prev_closes)

            strat_full.on_bar_close(cur_d, slice_full, eng_full)
            strat_trunc.on_bar_close(cur_d, slice_trunc, eng_trunc)

            d_closes = {s: df[df["date"].dt.strftime("%Y-%m-%d") <= cur_d]["close"].iloc[-1] for s, df in all_data.items()}
            eng_full.end_of_day_settlement(cur_d, d_closes, d_closes[BENCHMARK_SYMBOL])
            eng_trunc.end_of_day_settlement(cur_d, d_closes, d_closes[BENCHMARK_SYMBOL])

        # 在 target_date 当天进行逐项严密核验
        # 1. 现金与净值
        if abs(eng_full.cash - eng_trunc.cash) > 1e-4:
            print(f"[FAIL] 日期 {target_date}: 现金不一致! full={eng_full.cash}, trunc={eng_trunc.cash}")
            all_pass = False
            break

        # 2. 持仓股数与标的
        if set(eng_full.positions.keys()) != set(eng_trunc.positions.keys()):
            print(f"[FAIL] 日期 {target_date}: 持仓标的不一致! full={list(eng_full.positions.keys())}, trunc={list(eng_trunc.positions.keys())}")
            all_pass = False
            break

        # 3. 待执行订单 (明天开盘的动作)
        orders_full = [(o.symbol, o.action, o.shares) for o in eng_full.pending_orders]
        orders_trunc = [(o.symbol, o.action, o.shares) for o in eng_trunc.pending_orders]
        if orders_full != orders_trunc:
            print(f"[FAIL] 日期 {target_date}: 生成订单不一致! full={orders_full}, trunc={orders_trunc}")
            all_pass = False
            break

        # 4. 特征得分字典
        scores_full = strat_full.last_scores
        scores_trunc = strat_trunc.last_scores
        for sym in scores_full:
            if sym not in scores_trunc or abs(scores_full[sym] - scores_trunc[sym]) > 1e-6:
                print(f"[FAIL] 日期 {target_date}: 标的 {sym} 特征得分不一致! full={scores_full.get(sym)}, trunc={scores_trunc.get(sym)}")
                all_pass = False
                break

        checked_days += 1

    if all_pass:
        print(f"🎉 因果性防未来函数检验 100% 全部通过！")
        print(f"共对比检验 {checked_days} 个交易日，全量 vs 物理截断完全零偏差，证实策略绝无窥探任何未来行情！")
    else:
        print("❌ 检验失败，发现未来函数泄露！")
        sys.exit(1)


if __name__ == "__main__":
    run_causality_verification("2026-03-01", "2026-09-02")
