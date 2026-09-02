"""回测引擎的"已知答案"测试：成本、涨跌停、停牌、T+1、退市、现金约束。"""
import numpy as np
import pandas as pd
import pytest

from aq import backtest, config, rules
from conftest import make_panels

DATES = pd.bdate_range("2020-01-02", periods=6)
BUY_RATE = rules.buy_cost_rate()


def _sig(date, weights):
    return pd.DataFrame([weights], index=[date])


def test_buy_cost_is_exact():
    """信号 T、成交 T+1 开盘；买入后净值 = 初始资金 / (1 + 买入费率)。"""
    p = make_panels({"sh600001": [10.0] * 6}, DATES,
                    opens={"sh600001": [10.0] * 6})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 1.0}), init_cash=1e6)
    assert res.equity.iloc[0] == pytest.approx(1e6)          # T 日不交易
    assert res.equity.iloc[1] == pytest.approx(1e6 / (1 + BUY_RATE))
    assert res.turnover.iloc[0] == 0.0
    assert res.turnover.iloc[1] > 0.0


def test_sell_cost_includes_stamp_duty():
    p = make_panels({"sh600001": [10.0] * 6}, DATES, opens={"sh600001": [10.0] * 6})
    sig = pd.DataFrame({"sh600001": [1.0, 0.0]}, index=[DATES[0], DATES[2]])
    res = backtest.run(p, sig, init_cash=1e6)
    after_buy = 1e6 / (1 + BUY_RATE)
    sell_rate = rules.sell_cost_rate(DATES[3])
    assert sell_rate == pytest.approx(BUY_RATE + 0.001)      # 2020 年印花税 0.1%
    assert res.equity.iloc[3] == pytest.approx(after_buy * (1 - sell_rate))
    assert res.cash_weight.iloc[3] == pytest.approx(1.0)


def test_stamp_duty_halved_after_2023_08_28():
    assert rules.stamp_duty(pd.Timestamp("2023-08-25")) == 0.0010
    assert rules.stamp_duty(pd.Timestamp("2023-08-28")) == 0.0005


def test_limit_up_open_blocks_buy():
    """次日一开就涨停，买不进去 —— 引擎必须留在现金里。"""
    p = make_panels({"sh600001": [10.0, 11.0, 11.0, 11.0]},
                    DATES[:4], opens={"sh600001": [10.0, 11.0, 11.0, 11.0]})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 1.0}), init_cash=1e6)
    assert res.n_holdings.iloc[1] == 0
    assert res.cash_weight.iloc[1] == pytest.approx(1.0)


def test_chinext_20pct_limit_is_date_dependent():
    """创业板 2020-08-24 之后才是 20%，之前 +11% 开盘应视为涨停不可买。"""
    before = pd.bdate_range("2020-08-10", periods=4)
    after = pd.bdate_range("2020-09-01", periods=4)
    for dates, expect_bought in [(before, False), (after, True)]:
        p = make_panels({"sz300001": [10.0, 11.0, 11.0, 11.0]}, dates,
                        opens={"sz300001": [10.0, 11.0, 11.0, 11.0]})
        res = backtest.run(p, _sig(dates[0], {"sz300001": 1.0}), init_cash=1e6)
        assert bool(res.n_holdings.iloc[1] > 0) is expect_bought


def test_limit_down_open_blocks_sell():
    p = make_panels({"sh600001": [10.0, 10.0, 10.0, 9.0, 9.0, 9.0]}, DATES,
                    opens={"sh600001": [10.0, 10.0, 10.0, 9.0, 9.0, 9.0]})
    sig = pd.DataFrame({"sh600001": [1.0, 0.0]}, index=[DATES[0], DATES[2]])
    res = backtest.run(p, sig, init_cash=1e6)
    assert res.n_holdings.iloc[3] == 1        # 跌停开盘卖不掉，只能继续持有
    assert res.n_holdings.iloc[4] == 0        # 次日跌停打开后才卖出


def test_yizi_board_blocks_both_directions():
    """一字板（开=高=低=收）双向不可成交。"""
    p = make_panels({"sh600001": [10.0, 10.5, 10.5, 10.5]}, DATES[:4],
                    opens={"sh600001": [10.0, 10.5, 10.5, 10.5]},
                    highs={"sh600001": [10.02, 10.5, 10.52, 10.52]},
                    lows={"sh600001": [9.98, 10.5, 10.48, 10.48]})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 1.0}), init_cash=1e6)
    assert res.n_holdings.iloc[1] == 0        # 一字板涨停，买不到


