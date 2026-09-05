# -*- coding: utf-8 -*-
"""从（腾讯 hfq, 不复权）两条序列反解公司行动，重建乘法复权收益。

为什么需要：腾讯 fqkline 的 hfq 是**加法复权** `hfq = k·raw + c`，加法项进了收益率的
分母，于是 `r_hfq = r_raw × (k·raw/hfq)` —— 日收益被一个每天都在变、小于 1 的系数
系统性压缩（工行年化波动 0.1193，交易所口径 0.1837）。见 quant_research/blockers/B0005-*。

好在 k、c 只在除权日跳变，所以这两条序列已经把【事件日 + 送转比例 + 每股现金】
编码进去了：事件前后各拟合一段仿射关系，相邻两段之差就是那次公司行动。

    s = k_before / k_after        股数倍数（10送10 时 s = 2）
    C = s · (c_after − c_before) / k_after     每股现金，按事件前的股数计
    总收益 = (s · raw + C) / raw_prev − 1

离线批处理（scripts/rebuild_adjusted.py）另外用 baostock 的 pctChg 做事件定位与
金额校验，精度更高；实盘拿不到 baostock，用这里的纯仿射口径。两者实测等价：
逐日偏差中位 4.7e-17，单日最大偏差 p90 5e-04，年化波动相对误差最大 0.0123%。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FIT_WIN = 20      # 事件前后各取多少个交易日拟合
FIT_MIN = 6       # 拟合最少需要几个点
RESID_TOL = 0.004  # 仿射残差容差，约 4 倍报价跳动的一半
NOOP_TOL = 1e-4   # 小于此值视为没有公司行动


def _affine_at(h, r, i, win=FIT_WIN):
    """在下标 i 处解事件前后两段的 (k, c)，返回 (股数倍数 s, 每新股现金 d)。"""
    lo, hi = max(0, i - win), min(len(r), i + win)
    if i - lo < FIT_MIN or hi - i < FIT_MIN:
        return None
    out = []
    for a, b in ((lo, i), (i, hi)):
        rr, hh = r[a:b], h[a:b]
        if not (np.isfinite(rr).all() and np.isfinite(hh).all()):
            return None
        k, c = np.polyfit(rr, hh, 1)
        if np.max(np.abs(k * rr + c - hh)) > RESID_TOL:
            return None
        out.append((float(k), float(c)))
    (k0, c0), (k1, c1) = out
    if abs(k0) < 1e-12 or abs(k1) < 1e-12:
        return None
    return k0 / k1, (c1 - c0) / k1


def events(hfq: pd.Series, raw: pd.Series) -> dict:
    """返回 {日期: (股数倍数 s, 每股现金 C)}，C 按事件前的股数计。"""
    j = pd.concat([hfq.rename("h"), raw.rename("r")], axis=1).dropna().sort_index()
    if len(j) < 2 * FIT_MIN + 2:
        return {}
    h, r = j.h.to_numpy(float), j.r.to_numpy(float)
    days, i = [], 0
    while i < len(j):
        end = min(i + FIT_WIN, len(j))
        if end - i < FIT_MIN:
            break
        k, c = np.polyfit(r[i:end], h[i:end], 1)
        t = end
        while t < len(j) and abs(k * r[t] + c - h[t]) <= RESID_TOL:
            t += 1
        if t < len(j):
            days.append(t)
        i = t
    out = {}
    for t in days:
        got = _affine_at(h, r, t)
        if got is None:
            continue
        m, d_new = got
        if abs(m) < 1e-12:
            continue
        s = 1.0 / m
        C = s * d_new                      # 每新股 → 每旧股
        if abs(s - 1.0) < NOOP_TOL and abs(C) < NOOP_TOL:
            continue
        if C < 0:                          # 现金分红不可能为负；小额负值是报价量化残差
            C = 0.0
        out[j.index[t]] = (s, C)
    return out


def total_return(hfq: pd.Series, raw: pd.Series) -> pd.Series:
    """单只标的的乘法复权日收益。"""
    j = pd.concat([hfq.rename("h"), raw.rename("r")], axis=1).dropna().sort_index()
    if j.empty:
        return pd.Series(dtype=float)
    ev = events(j.h, j.r)
    s = pd.Series(1.0, index=j.index)
    c = pd.Series(0.0, index=j.index)
    for day, (ss, cc) in ev.items():
        s[day], c[day] = ss, cc
    return (j.r * s + c) / j.r.shift(1) - 1.0


def adjusted_close(hfq: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """把 (hfq, 不复权) 两张宽表重建成乘法复权收盘价面板。

    起点用该股第一根不复权收盘价，之后按重建的日收益累乘 —— 因子只用到收益与比值，
    绝对水平不影响任何判读。个股解不出事件时**退回不复权价**（价格收益），
    而不是退回 hfq；hfq 正是要修的东西，退回它等于什么都没修。
    """
    cols = [c for c in hfq.columns if c in raw.columns]
    out = {}
    for code in cols:
        h, r = hfq[code], raw[code]
        tr = total_return(h, r)
        if tr.empty:
            continue
        base = r.dropna()
        if base.empty:
            continue
        out[code] = base.iloc[0] * (1.0 + tr.fillna(0.0)).cumprod()
    if not out:
        return pd.DataFrame(index=hfq.index)
    df = pd.DataFrame(out).reindex(index=hfq.index)
    return df.astype(np.float32) if hfq.dtypes.iloc[0] == np.float32 else df
