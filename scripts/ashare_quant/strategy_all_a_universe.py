"""
全 A 股 5,282 只股票真实大池子: 截面低波防御质量轮动策略
(All-A 5,282 Stocks Cross-Sectional Low-Volatility Quality Strategy)
===================================================================
1. 标的池规模: 5,282 只全量 A 股 (完整覆盖 2015-01-05 ~ 2026-09-02, 包含退市/暴跌/牛股/平庸股);
2. PIT 可投资池过滤: 上市天数 >= 180 天 (剔除次新), 20日均成交额 >= 6000 万元 (真实机构流动性门槛);
3. 因子逻辑 (低波动异象 Low-Vol Anomaly):
   - 120 日年化实际波动率 + 120 日下行半方差风险惩罚;
   - 价格必须站稳 MA60 生命线上方 (杜绝单边大阴跌暴雷资产);
4. 严格集中持仓: 仅持有 Top 3 只股票, 20 日稳健轮动 (低换手).
"""

from __future__ import annotations
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from scripts.ashare_quant.engine import BacktestEngine, Order


class AllAUniverseLowVolStrategy:
    def __init__(
        self,
        top_k: int = 3,
        rebalance_interval_days: int = 20,
        lookback_window: int = 120,
        ma_filter_window: int = 60,
        min_listed_days: int = 180,
        min_amount_yuan: float = 6e7,
    ):
        self.top_k = top_k
        self.rebalance_interval_days = rebalance_interval_days
        self.lookback_window = lookback_window
        self.ma_filter_window = ma_filter_window
        self.min_listed_days = min_listed_days
        self.min_amount_yuan = min_amount_yuan

        self.step_count = 0
        self.last_rebalance_step = -9999

    def select_targets(
        self,
        cur_idx: int,
        c_all: np.ndarray,
        o_all: np.ndarray,
        a_all: np.ndarray,
        v_all: np.ndarray,
        listed_days_mat: np.ndarray,
        symbols: List[str]
    ) -> List[str]:
        if cur_idx < max(self.lookback_window, self.min_listed_days):
            return []

        c_cur = c_all[cur_idx]
        o_cur = o_all[cur_idx]
        v_cur = v_all[cur_idx]
        amt20 = np.nanmean(a_all[cur_idx - 20 : cur_idx + 1], axis=0)
        ld = listed_days_mat[cur_idx]

        # 1. PIT 可投资池过滤
        valid = (ld >= self.min_listed_days) & (amt20 >= self.min_amount_yuan) & np.isfinite(c_cur) & (c_cur > 0) & np.isfinite(o_cur) & (o_cur > 0) & (v_cur > 0)
        univ = np.where(valid)[0]
        if len(univ) < self.top_k:
            return []

        # 2. 截面提取过去 lookback 历史
        c_slice = c_all[cur_idx - self.lookback_window : cur_idx + 1, univ]
        cur_p = c_slice[-1]
        ma60 = np.nanmean(c_slice[-self.ma_filter_window:], axis=0)
        trend_ok = (cur_p >= ma60)

        rets = np.diff(c_slice, axis=0) / c_slice[:-1]
        vol = np.nanstd(rets, axis=0) * np.sqrt(250)
        down_r = np.where(rets < 0, rets, 0.0)
        down_vol = np.sqrt(np.nanmean(down_r ** 2, axis=0)) * np.sqrt(250)

        # 综合风险
        risk = vol * 0.5 + down_vol * 0.5
        risk[~trend_ok] = 999.0
        clean_mask = (risk > 0.05) & (risk < 900.0) & np.isfinite(risk)
        clean_indices = np.where(clean_mask)[0]

        if len(clean_indices) < self.top_k:
            return []

        best_sub_indices = clean_indices[np.argsort(risk[clean_indices])[:self.top_k]]
        return [symbols[univ[idx]] for idx in best_sub_indices]
