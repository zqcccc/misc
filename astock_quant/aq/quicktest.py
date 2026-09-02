"""快速分层测试（不含交易成本），只用于因子初筛。

口径：t 日收盘出信号 → t+1 起持有，用收盘价计算组合日收益。与正式引擎相比
少了成本、涨跌停、停牌约束，所以**只能用来比较因子强弱**，不能当作策略业绩；
最终结论一律以 backtest.run 的结果为准。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def daily_weights(signals: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """把调仓日权重展开成逐日权重（持有到下一个调仓日）。

    注意：必须先把调仓日那一行里没选中的股票补 0 再 ffill。直接 ffill 会让
    上一期选中、这一期没选中的股票把旧权重一路带下去，权重和会越滚越大
    （实测能滚到 6 倍）—— test_daily_weights_sum_to_one 就是盯这个的。
    """
    w = signals.fillna(0.0).reindex(dates).ffill()
    return w.fillna(0.0)


def portfolio_return(weights: pd.DataFrame, close: pd.DataFrame) -> pd.Series:
    """t 日权重 -> t+1 日收益，shift(1) 保证不用当日信息交易当日收益。"""
    ret = (close / close.shift(1) - 1.0).reindex(columns=weights.columns)
    w = weights.shift(1).fillna(0.0)
    # 停牌股当日收益按 0 处理（持仓不变），避免 NaN 传染
    r = (w * ret.fillna(0.0)).sum(axis=1)
    return r


def layered_returns(score: pd.DataFrame, close: pd.DataFrame,
                    rb_dates: pd.DatetimeIndex, q: int = 5) -> pd.DataFrame:
    """分 q 层的日收益序列（0 = 分数最低层）。"""
    dates = close.index
    cols: dict[int, pd.Series] = {}
    labels_by_date = {}
    for d in rb_dates:
        if d not in score.index:
            continue
        s = score.loc[d].dropna()
        if len(s) < q * 10:
            continue
        labels_by_date[d] = pd.qcut(s.rank(method="first"), q, labels=False)
    for g in range(q):
        rows = {}
        for d, lab in labels_by_date.items():
            picks = lab[lab == g].index
            if len(picks):
                rows[d] = pd.Series(1.0 / len(picks), index=picks)
        sig = pd.DataFrame(rows).T.sort_index()
        cols[g] = portfolio_return(daily_weights(sig, dates), close)
    return pd.DataFrame(cols)
