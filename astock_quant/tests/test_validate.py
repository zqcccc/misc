"""统计检验模块的已知答案测试。"""
import numpy as np
import pandas as pd
import pytest

from aq import validate


@pytest.fixture
def dates():
    return pd.bdate_range("2020-01-02", periods=800)


def test_pure_beta_series_has_zero_alpha(dates, rng):
    """收益完全由市场解释时，回归截距必须≈0、beta≈设定值、R²≈1。"""
    mkt = pd.Series(rng.normal(0.0003, 0.012, len(dates)), index=dates)
    strat = 0.8 * mkt
    out = validate.alpha_beta(strat, {"mkt": mkt})
    assert out["年化alpha"] == pytest.approx(0.0, abs=1e-8)
    assert out["beta_mkt"] == pytest.approx(0.8, abs=1e-8)
    assert out["R2"] == pytest.approx(1.0, abs=1e-8)


def test_injected_alpha_is_recovered(dates, rng):
    """人为注入每日 4bp 的超额，回归必须把它找回来且 t 值显著。"""
    mkt = pd.Series(rng.normal(0.0003, 0.012, len(dates)), index=dates)
    strat = 0.0004 + 0.9 * mkt + pd.Series(rng.normal(0, 0.002, len(dates)), index=dates)
    out = validate.alpha_beta(strat, {"mkt": mkt})
    assert out["年化alpha"] == pytest.approx(0.0004 * 244, rel=0.25)
    assert out["alpha_t(NW)"] > 3
    assert out["alpha_p值(双侧)"] < 0.01


def test_beta_exposure_alone_does_not_create_alpha(dates, rng):
    """只是放大市场敞口（beta=1.5）不算 alpha —— 这正是"跑赢指数"最常见的假象。"""
    mkt = pd.Series(rng.normal(0.0006, 0.013, len(dates)), index=dates)
    strat = 1.5 * mkt
    out = validate.alpha_beta(strat, {"mkt": mkt})
    assert strat.mean() > mkt.mean()            # 绝对收益确实更高
    assert abs(out["年化alpha"]) < 1e-6         # 但 alpha 是 0
    assert out["beta_mkt"] == pytest.approx(1.5, abs=1e-8)


def test_newey_west_se_matches_ols_when_no_autocorrelation(rng):
    n = 2000
    x = np.column_stack([np.ones(n), rng.normal(0, 1, n)])
    e = rng.normal(0, 1, n)
    se_nw = validate.newey_west_se(x, e, lags=0)
    xtx_inv = np.linalg.pinv(x.T @ x)
    se_ols = np.sqrt(np.diag(xtx_inv @ (x * e[:, None]).T @ (x * e[:, None]) @ xtx_inv
                             * n / (n - 2)))
    assert np.allclose(se_nw, se_ols)


def test_deflated_sharpe_penalises_more_trials(dates, rng):
    r = pd.Series(rng.normal(0.0006, 0.012, len(dates)), index=dates)
    few = validate.deflated_sharpe(r, n_trials=3, trial_sharpe_var=0.25)
    many = validate.deflated_sharpe(r, n_trials=5000, trial_sharpe_var=0.25)
    assert few["DSR"] > many["DSR"], "试的次数越多，同样的夏普越不值钱"
    assert many["纯运气可达夏普(年化)"] > few["纯运气可达夏普(年化)"]


def test_block_bootstrap_is_deterministic_and_sane(dates, rng):
    r = pd.Series(rng.normal(0.0008, 0.01, len(dates)), index=dates)
    a = validate.block_bootstrap(r, iters=400, block=10, seed=1)
    b = validate.block_bootstrap(r, iters=400, block=10, seed=1)
    assert a == b                                    # 同种子可复现
    assert 0.0 <= a["盈利路径占比"] <= 1.0
    assert a["P5"] < a["P50"] < a["P95"]


def test_block_bootstrap_flags_a_losing_curve(dates, rng):
    r = pd.Series(rng.normal(-0.0008, 0.01, len(dates)), index=dates)
    out = validate.block_bootstrap(r, iters=400, block=10, seed=3)
    assert out["盈利路径占比"] < 0.2


def test_percentile_rank():
    sample = np.arange(100.0)
    assert validate.percentile_rank(50.0, sample) == pytest.approx(0.50)
    assert validate.percentile_rank(200.0, sample) == 1.0


def test_permutation_p_never_returns_zero():
    sample = np.arange(200.0)
    assert validate.permutation_p(1e9, sample) == pytest.approx(1 / 201)
    assert validate.permutation_p(-1e9, sample) == pytest.approx(1.0)
    assert 0.4 < validate.permutation_p(100.0, sample) < 0.6


def test_year_jackknife_exposes_a_one_year_wonder(rng):
    """一整年贡献全部超额、其余年份为零的序列，剔除那一年后 alpha 必须塌掉。"""
    dates = pd.bdate_range("2020-01-02", periods=244 * 4)
    mkt = pd.Series(rng.normal(0.0002, 0.011, len(dates)), index=dates)
    r = 1.0 * mkt.copy()
    boom = dates.year == 2022
    r[boom] += 0.0012                     # 只有 2022 年每天多 12bp
    jk = validate.year_jackknife(r, {"mkt": mkt})
    assert jk["全样本alpha"] > 0.05
    assert jk["最不利年份"] == 2022
    assert jk["最低alpha"] == pytest.approx(0.0, abs=1e-6)
