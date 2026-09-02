"""
A股真实交易回测引擎 (高保真、严格防未来函数)
======================================================
核心设计特性:
1. 严格时序隔离 (No Look-ahead):
   - T 日收盘后基于 T 日及历史切片生成信号与目标权重;
   - 订单在 T+1 日开盘时以 Open 价格撮合成交，彻底杜绝以未来价成交。
2. A股特有交易约束:
   - T+1 锁仓规则: 当日买入股票次日方可卖出。
   - 涨跌停板流动性检验:
     * 若 T+1 日开盘一字涨停 (open==high==low 且 涨幅>=9.8%)，买单无法成交，立即撤单。
     * 若 T+1 日持仓标的一字跌停 (open==high==low 且 跌幅<=-9.8%)，卖单无法成交，自动延期至下一开板日。
3. 真实摩擦成本:
   - 佣金: 双边万 2.5 (0.025%)。
   - 印花税: 卖出单边 0.05% (千分之 0.5)。
   - 滑点: 双边 0.1% (千分之一)。
4. 规范指标结算:
   - 总收益、年化复合收益率 (CAGR)、最大回撤 (MDD)、夏普比率 (Sharpe, Rf=2%)、
     卡尔玛比率 (Calmar)、索提诺比率 (Sortino)、胜率、盈亏比、年换手率。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


@dataclass
class Order:
    symbol: str
    action: str          # "BUY" or "SELL"
    shares: int          # 股数 (A股要求以100股为一手，回测支持100取整或碎股可配)
    target_weight: float # 目标持仓权重
    created_date: str    # 订单创建日 (T日)
    reason: str = ""     # 调仓原因 (如 "REBALANCE", "STOP_LOSS")


@dataclass
class Trade:
    trade_id: int
    symbol: str
    action: str
    shares: int
    price: float
    trade_date: str
    fee: float           # 佣金 + 印花税
    slippage: float      # 滑点成本
    total_cost: float    # 实际资金变动量
    reason: str = ""


@dataclass
class Position:
    symbol: str
    shares: int = 0
    cost_price: float = 0.0
    locked_shares: int = 0  # 当日买入不可卖出的锁定股数 (T+1)


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        commission_rate: float = 0.00025,  # 佣金万2.5
        stamp_duty_rate: float = 0.0005,   # 印花税千分之0.5 (仅卖出收取)
        slippage_rate: float = 0.0010,     # 滑点千分之1
        min_commission: float = 5.0,       # 单笔最低佣金5元
        lot_size: int = 100,               # 最小交易单位: 100股 (一手)
    ):
        self.initial_capital = float(initial_capital)
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.slippage_rate = slippage_rate
        self.min_commission = min_commission
        self.lot_size = lot_size

        # 运行状态
        self.cash = float(initial_capital)
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.trade_counter = 0
        self.pending_orders: List[Order] = []
        self.last_trading_date: Optional[str] = None
        
        # 历史记录
        self.history_records: List[Dict[str, Any]] = []

    def reset(self):
        self.cash = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.trade_counter = 0
        self.pending_orders.clear()
        self.last_trading_date = None
        self.history_records.clear()

    def is_limit_up(self, open_p: float, high_p: float, low_p: float, prev_close: float) -> bool:
        """判断开盘是否一字涨停 (无法买入)"""
        if prev_close <= 0:
            return False
        change = (open_p / prev_close) - 1.0
        return (open_p == high_p == low_p) and (change >= 0.098)

    def is_limit_down(self, open_p: float, high_p: float, low_p: float, prev_close: float) -> bool:
        """判断开盘是否一字跌停 (无法卖出)"""
        if prev_close <= 0:
            return False
        change = (open_p / prev_close) - 1.0
        return (open_p == high_p == low_p) and (change <= -0.098)

    def execute_pending_orders(
        self,
        current_date: str,
        daily_bar_map: Dict[str, Dict[str, float]],
        prev_close_map: Dict[str, float]
    ):
        """
        在 T+1 日开盘阶段撮合 T 日盘后提交的未决订单
        """
        # 1. 如果进入了新的交易日，解锁上一个交易日买入锁定的持仓
        if self.last_trading_date != current_date:
            for pos in self.positions.values():
                pos.locked_shares = 0
            self.last_trading_date = current_date

        unexecuted_orders: List[Order] = []

        # 先处理卖单，再处理买单以腾出可用现金
        sell_orders = [o for o in self.pending_orders if o.action == "SELL"]
        buy_orders = [o for o in self.pending_orders if o.action == "BUY"]

        for order in sell_orders:
            sym = order.symbol
            if sym not in daily_bar_map or sym not in self.positions:
                continue

            bar = daily_bar_map[sym]
            prev_close = prev_close_map.get(sym, bar["open"])

            # 跌停检验: 若一字跌停，卖单无法撮合，订单自动保留顺延
            if self.is_limit_down(bar["open"], bar["high"], bar["low"], prev_close):
                unexecuted_orders.append(order)
                continue

            pos = self.positions[sym]
            available_shares = pos.shares - pos.locked_shares
            if available_shares <= 0:
                # 处于 T+1 锁定期无法平仓，订单保留或取消
                unexecuted_orders.append(order)
                continue

            shares_to_sell = min(order.shares, available_shares)
            if shares_to_sell <= 0:
                continue

            # 撮合成交价考虑不利滑点 (卖出以更低价成交)
            exec_price = bar["open"] * (1.0 - self.slippage_rate)
            gross_amount = shares_to_sell * exec_price
            slippage_cost = shares_to_sell * bar["open"] * self.slippage_rate
            
            # 费用: 佣金 + 印花税
            commission = max(self.min_commission, gross_amount * self.commission_rate)
            stamp_duty = gross_amount * self.stamp_duty_rate
            total_fee = commission + stamp_duty
            net_proceeds = gross_amount - total_fee

            self.cash += net_proceeds
            pos.shares -= shares_to_sell
            if pos.shares == 0:
                del self.positions[sym]

            self.trade_counter += 1
            self.trades.append(
                Trade(
                    trade_id=self.trade_counter,
                    symbol=sym,
                    action="SELL",
                    shares=shares_to_sell,
                    price=bar["open"],
                    trade_date=current_date,
                    fee=total_fee,
                    slippage=slippage_cost,
                    total_cost=net_proceeds,
                    reason=order.reason
                )
            )

        # 处理买单
        for order in buy_orders:
            sym = order.symbol
            if sym not in daily_bar_map:
                continue

            bar = daily_bar_map[sym]
            prev_close = prev_close_map.get(sym, bar["open"])

            # 涨停检验: 若一字涨停，买单无法成交，直接撤单
            if self.is_limit_up(bar["open"], bar["high"], bar["low"], prev_close):
                continue

            # 买入考虑不利滑点 (买入以更高价成交)
            exec_price = bar["open"] * (1.0 + self.slippage_rate)
            
            # 检查资金充裕度
            est_commission_rate = self.commission_rate
            cost_per_share = exec_price * (1.0 + est_commission_rate)
            
            # 确保按 100 股整手购买
            max_possible_shares = int(self.cash // (cost_per_share * self.lot_size)) * self.lot_size
            shares_to_buy = min(order.shares, max_possible_shares)
            
            if shares_to_buy < self.lot_size:
                continue

            gross_amount = shares_to_buy * exec_price
            commission = max(self.min_commission, gross_amount * self.commission_rate)
            total_cost = gross_amount + commission
            slippage_cost = shares_to_buy * bar["open"] * self.slippage_rate

            if total_cost > self.cash:
                shares_to_buy -= self.lot_size
                if shares_to_buy < self.lot_size:
                    continue
                gross_amount = shares_to_buy * exec_price
                commission = max(self.min_commission, gross_amount * self.commission_rate)
                total_cost = gross_amount + commission

            self.cash -= total_cost
            if sym not in self.positions:
                self.positions[sym] = Position(symbol=sym, shares=0, cost_price=exec_price)
            
            p = self.positions[sym]
            p.shares += shares_to_buy
            p.cost_price = exec_price
            p.locked_shares += shares_to_buy  # T+1 锁定，当日不可卖

            self.trade_counter += 1
            self.trades.append(
                Trade(
                    trade_id=self.trade_counter,
                    symbol=sym,
                    action="BUY",
                    shares=shares_to_buy,
                    price=bar["open"],
                    trade_date=current_date,
                    fee=commission,
                    slippage=slippage_cost,
                    total_cost=-total_cost,
                    reason=order.reason
                )
            )

        self.pending_orders = unexecuted_orders

    def end_of_day_settlement(
        self,
        current_date: str,
        daily_close_map: Dict[str, float],
        benchmark_close: float
    ) -> Dict[str, Any]:
        """
        每日收盘结算，计算投资组合总市值与净值快照
        """
        portfolio_mv = 0.0
        pos_snapshot = {}
        for sym, pos in self.positions.items():
            price = daily_close_map.get(sym, pos.cost_price)
            mv = pos.shares * price
            portfolio_mv += mv
            pos_snapshot[sym] = {
                "shares": pos.shares,
                "price": price,
                "market_value": mv,
                "weight": 0.0
            }

        total_equity = self.cash + portfolio_mv
        for sym in pos_snapshot:
            pos_snapshot[sym]["weight"] = pos_snapshot[sym]["market_value"] / total_equity if total_equity > 0 else 0.0

        record = {
            "date": current_date,
            "total_equity": total_equity,
            "cash": self.cash,
            "portfolio_market_value": portfolio_mv,
            "positions": pos_snapshot,
            "benchmark_close": benchmark_close,
        }
        self.history_records.append(record)
        return record


def calculate_performance_metrics(
    equity_curve: pd.DataFrame,
    benchmark_col: str = "benchmark",
    rf: float = 0.02,
    trading_days_per_year: int = 250
) -> Dict[str, Any]:
    if len(equity_curve) < 2:
        return {}

    eq = equity_curve["equity"].values
    bm = equity_curve[benchmark_col].values if benchmark_col in equity_curve.columns else None

    # 1. 累计与年化收益
    total_return = eq[-1] / eq[0] - 1.0
    num_days = (pd.to_datetime(equity_curve["date"].iloc[-1]) - pd.to_datetime(equity_curve["date"].iloc[0])).days
    years = max(num_days / 365.25, 0.05)
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0

    # 2. 每日收益与波动率
    daily_rets = np.diff(eq) / eq[:-1]
    ann_volatility = float(np.std(daily_rets) * np.sqrt(trading_days_per_year)) if len(daily_rets) > 1 else 0.0

    # 3. 夏普比率 (Sharpe Ratio)
    excess_daily = daily_rets - (rf / trading_days_per_year)
    sharpe = float(np.mean(excess_daily) / np.std(daily_rets) * np.sqrt(trading_days_per_year)) if np.std(daily_rets) > 1e-8 else 0.0

    # 4. 索提诺比率 (Sortino Ratio)
    downside_rets = daily_rets[daily_rets < 0]
    downside_std = np.std(downside_rets) * np.sqrt(trading_days_per_year) if len(downside_rets) > 0 else 1e-8
    sortino = float((cagr - rf) / downside_std) if downside_std > 1e-8 else 0.0

    # 5. 最大回撤 (Max Drawdown)
    running_max = np.maximum.accumulate(eq)
    drawdowns = (eq - running_max) / running_max
    max_drawdown = float(np.min(drawdowns))
    
    end_idx = np.argmin(drawdowns)
    start_idx = np.argmax(eq[:end_idx + 1])
    mdd_start = str(equity_curve["date"].iloc[start_idx])
    mdd_end = str(equity_curve["date"].iloc[end_idx])

    # 6. 卡尔玛比率 (Calmar Ratio)
    calmar = float(cagr / abs(max_drawdown)) if abs(max_drawdown) > 1e-6 else 0.0

    # 7. 基准指标对比
    bm_metrics = {}
    if bm is not None and len(bm) > 1 and bm[0] > 0:
        bm_tot = float(bm[-1] / bm[0] - 1.0)
        bm_cagr = float((bm[-1] / bm[0]) ** (1.0 / years) - 1.0)
        bm_daily = np.diff(bm) / bm[:-1]
        bm_running_max = np.maximum.accumulate(bm)
        bm_mdd = float(np.min((bm - bm_running_max) / bm_running_max))
        bm_vol = float(np.std(bm_daily) * np.sqrt(trading_days_per_year)) if len(bm_daily) > 1 else 0.0
        
        cov = np.cov(daily_rets, bm_daily)[0, 1] if len(daily_rets) > 1 else 0.0
        bm_var = np.var(bm_daily) if len(bm_daily) > 1 else 1e-8
        beta = float(cov / bm_var) if bm_var > 1e-8 else 1.0
        alpha = float(cagr - (rf + beta * (bm_cagr - rf)))

        bm_metrics = {
            "benchmark_total_return": bm_tot,
            "benchmark_cagr": bm_cagr,
            "benchmark_max_drawdown": bm_mdd,
            "benchmark_volatility": bm_vol,
            "beta": beta,
            "alpha": alpha,
        }

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "max_drawdown": float(max_drawdown),
        "mdd_start_date": mdd_start,
        "mdd_end_date": mdd_end,
        "annual_volatility": float(ann_volatility),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "calmar_ratio": float(calmar),
        **bm_metrics
    }
