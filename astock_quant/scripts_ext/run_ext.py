"""把 strategies_ext/ 里的平台策略在干净口径下跑一遍。

口径固定（协议铁律 2/3：宇宙先固定、成本先锁死）：
  - 共用股票池 aq.universe.investable(p)
  - 成本 = 佣金万2.5 + 过户费十万分之一 + 滑点单边10bp + 印花税（历史税率）
  - 信号 T、成交 T+1 开盘，涨跌停/停牌/一字板/T+1/现金约束全建模
  - 区间 2019-01-02 ~ 2026-09-01
用法：python3 scripts_ext/run_ext.py [--only s01,s02] [--wide-pool]
产物：verified/<key>_returns.csv、verified/ext_summary.json
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import backtest, config, datasource as ds, metrics, panel, strategy, universe  # noqa: E402
from strategies_ext import common  # noqa: E402

START, END = "2019-01-02", "2026-09-01"
VERIFIED = os.path.join(config.BASE_DIR, "verified")

MODULES = [
    "s01_guorn_smallcap_m1", "s02_jq_gjt_smallcap", "s03_jq_micro_smallest",
    "s04_haitong_rev22", "s05_haitong_rev22_intraday", "s06_cj_volweighted_rev",
    "s07_rev5_highvolume", "s08_lowvol_anomaly", "s08b_lowvol_raw",
    "s09_volsurge_lowamp", "s10_alpha001", "s11_alpha003", "s12_alpha022",
    "s13_cross_stock_reversal", "s14_dual_ma",
]


def index_ret(code: str, idx: pd.DatetimeIndex) -> pd.Series:
    df = ds.load_local(code, "hfq")
    s = pd.Series(df["close"].to_numpy(dtype=float), index=pd.to_datetime(df["date"]))
    s = s[~s.index.duplicated()].sort_index()
    return (s / s.shift(1) - 1.0).reindex(idx).fillna(0.0)


def run_one(mod, panels, base_mask, dates, wide_pool=False):
    meta = mod.META
    mask = base_mask
    if hasattr(mod, "mask_filter"):
        mask = mod.mask_filter(panels, mask)
    t0 = time.time()
    rb = strategy.rebalance_dates(dates, meta["freq"], start=START, end=END)
    if "rb_dates" in inspect.signature(mod.score).parameters:
        sc = mod.score(panels, mask, rb_dates=rb)
    else:
        sc = mod.score(panels, mask)
    if hasattr(mod, "build_signals"):
        win = dates[(dates >= pd.Timestamp(START)) & (dates <= pd.Timestamp(END))]
        sig = mod.build_signals(panels, mask, sc, win)
    else:
        sig = common.top_n(sc, rb, meta["top_n"], meta["buffer_mult"])
    sig = common.apply_blackout(sig, meta["blackout"], dates)
    res = backtest.run(panels, sig, start=START, end=END, keep_holdings=True)
    return res, sc, mask, time.time() - t0


def effective_holdings(res) -> float:
    """有效持仓只数：只数浮点残留的「尘埃仓」（权重 < 0.01%）不计。

    引擎清仓时 shares -= value/price 会留下 ~1e-11 股的浮点残渣，价值可以忽略，
    但会把 n_holdings 抬高一倍，直接用会误导。"""
    if not res.holdings:
        return float("nan")
    n = [(h > 1e-4).sum() for h in res.holdings.values()]
    n = [x for x in n if x > 0]        # 空仓日历期间的全现金目标不计入平均持仓
    return float(np.mean(n)) if n else 0.0


LADDER = ("2020-01-01", "2025-03-01")   # 聚宽策略天梯贴的统一回测区间


def _ladder_slice(r):
    return r.loc[(r.index >= pd.Timestamp(LADDER[0])) & (r.index <= pd.Timestamp(LADDER[1]))]


def ladder_ann(r):
    x = _ladder_slice(r)
    nav = (1 + x).cumprod()
    return (float(nav.iloc[-1]) ** (244 / len(x)) - 1) * 100 if len(x) > 60 else float("nan")


def ladder_mdd(r):
    x = _ladder_slice(r)
    return metrics.max_drawdown((1 + x).cumprod()) * 100 if len(x) > 60 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="ext_summary.json")
    ap.add_argument("--pool", default="base", choices=["base", "wide"],
                    help="wide = 取消「剔除最不活跃 20%」与 2000 万成交额下限，"
                         "还原平台策略真实用的全A池（含极端微盘）")
    args = ap.parse_args()

    p = panel.load_panels()
    dates = p["close"].index
    if args.pool == "wide":
        base_mask = universe.investable(p, min_amount=3e6, liquidity_top_pct=1.0)
    else:
        base_mask = universe.investable(p)
    bench_ew = universe.equal_weight_benchmark(p, base_mask)
    win = dates[(dates >= pd.Timestamp(START)) & (dates <= pd.Timestamp(END))]
    bench_ew = bench_ew.reindex(win).fillna(0.0)
    hs300 = index_ret("sh000300", win)
    zz500 = index_ret("sh000905", win)

    mods = [m for m in MODULES if not args.only or m.split("_")[0] in args.only.split(",")]
    summary = []
    for name in mods:
        mod = importlib.import_module(f"strategies_ext.{name}")
        meta = mod.META
        print(f"\n=== {meta['key']}  {meta['title']}", flush=True)
        res, sc, mask, secs = run_one(mod, p, base_mask, dates)
        r = res.ret.reindex(win).fillna(0.0)
        st = metrics.perf_stats(r, bench_ew, meta["title"])
        pool_ew = universe.equal_weight_benchmark(p, mask).reindex(win).fillna(0.0)
        suffix = "" if args.pool == "base" else "_wide"
        row = {
            "key": meta["key"] + suffix, "title": meta["title"], "family": meta["family"],
            "source": meta["source"], "claimed": meta["claimed"],
            "top_n": meta["top_n"], "freq": meta["freq"],
            "blackout": bool(meta["blackout"]), "data_gap": meta["data_gap"],
            "年化%": round(st["年化收益"] * 100, 2),
            "夏普": round(st["夏普(rf=0)"], 3),
            "最大回撤%": round(st["最大回撤"] * 100, 2),
            "对全池等权超额%": round(st["超额年化"] * 100, 2),
            "信息比率": round(st["信息比率"], 3),
            "对策略池等权超额%": round((((1 + (r - pool_ew)).cumprod().iloc[-1])
                                 ** (244 / len(r)) - 1) * 100, 2),
            "年化换手(倍)": round(float(res.turnover.mean() * 244), 1),
            "成本拖累%/年": round(float(res.cost.mean() * 244 * 100), 2),
            "blocked_frac": round(res.blocked_frac, 4),
            "平均持仓": round(effective_holdings(res), 1),
            "天梯期年化%": round(ladder_ann(r), 2),
            "天梯期回撤%": round(ladder_mdd(r), 2),
            "股票池": args.pool,
            "现金占比%": round(float(res.cash_weight.mean() * 100), 1),
            "秒": round(secs, 1),
        }
        print(f"  年化 {row['年化%']}%  夏普 {row['夏普']}  回撤 {row['最大回撤%']}%  "
              f"对等权超额 {row['对全池等权超额%']}%/年  换手 {row['年化换手(倍)']}x  "
              f"成本 {row['成本拖累%/年']}%  blocked {row['blocked_frac']}  "
              f"持仓 {row['平均持仓']}  ({row['秒']}s)", flush=True)
        summary.append(row)
        out = pd.DataFrame({"date": r.index.strftime("%Y-%m-%d"), "ret": r.to_numpy()})
        out.to_csv(os.path.join(VERIFIED, f"{meta['key']}{suffix}_returns.csv"), index=False)

    ref = [metrics.perf_stats(bench_ew, hs300, "可投池等权(基准)"),
           metrics.perf_stats(zz500, hs300, "中证500"),
           metrics.perf_stats(hs300, hs300, "沪深300")]
    print("\n" + metrics.stats_frame(ref).to_string(index=False))
    pd.DataFrame({"date": win.strftime("%Y-%m-%d"), "ret": bench_ew.to_numpy()}).to_csv(
        os.path.join(VERIFIED, "bench_ew_ext.csv"), index=False)
    pd.DataFrame({"date": win.strftime("%Y-%m-%d"), "ret": hs300.to_numpy()}).to_csv(
        os.path.join(VERIFIED, "bench_hs300_ext.csv"), index=False)
    path = os.path.join(VERIFIED, args.out)
    prev = json.load(open(path))["策略"] if os.path.exists(path) else []
    keep = [x for x in prev if x["key"] not in {s["key"] for s in summary}]
    json.dump({"区间": [START, END],
               "基准": json.loads(metrics.stats_frame(ref).to_json(orient="records",
                                                                 force_ascii=False)),
               "策略": keep + summary},
              open(path, "w"), ensure_ascii=False, indent=1)
    print(f"\n已写 {path}")


if __name__ == "__main__":
    main()
