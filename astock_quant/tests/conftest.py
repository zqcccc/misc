"""测试用的合成数据构造器。

单元测试不依赖真实行情下载：用可控的合成面板，才能对引擎做"已知答案"的
精确校验（成本、涨跌停、停牌、T+1、退市清算）。
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_panels(prices: dict[str, list[float]], dates: pd.DatetimeIndex = None,
                opens: dict[str, list[float]] = None,
                volumes: dict[str, list[float]] = None,
                highs: dict[str, list[float]] = None,
                lows: dict[str, list[float]] = None,
                amount_scale: float = 1e8) -> dict[str, pd.DataFrame]:
    n = len(next(iter(prices.values())))
    if dates is None:
        dates = pd.bdate_range("2020-01-02", periods=n)
    close = pd.DataFrame(prices, index=dates, dtype=float)
    open_ = pd.DataFrame(opens, index=dates, dtype=float) if opens else close.shift(1).fillna(close)
    high = pd.DataFrame(highs, index=dates, dtype=float) if highs else \
        pd.concat([close, open_]).groupby(level=0).max() * 1.001
    low = pd.DataFrame(lows, index=dates, dtype=float) if lows else \
        pd.concat([close, open_]).groupby(level=0).min() * 0.999
    volume = pd.DataFrame(volumes, index=dates, dtype=float) if volumes else \
        pd.DataFrame(1e6, index=dates, columns=close.columns)
    amount = volume * 0 + amount_scale
    amount = amount.where(close.notna())
    return {"open": open_, "high": high, "low": low, "close": close,
            "volume": volume, "amount": amount, "close_raw": close}


@pytest.fixture
def rng():
    return np.random.default_rng(20260902)


@pytest.fixture
def random_panels(rng):
    """80 只股票 * 400 天的随机游走面板，带随机停牌。"""
    n_days, n_stocks = 400, 80
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    codes = [f"sh60{i:04d}" for i in range(n_stocks)]
    rets = rng.normal(0.0005, 0.02, size=(n_days, n_stocks))
    close = pd.DataFrame(10 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=codes)
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.005, size=(n_days, n_stocks)))
    high = np.maximum(close, open_) * (1 + np.abs(rng.normal(0, 0.004, size=(n_days, n_stocks))))
    low = np.minimum(close, open_) * (1 - np.abs(rng.normal(0, 0.004, size=(n_days, n_stocks))))
    volume = pd.DataFrame(rng.lognormal(13, 0.5, size=(n_days, n_stocks)), index=dates, columns=codes)
    # 随机停牌
    halt = rng.random((n_days, n_stocks)) < 0.01
    close = close.mask(halt)
    open_ = open_.mask(halt)
    high = pd.DataFrame(high, index=dates, columns=codes).mask(halt)
    low = pd.DataFrame(low, index=dates, columns=codes).mask(halt)
    volume = volume.mask(halt)
    amount = (volume * close * 100).astype(float)
    return {"open": open_, "high": high, "low": low, "close": close,
            "volume": volume, "amount": amount, "close_raw": close}
