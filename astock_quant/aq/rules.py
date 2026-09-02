"""A 股交易规则：涨跌停、停牌、印花税。

这些规则决定"信号能不能真的成交"。回测里最常见的隐性作弊就是：昨天收盘出
信号，今天一字涨停照样买入。这里把可交易性显式建模。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def board_limit(code: str, date: pd.Timestamp) -> float:
    """当日涨跌停幅度（不含 ST，ST 由 infer_st_cap 单独处理）。"""
    num = code[2:]
    if num.startswith(("688", "689")):
        return config.LIMIT_STAR
    if num.startswith(("300", "301")):
        return (config.LIMIT_CHINEXT if date >= pd.Timestamp(config.CHINEXT_20PCT_DATE)
                else config.LIMIT_MAIN)
    return config.LIMIT_MAIN


def limit_matrix(codes: list[str], dates: pd.DatetimeIndex) -> pd.DataFrame:
    """(date × code) 的涨跌停幅度矩阵。"""
    star = np.array([c[2:].startswith(("688", "689")) for c in codes])
    cyb = np.array([c[2:].startswith(("300", "301")) for c in codes])
    base = np.where(star, config.LIMIT_STAR, config.LIMIT_MAIN)
    mat = np.tile(base, (len(dates), 1)).astype(np.float32)
    after = dates >= pd.Timestamp(config.CHINEXT_20PCT_DATE)
    mat[np.ix_(after, cyb)] = config.LIMIT_CHINEXT
    return pd.DataFrame(mat, index=dates, columns=codes)


def infer_st_cap(ret: pd.DataFrame, window: int = 60, cap: float = 0.055) -> pd.DataFrame:
    """用过去 window 天的最大绝对涨跌幅推断 ST（±5% 限制）。

    没有 PIT 的 ST 名单，只能反推。关键是只用**过去**的数据（rolling 到 t-1 为
    止），推断结果用于 t 日的可交易性判断，不引入未来信息。
    """
    rolling_max = ret.abs().rolling(window, min_periods=30).max().shift(1)
    return rolling_max <= cap


def tradability(panels: dict[str, pd.DataFrame], price: str = "open") -> dict[str, pd.DataFrame]:
    """返回 can_buy / can_sell / has_bar。

    price="open" 表示以次日开盘价成交（默认），"close" 表示以次日收盘价成交，
    后者用于稳健性检验。可交易性只用到成交那一刻已经发生的信息。
    """
    close, open_ = panels["close"], panels["open"]
    high, low, vol = panels["high"], panels["low"], panels["volume"]
    prev_close = close.shift(1)
    exec_px = open_ if price == "open" else close
    open_ret = exec_px / prev_close - 1.0
    ret = close / prev_close - 1.0

    limits = limit_matrix(list(close.columns), close.index)
    st = infer_st_cap(ret)
    limits = limits.where(~st, 0.05)

    has_bar = close.notna() & (vol > 0)
    yizi = has_bar & (high <= low * 1.0001)          # 一字板，全天无价差
    tol = config.LIMIT_TOLERANCE
    at_up = open_ret >= (limits - tol)
    at_down = open_ret <= -(limits - tol)

    can_buy = has_bar & ~at_up & ~(yizi & (open_ret > 0))
    can_sell = has_bar & ~at_down & ~(yizi & (open_ret < 0))
    return {"can_buy": can_buy.fillna(False), "can_sell": can_sell.fillna(False),
            "has_bar": has_bar.fillna(False), "open_ret": open_ret, "ret": ret}


def stamp_duty(date: pd.Timestamp) -> float:
    rate = config.STAMP_DUTY_SCHEDULE[0][1]
    for d, r in config.STAMP_DUTY_SCHEDULE:
        if date >= pd.Timestamp(d):
            rate = r
    return rate


def buy_cost_rate() -> float:
    return config.COMMISSION_RATE + config.TRANSFER_FEE_RATE + config.SLIPPAGE_RATE


def sell_cost_rate(date: pd.Timestamp) -> float:
    return (config.COMMISSION_RATE + config.TRANSFER_FEE_RATE
            + config.SLIPPAGE_RATE + stamp_duty(date))
