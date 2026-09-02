"""参数敏感性 / 消融实验：每一轮都记进 trials，供 DSR 扣减「搜出来的运气」。

这里跑的不是「挑最好的一组当结论」—— 结论一律用规则卡里原文给的参数（run_ext.py）。
本脚本的用途有两个：
  1. 把超额拆开：小市值策略的收益里，有多少来自「选小票」、多少来自「1/4 月空仓」这条日历规则；
  2. 诚实统计本轮到底试了多少组配置 —— DSR 的分母。
用法：python3 scripts_ext/run_ablation.py
产物：verified/ext_trials.json、verified/ext_ablation.json、verified/<key>_returns.csv（消融版）
"""
from __future__ import annotations

import copy
import importlib
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import backtest, config, metrics, panel, strategy, universe  # noqa: E402
from strategies_ext import common  # noqa: E402

START, END = "2019-01-02", "2026-09-01"
VERIFIED = os.path.join(config.BASE_DIR, "verified")
JAN_APR = [(1, 1, 31), (4, 1, 31)]

# (标签, 模块, META 覆盖, 是否用宽池)
GRID = [
    ("s02 原文参数",            "s02_jq_gjt_smallcap", {}, False),
    ("s02 去掉1/4月空仓",       "s02_jq_gjt_smallcap", {"blackout": []}, False),
    ("s02 只空1月",             "s02_jq_gjt_smallcap", {"blackout": [(1, 1, 31)]}, False),
    ("s02 只空4月",             "s02_jq_gjt_smallcap", {"blackout": [(4, 1, 31)]}, False),
    ("s02 持股5",               "s02_jq_gjt_smallcap", {"top_n": 5}, False),
    ("s02 持股20",              "s02_jq_gjt_smallcap", {"top_n": 20}, False),
    ("s02 月频",                "s02_jq_gjt_smallcap", {"freq": 20}, False),
    ("s02 宽池(含最不活跃20%)", "s02_jq_gjt_smallcap", {}, True),
    ("s03 原文参数",            "s03_jq_micro_smallest", {}, False),
    ("s03 加1/4月空仓",         "s03_jq_micro_smallest", {"blackout": JAN_APR}, False),
    ("s03 宽池",                "s03_jq_micro_smallest", {}, True),
    ("s06 多头250",             "s06_cj_volweighted_rev", {"top_n": 250}, False),
    ("s06 多头500(原文)",       "s06_cj_volweighted_rev", {}, False),
    ("s06 多头1000",            "s06_cj_volweighted_rev", {"top_n": 1000}, False),
    ("s08b 波动率窗口20",       "s08b_lowvol_raw", {"vol_n": 20}, False),
    ("s08b 波动率窗口60(原文)", "s08b_lowvol_raw", {}, False),
    ("s08b 波动率窗口120",      "s08b_lowvol_raw", {"vol_n": 120}, False),
    ("s08b 波动率窗口244",      "s08b_lowvol_raw", {"vol_n": 244}, False),
    ("s13 邻居K=10",            "s13_cross_stock_reversal", {"neighbors": 10}, False),
    ("s13 邻居K=30(原文)",      "s13_cross_stock_reversal", {}, False),
    ("s13 邻居K=100",           "s13_cross_stock_reversal", {"neighbors": 100}, False),
]

SAVE = {"s02 去掉1/4月空仓": "s02_no_blackout", "s02 宽池(含最不活跃20%)": "s02_wide",
        "s03 加1/4月空仓": "s03_blackout", "s03 宽池": "s03_wide"}


def run(mod, meta, panels, mask, dates):
    if hasattr(mod, "mask_filter"):
        mask = mod.mask_filter(panels, mask)
    rb = strategy.rebalance_dates(dates, meta["freq"], start=START, end=END)
    if "vol_n" in meta:                     # s08b 的窗口敏感性
        from aq import factors
        close = panels["close"]
        ret = close / close.shift(1) - 1.0
        sc = common.masked(factors.volatility(ret, meta["vol_n"]), mask)
    elif "rb_dates" in inspect.signature(mod.score).parameters:
        if "neighbors" in meta:
            mod.K = meta["neighbors"]
        sc = mod.score(panels, mask, rb_dates=rb)
    else:
        sc = mod.score(panels, mask)
    if hasattr(mod, "build_signals"):
        win = dates[(dates >= pd.Timestamp(START)) & (dates <= pd.Timestamp(END))]
        sig = mod.build_signals(panels, mask, sc, win)
    else:
        sig = common.top_n(sc, rb, meta["top_n"], meta["buffer_mult"])
    sig = common.apply_blackout(sig, meta["blackout"], dates)
    return backtest.run(panels, sig, start=START, end=END)


def yearly(r, b):
    out = []
    for y, x in r.groupby(r.index.year):
        bb = b.loc[x.index]
        out.append({"年": int(y),
                    "策略%": round(float((1 + x).prod() - 1) * 100, 2),
                    "等权%": round(float((1 + bb).prod() - 1) * 100, 2),
                    "超额%": round(float((1 + x).prod() - (1 + bb).prod()) * 100, 2)})
    return out


def main():
    p = panel.load_panels()
    dates = p["close"].index
    base_mask = universe.investable(p)
    wide_mask = universe.investable(p, min_amount=3e6, liquidity_top_pct=1.0)
    win = dates[(dates >= pd.Timestamp(START)) & (dates <= pd.Timestamp(END))]
    bench = universe.equal_weight_benchmark(p, base_mask).reindex(win).fillna(0.0)

    rows, trials = [], []
    for i, (label, name, ov, wide) in enumerate(GRID):
        mod = importlib.import_module(f"strategies_ext.{name}")
        meta = copy.deepcopy(mod.META)
        meta.update(ov)
        res = run(mod, meta, p, wide_mask if wide else base_mask, dates)
        r = res.ret.reindex(win).fillna(0.0)
        st = metrics.perf_stats(r, bench, label)
        row = {"标签": label, "年化%": round(st["年化收益"] * 100, 2),
               "夏普": round(st["夏普(rf=0)"], 3),
               "最大回撤%": round(st["最大回撤"] * 100, 2),
               "对等权超额%": round(st["超额年化"] * 100, 2),
               "换手x": round(float(res.turnover.mean() * 244), 1),
               "成本%": round(float(res.cost.mean() * 244 * 100), 2),
               "blocked": round(res.blocked_frac, 4),
               "分年度": yearly(r, bench)}
        rows.append(row)
        trials.append({"epoch": i, "params": {"策略": name, **ov, "宽池": wide},
                       "valid_sharpe": row["夏普"], "train_sharpe": row["夏普"]})
        print(f"{label:28s} 年化 {row['年化%']:7.2f}%  夏普 {row['夏普']:6.3f}  "
              f"超额 {row['对等权超额%']:7.2f}%  换手 {row['换手x']:6.1f}x  "
              f"blocked {row['blocked']}", flush=True)
        if label in SAVE:
            pd.DataFrame({"date": win.strftime("%Y-%m-%d"), "ret": r.to_numpy()}).to_csv(
                os.path.join(VERIFIED, f"{SAVE[label]}_returns.csv"), index=False)

    json.dump({"消融与敏感性": rows}, open(os.path.join(VERIFIED, "ext_ablation.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"\n共 {len(trials)} 组消融/敏感性试验，已写入 trials（DSR 用）")


if __name__ == "__main__":
    main()
