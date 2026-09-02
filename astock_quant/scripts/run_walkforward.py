"""滚动样本外回测：每年用过去 3 年重估因子权重，再交易下一年。

用法：python3 scripts/run_walkforward.py [--top-n 50] [--freq 20] [--scheme equal]
产物：reports/walkforward.json
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
                strategy, universe, walkforward)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--freq", type=int, default=20)
    ap.add_argument("--buffer", type=float, default=2.0)
    ap.add_argument("--scheme", default="equal", choices=["equal", "invvol"])
    ap.add_argument("--start", default="2019-01-02", help="滚动样本外起点（前面留给估计窗口）")
    args = ap.parse_args()
    t0 = time.time()

    p = panel.load_panels()
    close = p["close"]
    dates = close.index
    mask = universe.investable(p)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(p).items()}
    inv_vol = strategy.inverse_vol(close) if args.scheme == "invvol" else None

    print(f"滚动样本外：{args.start} ~ {config.BACKTEST_END}，"
          f"每年用过去 3 年重估权重，持股 {args.top_n}，每 {args.freq} 个交易日调仓")
    sig, schedule = walkforward.build_signals(
        fp, mask, close, start=args.start, end=config.BACKTEST_END,
        freq=args.freq, top_n=args.top_n, buffer_mult=args.buffer,
        scheme=args.scheme, inv_vol=inv_vol, verbose=True)

    res = backtest.run(p, sig, start=args.start, end=config.BACKTEST_END, keep_holdings=True)
    bench_eq = universe.equal_weight_benchmark(p, mask).reindex(res.ret.index).fillna(0.0)
    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).reindex(res.ret.index).fillna(0.0)
    zz500 = panel.load_index("sh000905")["close"].reindex(dates).astype(float)
    zz500_ret = (zz500 / zz500.shift(1) - 1.0).reindex(res.ret.index).fillna(0.0)

    rows = [metrics.perf_stats(res.ret, hs300_ret, f"滚动样本外策略 top{args.top_n}"),
            metrics.perf_stats(bench_eq, hs300_ret, "等权全A(可投池)"),
            metrics.perf_stats(zz500_ret, hs300_ret, "中证500"),
            metrics.perf_stats(hs300_ret, hs300_ret, "沪深300")]
    tbl = metrics.stats_frame(rows)
    print("\n" + tbl.to_string(index=False))

    # 分年度
    yearly = []
    for y, r in res.ret.groupby(res.ret.index.year):
        b = bench_eq.loc[r.index]
        h = hs300_ret.loc[r.index]
        yearly.append({"年份": int(y),
                       "策略%": round(float((1 + r).prod() - 1) * 100, 2),
                       "等权全A%": round(float((1 + b).prod() - 1) * 100, 2),
                       "沪深300%": round(float((1 + h).prod() - 1) * 100, 2),
                       "超额(对等权)%": round(float((1 + r).prod() - (1 + b).prod()) * 100, 2)})
    print("\n分年度：")
    print(pd.DataFrame(yearly).to_string(index=False))
    print(f"\n年化双边换手 {res.turnover.mean() * metrics.TRADING_DAYS:.1f} 倍，"
          f"成本拖累 {res.cost.mean() * metrics.TRADING_DAYS * 100:.2f}%/年")

    out = {
        "参数": vars(args),
        "权重表": schedule,
        "绩效": json.loads(tbl.to_json(orient="records", force_ascii=False)),
        "分年度": yearly,
        "换手年化": round(float(res.turnover.mean() * metrics.TRADING_DAYS), 2),
        "成本年化": round(float(res.cost.mean() * metrics.TRADING_DAYS), 5),
        "净值": {"日期": [d.strftime("%Y-%m-%d") for d in res.equity.index],
                 "策略": [round(float(x), 4) for x in res.equity / res.equity.iloc[0]],
                 "等权全A(可投池)": [round(float(x), 4) for x in (1 + bench_eq).cumprod()],
                 "沪深300": [round(float(x), 4) for x in (1 + hs300_ret).cumprod()],
                 "中证500": [round(float(x), 4) for x in (1 + zz500_ret).cumprod()]},
        "最新持仓": ({d.strftime("%Y-%m-%d"): {k: round(float(v), 4) for k, v in s.items()}
                     for d, s in list(res.holdings.items())[-1:]} if res.holdings else {}),
    }
    with open(os.path.join(config.REPORT_DIR, "walkforward.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n用时 {time.time() - t0:.0f}s，结果写入 reports/walkforward.json")


if __name__ == "__main__":
    main()
