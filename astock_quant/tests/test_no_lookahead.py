"""未来函数的机器化验证。

三种验证手段，逐层加强：
  1. 截断不变性：把数据在 D 日截断后重算，D 日及之前的结果必须逐点相同。
     真实交易在 D 日只有 <= D 的数据，如果截断后结果变了，说明原来用到了未来。
  2. 未来扰动不变性：把 D 日之后的数据换成完全不同的随机数，D 日及之前的结果
     必须不变。这能抓住"用未来数据做全样本标准化/填充"这类隐蔽泄漏。
  3. 时序对齐：前瞻收益、IC、成交价的下标关系用构造性例子精确校验。
"""
import numpy as np
import pandas as pd
import pytest

from aq import backtest, factors, metrics, strategy, universe


def _same_where_both_defined(a: pd.DataFrame, b: pd.DataFrame, label: str):
    a, b = a.align(b, join="inner")
    assert a.shape == b.shape and a.shape[0] > 0, f"{label}: 对齐后无数据"
    both_nan = a.isna() & b.isna()
    close = np.isclose(a.values, b.values, rtol=1e-10, atol=1e-12, equal_nan=False)
    bad = ~(close | both_nan.values)
    assert not bad.any(), (
        f"{label}: {bad.sum()} 个取值在截断/扰动后发生变化 —— 存在未来函数")


def _truncate(panels, cut):
    return {k: v.loc[:cut].copy() for k, v in panels.items()}


def _perturb_future(panels, cut, rng):
    out = {}
    for k, v in panels.items():
        v = v.copy()
        future = v.index > cut
        noise = rng.uniform(0.2, 5.0, size=(future.sum(), v.shape[1]))
        v.loc[future] = v.loc[future].values * noise
        out[k] = v
    return out


# ------------------------------------------------------------------ 1. 因子
def test_factors_truncation_invariant(random_panels):
    cut = random_panels["close"].index[250]
    full = factors.build_all(random_panels)
    trunc = factors.build_all(_truncate(random_panels, cut))
    for name in full:
        _same_where_both_defined(full[name].loc[:cut], trunc[name].loc[:cut], f"因子 {name}")


def test_factors_future_perturbation_invariant(random_panels, rng):
    cut = random_panels["close"].index[250]
    full = factors.build_all(random_panels)
    pert = factors.build_all(_perturb_future(random_panels, cut, rng))
    for name in full:
        _same_where_both_defined(full[name].loc[:cut], pert[name].loc[:cut], f"因子 {name}(扰动)")


def test_no_negative_shift_in_source():
    """源码级静态检查：因子/股票池/策略里不允许出现负向 shift 与 bfill。

    用 AST 而不是字符串匹配，避免注释/文档字符串里的示例误伤，也避免
    `shift( -1 )` 这种写法漏网。
    """
    import ast
    import inspect

    for mod in (factors, universe, strategy):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr = node.func.attr
            assert attr not in ("bfill", "backfill"), f"{mod.__name__} 用了 {attr}()"
            if attr == "shift":
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    neg = (isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub)) or \
                          (isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float))
                           and arg.value < 0)
                    assert not neg, f"{mod.__name__} 里出现了负向 shift（未来函数）"


# ------------------------------------------------------------------ 2. 股票池
def test_universe_truncation_invariant(random_panels):
    cut = random_panels["close"].index[250]
    full = universe.investable(random_panels)
    trunc = universe.investable(_truncate(random_panels, cut))
    _same_where_both_defined(full.loc[:cut].astype(float), trunc.loc[:cut].astype(float), "股票池")


# ------------------------------------------------------------------ 3. 回测
def _pipeline(panels, top_n=10, freq=5, cut=None):
    mask = universe.investable(panels, min_listed=60, min_amount=0.0,
                               liquidity_top_pct=1.0, exclude_st=False)
    fp = factors.build_all(panels)
    score = strategy.composite(fp, {"rev20": 1.0, "vol60": 0.5, "mom120_20": 0.5}, mask)
    dates = panels["close"].index
    rb = strategy.rebalance_dates(dates, freq, start=dates[130])
    sig = strategy.top_n_signals(score, rb, top_n)
    return backtest.run(panels, sig, start=dates[130])


def test_backtest_truncation_invariant(random_panels):
    cut = random_panels["close"].index[300]
    full = _pipeline(random_panels)
    trunc = _pipeline(_truncate(random_panels, cut))
    eq_full = full.equity.loc[:cut]
    eq_trunc = trunc.equity.loc[:cut]
    assert len(eq_trunc) > 100
    pd.testing.assert_series_equal(eq_full.loc[eq_trunc.index], eq_trunc,
                                   check_exact=False, rtol=1e-12)


