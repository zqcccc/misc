#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复现：腾讯行情源的 hfq（后复权）日收益与不复权日收益在绝大多数交易日都不一致。

复权只是把历史价位按分红送转整体缩放，**除了除权日，日收益必须完全相同**。
实测在 2017-01-03 ~ 2026-09-04 的 2349 个交易日里，两者有 2100+ 天不同，
且 hfq 系统性低估波动。对 510050 / 510300 还能用对应指数做独立标尺：
不复权序列的波动与指数吻合，hfq 不吻合。

运行：.venv/bin/python quant_research/blockers/B0005-evidence/repro_tencent_hfq.py
只读网络，不写任何台账。
"""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, "/Users/gongzhao/code/misc/astock_quant")
from aq import config, datasource as ds

config.DATA_START = "2005-01-01"
S, E = "2017-01-03", "2026-09-04"
N = np.sqrt(252)


def ret(code, fq):
    df, name = ds.fetch_history(code, fq=fq, start="2005-01-01", end=E)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].astype(float).loc[S:E].pct_change().dropna(), name


def main():
    print(f"窗口 {S} ~ {E}\n")
    print("① 同一标的、hfq vs 不复权：除权日之外日收益本应完全相同")
    print(f"{'代码':10s} {'名称':10s} {'vol_hfq':>8s} {'vol_raw':>8s} {'差>1bp 天数':>12s} {'最大单日差':>10s}")
    for code in ("sh510050", "sh510300", "sh510500", "sh600519", "sh601398", "sh600036", "sz000001"):
        a, name = ret(code, "hfq")
        b, _ = ret(code, "")
        j = pd.concat([a.rename("h"), b.rename("r")], axis=1).dropna()
        d = (j.h - j.r).abs()
        print(f"{code:10s} {name:10s} {j.h.std()*N:8.4f} {j.r.std()*N:8.4f} "
              f"{int((d > 1e-4).sum()):>7d}/{len(j):<4d} {d.max()*100:9.2f}%")

    print("\n② 拿指数当独立标尺：ETF 的日波动必须贴近其跟踪的指数")
    print(f"{'ETF':10s} {'指数':10s} {'vol_hfq':>8s} {'vol_raw':>8s} {'vol_指数':>8s}")
    for etf, idx in (("sh510050", "sh000016"), ("sh510300", "sh000300"), ("sh510500", "sh000905")):
        h, _ = ret(etf, "hfq")
        r, _ = ret(etf, "")
        i, _ = ret(idx, "")
        print(f"{etf:10s} {idx:10s} {h.std()*N:8.4f} {r.std()*N:8.4f} {i.std()*N:8.4f}")

    print("\n结论：hfq 序列不是不复权序列的缩放版本，且其波动与指数对不上；")
    print("不复权序列与指数吻合。所有基于 hfq 日收益的收益率、波动、beta 与因子都需要重新核验。")


if __name__ == "__main__":
    main()
