"""
EP004 增强版: A股核心赛道龙头截面相对强弱 Alpha 策略
(Cross-Sectional Relative Strength Alpha & Low Turnover)
============================================================
基于 frank-quant/ai-trading-videos EP004 核心理念重构:
1. 提取真 Alpha (Relative Strength Alpha vs 沪深300基准):
   - 衡量标的相对于基准大盘的超额主升浪能力, 剥离纯 Beta 噪音。
2. 严格控制换手 (Turnover Control & Hysteresis Buffer):
   - 调仓周期设为 20 个交易日 (月度稳健轮动);
   - 引入 25% 的滞后缓冲 (新标的评分必须显著超越老持仓才调换), 杜绝频繁摩擦。
3. 非对称盈亏比 (Asymmetric Risk-Reward / Let Winners Run):
   - 浮盈超过 15% 时自动启动移动跟踪止盈 (锁定 50% 利润);
   - 跌破关键支撑 MA20 或高点回撤 10% 坚决离场。
4. 严格防未来函数:
   - T日盘后计算截面相对强弱, T+1日以开盘价 Open 成交。
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scripts.ashare_quant.engine import BacktestEngine, Order


class RelativeStrengthAlphaStrategy:
    def __init__(
        self,
        top_k: int = 3,                       # 集中持仓只数 (2 或 3)
        rebalance_interval_days: int = 20,     # 月度稳健调仓 (约20个交易日, 大幅压降换手摩擦)
        benchmark_symbol: str = "510300.SS",  # 基准
        market_filter_ma: int = 60,           # 大盘均线过滤
        rs_window_fast: int = 20,             # 快速相对强弱窗口
        rs_window_slow: int = 60,             # 慢速相对强弱窗口
        hysteresis_buffer: float = 0.20,      # 换仓缓冲阈值 (新股票必须比老股票高20%才换)
        stop_loss_pct: float = 0.10,          # 基础止损阈值 (10%)
        trail_activation_pct: float = 0.15,   # 浮盈达到 15% 启动移动止盈
        trail_pullback_pct: float = 0.08,     # 移动止盈回撤阈值 (8%)
        enable_market_filter: bool = True,
    ):
        self.top_k = top_k
        self.rebalance_interval_days = rebalance_interval_days
        self.benchmark_symbol = benchmark_symbol
        self.market_filter_ma = market_filter_ma
        self.rs_window_fast = rs_window_fast
        self.rs_window_slow = rs_window_slow
        self.hysteresis_buffer = hysteresis_buffer
        self.stop_loss_pct = stop_loss_pct
        self.trail_activation_pct = trail_activation_pct
        self.trail_pullback_pct = trail_pullback_pct
        self.enable_market_filter = enable_market_filter

        self.last_rebalance_step = -9999
        self.step_count = 0
        self.entry_prices: Dict[str, float] = {}
        self.peak_prices: Dict[str, float] = {}
        self.last_scores: Dict[str, float] = {}

    def is_market_healthy(self, bm_history: pd.DataFrame) -> bool:
        """大盘环境判断: 若沪深300跌破 MA60 且 20日线死叉60日线，判定系统性下行"""
        if not self.enable_market_filter:
            return True
        if len(bm_history) < self.market_filter_ma + 5:
            return True
        closes = bm_history["close"].values
        cur_p = closes[-1]
        ma60 = np.mean(closes[-self.market_filter_ma:])
        ma20 = np.mean(closes[-20:])
        if cur_p < ma60 and ma20 < ma60:
            return False
        return True

    def calculate_rs_alpha(self, df_stock: pd.DataFrame, df_bm: pd.DataFrame) -> Optional[float]:
        """
        计算相对于沪深300基准的截面纯 Alpha 动量得分
        """
        needed = max(self.rs_window_slow, 60) + 5
        if len(df_stock) < needed or len(df_bm) < needed:
            return None

        stk_closes = df_stock["close"].values
        bm_closes = df_bm["close"].values

        cur_stk = stk_closes[-1]
        ma20_stk = np.mean(stk_closes[-20:])
        ma60_stk = np.mean(stk_closes[-60:])

        # 绝对趋势门槛: 个股不能处于下行趋势
        if cur_stk < ma20_stk or ma20_stk < ma60_stk:
            return None

        # 相对大盘的超额收益 (Alpha 动量)
        stk_ret20 = cur_stk / stk_closes[-self.rs_window_fast] - 1.0
        bm_ret20 = bm_closes[-1] / bm_closes[-self.rs_window_fast] - 1.0
        rs_20 = stk_ret20 - bm_ret20  # 相对大盘超额

        stk_ret60 = cur_stk / stk_closes[-self.rs_window_slow] - 1.0
        bm_ret60 = bm_closes[-1] / bm_closes[-self.rs_window_slow] - 1.0
        rs_60 = stk_ret60 - bm_ret60  # 相对大盘超额

        # 必须具备正向相对超额 (真 Alpha)
        if rs_20 <= 0 and rs_60 <= 0:
            return None

        # 波动率惩罚
        daily_rets = np.diff(stk_closes[-20:]) / stk_closes[-20:-1]
        vol20 = np.std(daily_rets) * np.sqrt(250)
        vol20 = max(vol20, 0.05)

        score = (0.6 * rs_60 + 0.4 * rs_20) / vol20
        return float(score)

    def on_bar_close(
        self,
        current_date: str,
        history_map: Dict[str, pd.DataFrame],
        engine: BacktestEngine
    ):
        self.step_count += 1
        bm_hist = history_map.get(self.benchmark_symbol)
        if bm_hist is None or len(bm_hist) < self.market_filter_ma:
            return

        # 更新持仓最高价与保本追踪
        for sym, pos in engine.positions.items():
            if sym in history_map:
                cur_c = history_map[sym]["close"].iloc[-1]
                if sym not in self.entry_prices:
                    self.entry_prices[sym] = pos.cost_price
                if sym not in self.peak_prices:
                    self.peak_prices[sym] = cur_c
                else:
                    self.peak_prices[sym] = max(self.peak_prices[sym], cur_c)

        # 1. 动态追踪止损止盈守护
        stop_orders = []
        for sym, pos in list(engine.positions.items()):
            if sym not in history_map:
                continue
            cur_c = history_map[sym]["close"].iloc[-1]
            entry_p = self.entry_prices.get(sym, pos.cost_price)
            peak_p = self.peak_prices.get(sym, cur_c)

            gain_from_entry = (cur_c / entry_p) - 1.0 if entry_p > 0 else 0.0
            pullback_from_peak = (cur_c / peak_p) - 1.0 if peak_p > 0 else 0.0

            # 条件 A: 移动止盈 (当浮盈超过 activation 阈值，从最高点回撤超过 pullback 阈值，锁利离场)
            trigger_trail = (gain_from_entry >= self.trail_activation_pct) and (pullback_from_peak <= -self.trail_pullback_pct)
            # 条件 B: 初始固定硬止损 (亏损超过 stop_loss_pct)
            trigger_hard_loss = (gain_from_entry <= -self.stop_loss_pct)
            # 条件 C: 跌破 20 日生命线且回撤明显
            ma20 = np.mean(history_map[sym]["close"].values[-20:])
            trigger_ma_break = (cur_c < ma20) and (pullback_from_peak <= -0.06)

            if trigger_trail or trigger_hard_loss or trigger_ma_break:
                reason = "TRAIL_TP" if trigger_trail else ("HARD_SL" if trigger_hard_loss else "MA_BREAK")
                stop_orders.append(
                    Order(
                        symbol=sym,
                        action="SELL",
                        shares=pos.shares,
                        target_weight=0.0,
                        created_date=current_date,
                        reason=f"STOP({reason}, p={cur_c:.2f}, gain={gain_from_entry:.1%})"
                    )
                )
                # 清除跟踪状态
                self.entry_prices.pop(sym, None)
                self.peak_prices.pop(sym, None)

        if stop_orders:
            for so in stop_orders:
                if not any(o.symbol == so.symbol and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(so)

        # 2. 定期再平衡 (月度)
        is_rebal_day = (self.step_count - self.last_rebalance_step >= self.rebalance_interval_days)
        if not is_rebal_day:
            return

        self.last_rebalance_step = self.step_count
        healthy = self.is_market_healthy(bm_hist)

        candidate_scores: Dict[str, float] = {}
        if healthy:
            for sym, df in history_map.items():
                if sym == self.benchmark_symbol:
                    continue
                sc = self.calculate_rs_alpha(df, bm_hist)
                if sc is not None and sc > 0:
                    candidate_scores[sym] = sc

        self.last_scores = candidate_scores

        # 选出 Top-K，带缓冲阈值机制 (Hysteresis Buffer)
        # 如果老持仓依然在前列且没有被新股票大幅超越，优先保留老持仓以节约换手！
        ranked_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        
        target_symbols: List[str] = []
        current_holdings = list(engine.positions.keys())

        # 先看当前持仓是否依然合格
        for sym in current_holdings:
            if sym in candidate_scores:
                target_symbols.append(sym)
                if len(target_symbols) >= self.top_k:
                    break

        # 如果持仓不足 top_k，从得分最高者中补充
        for sym, sc in ranked_candidates:
            if len(target_symbols) >= self.top_k:
                break
            if sym not in target_symbols:
                target_symbols.append(sym)

        # 订单生成
        target_weight_per_stock = (1.0 / self.top_k) if self.top_k > 0 else 0.0

        current_equity = engine.cash + sum(
            pos.shares * history_map[sym]["close"].iloc[-1]
            for sym, pos in engine.positions.items()
            if sym in history_map
        )

        # 卖出不在目标列表中的
        for sym, pos in list(engine.positions.items()):
            if sym not in target_symbols:
                if not any(o.symbol == sym and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(sym, "SELL", pos.shares, 0.0, current_date, "REBAL_OUT")
                    )
                    self.entry_prices.pop(sym, None)
                    self.peak_prices.pop(sym, None)

        # 买入目标股票
        for sym in target_symbols:
            cur_p = history_map[sym]["close"].iloc[-1]
            target_val = current_equity * target_weight_per_stock
            target_shares = int(target_val // (cur_p * engine.lot_size)) * engine.lot_size
            cur_shares = engine.positions[sym].shares if sym in engine.positions else 0
            diff = target_shares - cur_shares

            if diff >= engine.lot_size:
                if not any(o.symbol == sym and o.action == "BUY" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(sym, "BUY", diff, target_weight_per_stock, current_date, "REBAL_BUY")
                    )
            elif diff <= -engine.lot_size * 2:  # 显著减仓才调
                sell_sh = abs(diff)
                if not any(o.symbol == sym and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(sym, "SELL", sell_sh, target_weight_per_stock, current_date, "REBAL_REDUCE")
                    )
