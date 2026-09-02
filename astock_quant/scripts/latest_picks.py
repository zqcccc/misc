"""按当前数据给出最新一期的目标持仓（用滚动样本外同一套逻辑）。

用法：python3 scripts/latest_picks.py [--top-n 50] [--freq 20]
只用截至最后一个交易日收盘的数据出信号，实际成交对应下一个交易日开盘。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import config, factors, panel, strategy, universe, walkforward  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--freq", type=int, default=20)
    ap.add_argument("--est-years", type=int, default=3)
    args = ap.parse_args()

    p = panel.load_panels()
    close = p["close"]
    last = close.index[-1]
    mask = universe.investable(p)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(p).items()}

    fit_start = last - pd.DateOffset(years=args.est_years)
    w = walkforward.estimate_weights(fp, mask, close, fit_start, last)
    print(f"信号日 {last.date()}（成交对应下一交易日开盘）")
    print(f"因子权重（用 {fit_start.date()} ~ {last.date()} 估计）：")
    for k, v in w.items():
        print(f"  {factors.FACTOR_DESC.get(k, k):<26} {v:.4f}")

    score = strategy.composite(fp, w, mask)
    s = score.loc[last].dropna().nlargest(args.top_n)
    meta = pd.read_csv(os.path.join(config.DATA_DIR, "meta.csv")).drop_duplicates("code")
    names = meta.set_index("code")["name"].to_dict()
    amt = p["amount"].rolling(20).mean().loc[last]

    print(f"\n候选股票池 {int(mask.loc[last].sum())} 只，目标持仓 {len(s)} 只（等权 "
          f"{100 / len(s):.1f}%）：")
    rows = [{"代码": c, "名称": names.get(c, ""), "打分": round(float(v), 4),
             "20日均成交额(亿)": round(float(amt.get(c, np.nan)) / 1e8, 2)}
            for c, v in s.items()]
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