def test_backtest_future_perturbation_invariant(random_panels, rng):
    cut = random_panels["close"].index[300]
    full = _pipeline(random_panels)
    pert = _pipeline(_perturb_future(random_panels, cut, rng))
    a, b = full.equity.loc[:cut], pert.equity.loc[:cut]
    pd.testing.assert_series_equal(a, b.loc[a.index], check_exact=False, rtol=1e-12)


def test_signal_executes_next_day_not_same_day(random_panels):
    """信号日当天净值不受信号影响：成交发生在 T+1。"""
    panels = random_panels
    dates = panels["close"].index
    sig_date = dates[200]
    code = panels["close"].columns[0]
    sig = pd.DataFrame({code: [1.0]}, index=[sig_date])
    res = backtest.run(panels, sig, start=dates[150])
    assert res.turnover.loc[sig_date] == 0.0
    assert res.equity.loc[sig_date] == pytest.approx(res.equity.iloc[0])
    nxt = dates[201]
    assert res.turnover.loc[nxt] > 0


def test_oracle_signal_would_break_the_test(random_panels):
    """反向验证：故意造一个"偷看次日收益"的因子，截断检验必须报警。

    没有这一条，前面所有的不变性测试都可能是"因为检验太松而全过"。
    """
    close = random_panels["close"]
    cheating = close.shift(-1) / close - 1.0        # 明目张胆的未来函数
    cut = close.index[250]
    trunc_close = close.loc[:cut]
    cheating_trunc = trunc_close.shift(-1) / trunc_close - 1.0
    with pytest.raises(AssertionError):
        _same_where_both_defined(cheating.loc[:cut], cheating_trunc.loc[:cut], "作弊因子")


# ------------------------------------------------------------------ 4. 时序对齐
def test_forward_return_alignment():
    dates = pd.bdate_range("2020-01-02", periods=10)
    close = pd.DataFrame({"a": [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]},
                         index=dates, dtype=float)
    fwd = metrics.forward_return(close, horizon=1, exec_lag=1)
    # t 日信号 -> t+1 开仓 -> t+2 平仓，收益 = close[t+2]/close[t+1]-1 = 1.0
    assert fwd.iloc[0, 0] == pytest.approx(1.0)
    assert np.isnan(fwd.iloc[-1, 0]) and np.isnan(fwd.iloc[-2, 0])


def test_rank_ic_is_one_for_perfect_foresight():
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2020-01-02", periods=60)
    codes = [f"c{i}" for i in range(60)]
    close = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.02, (60, 60)), axis=0)),
                         index=dates, columns=codes)
    fwd = metrics.forward_return(close, horizon=5, exec_lag=1)
    ic = metrics.rank_ic(fwd, fwd)
    assert ic.dropna().mean() == pytest.approx(1.0)


def test_rank_ic_of_same_day_return_is_near_zero_on_random_data():
    """随机数据上，"当日收益"因子对未来收益不该有系统性预测力。"""
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2020-01-02", periods=600)
    codes = [f"c{i}" for i in range(80)]
    ret = pd.DataFrame(rng.normal(0, 0.02, (600, 80)), index=dates, columns=codes)
    close = (1 + ret).cumprod()
    fwd = metrics.forward_return(close, horizon=5, exec_lag=1)
    ic = metrics.rank_ic(ret, fwd).dropna()
    t = ic.mean() / ic.std() * np.sqrt(len(ic))
    assert abs(t) < 3.0, f"随机数据上出现了 t={t:.2f} 的 IC，说明对齐有问题"


# ------------------------------------------------------------------ 5. 滚动样本外
def test_walkforward_truncation_invariant(random_panels):
    """滚动重估权重的信号流，同样必须满足截断不变性。

    这是最容易出问题的一环：只要在估计窗口里不小心多取了一天数据，
    整条净值曲线就会被未来信息污染。
    """
    from aq import walkforward

    panels = random_panels
    close = panels["close"]
    dates = close.index
    cut = dates[330]
    start, end = dates[130], dates[-1]

    def build(p):
        c = p["close"]
        mask = universe.investable(p, min_listed=60, min_amount=0.0,
                                   liquidity_top_pct=1.0, exclude_st=False)
        fp = factors.build_all(p)
        sig, _ = walkforward.build_signals(
            fp, mask, c, start=start, end=min(end, c.index[-1]), freq=5, top_n=8,
            est_years=1, refit_months=3)
        return backtest.run(p, sig, start=start, end=c.index[-1])

    full = build(panels)
    trunc = build(_truncate(panels, cut))
    a = full.equity.loc[:cut]
    b = trunc.equity.loc[:cut]
    assert len(b) > 50
    pd.testing.assert_series_equal(a.loc[b.index], b, check_exact=False, rtol=1e-12)
