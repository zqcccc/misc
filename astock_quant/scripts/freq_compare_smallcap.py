# DEPRECATED (2026-09-08): 本脚本用 universe.investable() 默认 liquidity_top_pct=0.80，
# 与线上真口径 (liquidity_top_pct=1.0) 不符，两者 TEST 段年化差 20pp 量级，结论不可信。
# 频率研究请改用 freq_rigorous_smallcap.py（三段切分 + 四层证伪）。
"""线上微盘策略调仓频率单变量对比：N=7 × freq∈{5,10,20}（附 N=8 稳健性）。

口径与线上完全一致：
- 因子权重 liqsize20=1.0 / rev5=0.5 / ivol60=0.5（live_smallcap.FACTOR_WEIGHTS）
- 滞后带 buffer_mult=2.0（前 2N 名不卖），等权
- T 日收盘出信号，T+1 开盘成交（backtest.run exec_price="open"）
- 成本：佣金万2.5×2 + 印花税（动态）+ 滑点单边 10bp + 过户费（config）
- 股票池：universe.investable（剔除 ST/次新/停牌、最不活跃 20%、北交所/B 股）

本脚本只做频率单变量检验：N/buffer/权重全部固定为线上值，不搜参。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import backtest, config, factors, metrics, panel, strategy, universe  # noqa: E402

WEIGHTS = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}
START, END = config.BACKTEST_START, config.BACKTEST_END  # 2016-01-04 ~ 2026-09-01
OOS = config.OOS_START  # 2021-01-04
FREQS = (5, 10, 20)
NS = (7, 8)


def build_score(panels):
    """只算线上三个因子，与 live_smallcap 口径一致。"""
    close, open_, high, low = panels["close"], panels["open"], panels["high"], panels["low"]
    volume, amount = panels["volume"], panels["amount"]
    ret = factors.daily_return(close)
    fp = {
        "rev5": factors.rev(close, 5),
        "liqsize20": factors.liquidity_size(amount, 20),
        "ivol60": factors.idio_vol(ret, 60),
    }
    mask = universe.investable(panels)
    return strategy.composite(fp, WEIGHTS, mask), mask


def run_case(panels, score, mask, dates, top_n, freq, inv_vol):
    rb = strategy.rebalance_dates(dates, freq, start=START, end=END)
    sig = strategy.top_n_signals_buffered(score, rb, top_n, 2.0, "equal", inv_vol)
    res = backtest.run(panels, sig, start=START, end=END, exec_price="open", zero_cost=False)
    res_gross = backtest.run(panels, sig, start=START, end=END, exec_price="open", zero_cost=True)
    # 实际持仓只数（调仓日）
    n_hold = int(sig.notna().sum(axis=1).median())
    return sig, res, res_gross, n_hold


def seg_stats(r, bench_ew, hs300_ret, res, rg, seg_start, seg_end):
    idx = r.loc[seg_start:seg_end].index
    st = metrics.perf_stats(r.loc[idx], bench_ew.reindex(idx).fillna(0.0))
    st_hs = metrics.perf_stats(r.loc[idx], hs300_ret.reindex(idx).fillna(0.0))
    to = float(res.turnover.loc[idx].mean() * metrics.TRADING_DAYS)
    cost = float(res.cost.loc[idx].mean() * metrics.TRADING_DAYS * 100)
    rg_ret = rg.ret.loc[idx]
    return {
        "年化%": round(st["年化收益"] * 100, 2),
        "夏普": round(st["夏普(rf=0)"], 3),
        "回撤%": round(st["最大回撤"] * 100, 2),
        "超额等权%": round(st["超额年化"] * 100, 2),
        "超额沪深300%": round(st_hs["超额年化"] * 100, 2),
        "换手x": round(to, 1),
        "成本%": round(cost, 2),
        "毛年化%": round(metrics.perf_stats(rg_ret, bench_ew.reindex(idx).fillna(0.0))["年化收益"] * 100, 2),
    }


def yearly_excess(r, bench_ew):
    out = []
    for y, x in r.groupby(r.index.year):
        b = bench_ew.loc[x.index]
        ex = (1 + x).prod() - (1 + b).prod()
        out.append({"年": int(y), "超额%": round(float(ex) * 100, 2)})
    return out


def rebalance_turnover(sig, panels):
    """调仓日平均换手：相邻调仓日持仓差异（卖出+买入的名义额占比）。"""
    dates = panels["close"].index
    codes = list(panels["close"].columns)
    rows = []
    prev = None
    for d, row in sig.iterrows():
        cur = set(row.dropna().index)
        if prev is not None:
            changed = len(prev ^ cur)  # 换入+换出只数
            rows.append(changed)
        prev = cur
    return np.mean(rows) if rows else 0.0


def main():
    panels = panel.load_panels()
    dates = panels["close"].index
    score, mask = build_score(panels)
    inv_vol = strategy.inverse_vol(panels["close"])
    bench_ew = universe.equal_weight_benchmark(panels, mask)
    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).fillna(0.0)

    out = {"meta": {
        "因子权重": WEIGHTS, "buffer": 2.0, "执行": "T+1 开盘",
        "区间": f"{START} ~ {END}", "OOS起点": OOS,
    }, "cases": []}

    for n in NS:
        for freq in FREQS:
            sig, res, res_gross, n_hold = run_case(panels, score, mask, dates, n, freq, inv_vol)
            r = res.ret
            st_full = seg_stats(r, bench_ew, hs300_ret, res, res_gross, START, END)
            st_oos = seg_stats(r, bench_ew, hs300_ret, res, res_gross, OOS, END)
            rb_turn = rebalance_turnover(sig, panels)
            case = {
                "N": n, "freq": freq,
                "实际持仓中位数": n_hold,
                "每次调仓换手只数": round(float(rb_turn), 1),
                "全期": st_full,
                "OOS(2021+)": st_oos,
                "逐年超额": yearly_excess(r, bench_ew),
            }
            out["cases"].append(case)
            print(f"N={n} freq={freq:2d} | 持仓{n_hold}只 调仓换手{rb_turn:.1f}只/期 | "
                  f"全期 年化{st_full['年化%']}% 夏普{st_full['夏普']} 回撤{st_full['回撤%']}% "
                  f"超额等权{st_full['超额等权%']}% 换手{st_full['换手x']}x 成本{st_full['成本%']}% | "
                  f"OOS 年化{st_oos['年化%']}% 夏普{st_oos['夏普']} 超额{st_oos['超额等权%']}%",
                  flush=True)

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freq_compare_smallcap_result.json")
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
    print(f"\n结果已写入 {path}")


if __name__ == "__main__":
    main()
