"""分层测试工具的正确性测试。

这一层不参与正式回测，但因子筛选表全靠它。曾经踩过的坑：调仓日权重直接
ffill，导致上一期选中、这一期落选的股票把旧权重一路带下去，逐日权重和滚到
6 倍，分层年化全变成 -70%。
"""
import numpy as np
import pandas as pd
import pytest

from aq import quicktest


@pytest.fixture
def dates():
    return pd.bdate_range("2020-01-02", periods=40)


def test_daily_weights_sum_to_one(dates):
    """换股之后逐日权重和必须仍然是 1，落选的股票权重必须归零。"""
    sig = pd.DataFrame(
        [{"a": 0.5, "b": 0.5}, {"c": 0.5, "d": 0.5}],
        index=[dates[0], dates[10]])
    w = quicktest.daily_weights(sig, dates)
    assert w.loc[dates[5]].sum() == pytest.approx(1.0)
    assert w.loc[dates[20]].sum() == pytest.approx(1.0)
    assert w.loc[dates[20], "a"] == 0.0          # 已落选，不许把旧权重带下去
    assert w.loc[dates[20], "c"] == pytest.approx(0.5)
    assert np.allclose(w.sum(axis=1).loc[dates[0]:].to_numpy(), 1.0)


def test_portfolio_return_matches_manual(dates):
    """两只股票等权，组合收益 = 两者收益的算术平均（T+1 生效）。"""
    close = pd.DataFrame({"a": np.linspace(10, 20, len(dates)),
                          "b": np.linspace(10, 12, len(dates))}, index=dates)
    sig = pd.DataFrame([{"a": 0.5, "b": 0.5}], index=[dates[0]])
    w = quicktest.daily_weights(sig, dates)
    r = quicktest.portfolio_return(w, close)
    ret = close / close.shift(1) - 1.0
    assert r.iloc[0] == 0.0                       # 信号日当天不持仓
    assert r.iloc[2] == pytest.approx(ret.iloc[2].mean())


def test_layered_returns_are_monotone_for_a_perfect_factor(dates):
    """构造一个"分数越高、下一段涨得越多"的完美因子，分层年化必须单调递增。"""
    n = 60
    codes = [f"c{i}" for i in range(n)]
    drift = np.linspace(-0.002, 0.002, n)          # 第 i 只股票每天固定涨 drift[i]
    close = pd.DataFrame(
        {c: 10 * np.cumprod(1 + np.full(len(dates), drift[i])) for i, c in enumerate(codes)},
        index=dates)
    score = pd.DataFrame({c: np.full(len(dates), drift[i]) for i, c in enumerate(codes)},
                         index=dates)
    lr = quicktest.layered_returns(score, close, dates[::10], q=5)
    means = lr.mean().values
    assert (np.diff(means) > 0).all(), f"分层不单调: {means}"


def test_exclude_bottom_keeps_everyone_above_the_line():
    """剔除最差一档：低于买入线的不买，已持有的跌破卖出线才卖（迟滞）。"""
    from aq import strategy

    dates = pd.bdate_range("2020-01-02", periods=3)
    codes = [f"c{i}" for i in range(200)]
    # 第一期：分数就是序号；第二期把 c0 抬到中游、把 c199 压到最差
    s1 = pd.Series(np.arange(200.0), index=codes)
    s2 = s1.copy()
    s2["c0"], s2["c199"] = 100.5, -1.0
    score = pd.DataFrame([s1, s2], index=[dates[0], dates[1]])
    sig = strategy.exclude_bottom_signals(score, dates[:2], drop_pct=0.2, band=0.05)

    first = sig.loc[dates[0]].dropna()
    assert len(first) == 150                    # 只买排名前 75%（0.25 以上）
    assert "c0" not in first and "c199" in first
    assert first.sum() == pytest.approx(1.0)

    second = sig.loc[dates[1]].dropna()
    assert "c199" not in second                 # 跌到最差，卖出
    assert second.sum() == pytest.approx(1.0)
    # 迟滞：上期持有、这期排名滑到 0.15~0.25 之间的股票不应被卖掉
    held_in_band = [c for c in first.index
                    if 0.15 < score.loc[dates[1]].rank(pct=True)[c] <= 0.25]
    assert all(c in second.index for c in held_in_band)


def test_star_market_volume_unit_is_converted():
    """科创板成交量按「股」返回，必须折算成「手」再算成交额。

    不折算的话科创板的成交额会虚高 100 倍（实测中位数 122 亿 vs 其他板块 1 亿），
    结果是它们永远通过流动性过滤，liqsize20 / amihud20 两个因子整体错位。
    """
    from aq import panel as pn

    assert pn._is_share_unit("sh688981") and pn._is_share_unit("sh689009")
    assert not pn._is_share_unit("sh600519")
    assert not pn._is_share_unit("sz300750")
    assert not pn._is_share_unit("sz002594")
