"""重建因果闸的样本数据，带上 baostock 补回来的真实字段。

因果闸测的必须是**真正在跑的那条代码路径**。上一轮 verified/causal_data 里只有
OHLCV，策略里新接进来的市值 / ST 分支根本没被覆盖到。这里重新导出一份，
每只股票一个 CSV，列含 float_mktcap / total_mktcap / is_st / turn。

用法：python3 scripts_ext/build_causal_data.py [--n 120]
产物：verified/causal_data_v2/*.csv
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from aq import config  # noqa: E402
from strategies_ext import datalayer  # noqa: E402

OUT = os.path.join(config.BASE_DIR, "verified", "causal_data_v2")
COLS = ["open", "high", "low", "close", "volume", "amount",
        "float_mktcap", "total_mktcap", "is_st", "turn"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120, help="抽多少只股票")
    args = ap.parse_args()

    p = datalayer.load("real")
    close = p["close"]
    # 抽样：按 2019 年有效交易日数排序取最完整的一批，再等距抽样保证板块分散
    live = close.loc["2019":"2026"].notna().sum().sort_values(ascending=False)
    codes = sorted(live[live > 1200].index)
    step = max(1, len(codes) // args.n)
    codes = codes[::step][:args.n]

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for c in codes:
        df = pd.DataFrame({"date": close.index})
        for f in COLS:
            df[f] = p[f][c].to_numpy() if f in p and c in p[f].columns else float("nan")
        df = df.dropna(subset=["close"])
        df.to_csv(os.path.join(OUT, f"{c}.csv"), index=False)
    print(f"{len(codes)} 只 × {len(close)} 日 -> {OUT}", flush=True)
    print("列:", COLS, flush=True)


if __name__ == "__main__":
    main()
