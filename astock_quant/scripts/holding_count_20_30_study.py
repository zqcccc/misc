#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小微盘：20 / 30 个交易日调仓下的持仓数 N 研究。

这是在既有频率研究之后新增的 *联合规格搜索*，不是对 TEST 的重新预注册：
2024-01 之后的 TEST 已在此前频率研究中揭盲，故本脚本把该段明确标为
``diagnostic_test``，只用于描述稳定性，不能据此授予 PASS 或改线上规格。

冻结的时序：T 日收盘信息 -> T+1 开盘成交 -> 当日收盘开始计 PnL。
开发选择只读 TRAIN (2016-2021) 和 VALID (2022-2023)。
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(HERE)
ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, AQ_ROOT)

from aq import backtest, factors, metrics, panel, strategy, universe  # noqa: E402

OUT_JSON = os.path.join(ROOT, "deliverables", "smallcap_holding_count_20_30.json")
OUT_CSV = os.path.join(ROOT, "deliverables", "smallcap_holding_count_20_30_grid.csv")
TRADING_DAYS = 244
TRAIN = ("2016-01-04", "2021-12-31")
VALID = ("2022-01-04", "2023-12-29")
# Already exposed by the frequency study: diagnostic only, not a sealed test.
TEST = ("2024-01-02", "2026-09-01")
FREQS = (20, 30)
N_VALUES = (3, 5, 7, 10, 15, 20, 30, 40)
BUFFERS = (1.5, 2.0, 3.0)
DD_LIMITS = (-0.20, -0.25, -0.30, -0.35, -0.40, -0.50)
WEIGHTS = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}


def investable(p):
    return universe.investable(p, min_listed=250, exclude_st=True, liquidity_top_pct=1.0)


def build_score(p, mask):
    ret = factors.daily_return(p["close"])
    return strategy.composite({
        "liqsize20": factors.liquidity_size(p["amount"], 20),
        "rev5": factors.rev(p["close"], 5),
        "ivol60": factors.idio_vol(ret, 60),
    }, WEIGHTS, mask)


def run(p, score, dates, freq, n, buffer, start, end):
    rb = strategy.rebalance_dates(dates, freq, start=start, end=end)
    sig = strategy.top_n_signals_buffered(score, rb, n, buffer, "equal")
    net = backtest.run(p, sig, start=start, end=end, exec_price="open", zero_cost=False)
    gross = backtest.run(p, sig, start=start, end=end, exec_price="open", zero_cost=True)
    return net, gross, rb


def summary(net, gross, bench, start, end):
    r = net.ret.loc[start:end]
    rg = gross.ret.loc[start:end]
    b = bench.reindex(r.index).fillna(0.0)
    st = metrics.perf_stats(r, b)
    gross_st = metrics.perf_stats(rg)
    # One additional full realised-cost layer: a transparent stressed-cost proxy.
    # Costs occur on actual execution dates, so subtract the logged daily cost rather
    # than assume a smooth annual drag.
    stressed = r - net.cost.loc[r.index]
    stressed_st = metrics.perf_stats(stressed, b)
    return {
        "days": int(len(r)),
        "ann_return_pct": round(float(st["年化收益"]) * 100, 2),
        "sharpe": round(float(st["夏普(rf=0)"]), 3),
        "max_drawdown_pct": round(float(st["最大回撤"]) * 100, 2),
        "calmar": round(float(st["卡玛"]), 3),
        "excess_ew_pct": round(float(st.get("超额年化", np.nan)) * 100, 2),
        "gross_ann_return_pct": round(float(gross_st["年化收益"]) * 100, 2),
        "annual_turnover_x": round(float(net.turnover.loc[r.index].mean()) * TRADING_DAYS, 2),
        "annual_cost_pct": round(float(net.cost.loc[r.index].mean()) * TRADING_DAYS * 100, 2),
        "stressed_ann_return_pct": round(float(stressed_st["年化收益"]) * 100, 2),
        "stressed_sharpe": round(float(stressed_st["夏普(rf=0)"]), 3),
        "blocked_order_fraction": round(float(net.blocked_frac), 5),
        "mean_actual_holdings": round(float(net.n_holdings.loc[r.index].mean()), 2),
    }


def objective(train, valid):
    """Pre-result frozen development objective; higher is better.

    Prefer validation Sharpe, penalise train/valid optimism and a VALID MDD beyond
    35%.  The MDD sweep is reported separately so risk limits are not secretly tuned.
    """
    gap = max(0.0, train["sharpe"] - valid["sharpe"])
    dd_excess = max(0.0, abs(valid["max_drawdown_pct"]) - 35.0) / 100.0
    return round(valid["sharpe"] - 0.5 * gap - dd_excess, 4)


