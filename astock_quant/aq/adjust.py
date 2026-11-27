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

生产打分的**唯一复权入口**是 build_scoring_panels：研究/seed/历史回测管线喂已对账的
重建面板（baostock 校验，宁缺毋滥），实盘管线喂 (hfq, 不复权) 走仿射重建。仿射路径上
解不出的公司行动——尤其是后段窗口不足的近期除权——会把该股相关因子在事件窗口内
标记为无效并排除出当日截面排名，绝不悄悄退回 raw 收益（那正是 B0005 要修的错）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FIT_WIN = 20      # 事件前后各取多少个交易日拟合
FIT_MIN = 6       # 拟合最少需要几个点
RESID_TOL = 0.004  # 仿射残差容差，约 4 倍报价跳动的一半
NOOP_TOL = 1e-4   # 小于此值视为没有公司行动

# 未确认公司行动生效后，多少根 K 线内该股因子不可用。必须 ≥ 复合信号里最长的
# 回看窗口（ivol60 的 60 日）；rev5 的 5 日窗口被它覆盖。
UNCONFIRMED_EVENT_INVALID_BARS = 60


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


def classify_events(hfq: pd.Series, raw: pd.Series) -> tuple[dict, list]:
    """返回（解出的 {日期: (股数倍数 s, 每股现金 C)}，未解出的公司行动日列表）。

    C 按事件前的股数计。候选事件日找不到可用仿射解（前后窗口不足、残差超限、
    序列末端太短的近期除权）时进第二个返回值：调用方必须把这些日期的因子标记
    为无效，而不是按 raw 价格收益凑合。
    """
    j = pd.concat([hfq.rename("h"), raw.rename("r")], axis=1).dropna().sort_index()
    if len(j) < 2 * FIT_MIN + 2:
        return {}, []
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
    resolved: dict = {}
    unresolved: list = []
    for t in days:
        got = _affine_at(h, r, t)
        if got is None:
            unresolved.append(j.index[t])
            continue
        m, d_new = got
        if abs(m) < 1e-12:
            unresolved.append(j.index[t])
            continue
        s = 1.0 / m
        C = s * d_new                      # 每新股 → 每旧股
        if abs(s - 1.0) < NOOP_TOL and abs(C) < NOOP_TOL:
            continue
        if C < 0:                          # 现金分红不可能为负；小额负值是报价量化残差
            C = 0.0
        resolved[j.index[t]] = (s, C)
    return resolved, unresolved


def events(hfq: pd.Series, raw: pd.Series) -> dict:
    """解出的公司行动 {日期: (股数倍数 s, 每股现金 C)}，C 按事件前的股数计。"""
    return classify_events(hfq, raw)[0]


def adjusted_levels(hfq: pd.Series, raw: pd.Series) -> tuple[pd.Series, list]:
    """单只标的：重建的乘法复权价序列 + 未确认的公司行动日列表。

    事件解得出来按 (s·raw + C)/raw_prev − 1 累乘；解不出来（含近期除权窗口
    不足）的日期沿用原收益继续累乘——水平序列本身只是载体，该日期往后的因子
    窗口由 build_scoring_panels 标记无效并排除，绝不直接进打分。
    """
    j = pd.concat([hfq.rename("h"), raw.rename("r")], axis=1).dropna().sort_index()
    if j.empty:
        return pd.Series(dtype=float), []
    resolved, unresolved = classify_events(j.h, j.r)
    s = pd.Series(1.0, index=j.index)
    c = pd.Series(0.0, index=j.index)
    for day, (ss, cc) in resolved.items():
        s[day], c[day] = ss, cc
    tr = (j.r * s + c) / j.r.shift(1) - 1.0
    base = raw.dropna()
    if base.empty:
        return pd.Series(dtype=float), unresolved
    level = base.iloc[0] * (1.0 + tr.fillna(0.0)).cumprod()
    return level, unresolved


