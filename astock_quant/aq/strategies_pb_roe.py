"""PB + ROE 双打分选股策略模块。

包含变体：
1. simple_pb_roe_5050: 50% 低 PB + 50% 高 ROE (全市场横截面百分位)
2. simple_pb_roe_7030: 70% 低 PB + 30% 高 ROE
3. pb_roe_quality_gated: PB in [0.5, 5.0] & ROE >= 10% 质量门槛下的双打分
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from . import factors, strategy


def compute_pb_roe_score(
    pb: pd.DataFrame,
    roe: pd.DataFrame,
    mask: pd.DataFrame,
    weight_pb: float = 0.5,
    weight_roe: float = 0.5,
    pb_min: float | None = None,
    pb_max: float | None = None,
    roe_min: float | None = None,
) -> pd.DataFrame:
    """计算横截面 PB + ROE 综合得分。
    
    低 PB (越低越好): 1 - rank(pct=True)
    高 ROE (越高越好): rank(pct=True)
    """
    valid_mask = mask.copy()
    if pb_min is not None:
        valid_mask &= (pb >= pb_min)
    if pb_max is not None:
        valid_mask &= (pb <= pb_max)
    if roe_min is not None:
        valid_mask &= (roe >= roe_min)

    # 仅在有效池内打分
    pb_valid = pb.where(valid_mask)
    roe_valid = roe.where(valid_mask)

    # PB 越低得分越高 (降序排名百分位，等价于 1 - 升序百分位)
    pb_score = 1.0 - pb_valid.rank(axis=1, pct=True, ascending=True)
    # ROE 越高得分越高 (升序排名百分位)
    roe_score = roe_valid.rank(axis=1, pct=True, ascending=True)

    # 加权合成
    score = (weight_pb * pb_score + weight_roe * roe_score) / (weight_pb + weight_roe)
    # 保证非有效股票得分是 NaN
    return score.where(valid_mask)


def generate_signals(
    score: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
    top_n: int = 20,
    buffer_mult: int = 1,
) -> pd.DataFrame:
    """生成目标持仓权重面板 (rebalance_date x code)。
    
    buffer_mult=1: 严格 Top N (每次重新挑选前 N 只)
    buffer_mult>1: 带滞后缓冲带 (掉出 top_n * buffer_mult 才被替换)
    """
    if buffer_mult <= 1:
        return strategy.top_n_signals(score, rebalance_dates, top_n)
    else:
        return strategy.top_n_signals_buffered(score, rebalance_dates, top_n, buffer_mult=buffer_mult)
