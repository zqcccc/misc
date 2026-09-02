"""参数敏感性 + 稳健性检验。

对每组参数分别报告样本内 / 样本外表现。样本外那一列在参数选择时**不参与**
决策，只用来看结论稳不稳 —— 如果一个策略只在某一组参数上好看，那多半是
在噪声上过拟合。
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

from aq import (backtest, config, factors, metrics, panel,  # noqa: E402
                strategy, universe)


def build(panels, weights):
    mask = universe.investable(panels)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(panels).items()}
    return mask, strategy.composite(fp, weights, mask)


def one_run(panels, score, dates, top_n, freq, buffer, scheme, inv_vol,
            exec_price="open", cost=True, label=""):
    rb = strategy.rebalance_dates(dates, freq, start=config.BACKTEST_START,
                                  end=config.BACKTEST_END)
    sig = strategy.top_n_signals_buffered(score, rb, top_n, buffer, scheme, inv_vol)
    # cost=False 是零成本对照，用来分离"信号本身"和"成本拖累"
    return backtest.run(panels, sig, start=config.BACKTEST_START, end=config.BACKTEST_END,
                        exec_price=exec_price, zero_cost=not cost)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="", help="JSON 因子权重；留空则读 research.json")
    args = ap.parse_args()

    panels = panel.load_panels()
    dates = panels["close"].index
    if args.weights:
        weights = json.loads(args.weights)
    else:
        with open(os.path.join(config.REPORT_DIR, "research.json")) as f:
            weights = json.load(f)["因子权重"]
    print(f"因子权重：{weights}")

    mask, score = build(panels, weights)
    inv_vol = strategy.inverse_vol(panels["close"])
    bench = universe.equal_weight_benchmark(panels, mask)
    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).fillna(0.0)

    grid = []
    for top_n in (30, 50, 100):
        for freq in (5, 10, 20):
            for buffer in (1.0, 2.0, 3.0):
                grid.append(dict(top_n=top_n, freq=freq, buffer=buffer,
                                 scheme="equal", exec_price="open", cost=True))
    # 低换手组：成本是这类因子最硬的约束，单独测一组"少动、多持"的配置
    for top_n in (200, 300):
        for freq in (20, 40, 60):
            grid.append(dict(top_n=top_n, freq=freq, buffer=3.0,
                             scheme="equal", exec_price="open", cost=True))
    for freq in (40, 60):
        grid.append(dict(top_n=100, freq=freq, buffer=3.0, scheme="equal",
                         exec_price="open", cost=True))
    grid.append(dict(top_n=300, freq=60, buffer=3.0, scheme="equal",
                     exec_price="open", cost=False))
    for scheme in ("invvol",):
        for freq in (10, 20):
            grid.append(dict(top_n=50, freq=freq, buffer=2.0, scheme=scheme,
                             exec_price="open", cost=True))
    grid.append(dict(top_n=50, freq=20, buffer=2.0, scheme="equal",
                     exec_price="close", cost=True))
    grid.append(dict(top_n=50, freq=20, buffer=2.0, scheme="equal",
                     exec_price="open", cost=False))

    rows = []
    t0 = time.time()
    for i, g in enumerate(grid):
        res = one_run(panels, score, dates, inv_vol=inv_vol, **g)
        r = res.ret
        is_r = r.loc[config.BACKTEST_START:config.IS_END]
        oos_r = r.loc[config.OOS_START:config.BACKTEST_END]
        st_is = metrics.perf_stats(is_r, bench.reindex(is_r.index).fillna(0.0))
        st_oos = metrics.perf_stats(oos_r, bench.reindex(oos_r.index).fillna(0.0))
        st_all = metrics.perf_stats(r, hs300_ret.reindex(r.index).fillna(0.0))
        rows.append({
            "持股": g["top_n"], "调仓日": g["freq"], "缓冲": g["buffer"],
            "权重": g["scheme"], "成交价": g["exec_price"], "计成本": g["cost"],
            "IS年化%": round(st_is["年化收益"] * 100, 2),
            "IS超额%": round(st_is["超额年化"] * 100, 2),
            "OOS年化%": round(st_oos["年化收益"] * 100, 2),
            "OOS超额%": round(st_oos["超额年化"] * 100, 2),
            "OOS信息比": round(st_oos["信息比率"], 2),
            "全样本夏普": round(st_all["夏普(rf=0)"], 2),
            "最大回撤%": round(st_all["最大回撤"] * 100, 1),
            "换手(年)": round(float(res.turnover.mean() * metrics.TRADING_DAYS), 1),
            "成本%": round(float(res.cost.mean() * metrics.TRADING_DAYS * 100), 2),
        })
        print(f"  [{i + 1}/{len(grid)}] {rows[-1]}", flush=True)

    df = pd.DataFrame(rows)
    out = os.path.join(config.REPORT_DIR, "grid.json")
    df.to_json(out, orient="records", force_ascii=False, indent=1)
    print(f"\n用时 {time.time() - t0:.0f}s，结果写入 {out}")
    print(df.sort_values("OOS超额%", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    main()
