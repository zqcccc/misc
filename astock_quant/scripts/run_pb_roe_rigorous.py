"""A股 PB+ROE 双分位策略严谨回测与四层证伪全流程。

全量检验变体：
1. 50/50 纯双打分 Top 20 (月频)
2. 50/50 纯双打分 Top 10 (月频)
3. 70/30 纯双打分 Top 20 (月频)
4. PB+ROE 门槛版 (ROE>=10% & PB在0.5~5.0) Top 20 (月频)
5. PB+ROE 门槛版 (ROE>=10% & PB在0.5~5.0) Top 20 (每年5月调仓)
6. 线上看板双分位阈值版 (PB分位<=35% & ROE分位>=60%) Top 20 (月频)
7. 线上看板双分位阈值版 (PB分位<=35% & ROE分位>=60%) Top 10 (月频)

严格遵循因果律与交易摩擦约束：
- 信号 T 日收盘计算，T+1 日开盘价成交撮合
- 开盘涨停不可买入、跌停不可卖出、一字板不可成交、停牌不可交易
- 扣除佣金万2.5、过户费、10bp真实滑点、历史印花税
"""
from __future__ import annotations

import os
import json
import time
import numpy as np
import pandas as pd

from aq import panel, universe, backtest, metrics, validate, strategies_pb_roe


def annual_rebalance_dates(dates: pd.DatetimeIndex, month: int = 5) -> pd.DatetimeIndex:
    s = pd.Series(dates, index=dates)
    groups = s.groupby([s.dt.year, s.dt.month])
    rb = []
    years = sorted(list(set(dates.year)))
    for y in years:
        if (y, month) in groups.indices:
            idx = groups.indices[(y, month)]
            rb.append(dates[idx[0]])
    return pd.DatetimeIndex(rb)


def compute_threshold_score(pb: pd.DataFrame, roe: pd.DataFrame, mask: pd.DataFrame,
                            pb_thresh: float = 0.35, roe_thresh: float = 0.60) -> pd.DataFrame:
    """线上看板双分位过滤逻辑：
    低 PB 分位 <= 35% 且 高 ROE 分位 >= 60% 的交集中挑选综合打分最高者。
    """
    pb_valid = pb.where(mask)
    roe_valid = roe.where(mask)

    pb_rank = pb_valid.rank(axis=1, pct=True, ascending=True)       # 越小越好
    roe_rank = roe_valid.rank(axis=1, pct=True, ascending=True)     # 越大越好

    # 双分位门槛
    dual_mask = mask & (pb_rank <= pb_thresh) & (roe_rank >= roe_thresh)

    # 综合打分
    score = 0.5 * (1.0 - pb_rank) + 0.5 * roe_rank
    return score.where(dual_mask)


