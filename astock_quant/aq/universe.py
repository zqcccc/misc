"""可投资股票池（point-in-time）。

每一天的股票池只依赖到当天为止的信息：上市天数、是否停牌、过去 20 日成交额、
是否疑似 ST。特别注意**没有**做"剔除后来退市的股票"这类过滤 —— 那是最典型的
未来函数，也是幸存者偏差的来源。本项目的股票池按代码空间穷举下载，退市股在
退市前始终留在池子里，退市当天由引擎按最后价格清算。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, rules


def listed_days(close: pd.DataFrame) -> pd.DataFrame:
    """截至当日累计的有效交易日数（含当日）。"""
    return close.notna().cumsum()


def avg_amount(amount: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    return amount.rolling(n, min_periods=int(n * 0.5)).mean()


def investable(panels: dict[str, pd.DataFrame],
               min_listed: int = None,
               min_amount: float = None,
               liquidity_top_pct: float = None,
               exclude_st: bool = True) -> pd.DataFrame:
    close, amount = panels["close"], panels["amount"]
    min_listed = config.MIN_LISTED_DAYS if min_listed is None else min_listed
    min_amount = config.MIN_AMOUNT_YUAN if min_amount is None else min_amount
    top_pct = config.LIQUIDITY_TOP_PCT if liquidity_top_pct is None else liquidity_top_pct

    mask = close.notna()
    mask &= listed_days(close) >= min_listed
    amt = avg_amount(amount)
    mask &= amt >= min_amount
    if top_pct < 1.0:
        mask &= amt.rank(axis=1, pct=True, ascending=True) >= (1.0 - top_pct)
    if exclude_st:
        ret = close / close.shift(1) - 1.0
        mask &= ~rules.infer_st_cap(ret)      # 用过去 60 日幅度上限反推 ST
    return mask.fillna(False)


def equal_weight_benchmark(panels: dict[str, pd.DataFrame],
                           mask: pd.DataFrame) -> pd.Series:
    """可投资股票池的等权日收益（不含成本），作为选股 alpha 的对照基准。"""
    close = panels["close"]
    ret = (close / close.shift(1) - 1.0)
    m = mask.shift(1).fillna(False)          # t 日收益对应 t-1 日就在池子里的股票
    r = ret.where(m)
    return r.mean(axis=1).fillna(0.0)