def main():
    t0 = time.time()
    print("Loading panel and computing frozen production score…", flush=True)
    full = panel.load_panels()
    dates = full["close"].index
    dev = {k: v.loc[:VALID[1]] for k, v in full.items()}
    dev_mask = investable(dev)
    dev_score = build_score(dev, dev_mask)
    dev_bench = universe.equal_weight_benchmark(dev, dev_mask).fillna(0.0)

    # The test score is intentionally constructed separately with only history through
    # TEST end; this avoids an accidental future row in indicators, but it is disclosed.
    test = {k: v.loc["2022-01-01":TEST[1]] for k, v in full.items()}
    test_mask = investable(test)
    test_score = build_score(test, test_mask)
    test_bench = universe.equal_weight_benchmark(test, test_mask).fillna(0.0)

    rows = []
    for freq in FREQS:
        for n in N_VALUES:
            for buffer in BUFFERS:
                net, gross, _ = run(dev, dev_score, dev["close"].index, freq, n, buffer, TRAIN[0], VALID[1])
                tr = summary(net, gross, dev_bench, *TRAIN)
                va = summary(net, gross, dev_bench, *VALID)
                tn, tg, _ = run(test, test_score, test["close"].index, freq, n, buffer, *TEST)
                te = summary(tn, tg, test_bench, *TEST)
                row = {"freq": freq, "n": n, "buffer": buffer, "train": tr, "valid": va,
                       "diagnostic_test": te, "objective": objective(tr, va)}
                rows.append(row)
                print(f"f={freq:2} N={n:2} b={buffer:.1f} | valid SR={va['sharpe']:+.3f} "
                      f"MDD={va['max_drawdown_pct']:.2f}% obj={row['objective']:+.3f} | "
                      f"test(diag) SR={te['sharpe']:+.3f} MDD={te['max_drawdown_pct']:.2f}%", flush=True)

    rows.sort(key=lambda x: x["objective"], reverse=True)
    # Eligibility tables answer the requested larger drawdown range without changing
    # the selected objective after looking at performance.
    risk_frontiers = {}
    for limit in DD_LIMITS:
        eligible = [x for x in rows if x["valid"]["max_drawdown_pct"] >= limit * 100]
        risk_frontiers[str(int(limit * 100))] = ({
            "valid_mdd_limit_pct": int(limit * 100), "eligible_specs": len(eligible),
            "best_by_frozen_objective": {k: eligible[0][k] for k in ("freq", "n", "buffer", "objective")}
            if eligible else None,
        })

    flat = []
    for x in rows:
        flat.append({"freq": x["freq"], "n": x["n"], "buffer": x["buffer"], "objective": x["objective"],
                     **{f"train_{k}": v for k, v in x["train"].items()},
                     **{f"valid_{k}": v for k, v in x["valid"].items()},
                     **{f"diagnostic_test_{k}": v for k, v in x["diagnostic_test"].items()}})
    pd.DataFrame(flat).to_csv(OUT_CSV, index=False)
    result = {
        "meta": {
            "research_question": "For 20/30-trading-day rebalances, how does holding count N affect returns, drawdown, cost and stability?",
            "role": "small-cap style exposure / candidate diversifier; not claimed alpha",
            "time_contract": "T close information -> T+1 open execution -> T+1 close PnL",
            "splits": {"train": TRAIN, "validation": VALID, "diagnostic_test": TEST},
            "test_status": "Previously revealed in smallcap frequency work; diagnostic only. Do not select a live spec from it.",
            "frozen_grid": {"freq": list(FREQS), "n": list(N_VALUES), "buffer": list(BUFFERS)},
            "cost": "engine: commission + historical stamp duty + 10bp one-way slippage + transfer fee; stressed result subtracts one further realised cost layer",
            "universe": "min listed 250d, ex-ST, liquidity_top_pct=1.0; reconstructed multiplicatively adjusted prices",
            "selection": "maximize valid Sharpe - 0.5*max(0, train Sharpe-valid Sharpe) - max(0, |valid MDD|-35%)/100",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "best_development_spec": rows[0],
        "risk_frontiers": risk_frontiers,
        "grid": rows,
        "artifacts": {"csv": OUT_CSV},
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"\nWrote {OUT_JSON} and {OUT_CSV} in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
