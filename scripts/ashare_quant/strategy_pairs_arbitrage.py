"""
A股同赛道核心双龙头配对统计套利轮动策略 (Statistical Arbitrage Pairs Rotation)
================================================================================
非动量 (Non-Momentum) 纯 Alpha 策略，基于协整均值回归与相对价值偏离。

设计理念与微观机制:
1. 标的选定:
   - 选取 A 股商业壁垒深厚、自由现金流充沛的高股息核心双龙头:
     中国神华 (601088.SS) vs 长江电力 (600900.SS)
   - 两者均为红利防御核心资产，行业逻辑与现金流高度同向，长期对数价差呈现强协整性。
2. 统计套利信号构建 (Spread Z-Score):
   - 计算两只股票历史对数比值: Spread_t = ln(P_A,t / P_B,t)
   - 滚动 W 交易日 (默认 60 日) 均值 mu 与标准差 sigma 计算 Z-Score:
     Z_t = (Spread_t - mu_t) / sigma_t
3. 状态转移与滞后缓冲 (Hysteresis Buffer):
   - 当 Z_t < -z_threshold (默认 -1.3): 说明标的 A 发生极端非理性超跌错杀，全仓轮动持有标的 A。
   - 当 Z_t > +z_threshold (默认 +1.3): 说明标的 B 发生极端超跌错杀 (或标的 A 过度泡沫)，全仓轮动持有标的 B。
   - 当 -z_threshold <= Z_t <= z_threshold: 维持当前既有持仓，不进行任何调仓，大幅压降交易换手磨损。
4. 严格微观约束与防未来函数:
   - 严格集中持仓: 仅持有 1 组配对 (单持 1 只优势股票)，拒绝宽基分散。
   - T 日收盘后基于当时切片生成信号与订单，T+1 日以开盘价 Open 撮合成交。
   - 严格遵守 T+1 锁仓规则，涨跌停不可买卖限制，计入真实佣金、印花税与滑点。
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scripts.ashare_quant.engine import BacktestEngine, Order


class StatisticalPairsArbitrageStrategy:
    def __init__(
        self,
        symbol_a: str = "601088.SS",          # 标的 A (默认: 中国神华)
        symbol_b: str = "600900.SS",          # 标的 B (默认: 长江电力)
        window: int = 60,                     # 协整统计滑动窗口 (交易日数)
        z_threshold: float = 1.3,             # 偏离度触发阈值 (标准差倍数)
    ):
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.window = window
        self.z_threshold = z_threshold

        self.current_favored: Optional[str] = None  # 'A' 或 'B'
        self.last_z_score: float = 0.0

    def calculate_spread_zscore(self, df_a: pd.DataFrame, df_b: pd.DataFrame) -> Optional[float]:
        """
        基于截至 T 日收盘的历史切片，计算对数价差比率及其统计偏离 Z-Score。
        彻底杜绝引入 T 日之后的任何未来数据。
        """
        needed_bars = self.window + 10
        if len(df_a) < needed_bars or len(df_b) < needed_bars:
            return None

        closes_a = df_a["close"].values
        closes_b = df_b["close"].values

        # 取最近 window 根收盘价计算对数价比
        slice_a = closes_a[-self.window:]
        slice_b = closes_b[-self.window:]

        log_spreads = np.log(slice_a / slice_b)
        mu = np.mean(log_spreads)
        sigma = np.std(log_spreads)

        if sigma < 1e-6:
            return None

        z = float((log_spreads[-1] - mu) / sigma)
        return z

    def on_bar_close(
        self,
        current_date: str,
        history_map: Dict[str, pd.DataFrame],
        engine: BacktestEngine
    ):
        """
        T 日收盘触发回调函数:
        1. 读取截至 T 日的无未来历史数据
        2. 计算价差偏离 Z-Score
        3. 产生状态转移与 T+1 开盘执行订单
        """
        if self.symbol_a not in history_map or self.symbol_b not in history_map:
            return

        df_a = history_map[self.symbol_a]
        df_b = history_map[self.symbol_b]

        z = self.calculate_spread_zscore(df_a, df_b)
        if z is None:
            return

        self.last_z_score = z

        # 状态转移逻辑 (带滞后缓冲，只有越过阈值才触发方向切换)
        if z < -self.z_threshold:
            # 标的 A 相对极度低估，应持有 A
            self.current_favored = 'A'
        elif z > self.z_threshold:
            # 标的 B 相对极度低估，应持有 B
            self.current_favored = 'B'
        elif self.current_favored is None:
            # 初始状态冷启动
            self.current_favored = 'A' if z <= 0.0 else 'B'

        # 确定各标的目标持仓权重 (集中持有 1 组配对中被错杀的一只)
        target_weight_a = 1.0 if self.current_favored == 'A' else 0.0
        target_weight_b = 1.0 if self.current_favored == 'B' else 0.0

        p_a = df_a["close"].iloc[-1]
        p_b = df_b["close"].iloc[-1]

        # 计算当前动态总市值与当前各标的持仓股数
        shares_a = engine.positions[self.symbol_a].shares if self.symbol_a in engine.positions else 0
        shares_b = engine.positions[self.symbol_b].shares if self.symbol_b in engine.positions else 0
        current_equity = engine.cash + (shares_a * p_a) + (shares_b * p_b)

        target_shares_a = int((current_equity * target_weight_a) // (p_a * engine.lot_size)) * engine.lot_size
        target_shares_b = int((current_equity * target_weight_b) // (p_b * engine.lot_size)) * engine.lot_size

        diff_a = target_shares_a - shares_a
        diff_b = target_shares_b - shares_b

        # 卖单优先生成 (以便在 T+1 开盘腾出可用资金)
        if diff_a < -engine.lot_size:
            if not any(o.symbol == self.symbol_a and o.action == "SELL" for o in engine.pending_orders):
                engine.pending_orders.append(
                    Order(
                        symbol=self.symbol_a,
                        action="SELL",
                        shares=abs(diff_a),
                        target_weight=target_weight_a,
                        created_date=current_date,
                        reason=f"PAIR_REBALANCE_OUT(z={z:.2f})"
                    )
                )

        if diff_b < -engine.lot_size:
            if not any(o.symbol == self.symbol_b and o.action == "SELL" for o in engine.pending_orders):
                engine.pending_orders.append(
                    Order(
                        symbol=self.symbol_b,
                        action="SELL",
                        shares=abs(diff_b),
                        target_weight=target_weight_b,
                        created_date=current_date,
                        reason=f"PAIR_REBALANCE_OUT(z={z:.2f})"
                    )
                )

        # 买单生成
        if diff_a >= engine.lot_size:
            if not any(o.symbol == self.symbol_a and o.action == "BUY" for o in engine.pending_orders):
                engine.pending_orders.append(
                    Order(
                        symbol=self.symbol_a,
                        action="BUY",
                        shares=diff_a,
                        target_weight=target_weight_a,
                        created_date=current_date,
                        reason=f"PAIR_REBALANCE_IN(z={z:.2f})"
                    )
                )

        if diff_b >= engine.lot_size:
            if not any(o.symbol == self.symbol_b and o.action == "BUY" for o in engine.pending_orders):
                engine.pending_orders.append(
                    Order(
                        symbol=self.symbol_b,
                        action="BUY",
                        shares=diff_b,
                        target_weight=target_weight_b,
                        created_date=current_date,
                        reason=f"PAIR_REBALANCE_IN(z={z:.2f})"
                    )
                )