def run_all_evaluations():
    t0 = time.time()
    print("=" * 75)
    print("  A股 PB+ROE 双分位选股策略 · 工业级严谨回测与证伪审查 (全变体矩阵)")
    print("=" * 75)

    print("\n[Step 1] 加载行情与 PIT 财报面板...")
    p = panel.load_panels(["open", "high", "low", "close", "close_raw", "volume", "amount"])
    p["pb"] = pd.read_parquet("astock_quant/data/panel/pb.parquet")
    p["roe"] = pd.read_parquet("astock_quant/data/panel/roe.parquet")
    trading_dates = p["close"].index

    print("\n[Step 2] 构建可投股票池与基准...")
    mask = universe.investable(p)
    bench_ew = universe.equal_weight_benchmark(p, mask)
    hs300 = panel.load_index("sh000300")
    hs300_close = hs300["close"].reindex(trading_dates).ffill()
    bench_hs300 = (hs300_close / hs300_close.shift(1) - 1.0).fillna(0.0)

    bt_start = "2016-01-04"
    bt_end = "2026-09-01"
    sub_dates = trading_dates[(trading_dates >= pd.Timestamp(bt_start)) & (trading_dates <= pd.Timestamp(bt_end))]
    rb_dates_monthly = trading_dates[::20]
    rb_dates_monthly = rb_dates_monthly[(rb_dates_monthly >= pd.Timestamp(bt_start)) & (rb_dates_monthly <= pd.Timestamp(bt_end))]
    rb_dates_annual = annual_rebalance_dates(trading_dates, month=5)
    rb_dates_annual = rb_dates_annual[(rb_dates_annual >= pd.Timestamp(bt_start)) & (rb_dates_annual <= pd.Timestamp(bt_end))]

    print(f"  回测区间: {bt_start} ~ {bt_end} (共 {len(sub_dates)} 交易日)")

    print("\n[Step 3] 计算各策略打分矩阵...")
    # 纯排名
    score_5050 = strategies_pb_roe.compute_pb_roe_score(p["pb"], p["roe"], mask, weight_pb=0.5, weight_roe=0.5)
    score_7030 = strategies_pb_roe.compute_pb_roe_score(p["pb"], p["roe"], mask, weight_pb=0.7, weight_roe=0.3)
    # 门槛版 (ROE >= 10%, PB 0.5~5.0)
    score_gated = strategies_pb_roe.compute_pb_roe_score(
        p["pb"], p["roe"], mask, weight_pb=0.5, weight_roe=0.5, pb_min=0.5, pb_max=5.0, roe_min=10.0
    )
    # 线上双分位阈值版 (PB <= 35% & ROE >= 60%)
    score_thresh = compute_threshold_score(p["pb"], p["roe"], mask, pb_thresh=0.35, roe_thresh=0.60)

    variants = [
        ("纯打分 50/50 (Top20, 月频)", score_5050, rb_dates_monthly, 20, 1),
        ("纯打分 50/50 (Top10, 月频)", score_5050, rb_dates_monthly, 10, 1),
        ("纯打分 70/30 (Top20, 月频)", score_7030, rb_dates_monthly, 20, 1),
        ("门槛版 PB0.5-5 ROE>=10% (Top20, 月频)", score_gated, rb_dates_monthly, 20, 1),
        ("门槛版 PB0.5-5 ROE>=10% (Top20, 每年5月调仓)", score_gated, rb_dates_annual, 20, 1),
        ("线上双分位阈值 35/60 (Top20, 月频)", score_thresh, rb_dates_monthly, 20, 1),
        ("线上双分位阈值 35/60 (Top10, 月频)", score_thresh, rb_dates_monthly, 10, 1),
    ]

    results = {}
    perf_rows = []

    print("\n[Step 4] 执行全变体严谨撮合回测...")
    for name, score_df, rbs, top_n, buf in variants:
        t_sub = time.time()
        signals = strategies_pb_roe.generate_signals(score_df, rbs, top_n=top_n, buffer_mult=buf)
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

    print("\n" + "=" * 75)
    print("  📊 各策略严谨回测指标对比表 (扣除真实交易摩擦)")
    print("=" * 75)
    df_perf = metrics.stats_frame(perf_rows)
    print(df_perf.to_string(index=False))

    # 重点评估线上同款策略：线上双分位阈值 35/60 (Top10, 月频)
    target_name = "线上双分位阈值 35/60 (Top10, 月频)"
    target_res = results[target_name]
    target_ret = target_res.ret.dropna()

    print("\n" + "=" * 75)
    print(f"  🔬 深度证伪审计: {target_name}")
    print("=" * 75)

    # 1. 摩擦损耗
    total_cost = float(target_res.cost.sum())
    gross_pnl = float(target_res.equity.iloc[-1] - target_res.equity.iloc[0] + total_cost)
    net_pnl = float(target_res.equity.iloc[-1] - target_res.equity.iloc[0])
    cost_drag = (total_cost / gross_pnl) * 100 if gross_pnl > 0 else 0
    print(f"\n[1. 交易摩擦损耗]")
    print(f"  期末净资产:   {target_res.equity.iloc[-1]:,.2f} 元")
    print(f"  毛利润:       {gross_pnl:,.2f} 元")
    print(f"  净利润:       {net_pnl:,.2f} 元")
    print(f"  总摩擦成本:   {total_cost:,.2f} 元 (吞噬毛利润 {cost_drag:.2f}%)")

    # 2. Alpha/Beta 归因
    print(f"\n[2. Alpha / Beta 归因 (对沪深300及小盘风格因子)]")
    factors_dict = {
        "HS300": bench_hs300.reindex(target_ret.index),
        "EW_SMB": (bench_ew - bench_hs300).reindex(target_ret.index),
    }
    attribution = validate.alpha_beta(target_ret, factors_dict, lags=5)
    for k, v in attribution.items():
        if "alpha" in k and isinstance(v, float) and "t" not in k and "p" not in k:
            print(f"  {k}: {v*100:.2f}%")
        elif isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    # 3. 逐年收益
    print(f"\n[3. 逐年收益与超额分解]")
    years_list = sorted(list(set(target_ret.index.year)))
    yearly_table = []
    for y in years_list:
        y_ret = target_ret[target_ret.index.year == y]
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
    mc = validate.block_bootstrap(target_ret, iters=5000, block=10)
    print(f"  实际累计倍数: {mc['实际累计']:.4f}")
    print(f"  盈利路径占比 prob(profit): {mc['盈利路径占比']*100:.2f}%")
    print(f"  P5: {mc['P5']:.4f}, P50: {mc['P50']:.4f}, P95: {mc['P95']:.4f}")

    # 5. DSR
    print(f"\n[5. Deflated Sharpe Ratio (DSR)]")
    all_sharpes = [metrics.perf_stats(r.ret.dropna())['夏普(rf=0)'] for r in results.values()]
    trial_var = float(np.var(all_sharpes)) if len(all_sharpes) > 1 else 0.05
    dsr_dict = validate.deflated_sharpe(target_ret, trial_sharpe_var=trial_var, n_trials=len(variants))
    dsr_val = dsr_dict.get('DSR', 0.0)
    print(f"  DSR ({len(variants)}组试验惩罚后): {dsr_val} (判定: {dsr_dict.get('判定', '未知')})")

    # 落盘 JSON
    os.makedirs("astock_quant/reports", exist_ok=True)
    out_json = "astock_quant/reports/pb_roe_audit_results.json"
    summary_data = {
        "period": f"{bt_start} ~ {bt_end}",
        "perf_table": df_perf.to_dict("records"),
        "friction": {
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "total_cost": total_cost,
            "cost_drag_pct": cost_drag,
        },
        "attribution": attribution,
        "yearly": yearly_table,
        "monte_carlo": mc,
        "dsr": float(dsr_val),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    print(f"\n  ✓ 完整审计数据已落盘: {out_json}")
    print(f"  全流程总耗时: {time.time()-t0:.2f}s")


if __name__ == "__main__":
    run_all_evaluations()
