"""
EP004 量化评测分析方法实现 (基于 frank-quant/ai-trading-videos EP004)
========================================================================
包含:
1. Alpha / Beta 回归分解 (逐日盯市 CAPM 回归: 年化 Alpha, Beta, R^2, t值, p值, 纯Alpha贡献 vs Beta拖累)
2. 极端熊市压力测试 (Bear Market Stress Test, 如 2022 年大盘 -21.6% 或 2024 年初杀跌期)
3. 蒙特卡洛分块自助重采样 (Trade-level & Daily-level Block Bootstrap: prob(profit), P5/P50/P95)
4. Deflated Sharpe Ratio (DSR, Bailey & López de Prado): 检验夏普是否由多轮试错产生的假象
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def decompose_alpha_beta(
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    trading_days_per_year: int = 250,
    rf_annual: float = 0.02
) -> Dict[str, Any]:
    """
    1. Alpha / Beta 归因分解 (EP004 核心方法)
    R_strat - Rf = alpha + beta * (R_bm - Rf) + epsilon
    """
    if len(strategy_returns) < 10 or len(benchmark_returns) < 10:
        return {}

    rf_daily = rf_annual / trading_days_per_year
    y = strategy_returns - rf_daily
    x = benchmark_returns - rf_daily

    # OLS 回归
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    var_x = np.var(x, ddof=1)
    
    if var_x < 1e-10:
        beta = 1.0
        alpha_daily = 0.0
        r2 = 0.0
        t_stat = 0.0
        p_val = 1.0
    else:
        cov_xy = np.cov(x, y)[0, 1]
        beta = float(cov_xy / var_x)
        alpha_daily = float(y_mean - beta * x_mean)
        
        # 拟合值与残差
        y_pred = alpha_daily + beta * x
        residuals = y - y_pred
        ss_tot = np.sum((y - y_mean) ** 2)
        ss_res = np.sum(residuals ** 2)
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-10 else 0.0
        
        # Alpha t-stat & p-value
        n = len(y)
        se_res = np.sqrt(ss_res / (n - 2)) if n > 2 else 1e-6
        se_alpha = se_res * np.sqrt(1.0 / n + (x_mean ** 2) / ((n - 1) * var_x)) if var_x > 0 else 1e-6
        t_stat = float(alpha_daily / se_alpha) if se_alpha > 1e-10 else 0.0
        # 双尾 p-value (正态近似)
        p_val = float(2.0 * (1.0 - _norm_cdf(abs(t_stat))))

    annual_alpha = float((1.0 + alpha_daily) ** trading_days_per_year - 1.0)
    
    # 收益贡献拆解
    total_strat_return = float(np.prod(1.0 + strategy_returns) - 1.0)
    total_bm_return = float(np.prod(1.0 + benchmark_returns) - 1.0)
    beta_drag = float(beta * total_bm_return)
    alpha_contribution = float(total_strat_return - beta_drag)

    return {
        "annual_alpha": annual_alpha,
        "daily_alpha": alpha_daily,
        "beta": beta,
        "r_squared": r2,
        "t_stat": t_stat,
        "p_value": p_val,
        "is_alpha_significant": bool(p_val < 0.05),
        "total_strat_return": total_strat_return,
        "total_bm_return": total_bm_return,
        "beta_drag": beta_drag,
        "alpha_contribution": alpha_contribution,
    }


def compute_deflated_sharpe(
    daily_returns: np.ndarray,
    n_trials: int = 50,              # 参数/模型试验次数
    trading_days_per_year: int = 250,
    expected_sr_trials_var: float = 0.25
) -> Dict[str, Any]:
    """
    2. Deflated Sharpe Ratio (Bailey & López de Prado 2014)
    回答: 这个夏普有多少是「在 N 组试验中选最好的那组」带来的运气成分?
    """
    r = pd.Series(daily_returns).dropna()
    T = len(r)
    if T < 20 or r.std() == 0:
        return {"DSR": 0.0, "verdict": "样本过短"}

    mean_r = float(r.mean())
    std_r = float(r.std())
    sr_daily = mean_r / std_r
    sr_annual = float(sr_daily * math.sqrt(trading_days_per_year))

    g3 = float(r.skew())
    g4 = float(r.kurt()) + 3.0  # 超额峰度转真实峰度

    # 纯运气基线夏普 (Expected Maximum Sharpe)
    e = math.e
    gamma = 0.5772156649
    sr0_daily = math.sqrt(expected_sr_trials_var / trading_days_per_year) * (
        (1 - gamma) * _norm_ppf(1 - 1.0 / n_trials) + gamma * _norm_ppf(1 - 1.0 / (n_trials * e))
    )
    expected_luck_sr_annual = float(sr0_daily * math.sqrt(trading_days_per_year))

    denom = 1.0 - g3 * sr_daily + (g4 - 1.0) / 4.0 * (sr_daily ** 2)
    if denom <= 0:
        dsr = 0.0
    else:
        z = (sr_daily - sr0_daily) * math.sqrt(T - 1) / math.sqrt(denom)
        dsr = float(_norm_cdf(z))

    verdict = (
        "显著真实 Alpha (DSR ≥ 0.95)" if dsr >= 0.95 else
        "临界显著 (0.90 ≤ DSR < 0.95)" if dsr >= 0.90 else
        "不显著 (大概率是试出来的运气，DSR < 0.90)"
    )

    return {
        "DSR": dsr,
        "n_trials": n_trials,
        "observed_sharpe_annual": sr_annual,
        "expected_luck_sharpe_annual": expected_luck_sr_annual,
        "skewness": g3,
        "kurtosis": g4,
        "verdict": verdict,
    }


def run_monte_carlo_block_bootstrap(
    trades_profit_pcts: List[float],
    iters: int = 5000,
    block_size: int = 8,
    start_capital: float = 1.0,
    seed: int = 42
) -> Dict[str, Any]:
    """
    3. 蒙特卡洛分块自助重采样 (Monte Carlo Block Bootstrap, EP004 核心检验)
    重采样 5000 次，保留时序自相关，回答: 这条曲线最终能赚钱的概率有多大?
    """
    if len(trades_profit_pcts) < 5:
        return {"prob_profit": 0.0, "p5": 0.0, "p50": 0.0, "p95": 0.0}

    arr = np.asarray(trades_profit_pcts, dtype=float)
    N = len(arr)
    rng = np.random.default_rng(seed)
    
    final_capitals = np.empty(iters)
    for k in range(iters):
        sampled_indices = []
        while len(sampled_indices) < N:
            start_idx = int(rng.integers(0, max(1, N - block_size + 1)))
            sampled_indices.extend(range(start_idx, min(start_idx + block_size, N)))
        sub = arr[sampled_indices[:N]]
        final_capitals[k] = start_capital * np.prod(1.0 + sub)

    prob_profit = float(np.mean(final_capitals > start_capital))
    p5 = float(np.percentile(final_capitals, 5))
    p50 = float(np.percentile(final_capitals, 50))
    p95 = float(np.percentile(final_capitals, 95))
    orig_final = float(start_capital * np.prod(1.0 + arr))

    return {
        "iters": iters,
        "n_trades": N,
        "prob_profit": prob_profit,
        "p5": p5,
        "p50": p50,
        "p95": p95,
        "orig_final": orig_final,
    }
