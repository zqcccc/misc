#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两个诊断性 A/B（不是参数搜索，结论只用于解释，不用于选参）

A. 流动性门槛：liq_top_pct ∈ {0.6..1.0}
   要不要剔掉最不活跃的 20%？口径差异有多大？
   背景：`universe.investable()` 默认 liq_top_pct=0.80，而线上生产用的是 1.0。
   小微盘策略的超额正来自最不活跃那批，这个参数可能就是「回测 21% vs 3%」的根源。

B. 滞后带 buffer ∈ {1.0(无缓冲) .. 6.0}
   现象：N=7 + buffer=2.0，每期变动 ~13 只 ≈ 全进全出，滞后带形同虚设。
   问：把它调到真正生效的值，比「完全不缓冲」好多少？换手能砍掉多少、收益掉不掉？
   附带诊断：把 rev5 权重置 0，看变动只数是否下降 —— 验证排名抖动是不是 rev5 造成的。

三段切分照旧（TRAIN/VALID/TEST），但这是诊断实验：不在上面选参数，
只展示影响方向与量级。若要正式改这两个参数，需重走完整搜索 + 物理隔离流程。
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

from aq import backtest, factors, metrics, panel, strategy, universe  # noqa: E402

TRADING_DAYS = 244
WEIGHTS = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}
N_HOLD = 7
TRAIN = ("2016-01-04", "2021-12-31")
VALID = ("2022-01-04", "2023-12-29")
TEST = ("2024-01-02", "2026-09-01")
TEST_WARMUP = "2022-01-01"

OUT = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_ab.json")


def score_of(panels, liq_top_pct=1.0, weights=None):
    w = WEIGHTS if weights is None else weights
    mask = universe.investable(panels, min_listed=250, exclude_st=True,
                               liquidity_top_pct=liq_top_pct)
    close, amount = panels["close"], panels["amount"]
    ret = factors.daily_return(close)
    fp = {
        "rev5": factors.rev(close, 5),
        "liqsize20": factors.liquidity_size(amount, 20),
        "ivol60": factors.idio_vol(ret, 60),
    }
    return strategy.composite(fp, w, mask), mask


def run(panels, score, dates, freq, start, end, top_n=N_HOLD, buffer_mult=2.0):
    rb = strategy.rebalance_dates(dates, freq, start=start, end=end)
    sig = strategy.top_n_signals_buffered(score, rb, top_n, buffer_mult, "equal")
    if sig.empty:
        return None, None, None, None
    net = backtest.run(panels, sig, start=start, end=end, exec_price="open", zero_cost=False)
    gross = backtest.run(panels, sig, start=start, end=end, exec_price="open", zero_cost=True)
    return sig, net, gross, rb


def churn(sig):
    prev, rows = None, []
    for _, row in sig.iterrows():
        cur = set(row.dropna().index)
        if prev is not None:
            rows.append(len(prev ^ cur))
        prev = cur
    return float(np.mean(rows)) if rows else 0.0


def stats(net, gross, bench, hs300, s, e):
    r = net.ret.loc[s:e]
    if len(r) < 30:
        return {}
    st = metrics.perf_stats(r, bench.reindex(r.index).fillna(0.0))
    rg = metrics.perf_stats(gross.ret.loc[s:e])
    to = float(net.turnover.loc[s:e].mean() * TRADING_DAYS)
    cost = float(net.cost.loc[s:e].mean() * TRADING_DAYS)
    return {
        "年化%": round(st["年化收益"] * 100, 2),
        "夏普": round(st["夏普(rf=0)"], 3),
        "回撤%": round(st["最大回撤"] * 100, 2),
        "毛年化%": round(rg["年化收益"] * 100, 2),
        "换手x": round(to, 1),
        "成本%": round(cost * 100, 2),
    }


