"""统计显著性验证：alpha/beta 归因、Deflated Sharpe、蒙特卡洛、随机组合置换检验。

用法：python3 scripts/run_validation.py [--iters 200] [--top-n 50] [--freq 20]
产物：reports/validation.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import (backtest, config, factors, metrics, panel, strategy,  # noqa: E402
                universe, validate, walkforward)


def ann(ret: pd.Series) -> float:
    return float((1 + ret).prod() ** (metrics.TRADING_DAYS / len(ret)) - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=200, help="随机组合次数")
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--freq", type=int, default=20)
    ap.add_argument("--buffer", type=float, default=2.0)
    ap.add_argument("--start", default="2019-01-02")
    args = ap.parse_args()
    t0 = time.time()

    p = panel.load_panels()
    close = p["close"]
    dates = close.index
    mask = universe.investable(p)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(p).items()}

    print("重建滚动样本外策略 ...", flush=True)
    sig, _ = walkforward.build_signals(fp, mask, close, start=args.start,
                                       end=config.BACKTEST_END, freq=args.freq,
                                       top_n=args.top_n, buffer_mult=args.buffer)
    res = backtest.run(p, sig, start=args.start, end=config.BACKTEST_END)
    res_gross = backtest.run(p, sig, start=args.start, end=config.BACKTEST_END, zero_cost=True)
    r = res.ret
    idx = r.index

    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).reindex(idx).fillna(0.0)
    zz500 = panel.load_index("sh000905")["close"].reindex(dates).astype(float)
    zz500_ret = (zz500 / zz500.shift(1) - 1.0).reindex(idx).fillna(0.0)
    ew = universe.equal_weight_benchmark(p, mask).reindex(idx).fillna(0.0)
    style = ew - hs300_ret          # 小盘/等权风格因子

    print("\n=== 1. alpha / beta 归因（Newey-West t，滞后 5 期）===")
    models = {
        "对沪深300": validate.alpha_beta(r, {"沪深300": hs300_ret}),
        "对等权全A": validate.alpha_beta(r, {"等权全A": ew}),
        "对沪深300+小盘风格": validate.alpha_beta(r, {"沪深300": hs300_ret, "小盘风格": style}),
        "毛收益对沪深300+小盘风格": validate.alpha_beta(
            res_gross.ret, {"沪深300": hs300_ret, "小盘风格": style}),
    }
    for k, v in models.items():
        if not v:
            continue
        line = (f"  {k:<24} 年化alpha {v['年化alpha'] * 100:6.2f}%  "
                f"t={v['alpha_t(NW)']:5.2f}  p={v['alpha_p值(双侧)']:.4f}  R²={v['R2']:.3f}  "
                + "  ".join(f"β_{n.split('_', 1)[1]}={val:.2f}"
                            for n, val in v.items() if n.startswith("beta_")))
        print(line, flush=True)

    print("\n=== 2. Deflated Sharpe ===")
    grid = None
    gp = os.path.join(config.REPORT_DIR, "grid.json")
    if os.path.exists(gp):
        grid = json.load(open(gp))
    if grid:
        trial_sharpes = [g["全样本夏普"] for g in grid if g.get("全样本夏普") is not None]
        n_trials = len(trial_sharpes) + len(fp)     # 参数组合 + 因子筛选各算一次试验
        var = float(np.var(trial_sharpes, ddof=1)) if len(trial_sharpes) > 1 else 0.25
    else:
        n_trials, var = 40, 0.25
        print("  （未找到 grid.json，用保守默认：40 次试验、方差 0.25）")
    dsr = validate.deflated_sharpe(r, n_trials, var)
    for k, v in dsr.items():
        print(f"  {k}: {v}")

    print("\n=== 3. Block bootstrap 蒙特卡洛 ===")
    mc_abs = validate.block_bootstrap(r, iters=5000, block=10, seed=7)
    mc_exc = validate.block_bootstrap(r - ew, iters=5000, block=10, seed=7)
    print(f"  绝对收益：盈利路径 {mc_abs['盈利路径占比'] * 100:.1f}%  "
          f"P5={mc_abs['P5']:.2f} P50={mc_abs['P50']:.2f} P95={mc_abs['P95']:.2f}")
    print(f"  超额收益：为正路径 {mc_exc['盈利路径占比'] * 100:.1f}%  "
          f"P5={mc_exc['P5']:.2f} P50={mc_exc['P50']:.2f} P95={mc_exc['P95']:.2f}")

    print(f"\n=== 4. 随机组合置换检验（{args.iters} 次，零成本口径）===", flush=True)
    rb = strategy.rebalance_dates(dates, args.freq, start=args.start, end=config.BACKTEST_END)
    strat_gross_ann = ann(res_gross.ret)
    rand_ann, rand_alpha, rand_to = [], [], []
    for i in range(args.iters):
        rs = validate.random_scores(mask, rb, seed=1000 + i)
        rsig = strategy.top_n_signals_buffered(rs, rb, args.top_n, args.buffer)
        rres = backtest.run(p, rsig, start=args.start, end=config.BACKTEST_END, zero_cost=True)
        rand_ann.append(ann(rres.ret))
        ab = validate.alpha_beta(rres.ret, {"沪深300": hs300_ret, "小盘风格": style})
        rand_alpha.append(ab.get("年化alpha", np.nan))
        rand_to.append(float(rres.turnover.mean() * metrics.TRADING_DAYS))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{args.iters} ...", flush=True)
    rand_ann = np.array(rand_ann)
    rand_alpha = np.array(rand_alpha, dtype=float)
    strat_alpha_gross = models["毛收益对沪深300+小盘风格"]["年化alpha"]
    pct_ann = validate.percentile_rank(strat_gross_ann, rand_ann)
    pct_alpha = validate.percentile_rank(strat_alpha_gross, rand_alpha[~np.isnan(rand_alpha)])
    p_ann = validate.permutation_p(strat_gross_ann, rand_ann)
    p_alpha = validate.permutation_p(strat_alpha_gross, rand_alpha)
    print(f"  策略毛年化 {strat_gross_ann * 100:.2f}% vs 随机组合 "
          f"均值 {rand_ann.mean() * 100:.2f}% / P5 {np.percentile(rand_ann, 5) * 100:.2f}% "
          f"/ P95 {np.percentile(rand_ann, 95) * 100:.2f}%")
    print(f"  百分位 {pct_ann * 100:.1f}%  →  置换检验单侧 p = {p_ann:.4f}")
    print(f"  策略毛 alpha {strat_alpha_gross * 100:.2f}% vs 随机组合 alpha 均值 "
          f"{np.nanmean(rand_alpha) * 100:.2f}%，百分位 {pct_alpha * 100:.1f}%，"
          f"单侧 p = {p_alpha:.4f}")
    print(f"  换手对照：策略 {res_gross.turnover.mean() * metrics.TRADING_DAYS:.1f}×，"
          f"随机组合均值 {np.mean(rand_to):.1f}×")

    out = {
        "参数": vars(args),
        "区间": f"{idx[0].date()} ~ {idx[-1].date()}",
        "alpha归因": models,
        "DSR": dsr,
        "蒙特卡洛_绝对": mc_abs,
        "蒙特卡洛_超额": mc_exc,
        "随机组合": {
            "次数": args.iters,
            "策略毛年化": round(strat_gross_ann, 4),
            "策略净年化": round(ann(r), 4),
            "随机均值": round(float(rand_ann.mean()), 4),
            "随机P5": round(float(np.percentile(rand_ann, 5)), 4),
            "随机P50": round(float(np.percentile(rand_ann, 50)), 4),
            "随机P95": round(float(np.percentile(rand_ann, 95)), 4),
            "百分位": round(pct_ann, 4), "p值": round(p_ann, 4),
            "策略毛alpha": round(strat_alpha_gross, 4),
            "随机alpha均值": round(float(np.nanmean(rand_alpha)), 4),
            "随机alphaP95": round(float(np.nanpercentile(rand_alpha, 95)), 4),
            "alpha百分位": round(pct_alpha, 4), "alpha_p值": round(p_alpha, 4),
            "策略换手": round(float(res_gross.turnover.mean() * metrics.TRADING_DAYS), 2),
            "随机换手": round(float(np.mean(rand_to)), 2),
            "随机年化分布": [round(float(x), 4) for x in rand_ann],
            "随机alpha分布": [round(float(x), 4) for x in rand_alpha],
        },
    }
    with open(os.path.join(config.REPORT_DIR, "validation.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n用时 {time.time() - t0:.0f}s，结果写入 reports/validation.json")


if __name__ == "__main__":
    main()
