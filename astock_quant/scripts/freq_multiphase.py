"""调仓频率：多相位（staggered rebalance）实验。

问题：freq=60 在 TEST 段只调仓 11 次，单点估计完全被「调仓日历运气」支配
      —— 早一天晚一天调仓，选中的 7 只票可能完全不同。

解法：freq=f 的周期有 f 个不同的起始偏移。把每个偏移都跑一遍，得到 f 条路径；
      f 条路径的调仓事件总数相同（= 总天数），所以跨 freq 对比是公平的。
      多相位等权平均组合 = 每天等权持有所有相位子组合，它抹掉「调运日历运气」，
      保留「信号 + 调仓频率」的真实效应。这个组合本身也是可执行的（每天调 1/f 仓位）。

注意：多相位**不能**消除「期段运气」（2024-2026 这段市场恰好如何）。
      那个只能靠拉长历史，见 freq 研究的下一步。

产出：deliverables/smallcap_freq_multiphase.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aq import backtest, config, factors, metrics, panel, strategy, universe  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_multiphase.json")

TRADING_DAYS = 244
WEIGHTS = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}
N_HOLD = 7
BUFFER = 2.0
FREQS = (5, 10, 20, 30, 60)
BASELINE = 20                      # 与谁比
TEST = ("2024-01-02", "2026-09-01")
FULL = ("2016-01-04", "2026-09-01")
BLOCK = 21                         # block bootstrap 块长（约一个月）
N_BOOT = 2000
RNG = np.random.default_rng(20260908)


def investable(panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return universe.investable(panels, min_listed=250, exclude_st=True,
                               liquidity_top_pct=1.0)


def build_score(panels: dict[str, pd.DataFrame], mask: pd.DataFrame):
    close, amount = panels["close"], panels["amount"]
    ret = factors.daily_return(close)
    fp = {
        "rev5": factors.rev(close, 5),
        "liqsize20": factors.liquidity_size(amount, 20),
        "ivol60": factors.idio_vol(ret, 60),
    }
    return strategy.composite(fp, WEIGHTS, mask)


def rb_offset(dates: pd.DatetimeIndex, freq: int, k: int, start: str, end: str):
    """第 k 个相位：i0 建仓，此后每 freq 天调一次，整体偏移 k 天。"""
    i0 = int(np.searchsorted(dates, pd.Timestamp(start)))
    i1 = int(np.searchsorted(dates, pd.Timestamp(end), side="right"))
    out = [i0]
    j = 0
    while True:
        idx = i0 + k + j * freq
        if idx >= i1:
            break
        if idx > i0:
            out.append(idx)
        j += 1
    return dates[sorted(set(out))]


def run_phase(panels, score, dates, freq, k, start, end):
    rb = rb_offset(dates, freq, k, start, end)
    sig = strategy.top_n_signals_buffered(score, rb, N_HOLD, BUFFER, "equal")
    net = backtest.run(panels, sig, start=start, end=end,
                       exec_price="open", zero_cost=False)
    return net


def stats_of(r: pd.Series) -> dict:
    st = metrics.perf_stats(r)
    return {
        "年化%": round(float(st["年化收益"]) * 100, 2),
        "夏普": round(float(st["夏普(rf=0)"]), 3),
    }


def block_bootstrap_diff(a: pd.Series, b: pd.Series, n: int, block: int, rng):
    """a - b 的年化差异的分布（分块自助，保留日收益自相关）。"""
    d = (a - b).to_numpy(dtype=float)
    d = d[np.isfinite(d)]
    T = len(d)
    if T < 60:
        return None
    nblk = int(np.ceil(T / block))
    starts = rng.integers(0, max(1, T - block), size=(n, nblk))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % T
    samples = d[idx.reshape(n, -1)[:, :T]]
    ann = samples.mean(axis=1) * TRADING_DAYS * 100
    return ann


def main():
    print("加载面板 ...", flush=True)
    panels = panel.load_panels()
    dates = panels["close"].index
    mask = investable(panels)
    score = build_score(panels, mask)
    print(f"  面板 {dates[0].date()} -> {dates[-1].date()}  分数 {score.shape}", flush=True)

    result = {
        "meta": {
            "说明": "多相位（staggered rebalance）：freq=f 跑 f 个起始偏移，抹掉调仓日历运气",
            "能消除": "调仓日历运气（freq=60 只有 11 次调仓的问题）",
            "不能消除": "期段运气（2024-2026 这段市场恰好如何）—— 只能靠拉长历史",
            "持仓N": N_HOLD, "buffer": BUFFER, "权重": WEIGHTS,
            "频率": list(FREQS), "TEST段": TEST, "全段": FULL,
            "块长": BLOCK, "自助次数": N_BOOT,
        },
        "段": {},
    }

    for seg_name, (s0, s1) in (("TEST", TEST), ("全段", FULL)):
        print(f"\n=== {seg_name} {s0} ~ {s1} ===", flush=True)
        seg = {"相位": {}, "平均组合": {}, "对比基线": {}}
        avg_ret = {}

        for f in FREQS:
            anns, shps, rets = [], [], []
            for k in range(f):
                net = run_phase(panels, score, dates, f, k, s0, s1)
                r = net.ret.loc[s0:s1]
                st = stats_of(r)
                anns.append(st["年化%"])
                shps.append(st["夏普"])
                rets.append(r)
            arr = np.array(anns, dtype=float)
            # 多相位等权平均组合：各相位日收益算术平均
            R = pd.concat(rets, axis=1)
            avg = R.mean(axis=1)
            a_st = stats_of(avg)
            seg["相位"][str(f)] = {
                "相位数": f,
                "年化均值%": round(float(arr.mean()), 2),
                "年化中位%": round(float(np.median(arr)), 2),
                "年化std": round(float(arr.std(ddof=1)), 2),
                "年化min%": round(float(arr.min()), 2),
                "年化p25%": round(float(np.percentile(arr, 25)), 2),
                "年化p75%": round(float(np.percentile(arr, 75)), 2),
                "年化max%": round(float(arr.max()), 2),
                "极差pp": round(float(arr.max() - arr.min()), 2),
                "夏普均值": round(float(np.mean(shps)), 3),
                "年化序列": [round(float(x), 2) for x in anns],
            }
            seg["平均组合"][str(f)] = a_st
            avg_ret[f] = avg
            print(f"  freq={f:>3}  相位{f:>2}个  "
                  f"年化 均值{arr.mean():7.2f}%  中位{np.median(arr):7.2f}%  "
                  f"std{arr.std(ddof=1):6.2f}  "
                  f"[{arr.min():7.2f} , {arr.max():7.2f}]  极差{arr.max()-arr.min():6.2f}pp  "
                  f"| 平均组合 {a_st['年化%']:7.2f}% 夏普{a_st['夏普']:6.3f}", flush=True)

        # 各 freq 的平均组合 vs 基线平均组合，分块自助
        base = avg_ret[BASELINE]
        for f in FREQS:
            if f == BASELINE:
                continue
            ann = block_bootstrap_diff(avg_ret[f], base, N_BOOT, BLOCK, RNG)
            if ann is None:
                continue
            diff = float(seg["平均组合"][str(f)]["年化%"]
                         - seg["平均组合"][str(BASELINE)]["年化%"])
            p = 2 * min((ann <= 0).mean(), (ann >= 0).mean())
            seg["对比基线"][str(f)] = {
                "年化差pp": round(diff, 2),
                "自助均值pp": round(float(ann.mean()), 2),
                "自助95区间": [round(float(np.percentile(ann, 2.5)), 2),
                               round(float(np.percentile(ann, 97.5)), 2)],
                "p值": round(float(p), 4),
                "显著5%": bool(p < 0.05),
            }
        result["段"][seg_name] = seg

        for f, v in seg["对比基线"].items():
            print(f"    freq={f:>3} vs {BASELINE}: Δ{v['年化差pp']:+7.2f}pp  "
                  f"95%CI[{v['自助95区间'][0]:+7.2f}, {v['自助95区间'][1]:+7.2f}]  "
                  f"p={v['p值']:.4f} {'显著' if v['显著5%'] else '不显著'}", flush=True)

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    print(f"\n已写出 {OUT}")


if __name__ == "__main__":
    main()
