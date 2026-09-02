"""策略层：因子合成 → 打分 → 目标权重。

只做两件事：把因子面板在**每个截面内**标准化后加权合成；按调仓日取分数最高
的 N 只等权。任何跨时间的全样本统计（例如用整段样本的均值/方差去标准化因子、
或用全样本 IC 决定权重后回头跑同一段样本）都是未来函数，本模块刻意不提供这
类接口；因子权重由 scripts/run_research.py 在样本内确定，样本外原样使用。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import factors


def masked_rank_score(factor: pd.DataFrame, mask: pd.DataFrame) -> pd.DataFrame:
    """在可投资股票池内做截面百分位排名，池外置 NaN。"""
    f = factor.where(mask.reindex_like(factor).fillna(False))
    return factors.cs_rank(f) - 0.5


def composite(factor_panels: dict[str, pd.DataFrame], weights: dict[str, float],
              mask: pd.DataFrame) -> pd.DataFrame:
    """加权合成打分。用秩而非原始值，抗极值、抗量纲差异。"""
    total = None
    wsum = 0.0
    for name, w in weights.items():
        if w == 0:
            continue
        s = masked_rank_score(factor_panels[name], mask) * w
        total = s if total is None else total.add(s, fill_value=0.0)
        wsum += abs(w)
    if total is None:
        raise ValueError("weights 全为 0")
    valid = mask.reindex_like(total).fillna(False)
    return (total / wsum).where(valid)


def rebalance_dates(dates: pd.DatetimeIndex, freq: int, start=None, end=None) -> pd.DatetimeIndex:
    """每 freq 个交易日调仓一次（freq=5 约等于周频，20 约等于月频）。"""
    d = dates
    if start is not None:
        d = d[d >= pd.Timestamp(start)]
    if end is not None:
        d = d[d <= pd.Timestamp(end)]
    return d[::freq]


def top_n_signals(score: pd.DataFrame, rb_dates: pd.DatetimeIndex, top_n: int,
                  max_weight: float = None) -> pd.DataFrame:
    """每个调仓日取分数最高的 top_n 只等权。"""
    rows = {}
    for d in rb_dates:
        if d not in score.index:
            continue
        s = score.loc[d].dropna()
        if len(s) < top_n:
            if s.empty:
                continue
        picks = s.nlargest(min(top_n, len(s)))
        w = pd.Series(1.0 / len(picks), index=picks.index)
        if max_weight is not None:
            w = w.clip(upper=max_weight)
        rows[d] = w
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).T.sort_index()


def _weights_for(picks: list, d: pd.Timestamp, scheme: str,
                 inv_vol: pd.DataFrame = None, max_weight: float = None) -> pd.Series:
    """给定选中的股票，计算权重。inv_vol 用过去 60 日波动率的倒数（PIT 可得）。"""
    if scheme == "invvol" and inv_vol is not None:
        v = inv_vol.loc[d, picks].replace([np.inf, -np.inf], np.nan)
        if v.notna().sum() >= max(1, int(len(picks) * 0.6)):
            v = v.fillna(v.median())
            w = v / v.sum()
        else:
            w = pd.Series(1.0 / len(picks), index=picks)
    else:
        w = pd.Series(1.0 / len(picks), index=picks)
    if max_weight is not None:
        w = w.clip(upper=max_weight)
        w = w / w.sum()
    return w


def inverse_vol(close: pd.DataFrame, n: int = 60) -> pd.DataFrame:
    ret = close / close.shift(1) - 1.0
    vol = ret.rolling(n, min_periods=int(n * 0.6)).std()
    return 1.0 / vol.replace(0.0, np.nan)


def top_n_signals_buffered(score: pd.DataFrame, rb_dates: pd.DatetimeIndex, top_n: int,
                          buffer_mult: float = 2.0, scheme: str = "equal",
                          inv_vol: pd.DataFrame = None, max_weight: float = None) -> pd.DataFrame:
    """带缓冲区的选股：已持有的股票只要还排在前 top_n * buffer_mult 名就不换。

    A 股双边成本约 0.3%，无缓冲的周频换手会吃掉 8% 以上的年化收益。缓冲区能把
    换手砍掉一半以上而基本不损失打分质量。状态只沿时间正向传递，不引入未来信息。
    """
    rows: dict = {}
    held: list[str] = []
    keep_rank = int(top_n * buffer_mult)
    for d in rb_dates:
        if d not in score.index:
            continue
        s = score.loc[d].dropna()
        if s.empty:
            continue
        order = s.rank(ascending=False, method="first")
        keep = [c for c in held if c in order.index and order[c] <= keep_rank]
        if len(keep) > top_n:                      # 超额时保留排名最靠前的
            keep = sorted(keep, key=lambda c: order[c])[:top_n]
        need = top_n - len(keep)
        if need > 0:
            cands = order[~order.index.isin(keep)].nsmallest(need).index.tolist()
            keep = keep + cands
        held = keep
        if held:
            rows[d] = _weights_for(held, d, scheme, inv_vol, max_weight)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).T.sort_index()


def exclude_bottom_signals(score: pd.DataFrame, rb_dates: pd.DatetimeIndex,
                          drop_pct: float = 0.2, band: float = 0.05,
                          max_holdings: int = None,
                          scheme: str = "equal", inv_vol: pd.DataFrame = None) -> pd.DataFrame:
    """"剔除打分最差的一档，剩下的等权持有"。

    分层测试显示这些量价因子的信息几乎全在最差那一档：Q1 显著为负，Q2~Q5 之间
    近乎持平。"精选前 20%"没有额外收益，"避开后 20%"才是纯多头能吃到的那部分
    （A 股个股不能做空，多空价差拿不到）。

    drop_pct: 名义剔除比例。band: 迟滞带宽 —— 新买入要排到 drop_pct + band 之上，
    已持有的跌破 drop_pct - band 才卖，避免在边界上来回换手。
    max_holdings: 持仓上限；剔除后剩下上千只不现实，超过上限时取打分最高的若干只。
    """
    buy_th, hold_th = drop_pct + band, max(0.0, drop_pct - band)
    rows: dict = {}
    held: list[str] = []
    for d in rb_dates:
        if d not in score.index:
            continue
        s = score.loc[d].dropna()
        if len(s) < 100:
            continue
        pct = s.rank(pct=True)                 # 1 = 打分最高
        picks = sorted(set(pct[pct > buy_th].index)
                       | {c for c in held if c in pct.index and pct[c] > hold_th})
        if max_holdings and len(picks) > max_holdings:
            picks = pct[picks].nlargest(max_holdings).index.tolist()
        held = picks
        if held:
            rows[d] = _weights_for(held, d, scheme, inv_vol)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).T.sort_index()


def quantile_signals(score: pd.DataFrame, rb_dates: pd.DatetimeIndex,
                     q: int, group: int) -> pd.DataFrame:
    """分层回测用：取第 group 层（0 = 分数最低层）等权。"""
    rows = {}
    for d in rb_dates:
        if d not in score.index:
            continue
        s = score.loc[d].dropna()
        if len(s) < q * 5:
            continue
        labels = pd.qcut(s.rank(method="first"), q, labels=False)
        picks = s[labels == group]
        if picks.empty:
            continue
        rows[d] = pd.Series(1.0 / len(picks), index=picks.index)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).T.sort_index()