def adjusted_open(open_raw: pd.DataFrame, close_raw: pd.DataFrame,
                  close_adj: pd.DataFrame) -> pd.DataFrame:
    """乘法复权开盘价 = 不复权开盘 × 当日复权因子（复权收盘 ÷ 不复权收盘）。

    除权日的开盘价已按新股数报价，与收盘共用同一因子，口径一致；
    不复权收盘缺失或为 0 的地方因子不可信，开盘价置 NaN，不冒充可用。
    """
    factor = close_adj / close_raw.replace(0.0, np.nan)
    return open_raw * factor


@dataclass
class ScoringAdjustment:
    """打分用复权面板及其可信度。

    close/open 是乘法复权价；factor_valid[date, code] = False 表示该股当日因子
    无效（事件日起 UNCONFIRMED_EVENT_INVALID_BARS 根 K 线内存在未确认公司行动），
    必须从当日截面排名中排除；unresolved_events 是逐股的未确认事件日明细，
    供本期收益判断建仓到最新收盘之间是否跨过事件。
    """

    close: pd.DataFrame
    open: pd.DataFrame
    factor_valid: pd.DataFrame
    unresolved_events: dict[str, pd.DatetimeIndex]
    source: str


def build_scoring_panels(
    close_verified: pd.DataFrame | None,
    close_raw: pd.DataFrame,
    close_hfq: pd.DataFrame | None = None,
    open_verified: pd.DataFrame | None = None,
    open_raw: pd.DataFrame | None = None,
    invalid_bars: int = UNCONFIRMED_EVENT_INVALID_BARS,
) -> ScoringAdjustment:
    """生产打分的唯一复权入口（seed / 历史回测 / live 共用）。

    - 有已对账的重建面板（研究管线，baostock 校验过、宁缺毋滥）→ 直接采用；
    - 否则用 (hfq, 不复权) 做仿射重建（实盘管线，见模块 docstring）；
    - 仿射路径上解不出的公司行动（近期除权后段窗口不足等）→ 该股因子从事件日
      起 invalid_bars 根 K 线内标记无效并排除，绝不退回 raw 收益凑数。
    """
    if close_verified is not None:
        valid = pd.DataFrame(True, index=close_verified.index,
                             columns=close_verified.columns, dtype=bool)
        if open_verified is not None:
            open_adj = open_verified.reindex(index=close_verified.index,
                                             columns=close_verified.columns)
        elif open_raw is not None:
            open_adj = adjusted_open(open_raw, close_raw, close_verified)
        else:
            open_adj = pd.DataFrame(index=close_verified.index)
        return ScoringAdjustment(
            close=close_verified, open=open_adj, factor_valid=valid,
            unresolved_events={}, source="verified_rebuild",
        )

    if close_hfq is None:
        raise ValueError("必须提供 close_verified（已对账重建）或 close_hfq（仿射重建原料）之一")

    close_out: dict[str, pd.Series] = {}
    open_out: dict[str, pd.Series] = {}
    valid_out: dict[str, pd.Series] = {}
    unresolved: dict[str, pd.DatetimeIndex] = {}
    for code in close_hfq.columns:
        if code not in close_raw.columns:
            continue
        level, unresolved_days = adjusted_levels(close_hfq[code], close_raw[code])
        if level.empty:
            continue
        close_out[code] = level
        if open_raw is not None and code in open_raw.columns:
            factor = level / close_raw[code].replace(0.0, np.nan).reindex(level.index)
            open_out[code] = open_raw[code].reindex(level.index) * factor
        flag = pd.Series(True, index=level.index, dtype=bool)
        for day in unresolved_days:
            start = level.index.get_loc(day)
            flag.iloc[start : start + invalid_bars] = False
        valid_out[code] = flag
        if unresolved_days:
            unresolved[code] = pd.DatetimeIndex(unresolved_days)

    close_df = pd.DataFrame(close_out).reindex(index=close_hfq.index).sort_index(axis=1)
    open_df = pd.DataFrame(open_out).reindex(index=close_hfq.index).sort_index(axis=1)
    valid_df = (
        pd.DataFrame(valid_out)
        .reindex(index=close_hfq.index)
        .reindex(columns=close_df.columns)
        .fillna(False)
        .astype(bool)
    )
    return ScoringAdjustment(
        close=close_df, open=open_df, factor_valid=valid_df,
        unresolved_events=unresolved, source="affine_reconstruct",
    )