def main():
    t0 = time.time()
    full = panel.load_panels()
    hs300_all = panel.load_index("sh000300")["close"]
    out = {}

    # ---------------------------------------------------------------- A
    print("=" * 78)
    print("A. 流动性门槛 liq_top_pct（剔不剔最不活跃的那批）")
    print("=" * 78, flush=True)
    rows_a = []
    for pct in (0.6, 0.7, 0.8, 0.9, 1.0):
        sc_dev, mask_dev = score_of(full, pct)
        bench_dev = universe.equal_weight_benchmark(full, mask_dev).fillna(0.0)
        hs_dev = (hs300_all / hs300_all.shift(1) - 1.0).reindex(full["close"].index).fillna(0.0)
        tp = {k: v.loc[TEST_WARMUP:TEST[1]] for k, v in full.items()}
        sc_te, mask_te = score_of(tp, pct)
        bench_te = universe.equal_weight_benchmark(tp, mask_te).fillna(0.0)
        hs_te = (hs300_all / hs300_all.shift(1) - 1.0).reindex(tp["close"].index).fillna(0.0)

        for freq in (10, 20, 60):
            sig, net, gross, rb = run(full, sc_dev, full["close"].index, freq, TRAIN[0], TEST[1])
            m_tr = stats(net, gross, bench_dev, hs_dev, *TRAIN)
            m_va = stats(net, gross, bench_dev, hs_dev, *VALID)
            n_stocks = int(mask_dev.loc[TRAIN[0]:TEST[1]].sum(axis=1).median())
            ch = churn(sig)
            sig2, net2, gross2, _ = run(tp, sc_te, tp["close"].index, freq, TEST[0], TEST[1])
            m_te = stats(net2, gross2, bench_te, hs_te, *TEST)
            rows_a.append({
                "liq_top_pct": pct, "freq": freq, "池内股票中位数": n_stocks,
                "每期变动只数": round(ch, 2), "TRAIN": m_tr, "VALID": m_va, "TEST": m_te,
            })
            print(f"  pct={pct:<4} freq={freq:>3} | 池内{n_stocks:>5}只 变动{ch:>5.2f}只/期 | "
                  f"TRAIN {m_tr['年化%']:>7.2f}% | VALID {m_va['年化%']:>7.2f}% | "
                  f"TEST {m_te['年化%']:>7.2f}% 夏普{m_te['夏普']:>6.3f} 回撤{m_te['回撤%']:>7.2f}% "
                  f"换手{m_te['换手x']:>5.1f}x 成本{m_te['成本%']:>5.2f}%", flush=True)
    out["A_流动性门槛"] = rows_a

    # ---------------------------------------------------------------- B
    print("\n" + "=" * 78)
    print("B. 滞后带 buffer（1.0 = 不缓冲，越大越懒得换）")
    print("=" * 78, flush=True)
    sc_dev, mask_dev = score_of(full, 1.0)
    bench_dev = universe.equal_weight_benchmark(full, mask_dev).fillna(0.0)
    hs_dev = (hs300_all / hs300_all.shift(1) - 1.0).reindex(full["close"].index).fillna(0.0)
    tp = {k: v.loc[TEST_WARMUP:TEST[1]] for k, v in full.items()}
    sc_te, mask_te = score_of(tp, 1.0)
    bench_te = universe.equal_weight_benchmark(tp, mask_te).fillna(0.0)
    hs_te = (hs300_all / hs300_all.shift(1) - 1.0).reindex(tp["close"].index).fillna(0.0)

    rows_b = []
    for buf in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0):
        for freq in (10, 20):
            sig, net, gross, rb = run(full, sc_dev, full["close"].index, freq, TRAIN[0], TEST[1],
                                      buffer_mult=buf)
            ch = churn(sig)
            m_tr = stats(net, gross, bench_dev, hs_dev, *TRAIN)
            m_va = stats(net, gross, bench_dev, hs_dev, *VALID)
            _, net2, gross2, _ = run(tp, sc_te, tp["close"].index, freq, TEST[0], TEST[1],
                                     buffer_mult=buf)
            m_te = stats(net2, gross2, bench_te, hs_te, *TEST)
            rows_b.append({
                "buffer": buf, "freq": freq, "保留名次": int(N_HOLD * buf),
                "每期变动只数": round(ch, 2), "TRAIN": m_tr, "VALID": m_va, "TEST": m_te,
            })
            print(f"  buffer={buf:<4} (前{int(N_HOLD * buf):>2}名保留) freq={freq:>3} | "
                  f"变动{ch:>5.2f}只/期 | TRAIN {m_tr['年化%']:>7.2f}% 换手{m_tr['换手x']:>5.1f}x | "
                  f"VALID {m_va['年化%']:>7.2f}% | TEST {m_te['年化%']:>7.2f}% 夏普{m_te['夏普']:>6.3f} "
                  f"回撤{m_te['回撤%']:>7.2f}% 换手{m_te['换手x']:>5.1f}x 成本{m_te['成本%']:>5.2f}%",
                  flush=True)
    out["B_滞后带"] = rows_b

    # ---------------------------------------------------------------- B 诊断
    print("\n[B-诊断] 排名抖动是谁造成的？（去掉某个因子后，每期变动只数）", flush=True)
    diag = []
    for label, w in (("全因子（线上）", WEIGHTS),
                     ("去掉 rev5", {"liqsize20": 1.0, "ivol60": 0.5}),
                     ("只留 liqsize20", {"liqsize20": 1.0})):
        sc, _ = score_of(full, 1.0, weights=w)
        sig, net, gross, _ = run(full, sc, full["close"].index, 10, TRAIN[0], TEST[1],
                                 buffer_mult=2.0)
        # 排名自相关：相邻调仓日 score 排名的 Spearman 相关
        rb = strategy.rebalance_dates(full["close"].index, 10, start=TRAIN[0], end=TEST[1])
        sub = sc.loc[rb]
        corr = sub.corrwith(sub.shift(1), axis=1, method="spearman").mean()
        diag.append({"口径": label, "每期变动只数": round(churn(sig), 2),
                     "相邻调仓日排名自相关": round(float(corr), 3)})
        print(f"  {label:<16} 变动 {churn(sig):>5.2f} 只/期   相邻调仓日排名自相关 {corr:.3f}", flush=True)
    out["B_诊断_抖动来源"] = diag

    out["meta"] = {
        "说明": "诊断性 A/B，不用于选参；三段切分仅作展示",
        "持仓数N": N_HOLD, "因子权重": WEIGHTS,
        "切分": {"TRAIN": TRAIN, "VALID": VALID, "TEST": TEST},
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n完成，用时 {time.time() - t0:.1f}s → {OUT}", flush=True)


if __name__ == "__main__":
    main()
