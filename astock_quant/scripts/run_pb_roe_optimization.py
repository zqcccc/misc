"""A股 PB+ROE 策略全维度消融与系统性优化 (Quality-Value-LowVol).

消融实验矩阵：
1. [基线] 原版 PB+ROE 50/50 纯打分 (Top 20, 月频20日)
2. [消融1] 仅换手缓冲 (buffer_mult=2.0)
3. [消融2] 仅质量防雷 (OCF > 0 & ROE >= 8% & PB >= 0.6)
4. [消融3] 仅趋势过滤 (Close >= 0.95 * MA60, 拒绝左侧阴跌)
5. [消融4] 质量防雷 + 趋势过滤 + 换手缓冲 (三项合一)
6. [终极A] Quality-Value-LowVol 复合模型 (月频20日, Top20, 缓冲2x)
   - 因子: 40% 低PB + 30% 高ROE + 30% 低波动(vol60)
   - 门槛: 现金流>0 + ROE>=8% + PB>=0.6 + 趋势>=0.95*MA60
7. [终极B] Quality-Value-LowVol 复合模型 (季频60日, Top20, 缓冲2x)
"""
from __future__ import annotations

import os
import json
import time
import numpy as np
import pandas as pd

from aq import panel, universe, backtest, metrics, validate, factors, strategies_pb_roe