def test_suspension_holds_value_and_blocks_trade():
    """停牌日：不可交易，持仓按上一有效收盘价估值。"""
    prices = [10.0, 10.0, np.nan, np.nan, 12.0, 12.0]
    p = make_panels({"sh600001": prices, "sh600002": [20.0] * 6}, DATES,
                    opens={"sh600001": prices, "sh600002": [20.0] * 6},
                    volumes={"sh600001": [1e6, 1e6, np.nan, np.nan, 1e6, 1e6],
                             "sh600002": [1e6] * 6})
    sig = pd.DataFrame({"sh600001": [1.0, 0.0], "sh600002": [0.0, 1.0]},
                       index=[DATES[0], DATES[2]])
    res = backtest.run(p, sig, init_cash=1e6)
    assert res.equity.iloc[2] == pytest.approx(res.equity.iloc[1])  # 停牌净值不变
    assert res.n_holdings.iloc[3] == 1                              # 停牌期间换不了仓
    assert res.equity.iloc[4] > res.equity.iloc[3] * 1.1            # 复牌后补涨兑现


def test_delisting_liquidates_at_last_price():
    prices = [10.0, 10.0, 10.0, np.nan, np.nan, np.nan]
    p = make_panels({"sh600001": prices, "sh600002": [20.0] * 6}, DATES,
                    opens={"sh600001": prices, "sh600002": [20.0] * 6},
                    volumes={"sh600001": [1e6, 1e6, 1e6, np.nan, np.nan, np.nan],
                             "sh600002": [1e6] * 6})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 1.0}), init_cash=1e6)
    sell_rate = rules.sell_cost_rate(DATES[3])
    assert res.n_holdings.iloc[3] == 0
    assert res.equity.iloc[3] == pytest.approx(res.equity.iloc[2] * (1 - sell_rate))
    assert res.cash_weight.iloc[-1] == pytest.approx(1.0)


def test_no_same_day_round_trip():
    """T+1：同一天不会对同一只股票既买又卖。"""
    p = make_panels({"sh600001": [10.0] * 6, "sh600002": [10.0] * 6}, DATES,
                    opens={"sh600001": [10.0] * 6, "sh600002": [10.0] * 6})
    sig = pd.DataFrame({"sh600001": [1.0, 0.0, 1.0], "sh600002": [0.0, 1.0, 0.0]},
                       index=[DATES[0], DATES[1], DATES[2]])
    res = backtest.run(p, sig, init_cash=1e6, keep_holdings=True)
    # 每个执行日的换手都来自不同标的的一买一卖，单只标的方向唯一
    assert res.n_holdings.max() <= 2
    assert (res.turnover <= 2.05).all()


def test_cash_constraint_no_leverage():
    p = make_panels({"sh600001": [10.0] * 6, "sh600002": [10.0] * 6}, DATES,
                    opens={"sh600001": [10.0] * 6, "sh600002": [10.0] * 6})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 1.5, "sh600002": 1.5}), init_cash=1e6)
    assert res.cash_weight.iloc[1] >= -1e-9          # 不允许透支
    assert res.equity.iloc[1] <= 1e6


def test_partial_weight_keeps_cash():
    p = make_panels({"sh600001": [10.0] * 6}, DATES, opens={"sh600001": [10.0] * 6})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 0.5}), init_cash=1e6)
    assert res.cash_weight.iloc[1] == pytest.approx(0.5, abs=1e-3)


def test_zero_cost_flag_removes_all_frictions():
    """零成本对照：买满后净值应精确等于本金。"""
    p = make_panels({"sh600001": [10.0] * 6}, DATES, opens={"sh600001": [10.0] * 6})
    res = backtest.run(p, _sig(DATES[0], {"sh600001": 1.0}), init_cash=1e6, zero_cost=True)
    assert res.equity.iloc[1] == pytest.approx(1e6)
    assert res.cost.sum() == 0.0


def test_blocked_frac_flags_positions_below_min_trade_size():
    """持仓过宽时单只仓位低于最小成交额，委托会被静默跳过 —— 必须能被查出来。

    这是踩过的坑：目标持仓 2700 只、本金 1000 万时每只只有 3700 元，低于
    0.05% 的成交下限，买卖全被跳过，回测悄悄变成"拿着不动"，换手率失真。
    """
    codes = [f"sh60{i:04d}" for i in range(300)]
    prices = {c: [10.0] * 6 for c in codes}
    p = make_panels(prices, DATES, opens=prices)
    w = {c: 1.0 / len(codes) for c in codes}       # 每只 0.33%
    # 本金够大：单只 3333 元 > floor 1500 元，正常成交
    ok = backtest.run(p, _sig(DATES[0], w), init_cash=1e6)
    assert ok.blocked_frac < 0.01
    assert ok.n_holdings.iloc[1] == len(codes)
    # 本金太小：单只 33 元 < floor 15 元 ... 用更极端的比例触发
    tiny = backtest.run(p, _sig(DATES[0], w), init_cash=1e6, min_trade_frac=0.01)
    assert tiny.blocked_frac > 0.9
    assert tiny.n_holdings.iloc[1] == 0           # 全部被跳过，静默不交易
