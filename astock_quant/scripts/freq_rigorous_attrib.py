#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""beta 归因重做：只用「最广为人知 / 可直接买」的基准，不用自制合成风格因子。

上一版用 small_style = 全A等权 − 沪深300 这个自制残差因子做第二解释变量，
等于把大部分收益记在一个别人无法理解、也无法直接交易的合成因子账上 —— 那是给
alpha 打掩护。这一版只认三类基准：

  1. 沪深300（sh000300）      —— 最广为人知的大盘指数，可直接买 ETF
  2. 可投资宇宙等权           —— 策略实际能买的那批股票的等权组合（剔除 ST/次新/北交/
                                日均额<2000万），是横截面选股策略唯一诚实的对照基准
  3. 全市场等权（无任何筛选） —— 极端口径，连 ST/次新都算进去，最宽松

再跑一个双因子：沪深300 + 可投资宇宙等权（检验是否只是"小盘 beta + 大盘 beta"）。

判定口径：alpha 的 t(NW) 绝对值 ≥ 1.96 才算显著；否则收益应记在 beta 上。
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, AQ_ROOT)

from aq import backtest, panel, strategy, universe, validate  # noqa: E402
from freq_rigorous_smallcap import (  # noqa: E402
    TEST, build_score, investable, run_freq,
)

FREQS = (10, 20, 30, 60)
OUT = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_attrib.json")


def main():
    print("重新做 beta 归因：只用可交易 / 最广为人知的基准\n", flush=True)
    full = panel.load_panels()
    tp = {k: v.loc["2022-01-01":TEST[1]] for k, v in full.items()}
    t_dates = tp["close"].index

    # 三个基准
    hs300 = panel.load_index("sh000300")["close"].reindex(t_dates).astype(float)
    b_hs300 = (hs300 / hs300.shift(1) - 1.0).fillna(0.0)

    mask = investable(tp)
    b_univ = universe.equal_weight_benchmark(tp, mask).fillna(0.0)      # 可投资宇宙等权

    all_mask = tp["close"].notna()                                       # 全市场等权（无筛选）
    b_all = universe.equal_weight_benchmark(tp, all_mask).fillna(0.0)

    score = build_score(tp, mask)

    out = {"基准说明": {
        "沪深300": "sh000300 日收益，可直接买 ETF",
        "可投资宇宙等权": "策略实际可买池（剔除 ST/次新<250日/北交所B股/日均额<2000万）等权日收益，无成本",
        "全市场等权": "面板内全部 A 股等权日收益，不做任何剔除",
        "双因子": "沪深300 + 可投资宇宙等权",
    }, "cases": []}

    for freq in FREQS:
        _, net, _, _ = run_freq(tp, score, t_dates, freq, TEST[0], TEST[1])
        r = net.ret.loc[TEST[0]:TEST[1]]
        row = {"freq": freq, "TEST调仓次数": int(
            len(strategy.rebalance_dates(t_dates, freq, start=TEST[0], end=TEST[1])))}
        for name, b in (("沪深300", b_hs300), ("可投资宇宙等权", b_univ), ("全市场等权", b_all)):
            reg = validate.alpha_beta(r, {name: b.reindex(r.index).fillna(0.0)})
            row[name] = {
                "年化alpha%": round(reg.get("年化alpha", np.nan) * 100, 2),
                "alpha_t(NW)": round(reg.get("alpha_t(NW)", np.nan), 2),
                "p值": round(reg.get("alpha_p值(双侧)", np.nan), 3),
                "beta": round(reg.get(f"beta_{name}", np.nan), 3),
                "R2": round(reg.get("R2", np.nan), 3),
            }
        reg2 = validate.alpha_beta(r, {
            "沪深300": b_hs300.reindex(r.index).fillna(0.0),
            "可投资宇宙等权": b_univ.reindex(r.index).fillna(0.0)})
        row["双因子"] = {
            "年化alpha%": round(reg2.get("年化alpha", np.nan) * 100, 2),
            "alpha_t(NW)": round(reg2.get("alpha_t(NW)", np.nan), 2),
            "p值": round(reg2.get("alpha_p值(双侧)", np.nan), 3),
            "beta_沪深300": round(reg2.get("beta_沪深300", np.nan), 3),
            "beta_可投资宇宙等权": round(reg2.get("beta_可投资宇宙等权", np.nan), 3),
            "R2": round(reg2.get("R2", np.nan), 3),
        }
        row["判定"] = ("显著" if abs(row["可投资宇宙等权"]["alpha_t(NW)"]) >= 1.96
                       else "不显著 —— 收益记在 beta 上")
        out["cases"].append(row)

        print(f"freq={freq:>3}（TEST 调仓 {row['TEST调仓次数']} 次）", flush=True)
        for k in ("沪深300", "可投资宇宙等权", "全市场等权"):
            v = row[k]
            print(f"    vs {k:<12} alpha {v['年化alpha%']:>7.2f}%/年  t(NW)={v['alpha_t(NW)']:>6}  "
                  f"p={v['p值']:<6} beta={v['beta']:>5}  R2={v['R2']}", flush=True)
        v = row["双因子"]
        print(f"    vs 沪深300+宇宙等权 alpha {v['年化alpha%']:>7.2f}%/年  t(NW)={v['alpha_t(NW)']:>6}  "
              f"p={v['p值']:<6} beta300={v['beta_沪深300']} beta宇宙={v['beta_可投资宇宙等权']}  R2={v['R2']}",
              flush=True)
        print(f"    → {row['判定']}\n", flush=True)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("已写入", OUT, flush=True)


if __name__ == "__main__":
    main()
