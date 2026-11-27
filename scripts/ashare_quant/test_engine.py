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
        self.assertAlmostEqual(self.engine.trades[0].price, 1500.0 * 1.001, places=6)  # 实际成交价含滑点
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


class TestFifoRealizedPnl(unittest.TestCase):
    """确定性场景: 多次加仓 -> 部分减仓 -> 全部卖出 -> 再次买入 -> 卖出。
    校验 FIFO 批次配对不重复配对, Trade 记录含滑点成交价, 已实现净盈亏 (含费用) 精确可重建。"""

    def _exec(self):
        eng = BacktestEngine(initial_capital=1_000_000.0)
        sym = "600519.SS"
        steps = [
            # (日期, 动作, 股数, 开盘价)
            ("2024-01-02", "BUY", 1000, 100.0),
            ("2024-01-03", "BUY", 1000, 110.0),
            ("2024-01-04", "SELL", 500, 120.0),
            ("2024-01-05", "SELL", 1500, 130.0),
            ("2024-01-08", "BUY", 1000, 90.0),
            ("2024-01-09", "SELL", 1000, 95.0),
        ]
        for d, action, shares, open_p in steps:
            eng.pending_orders.append(Order(sym, action, shares, 0.0, d))
            bar = {sym: {"open": open_p, "high": open_p * 1.01, "low": open_p * 0.99, "close": open_p}}
            eng.execute_pending_orders(d, bar, {sym: open_p})
        return eng, sym

    def test_fifo_matching_and_net_pnl(self):
        eng, sym = self._exec()
        sells = [t for t in eng.trades if t.action == "SELL"]
        buys = [t for t in eng.trades if t.action == "BUY"]
        self.assertEqual(len(sells), 3)
        self.assertEqual(len(buys), 3)

        # 买入批次含费成本: (成交金额 + 佣金) / 股数
        lot1_ps = (1000 * 100.0 * 1.001 + max(5.0, 100100.0 * 0.00025)) / 1000
        lot2_ps = (1000 * 110.0 * 1.001 + max(5.0, 110110.0 * 0.00025)) / 1000
        lot3_ps = (1000 * 90.0 * 1.001 + max(5.0, 90090.0 * 0.00025)) / 1000

        # 卖1 (500股): 只消耗批次1前半, 净额 = 卖出净进款 - 匹配成本
        sell1_net = 500 * 120.0 * 0.999 - (max(5.0, 59940.0 * 0.00025) + 59940.0 * 0.0005)
        self.assertAlmostEqual(sells[0].realized_pnl, sell1_net - 500 * lot1_ps, places=4)
        self.assertAlmostEqual(sells[0].realized_basis, 500 * lot1_ps, places=4)

        # 卖2 (1500股): 批次1剩余500股 + 批次2全部1000股, 不重复配对批次1已卖部分
        sell2_net = 1500 * 130.0 * 0.999 - (max(5.0, 194805.0 * 0.00025) + 194805.0 * 0.0005)
        self.assertAlmostEqual(
            sells[1].realized_pnl, sell2_net - (500 * lot1_ps + 1000 * lot2_ps), places=4
        )
        self.assertAlmostEqual(sells[1].realized_basis, 500 * lot1_ps + 1000 * lot2_ps, places=4)

        # 卖3 (1000股): 再买入的批次3
        sell3_net = 1000 * 95.0 * 0.999 - (max(5.0, 94905.0 * 0.00025) + 94905.0 * 0.0005)
        self.assertAlmostEqual(sells[2].realized_pnl, sell3_net - 1000 * lot3_ps, places=4)
        self.assertAlmostEqual(sells[2].realized_basis, 1000 * lot3_ps, places=4)

        # 盈亏守恒: 全部平仓后, 已实现净盈亏之和 == 账户净变动
        total_realized = sum(t.realized_pnl for t in sells)
        self.assertAlmostEqual(eng.cash - 1_000_000.0, total_realized, places=4)
        self.assertNotIn(sym, eng.positions)
        self.assertNotIn(sym, eng.open_lots)

        # Trade 记录真实含滑点成交价
        self.assertAlmostEqual(sells[0].price, 120.0 * 0.999, places=6)
        self.assertAlmostEqual(buys[0].price, 100.0 * 1.001, places=6)

    def test_partial_sell_consumes_earliest_lot_first(self):
        """部分减仓只消耗最早批次的剩余股数, 全部平仓后批次清空。"""
        eng = BacktestEngine(initial_capital=1_000_000.0)
        sym = "600519.SS"

        def bar(open_p):
            return {sym: {"open": open_p, "high": open_p * 1.01, "low": open_p * 0.99, "close": open_p}}

        eng.pending_orders.append(Order(sym, "BUY", 1000, 0.0, "2024-01-02"))
        eng.execute_pending_orders("2024-01-02", bar(100.0), {sym: 100.0})
        eng.pending_orders.append(Order(sym, "BUY", 1000, 0.0, "2024-01-03"))
        eng.execute_pending_orders("2024-01-03", bar(110.0), {sym: 110.0})

        lot1_ps = eng.open_lots[sym][0][1]
        lot2_ps = eng.open_lots[sym][1][1]
        self.assertNotAlmostEqual(lot1_ps, lot2_ps, places=6)  # 两个批次成本不同

        eng.pending_orders.append(Order(sym, "SELL", 500, 0.0, "2024-01-04"))
        eng.execute_pending_orders("2024-01-04", bar(120.0), {sym: 120.0})

        lots = eng.open_lots[sym]
        self.assertEqual(len(lots), 2)
        self.assertEqual(lots[0][0], 500)   # 最早批次只剩 500 股
        self.assertEqual(lots[1][0], 1000)  # 第二批次未被动过
        sell = eng.trades[-1]
        self.assertAlmostEqual(sell.realized_basis, 500 * lot1_ps, places=6)

        # 全部平仓后批次清空
        eng.pending_orders.append(Order(sym, "SELL", 1500, 0.0, "2024-01-05"))
        eng.execute_pending_orders("2024-01-05", bar(130.0), {sym: 130.0})
        self.assertNotIn(sym, eng.open_lots)
        self.assertNotIn(sym, eng.positions)

    def test_realized_series_rebuildable_from_trades(self):
        """交付物口径: 盈亏序列可由 trades 逐笔重建 (net_proceeds - matched_basis)。"""
        eng, sym = self._exec()
        rebuilt = []
        for t in eng.trades:
            if t.action == "SELL" and t.realized_basis > 0:
                rebuilt.append(t.realized_pnl / t.realized_basis)
        self.assertEqual(len(rebuilt), 3)
        for r, t in zip(rebuilt, [t for t in eng.trades if t.action == "SELL"]):
            self.assertAlmostEqual(r, t.realized_pnl / t.realized_basis, places=12)


if __name__ == "__main__":
    unittest.main()
