"""
核心赛道白马龙头自适应动量与择时策略
(Core-Leader Adaptive Momentum & Regime Strategy)
=====================================================
设计理念:
- 每次精选 2~3 只股票集中持仓 (默认 top_k = 3)。
- 宏观择时 (Regime Filter): 大盘 (沪深300ETF) 破位下行时持币空仓避险。
- 个股趋势 (Trend Gate): 价格站上 MA20/MA60 均线，剔除下行趋势个股。
- 风险调整动量 (Risk-Adjusted Momentum): 综合 20日/60日收益率与波动率比值排序。
- 动态离场: 跌破 MA20 止损保护，防范龙头补跌。
- 严格无未来函数:
  T日收盘后仅根据截至T日已知历史数据计算指标与生成订单;
  订单在 T+1 日开盘执行。
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scripts.ashare_quant.engine import BacktestEngine, Order


class AdaptiveLeaderStrategy:
    def __init__(
        self,
        top_k: int = 3,                       # 精选持仓只数 (2 或 3)
        rebalance_interval_days: int = 5,      # 调仓周期 (5个交易日约一周)
        benchmark_symbol: str = "510300.SS",  # 大盘基准
        market_ma_filter: int = 60,           # 大盘均线过滤周期
        stock_fast_ma: int = 20,              # 个股快速均线
        stock_slow_ma: int = 60,              # 个股慢速均线
        vol_lookback: int = 20,               # 波动率回看窗口
        stop_loss_pct: float = 0.08,          # 个股相对最高点回撤止损阈值 (8%)
        enable_market_filter: bool = True,    # 是否启用大盘避险过滤
    ):
        self.top_k = top_k
        self.rebalance_interval_days = rebalance_interval_days
        self.benchmark_symbol = benchmark_symbol
        self.market_ma_filter = market_ma_filter
        self.stock_fast_ma = stock_fast_ma
        self.stock_slow_ma = stock_slow_ma
        self.vol_lookback = vol_lookback
        self.stop_loss_pct = stop_loss_pct
        self.enable_market_filter = enable_market_filter

        self.last_rebalance_step = -9999
        self.step_count = 0
        self.peak_prices: Dict[str, float] = {}

    def compute_regime_state(self, bm_history: pd.DataFrame) -> bool:
        """
        判断大盘市场环境:
        返回 True 表示市场处于健康上升/震荡市，允许开仓;
        返回 False 表示市场处于空头下行期，强制避险空仓。
        """
        if not self.enable_market_filter:
            return True

        if len(bm_history) < self.market_ma_filter + 5:
            return True

        closes = bm_history["close"].values
        cur_price = closes[-1]
        ma_filter = np.mean(closes[-self.market_ma_filter:])
        ma20 = np.mean(closes[-20:])

        # 大盘破位条件: 价格在 60 日线下方且 20 日均线在 60 日均线下方
        if cur_price < ma_filter and ma20 < ma_filter:
            return False
        return True

    def calculate_stock_score(self, df_history: pd.DataFrame) -> Optional[float]:
        """
        计算单只个股的风险调整动量得分。
        若不满足基础趋势门槛则返回 None。
        """
        needed_bars = max(self.stock_slow_ma, 60) + 5
        if len(df_history) < needed_bars:
            return None

        closes = df_history["close"].values
        cur_p = closes[-1]
        ma20 = np.mean(closes[-self.stock_fast_ma:])
        ma60 = np.mean(closes[-self.stock_slow_ma:])

        # 趋势门槛 1: 当前价格必须站在 MA20 之上 (处于上升波段)
        if cur_p < ma20:
            return None

        # 趋势门槛 2: MA20 大于 MA60 (中期趋势向好)
        if ma20 < ma60:
            return None

        # 收益率
        ret20 = (cur_p / closes[-20]) - 1.0
        ret60 = (cur_p / closes[-60]) - 1.0

        if ret20 <= 0:
            return None

        # 20日历史年化波动率
        daily_rets = np.diff(closes[-self.vol_lookback:]) / closes[-self.vol_lookback:-1]
        vol20 = np.std(daily_rets) * np.sqrt(250)
        if vol20 < 1e-4:
            vol20 = 1e-4

        # 综合评分: 动量 / 波动率
        score = 0.5 * (ret20 / vol20) + 0.5 * (ret60 / vol20)
        return float(score)

    def on_bar_close(
        self,
        current_date: str,
        history_map: Dict[str, pd.DataFrame],
        engine: BacktestEngine
    ):
        """
        T 日收盘触发的回测策略逻辑:
        1. 检查持仓标的止损 (破位/高点回撤);
        2. 周期调仓 (选出 Top-K 股票并调整目标持仓);
        3. 生成订单并放入 engine.pending_orders (T+1 执行)。
        """
        self.step_count += 1
        bm_history = history_map.get(self.benchmark_symbol)
        if bm_history is None or len(bm_history) < self.stock_slow_ma:
            return

        # 更新持仓标的历史最高价用于追踪止损
        for sym, pos in engine.positions.items():
            if sym in history_map:
                cur_close = history_map[sym]["close"].iloc[-1]
                if sym not in self.peak_prices:
                    self.peak_prices[sym] = cur_close
                else:
                    self.peak_prices[sym] = max(self.peak_prices[sym], cur_close)

        # 1. 紧急风控/止损检查 (每日收盘检查)
        stop_orders = []
        for sym, pos in list(engine.positions.items()):
            if sym not in history_map:
                continue
            df_sym = history_map[sym]
            closes = df_sym["close"].values
            cur_close = closes[-1]
            ma20 = np.mean(closes[-self.stock_fast_ma:])

            # 跌破 MA20 或 高点回撤超过止损阈值
            peak = self.peak_prices.get(sym, cur_close)
            dd_from_peak = (cur_close / peak) - 1.0 if peak > 0 else 0.0

            should_stop = (cur_close < ma20) or (dd_from_peak < -self.stop_loss_pct)
            if should_stop:
                stop_orders.append(
                    Order(
                        symbol=sym,
                        action="SELL",
                        shares=pos.shares,
                        target_weight=0.0,
                        created_date=current_date,
                        reason=f"STOP_LOSS(dd={dd_from_peak:.1%}, p={cur_close:.2f}<ma={ma20:.2f})"
                    )
                )

        if stop_orders:
            # 加入未决订单
            for so in stop_orders:
                # 避免重复提交
                if not any(o.symbol == so.symbol and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(so)

        # 2. 定期轮动再平衡
        is_rebal_day = (self.step_count - self.last_rebalance_step >= self.rebalance_interval_days)
        if not is_rebal_day:
            return

        self.last_rebalance_step = self.step_count

        # 大盘环境检查
        regime_bull = self.compute_regime_state(bm_history)

        target_symbols: List[str] = []
        if regime_bull:
            # 扫描个股打分
            candidate_scores: List[Tuple[str, float]] = []
            for sym, df_sym in history_map.items():
                if sym == self.benchmark_symbol:
                    continue
                score = self.calculate_stock_score(df_sym)
                if score is not None and score > 0:
                    candidate_scores.append((sym, score))

            # 按得分降序排列
            candidate_scores.sort(key=lambda x: x[1], reverse=True)
            target_symbols = [x[0] for x in candidate_scores[:self.top_k]]

        # 计算目标持仓配置
        # 如果选出 N 只 (N <= top_k)，每只股票目标权重为 1 / top_k
        # 剩余的 1 - N/top_k 保持现金
        target_weight_per_stock = (1.0 / self.top_k) if self.top_k > 0 else 0.0

        current_total_equity = engine.cash + sum(
            pos.shares * history_map[sym]["close"].iloc[-1]
            for sym, pos in engine.positions.items()
            if sym in history_map
        )

        # 准备订单
        # A. 卖出不在 target_symbols 中的股票
        for sym, pos in list(engine.positions.items()):
            if sym not in target_symbols:
                if not any(o.symbol == sym and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(
                            symbol=sym,
                            action="SELL",
                            shares=pos.shares,
                            target_weight=0.0,
                            created_date=current_date,
                            reason="REBALANCE_OUT"
                        )
                    )

        # B. 买入或调整目标股票
        for sym in target_symbols:
            cur_close = history_map[sym]["close"].iloc[-1]
            target_val = current_total_equity * target_weight_per_stock
            target_shares = int(target_val // (cur_close * engine.lot_size)) * engine.lot_size

            cur_shares = engine.positions[sym].shares if sym in engine.positions else 0
            diff_shares = target_shares - cur_shares

            if diff_shares >= engine.lot_size:
                # 检查是否已有同标的买单
                if not any(o.symbol == sym and o.action == "BUY" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(
                            symbol=sym,
                            action="BUY",
                            shares=diff_shares,
                            target_weight=target_weight_per_stock,
                            created_date=current_date,
                            reason="REBALANCE_BUY"
                        )
                    )
            elif diff_shares <= -engine.lot_size:
                # 减仓
                sell_shares = abs(diff_shares)
                if not any(o.symbol == sym and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(
                            symbol=sym,
                            action="SELL",
                            shares=sell_shares,
                            target_weight=target_weight_per_stock,
                            created_date=current_date,
                            reason="REBALANCE_REDUCE"
                        )
                    )
