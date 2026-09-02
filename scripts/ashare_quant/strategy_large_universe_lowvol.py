"""
全市场客观大股票池: 截面低波动异象与防御质量轮动策略
(Large Universe Cross-Sectional Low-Volatility Quality Strategy)
===================================================================
彻底摆脱人工预选特定标的的幸存者偏差与过拟合:
1. 股票池基础:
   - 全景客观可投资股票池 (沪深300全量成分股池 / 全A股高流动性池，298~5000+标的);
   - 涵盖各行业真实牛股、腰斩暴跌股、周期轮动股与平庸震荡股。
2. 因子构建 (学术界与实战公认经典非动量 Alpha: 低波动异象 Low-Vol Anomaly):
   - 实际波动率 (Realized Volatility 120d): 散户过度投机高波动题材，导致高波动资产长期收益低; 低波动资产被机构锁定筹码，长期复利高。
   - 下行半方差 (Downside Semi-variance 120d): 严格惩罚下跌日的波动，挑选全市场抗跌属性最强的优质核心资产。
   - 换手率平稳度 (Turnover Stability 20d vs 120d): 剔除短期散户投机过度拥挤标的。
   - 基础生命线过滤: 价格必须处于 60 日均线 (MA60) 之上，杜绝暴雷资产与单边大阴跌垃圾。
3. 严格集中持仓与微观约束:
   - 仅限集中持有 Top 2~3 只股票 (默认 top_k = 3);
   - 月度稳健轮动 (约 20 个交易日)，配合 20% 滞后缓冲，年化换手率控制在 30x 以内;
   - 严格复用 engine.py: T 日收盘计算截面打分，T+1 日以开盘价 Open 撮合成交，T+1 锁仓，计入真实佣金/印花税/滑点。
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scripts.ashare_quant.engine import BacktestEngine, Order


class LargeUniverseLowVolStrategy:
    def __init__(
        self,
        top_k: int = 3,                      # 严格集中持仓只数 (2~3 只)
        rebalance_interval_days: int = 20,    # 月度稳健调仓周期 (20 个交易日)
        lookback_window: int = 120,          # 波动率与下行风险计算窗口 (120 日)
        ma_filter_window: int = 60,          # 基础生命线均线过滤窗口
        hysteresis_buffer: float = 0.20,     # 换仓滞后缓冲 (老持仓若仍处前列优先保留)
    ):
        self.top_k = top_k
        self.rebalance_interval_days = rebalance_interval_days
        self.lookback_window = lookback_window
        self.ma_filter_window = ma_filter_window
        self.hysteresis_buffer = hysteresis_buffer

        self.step_count = 0
        self.last_rebalance_step = -9999
        self.last_scores: Dict[str, float] = {}

    def calculate_single_stock_score(self, df: pd.DataFrame) -> Optional[float]:
        """
        基于截至 T 日历史切片，计算单只股票的防御质量得分 (纯无未来函数)
        """
        needed_bars = max(self.lookback_window, self.ma_filter_window) + 5
        if len(df) < needed_bars:
            return None

        closes = df["close"].values
        cur_p = closes[-1]
        if not (np.isfinite(cur_p) and cur_p > 0):
            return None

        # 基础趋势门槛: 价格必须站上 MA60 (排除行业产能出清、持续破位阴跌的衰退资产)
        ma60 = np.mean(closes[-self.ma_filter_window:])
        if cur_p < ma60:
            return None

        # 提取过去 lookback 根收盘价计算日收益率
        slice_c = closes[-self.lookback_window:]
        daily_rets = np.diff(slice_c) / slice_c[:-1]
        ann_vol = float(np.std(daily_rets) * np.sqrt(250))
        if ann_vol < 1e-5:
            return None

        # 下行风险 (Downside Semi-variance)
        downside_rets = daily_rets[daily_rets < 0]
        downside_vol = float(np.std(downside_rets) * np.sqrt(250)) if len(downside_rets) > 2 else ann_vol

        # 换手锁定度 (若有成交量数据)
        v_ratio = 1.0
        if "volume" in df.columns:
            vols = df["volume"].values
            v20 = np.mean(vols[-20:]) if len(vols) >= 20 else 1.0
            v120 = np.mean(vols[-self.lookback_window:]) if len(vols) >= self.lookback_window else 1.0
            if v120 > 0:
                v_ratio = float(v20 / v120)

        # 综合风险惩罚: 波动越低、下行回撤越平稳、成交量无暴炒拥挤，风险值越低
        composite_risk = ann_vol * 0.5 + downside_vol * 0.5 + v_ratio * 0.05
        if composite_risk <= 0.02:
            return None

        # 综合得分: 风险的倒数 (得分越高，防御质量越卓越)
        score = 1.0 / composite_risk
        return float(score)

    def on_bar_close(
        self,
        current_date: str,
        history_map: Dict[str, pd.DataFrame],
        engine: BacktestEngine
    ):
        """
        T 日收盘触发回调函数:
        1. 检查是否到达月度调仓窗口
        2. 在当前全池子所有标的上进行客观截面打分
        3. 选出 Top 2~3 只标的，带滞后缓冲生成订单，T+1 日开盘 Open 撮合
        """
        self.step_count += 1
        is_rebal_day = (self.step_count - self.last_rebalance_step >= self.rebalance_interval_days)
        if not is_rebal_day:
            return

        self.last_rebalance_step = self.step_count

        candidate_scores: Dict[str, float] = {}
        for sym, df in history_map.items():
            # 排除基准指数
            if "000300" in sym or "510300" in sym:
                continue
            sc = self.calculate_single_stock_score(df)
            if sc is not None and sc > 0:
                candidate_scores[sym] = sc

        self.last_scores = candidate_scores
        if len(candidate_scores) < self.top_k:
            return

        # 排序
        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)

        # 滞后缓冲机制 (Hysteresis Buffer):
        # 如果老持仓依然在排名前 top_k * 2 内，优先保留，大幅节省无谓换手摩擦
        target_symbols: List[str] = []
        current_holdings = list(engine.positions.keys())
        buffer_pool = [s for s, _ in ranked[:int(self.top_k * (1.0 + self.hysteresis_buffer * 2.0)) + 1]]

        for s in current_holdings:
            if s in buffer_pool:
                target_symbols.append(s)
                if len(target_symbols) >= self.top_k:
                    break

        # 不足部分从得分最高者中补充
        for s, _ in ranked:
            if len(target_symbols) >= self.top_k:
                break
            if s not in target_symbols:
                target_symbols.append(s)

        # 资金分配与订单生成
        target_weight = 1.0 / self.top_k
        current_equity = engine.cash + sum(
            pos.shares * history_map[s]["close"].iloc[-1]
            for s, pos in engine.positions.items()
            if s in history_map
        )

        # 1. 卖出订单 (优先提交)
        for s, pos in list(engine.positions.items()):
            if s not in target_symbols:
                if not any(o.symbol == s and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(s, "SELL", pos.shares, 0.0, current_date, "LOWVOL_REBAL_OUT")
                    )

        # 2. 买入 / 调平订单
        for s in target_symbols:
            cur_p = history_map[s]["close"].iloc[-1]
            target_val = current_equity * target_weight
            target_sh = int(target_val // (cur_p * engine.lot_size)) * engine.lot_size
            cur_sh = engine.positions[s].shares if s in engine.positions else 0
            diff = target_sh - cur_sh

            if diff >= engine.lot_size:
                if not any(o.symbol == s and o.action == "BUY" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(s, "BUY", diff, target_weight, current_date, f"LOWVOL_REBAL_BUY(sc={candidate_scores[s]:.2f})")
                    )
            elif diff <= -engine.lot_size * 2:
                if not any(o.symbol == s and o.action == "SELL" for o in engine.pending_orders):
                    engine.pending_orders.append(
                        Order(s, "SELL", abs(diff), target_weight, current_date, "LOWVOL_REDUCE")
                    )
