#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补跑两个决定性检验（主脚本 smallcap 频率研究的附录）

A. 硬因果闸：历史前缀重算 + 未来数据投毒。
   主脚本用的「信息注入 uplift」判定不成立（注入后收益反而下降，说明 uplift 不是
   可靠的泄露探测器）。项目里真正过闸的标准是 `tests/test_no_lookahead.py` 的两条：
     1) 把数据截断在 T 重算，T 之前的持仓必须与全量运行逐位一致（max diff = 0）
     2) 把 T 之后的未来价格任意投毒，T 之前的持仓仍逐位不变（max diff = 0）

B. 频率效应是不是 alpha：对每个 freq 做随机组合置换，看真实策略在
   「同池、同持股数、同调仓日、随机打分」的分布里排第几。
   关键对照：随机组合的年化是否也随 freq 上升？如果也上升，说明「低频更好」
   只是成本与 beta 暴露，不是选股能力 —— 换频率救不了策略。
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, AQ_ROOT)

from aq import backtest, factors, panel, strategy, universe, validate  # noqa: E402
from freq_rigorous_smallcap import (  # noqa: E402
    BUFFER, N_HOLD, TEST, WEIGHTS, build_score, investable, run_freq,
)

TRADING_DAYS = 244
CUT = "2025-06-30"          # 前缀截断点
POISON = "2025-07-01"       # 未来投毒起点
N_PERM = 200
FREQS = (5, 10, 15, 20, 30, 40, 60)


def cagr(s: pd.Series) -> float:
    return float((1 + s).prod() ** (TRADING_DAYS / len(s)) - 1)


# ------------------------------------------------------------------ A 因果闸
def gate_causality():
    print("\n[A] 硬因果闸：前缀重算 / 未来投毒（freq=10，TEST 段）", flush=True)
    full = panel.load_panels()
    p_full = {k: v.loc["2022-01-01":TEST[1]] for k, v in full.items()}

    def signals_of(p):
        mask = investable(p)
        sc = build_score(p, mask)
        rb = strategy.rebalance_dates(p["close"].index, 10, start=TEST[0], end=TEST[1])
        return strategy.top_n_signals_buffered(sc, rb, N_HOLD, BUFFER, "equal")

    base = signals_of(p_full)

    # 1) 前缀重算：截断到 CUT
    p_cut = {k: v.loc[:CUT] for k, v in p_full.items()}
    trunc = signals_of(p_cut)
    common = base.index.intersection(trunc.index)
    common = common[common <= pd.Timestamp(CUT)]
    a, b = base.loc[common], trunc.loc[common]
    a, b = a.align(b, join="outer")
    diff1 = float(np.nanmax(np.abs(a.fillna(0).to_numpy() - b.fillna(0).to_numpy()))) if len(common) else np.nan

    # 2) 未来投毒：CUT 之后的价格乘荒谬倍率
    rng = np.random.default_rng(7)
    p_poison = {}
    for k, v in p_full.items():
        v = v.copy()
        tail = v.index > pd.Timestamp(CUT)
        if k.endswith("_raw") or k in ("close", "open", "high", "low"):
            mult = pd.Series(
                np.where(tail, rng.choice([0.01, 0.5, 3.0, 50.0], size=len(v)), 1.0),
                index=v.index)
            v = v.mul(mult, axis=0)
        p_poison[k] = v
    pois = signals_of(p_poison)
    cp = base.index.intersection(pois.index)
    cp = cp[cp <= pd.Timestamp(CUT)]
    a2, b2 = base.loc[cp], pois.loc[cp]
    a2, b2 = a2.align(b2, join="outer")
    diff2 = float(np.nanmax(np.abs(a2.fillna(0).to_numpy() - b2.fillna(0).to_numpy()))) if len(cp) else np.nan

    res = {
        "截断点": CUT,
        "比对调仓日数": int(len(common)),
        "前缀重算_max_abs_diff": round(diff1, 12),
        "前缀重算_判定": "PASS" if diff1 == 0 else "FAIL",
        "未来投毒_max_abs_diff": round(diff2, 12),
        "未来投毒_判定": "PASS" if diff2 == 0 else "FAIL",
    }
    print(f"  前缀重算：{len(common)} 个调仓日逐位比对，max|diff| = {diff1} → {res['前缀重算_判定']}", flush=True)
    print(f"  未来投毒：{len(cp)} 个调仓日逐位比对，max|diff| = {diff2} → {res['未来投毒_判定']}", flush=True)
    return res


# ------------------------------------------------------------------ B 置换
def gate_permutation():
    print("\n[B] 频率效应 = alpha 还是 beta/运气？（TEST 段，每 freq %d 次随机置换）" % N_PERM, flush=True)
    full = panel.load_panels()
    tp = {k: v.loc["2022-01-01":TEST[1]] for k, v in full.items()}
    t_dates = tp["close"].index
    mask = investable(tp)
    score = build_score(tp, mask)
    bench_ew = universe.equal_weight_benchmark(tp, mask).fillna(0.0)

    out = []
    rng = np.random.default_rng(20260908)
    for freq in FREQS:
        sig, net, _, rb = run_freq(tp, score, t_dates, freq, TEST[0], TEST[1])
        real = cagr(net.ret.loc[TEST[0]:TEST[1]])
        perm = []
        for _ in range(N_PERM):
            rs = validate.random_scores(mask, rb, seed=int(rng.integers(1, 10 ** 9)))
            sg = strategy.top_n_signals_buffered(rs, rb, N_HOLD, BUFFER, "equal")
            rr = backtest.run(tp, sg, start=TEST[0], end=TEST[1], exec_price="open", zero_cost=False)
            perm.append(cagr(rr.ret.loc[TEST[0]:TEST[1]]))
        perm = np.asarray(perm)
        row = {
            "freq": freq,
            "TEST调仓次数": int(len(rb)),
            "真实年化%": round(real * 100, 2),
            "随机均值%": round(float(perm.mean()) * 100, 2),
            "随机中位%": round(float(np.median(perm)) * 100, 2),
            "随机P95%": round(float(np.percentile(perm, 95)) * 100, 2),
            "真实分位": round(validate.percentile_rank(real, perm), 3),
            "置换p值": round(validate.permutation_p(real, perm), 4),
            "真实-随机均值_pp": round((real - float(perm.mean())) * 100, 2),
        }
        out.append(row)
        print(f"  freq={freq:>3}  调仓{row['TEST调仓次数']:>3}次 | 真实 {row['真实年化%']:>7.2f}%  "
              f"随机均值 {row['随机均值%']:>7.2f}% (P95 {row['随机P95%']:>7.2f}%)  "
              f"差 {row['真实-随机均值_pp']:>+7.2f}pp  分位 {row['真实分位']:.3f}  p={row['置换p值']}",
              flush=True)
    return out


def main():
    t0 = time.time()
    res = {"cut": CUT, "n_perm": N_PERM}
    res["因果闸"] = gate_causality()
    res["置换"] = gate_permutation()

    # 随机组合基准：等权全池（无任何选股）
    out_path = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_gate.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n完成，用时 {time.time() - t0:.1f}s → {out_path}", flush=True)


if __name__ == "__main__":
    main()