def run_optimizations():
    t0 = time.time()
    print("=" * 80)
    print("  A股 PB+ROE 策略系统性优化与逐层消融实验 (Quality-Value-LowVol)")
    print("=" * 80)

    print("\n[Step 1] 加载行情、PIT 财报与量价面板...")
    p = panel.load_panels(["open", "high", "low", "close", "close_raw", "volume", "amount"])
    p["pb"] = pd.read_parquet("astock_quant/data/panel/pb.parquet")
    p["roe"] = pd.read_parquet("astock_quant/data/panel/roe.parquet")
    p["ocf"] = pd.read_parquet("astock_quant/data/panel/ocf.parquet")
    trading_dates = p["close"].index

    print("\n[Step 2] 构建基础股票池与辅助因子...")
    # 可投资池 (剔除ST、停牌、上市未满250日)
    mask_base = universe.investable(p, liquidity_top_pct=0.85)

    # 1. 均线趋势过滤: Close >= 0.95 * MA60
    ma60 = p["close"].rolling(60, min_periods=40).mean()
    trend_filter = (p["close"] >= 0.95 * ma60)

    # 2. 质量防雷门禁: OCF > 0 且 ROE >= 8% 且 PB >= 0.6
    quality_filter = (p["ocf"] > 0) & (p["roe"] >= 8.0) & (p["pb"] >= 0.6)

    # 3. 60日低波动率因子 (波动率越低分越高)
    ret_daily = p["close"] / p["close"].shift(1) - 1.0
    vol60 = factors.volatility(ret_daily, n=60) # 内部已取负号，数值越大波动越低

    # 基准
    bench_ew = universe.equal_weight_benchmark(p, mask_base)
    hs300 = panel.load_index("sh000300")
    hs300_close = hs300["close"].reindex(trading_dates).ffill()
    bench_hs300 = (hs300_close / hs300_close.shift(1) - 1.0).fillna(0.0)

    bt_start = "2016-01-04"
    bt_end = "2026-09-01"
    sub_dates = trading_dates[(trading_dates >= pd.Timestamp(bt_start)) & (trading_dates <= pd.Timestamp(bt_end))]
    rb_monthly = trading_dates[::20]
    rb_monthly = rb_monthly[(rb_monthly >= pd.Timestamp(bt_start)) & (rb_monthly <= pd.Timestamp(bt_end))]
    rb_quarterly = trading_dates[::60]
    rb_quarterly = rb_quarterly[(rb_quarterly >= pd.Timestamp(bt_start)) & (rb_quarterly <= pd.Timestamp(bt_end))]

    print(f"  回测区间: {bt_start} ~ {bt_end} (共 {len(sub_dates)} 交易日)")
    print(f"  月频调仓点数: {len(rb_monthly)} 次, 季频调仓点数: {len(rb_quarterly)} 次")

    print("\n[Step 3] 计算各消融组打分矩阵...")
    # 纯 50/50 打分
    score_raw = strategies_pb_roe.compute_pb_roe_score(p["pb"], p["roe"], mask_base, 0.5, 0.5)

    # 质量门禁打分
    mask_quality = mask_base & quality_filter
    score_quality = strategies_pb_roe.compute_pb_roe_score(p["pb"], p["roe"], mask_quality, 0.5, 0.5)

    # 趋势过滤打分
    mask_trend = mask_base & trend_filter
    score_trend = strategies_pb_roe.compute_pb_roe_score(p["pb"], p["roe"], mask_trend, 0.5, 0.5)

    # 质量 + 趋势打分
    mask_q_t = mask_base & quality_filter & trend_filter
    score_q_t = strategies_pb_roe.compute_pb_roe_score(p["pb"], p["roe"], mask_q_t, 0.5, 0.5)

    # Quality-Value-LowVol 三因子打分 (40% PB + 30% ROE + 30% LowVol)
    pb_valid = p["pb"].where(mask_q_t)
    roe_valid = p["roe"].where(mask_q_t)
    vol_valid = vol60.where(mask_q_t)

    pb_rank = 1.0 - pb_valid.rank(axis=1, pct=True, ascending=True)
    roe_rank = roe_valid.rank(axis=1, pct=True, ascending=True)
    vol_rank = vol_valid.rank(axis=1, pct=True, ascending=True)

    score_qvlv = (0.4 * pb_rank + 0.3 * roe_rank + 0.3 * vol_rank).where(mask_q_t)

    ablation_groups = [
        ("0. [基线] 原版 PB+ROE 50/50 (月频, 纯换仓)", score_raw, rb_monthly, 20, 1),
        ("1. [消融1] + 换手缓冲 2.0x", score_raw, rb_monthly, 20, 2),
        ("2. [消融2] + 质量防雷 (现金流>0, PB>=0.6)", score_quality, rb_monthly, 20, 1),
        ("3. [消融3] + 趋势过滤 (Close>=0.95*MA60)", score_trend, rb_monthly, 20, 1),
        ("4. [消融4] 质量防雷 + 趋势过滤 + 换手缓冲", score_q_t, rb_monthly, 20, 2),
        ("5. [终极A] Quality-Value-LowVol 复合模型 (月频20日)", score_qvlv, rb_monthly, 20, 2),
        ("6. [终极B] Quality-Value-LowVol 复合模型 (季频60日)", score_qvlv, rb_quarterly, 20, 2),
    ]

    results = {}
    perf_rows = []

    print("\n[Step 4] 执行严谨撮合回测 (全真实摩擦)...")
    for name, s_df, rbs, top_n, buf in ablation_groups:
        t_sub = time.time()
        signals = strategies_pb_roe.generate_signals(s_df, rbs, top_n=top_n, buffer_mult=buf)
        res = backtest.run(p, signals, start=bt_start, end=bt_end, init_cash=1e7, exec_price="open")
        results[name] = res

        r_series = res.ret.dropna()
        p_stats = metrics.perf_stats(r_series, bench=bench_hs300.reindex(r_series.index), name=name)
        p_stats["年化换手"] = round(float(res.turnover.sum() / (len(r_series) / 244.0)), 2)
        p_stats["跳过委托比"] = f"{res.blocked_frac:.2%}"
        perf_rows.append(p_stats)
        print(f"  ✓ {name}: 年化={p_stats['年化收益']*100:.2f}%, 回撤={p_stats['最大回撤']*100:.2f}%, 夏普={p_stats['夏普(rf=0)']:.2f}, 换手={p_stats['年化换手']}x ({time.time()-t_sub:.1f}s)")

    b_hs300_sub = bench_hs300.reindex(sub_dates).dropna()
    bench_stats = metrics.perf_stats(b_hs300_sub, name="基准: 沪深300")
    bench_stats["年化换手"] = 0.0
    bench_stats["跳过委托比"] = "0.00%"
    perf_rows.append(bench_stats)

    b_ew_sub = bench_ew.reindex(sub_dates).dropna()
    ew_stats = metrics.perf_stats(b_ew_sub, name="基准: 可投池等权")
    ew_stats["年化换手"] = 0.0
    ew_stats["跳过委托比"] = "0.00%"
    perf_rows.append(ew_stats)

    print("\n" + "=" * 80)
    print("  📊 优化方案逐层消融实验对比表 (2016-2026, 真实摩擦全扣除)")
    print("=" * 80)
    df_perf = metrics.stats_frame(perf_rows)
    print(df_perf.to_string(index=False))

    # 重点深度剖析终极推荐方案
    best_name = "5. [终极A] Quality-Value-LowVol 复合模型 (月频20日)"
    best_res = results[best_name]
    best_ret = best_res.ret.dropna()

    print("\n" + "=" * 80)
    print(f"  🔬 终极优化策略深度审查: {best_name}")
    print("=" * 80)

    # 1. 摩擦损耗
    total_cost = float(best_res.cost.sum())
    gross_pnl = float(best_res.equity.iloc[-1] - best_res.equity.iloc[0] + total_cost)
    net_pnl = float(best_res.equity.iloc[-1] - best_res.equity.iloc[0])
    cost_drag = (total_cost / gross_pnl) * 100 if gross_pnl > 0 else 0
    print(f"\n[1. 交易摩擦损耗对比]")
    print(f"  初始本金:     10,000,000 元")
    print(f"  期末净资产:   {best_res.equity.iloc[-1]:,.2f} 元")
    print(f"  累计总净利:   {net_pnl:,.2f} 元 (毛利 {gross_pnl:,.2f} 元)")
    print(f"  总交易成本:   {total_cost:,.2f} 元 (吞噬率降至 {cost_drag:.2f}%)")

    # 2. Alpha/Beta 归因
    print(f"\n[2. Alpha / Beta 归因 (对沪深300及小盘风格因子)]")
    factors_dict = {
        "HS300": bench_hs300.reindex(best_ret.index),
        "EW_SMB": (bench_ew - bench_hs300).reindex(best_ret.index),
    }
    attribution = validate.alpha_beta(best_ret, factors_dict, lags=5)
    for k, v in attribution.items():
        if "alpha" in k and isinstance(v, float) and "t" not in k and "p" not in k:
            print(f"  {k}: {v*100:.2f}%")
        elif isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    # 3. 逐年超额
    print(f"\n[3. 逐年收益与基准超额分布]")
    years_list = sorted(list(set(best_ret.index.year)))
    yearly_table = []
    for y in years_list:
        y_ret = best_ret[best_ret.index.year == y]
        y_hs300 = bench_hs300.reindex(y_ret.index)
        y_ew = bench_ew.reindex(y_ret.index)
        y_strat_cum = (1 + y_ret).cumprod().iloc[-1] - 1.0
        y_hs300_cum = (1 + y_hs300).cumprod().iloc[-1] - 1.0
        y_ew_cum = (1 + y_ew).cumprod().iloc[-1] - 1.0
        yearly_table.append({
            "年份": y,
            "策略收益": f"{y_strat_cum*100:.2f}%",
            "沪深300": f"{y_hs300_cum*100:.2f}%",
            "超额(vs300)": f"{(y_strat_cum - y_hs300_cum)*100:.2f}%",
            "可投等权": f"{y_ew_cum*100:.2f}%",
            "超额(vs等权)": f"{(y_strat_cum - y_ew_cum)*100:.2f}%",
        })
    df_yearly = pd.DataFrame(yearly_table)
    print(df_yearly.to_string(index=False))

    # 4. Block Bootstrap
    print(f"\n[4. 分块蒙特卡洛检验 (Block Bootstrap 5,000 次)]")
    mc = validate.block_bootstrap(best_ret, iters=5000, block=10)
    print(f"  实际累计净值倍数: {mc['实际累计']:.4f}")
    print(f"  盈利路径概率 prob(profit): {mc['盈利路径占比']*100:.2f}%")
    print(f"  5% 分位净值 (P5): {mc['P5']:.4f}, 中位数 (P50): {mc['P50']:.4f}, 95% 分位 (P95): {mc['P95']:.4f}")

    # 5. DSR 检验
    print(f"\n[5. Deflated Sharpe Ratio (DSR)]")
    all_sharpes = [metrics.perf_stats(r.ret.dropna())["夏普(rf=0)"] for r in results.values()]
    trial_var = float(np.var(all_sharpes)) if len(all_sharpes) > 1 else 0.05
    dsr_dict = validate.deflated_sharpe(best_ret, trial_sharpe_var=trial_var, n_trials=len(ablation_groups))
    print(f"  DSR ({len(ablation_groups)}组消融试验惩罚后): {dsr_dict.get('DSR', 0.0)} (判定: {dsr_dict.get('判定', '未知')})")

    # 落盘 JSON
    os.makedirs("astock_quant/reports", exist_ok=True)
    out_json = "astock_quant/reports/pb_roe_optimization_results.json"
    summary_data = {
        "period": f"{bt_start} ~ {bt_end}",
        "perf_table": df_perf.to_dict("records"),
        "best_strategy": best_name,
        "friction": {
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "total_cost": total_cost,
            "cost_drag_pct": cost_drag,
        },
        "attribution": attribution,
        "yearly": yearly_table,
        "monte_carlo": mc,
        "dsr": dsr_dict,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ 完整优化消融数据已落盘: {out_json}")
    print(f"  优化全流程耗时: {time.time()-t0:.2f}s")


if __name__ == "__main__":
    run_optimizations()
