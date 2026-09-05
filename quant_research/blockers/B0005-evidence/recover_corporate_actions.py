#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B0005 可行性验证：公司行动表能不能只用本地已有数据反解出来。

背景：腾讯 fqkline 的 hfq 是加法复权 `hfq = k·raw + c`，k 与 c 只在除权日跳变。
既然两条序列都在本地缓存里，(k, c) 的台阶就把【事件日期 + 送转比例 + 每股现金】
全编码进去了 —— 不需要外部的公司行动表。

本脚本做三件事：
  1. 用滚动仿射拟合把 (k, c) 分段，跳变点即事件日；
  2. 从相邻两段解出 m = k_old/k_new（股数倍数的倒数）与 D = Δc/k_new（每股现金）；
  3. 用 (m, D) 重建总收益 `(raw_t·m + D)/raw_{t-1} − 1`，与 baostock 的交易所口径
     pctChg 对账。

用法：
    cd astock_quant && ../.venv/bin/python ../quant_research/blockers/B0005-evidence/recover_corporate_actions.py

只读本地缓存，不联网、不写台账、不改任何策略数据。
"""
import glob
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HFQ, RAW, BS = "data/kline_hfq", "data/kline_raw", "data_bs/daily"
START, END = "2017-01-01", "2026-09-04"
WIN, TOL = 15, 0.004          # 拟合窗口；残差容差取 4 倍报价跳动的一半
N = np.sqrt(252)


def affine_segments(code, start=START, win=WIN, tol=TOL):
    """把 (raw, hfq) 切成若干仿射段。段内 hfq = k·raw + c，段界就是公司行动日。"""
    if not (os.path.exists(f"{HFQ}/{code}.csv") and os.path.exists(f"{RAW}/{code}.csv")):
        return None, None
    h = pd.read_csv(f"{HFQ}/{code}.csv").set_index("date")["close"]
    r = pd.read_csv(f"{RAW}/{code}.csv").set_index("date")["close"]
    j = pd.concat([h.rename("h"), r.rename("r")], axis=1).dropna().sort_index().loc[start:]
    if len(j) < 120:
        return None, None
    H, R, D = j.h.to_numpy(), j.r.to_numpy(), list(j.index)
    segs, i = [], 0
    while i < len(D):
        end = min(i + win, len(D))
        if end - i < 5:
            break
        k, c = np.polyfit(R[i:end], H[i:end], 1)
        t = end
        while t < len(D) and abs(k * R[t] + c - H[t]) <= tol:
            t += 1
        segs.append((D[i], float(k), float(c)))
        i = t
    return j, segs


def corporate_actions(segs):
    """相邻两段之差 = 一次公司行动。m 是股数倍数，D 是每股现金（按事件前股数计）。"""
    out = {}
    for (_, k0, c0), (d1, k1, c1) in zip(segs[:-1], segs[1:]):
        out[d1] = {"m": k0 / k1, "D": (c1 - c0) / k1}
    return out


def total_return(raw, actions):
    m = pd.Series(1.0, index=raw.index)
    d = pd.Series(0.0, index=raw.index)
    for day, a in actions.items():
        if day in m.index:
            m[day], d[day] = a["m"], a["D"]
    return (raw * m + d) / raw.shift(1) - 1


def baostock_pct(code):
    p = f"{BS}/{code[:2]}_{code[2:]}.csv"
    if not os.path.exists(p):
        return None
    bs = pd.read_csv(p)
    bs["date"] = bs["date"].astype(str)
    return pd.to_numeric(bs.set_index("date").sort_index()["pctChg"], errors="coerce") / 100


def main():
    codes = [os.path.basename(f)[:-4] for f in sorted(glob.glob(f"{HFQ}/*.csv"))]
    step = max(1, len(codes) // int(sys.argv[1] if len(sys.argv) > 1 else 400))
    sample = codes[::step]

    n_ok = n_short = n_bs = 0
    ev_counts, splits, rows = [], [], []
    for code in sample:
        j, segs = affine_segments(code)
        if segs is None:
            n_short += 1
            continue
        n_ok += 1
        acts = corporate_actions(segs)
        ev_counts.append(len(acts))
        for day, a in acts.items():
            if abs(a["m"] - 1) > 0.02:
                splits.append((code, day, round(a["m"], 4)))
        b = baostock_pct(code)
        if b is None:
            continue
        n_bs += 1
        tr = total_return(j.r, acts)
        h = j.h.pct_change()
        z = pd.concat([tr.rename("t"), h.rename("h"), b.rename("b")], axis=1).sort_index().dropna()
        z = z[(z.index >= "2017-01-04") & (z.index <= END)]
        if len(z) < 200:
            continue
        rows.append({
            "code": code, "n": len(z),
            "fix_vs_bs": float((z.t - z.b).abs().median()),
            "hfq_vs_bs": float((z.h - z.b).abs().median()),
            "fix_off_1bp": int(((z.t - z.b).abs() > 1e-4).sum()),
            "hfq_off_1bp": int(((z.h - z.b).abs() > 1e-4).sum()),
            "vol_fix": float(z.t.std() * N), "vol_bs": float(z.b.std() * N),
            "vol_hfq": float(z.h.std() * N),
        })

    ev = np.array(ev_counts)
    print(f"抽样 {len(sample)} 只 / 全库 {len(codes)} 只；可分析 {n_ok}，样本太短 {n_short}，有 baostock 对照 {n_bs}")
    print(f"每只检出公司行动数：中位 {np.median(ev):.0f}，均值 {ev.mean():.1f}，p90 {np.percentile(ev, 90):.0f}")
    print(f"送转事件（股数倍数偏离 1 超 2%）{len(splits)} 个，比例应为 1/1.3、1/1.4、1/2 这类整数分之一：")
    for x in splits[:6]:
        print("   ", x)

    df = pd.DataFrame(rows)
    if df.empty:
        print("\n没有可对账的样本")
        return
    print(f"\n与 baostock 交易所口径对账（{len(df)} 只）：")
    print(f"  逐日偏差中位数    修正后 {df.fix_vs_bs.median():.2e}   原 hfq {df.hfq_vs_bs.median():.2e}")
    print(f"  偏差>1bp 的天数占比 修正后 {(df.fix_off_1bp / df.n).median() * 100:.2f}%   原 hfq {(df.hfq_off_1bp / df.n).median() * 100:.2f}%")
    rel_fix = (df.vol_fix / df.vol_bs - 1).abs()
    rel_hfq = (df.vol_hfq / df.vol_bs - 1).abs()
    print(f"  年化波动相对误差  修正后 中位 {rel_fix.median() * 100:.2f}% / p90 {rel_fix.quantile(.9) * 100:.2f}%"
          f"   原 hfq 中位 {rel_hfq.median() * 100:.2f}% / p90 {rel_hfq.quantile(.9) * 100:.2f}%")
    worst = df.reindex(rel_fix.sort_values(ascending=False).index).head(5)
    print("\n  修正后仍对不上的前 5 只（多为配股；本脚本不处理配股）：")
    for _, w in worst.iterrows():
        print(f"    {w['code']} vol 修正 {w['vol_fix']:.4f} vs bs {w['vol_bs']:.4f}"
              f"  相对误差 {abs(w['vol_fix'] / w['vol_bs'] - 1) * 100:.1f}%")


if __name__ == "__main__":
    main()
