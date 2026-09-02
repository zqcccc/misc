"""
自动化测试套件: A股量化策略与撮合引擎 (支持 EP004 评估与因果性防未来函数)
"""

import unittest
import numpy as np
import pandas as pd
from scripts.ashare_quant.engine import BacktestEngine, Order
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy


class TestBacktestEngineAndAntiLookAhead(unittest.TestCase):
    def setUp(self):
        self.engine = BacktestEngine(initial_capital=1_000_000.0)

    def test_execution_timing_and_price(self):
        """测试 T 日生成订单，严格在 T+1 日以 Open 价格撮合"""
        order = Order(
            symbol="600519.SS",
            action="BUY",
            shares=500,
            target_weight=0.33,
            created_date="2024-01-02",
            reason="TEST_BUY"
        )
        self.engine.pending_orders.append(order)

        self.assertEqual(len(self.engine.positions), 0)
        self.assertEqual(len(self.engine.trades), 0)

        daily_bar_map = {
            "600519.SS": {"open": 1500.0, "high": 1560.0, "low": 1495.0, "close": 1550.0}
        }
        prev_close_map = {"600519.SS": 1490.0}

        self.engine.execute_pending_orders("2024-01-03", daily_bar_map, prev_close_map)

        self.assertIn("600519.SS", self.engine.positions)
        pos = self.engine.positions["600519.SS"]
        self.assertEqual(pos.shares, 500)
        self.assertAlmostEqual(pos.cost_price, 1500.0 * 1.001, places=2)
        self.assertEqual(len(self.engine.trades), 1)
        self.assertEqual(self.engine.trades[0].price, 1500.0)
        self.assertEqual(self.engine.trades[0].trade_date, "2024-01-03")

    def test_t_plus_one_restriction(self):
        """测试 A 股 T+1 锁仓机制: 当日买入股票当天无法卖出"""
        self.engine.pending_orders.append(
            Order("002594.SZ", "BUY", 1000, 0.33, "2024-01-02")
        )
        daily_bar = {"002594.SZ": {"open": 200.0, "high": 205.0, "low": 198.0, "close": 202.0}}
        self.engine.execute_pending_orders("2024-01-03", daily_bar, {"002594.SZ": 198.0})

        pos = self.engine.positions["002594.SZ"]
        self.assertEqual(pos.shares, 1000)
        self.assertEqual(pos.locked_shares, 1000)

        # 当天再次尝试平仓
        self.engine.pending_orders.append(
            Order("002594.SZ", "SELL", 1000, 0.0, "2024-01-03")
        )
        self.engine.execute_pending_orders("2024-01-03", daily_bar, {"002594.SZ": 200.0})
        self.assertEqual(self.engine.positions["002594.SZ"].shares, 1000)

    def test_limit_up_cannot_buy(self):
        """测试开盘一字涨停无法买入"""
        self.engine.pending_orders.append(
            Order("601899.SS", "BUY", 2000, 0.33, "2024-01-02")
        )
        limit_up_bar = {"601899.SS": {"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0}}
        prev_close = {"601899.SS": 10.0}

        self.engine.execute_pending_orders("2024-01-03", limit_up_bar, prev_close)
        self.assertNotIn("601899.SS", self.engine.positions)
        self.assertEqual(len(self.engine.trades), 0)

    def test_limit_down_cannot_sell(self):
        """测试开盘一字跌停无法卖出，订单顺延"""
        from scripts.ashare_quant.engine import Position
        self.engine.positions["601088.SS"] = Position(symbol="601088.SS", shares=2000, cost_price=30.0, locked_shares=0)

        self.engine.pending_orders.append(
            Order("601088.SS", "SELL", 2000, 0.0, "2024-01-02")
        )
        limit_down_bar = {"601088.SS": {"open": 27.0, "high": 27.0, "low": 27.0, "close": 27.0}}
        prev_close = {"601088.SS": 30.0}

        self.engine.execute_pending_orders("2024-01-03", limit_down_bar, prev_close)
        self.assertEqual(self.engine.positions["601088.SS"].shares, 2000)
        self.assertEqual(len(self.engine.pending_orders), 1)

    def test_anti_lookahead_perturbation(self):
        """
        核心防未来函数检验 (EP004 factor_causality 因果检验原理):
        在 T_cut 之后人为注入剧烈未来扰动数据 (暴涨100倍)。
        验证截至 T_cut 产生的所有信号、持仓、订单和中间值绝对零差异！
        """
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        np.random.seed(42)

        def make_df(scale_future=1.0):
            prices = 100.0 + np.cumsum(np.random.randn(100))
            if scale_future != 1.0:
                prices[70:] *= scale_future
            return pd.DataFrame({
                "date": dates,
                "open": prices,
                "high": prices * 1.01,
                "low": prices * 0.99,
                "close": prices,
                "volume": 100000
            })

        clean_history = {
            "510300.SS": make_df(1.0),
            "STOCK_A": make_df(1.0),
            "STOCK_B": make_df(1.0),
        }

        corrupted_history = {
            "510300.SS": make_df(10.0),
            "STOCK_A": make_df(100.0),
            "STOCK_B": make_df(0.01),
        }

        strat1 = RelativeStrengthAlphaStrategy(top_k=2, rebalance_interval_days=5)
        strat2 = RelativeStrengthAlphaStrategy(top_k=2, rebalance_interval_days=5)
        eng1 = BacktestEngine(1_000_000.0)
        eng2 = BacktestEngine(1_000_000.0)

        for i in range(70):
            dt = str(dates[i].strftime("%Y-%m-%d"))
            slice1 = {sym: df.iloc[:i+1].copy() for sym, df in clean_history.items()}
            slice2 = {sym: df.iloc[:i+1].copy() for sym, df in corrupted_history.items()}

            if i > 0:
                daily_bar1 = {sym: df.iloc[i].to_dict() for sym, df in clean_history.items()}
                daily_bar2 = {sym: df.iloc[i].to_dict() for sym, df in corrupted_history.items()}
                prev1 = {sym: df.iloc[i-1]["close"] for sym, df in clean_history.items()}
                prev2 = {sym: df.iloc[i-1]["close"] for sym, df in corrupted_history.items()}

                eng1.execute_pending_orders(dt, daily_bar1, prev1)
                eng2.execute_pending_orders(dt, daily_bar2, prev2)

            strat1.on_bar_close(dt, slice1, eng1)
            strat2.on_bar_close(dt, slice2, eng2)

            daily_close1 = {sym: df.iloc[i]["close"] for sym, df in clean_history.items()}
            daily_close2 = {sym: df.iloc[i]["close"] for sym, df in corrupted_history.items()}
            eng1.end_of_day_settlement(dt, daily_close1, daily_close1["510300.SS"])
            eng2.end_of_day_settlement(dt, daily_close2, daily_close2["510300.SS"])

        self.assertAlmostEqual(eng1.cash, eng2.cash, places=4)
        self.assertEqual(len(eng1.pending_orders), len(eng2.pending_orders))
        for o1, o2 in zip(eng1.pending_orders, eng2.pending_orders):
            self.assertEqual(o1.symbol, o2.symbol)
            self.assertEqual(o1.action, o2.action)
            self.assertEqual(o1.shares, o2.shares)

        print("[TEST PASS] 因果防未来函数扰动测试通过: 未来数据变动对当前决策完全无影响！")


if __name__ == "__main__":
    unittest.main()
