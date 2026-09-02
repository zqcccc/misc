"""统计显著性检验：这条净值曲线里有多少是真 alpha，有多少是运气。

参考 frank-quant/ai-trading-videos EP004 的三层验证思路，按 A 股横截面选股的
特点做了适配：

  1. alpha / beta 归因 —— 跑赢指数可能只是因为 beta 低。把日收益对市场（和
     小盘风格）做回归，看截距还剩多少，t 值用 Newey-West 修正自相关。
  2. Deflated Sharpe Ratio（Bailey & López de Prado）—— 「以你试了这么多组
     参数的规模，纯靠运气能刷到多高的夏普」。
  3. Block bootstrap 蒙特卡洛 —— 保留一点序列相关性地重采样，给出 prob(profit)。
  4. 随机组合置换检验 —— 同一个股票池、同样的持股数、同样的调仓日，随机选股
     N 次，看真实策略排在分布的哪个位置。这一条是选股策略最直接的「有没有
     alpha」证据：它把市场、股票池、调仓节奏全部控住了。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 244


# ------------------------------------------------------------------ 回归
def newey_west_se(x: np.ndarray, resid: np.ndarray, lags: int = 5) -> np.ndarray:
    """Newey-West HAC 标准误。日频收益有自相关，普通 OLS 的 t 值会偏大。"""
    n, k = x.shape
    xtx_inv = np.linalg.pinv(x.T @ x)
    s = (x * resid[:, None])
    omega = s.T @ s
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)
        gamma = s[lag:].T @ s[:-lag]
        omega += w * (gamma + gamma.T)
    cov = xtx_inv @ omega @ xtx_inv * n / max(n - k, 1)
    return np.sqrt(np.diag(cov))


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def alpha_beta(ret: pd.Series, factors: dict[str, pd.Series], lags: int = 5) -> dict:
    """把策略日收益对若干风格因子回归，返回年化 alpha、beta 与 NW t 值。"""
    df = pd.DataFrame({"r": ret})
    for k, v in factors.items():
        df[k] = v.reindex(ret.index)
    df = df.dropna()
    if len(df) < 60:
        return {}
    y = df["r"].to_numpy()
    names = list(factors.keys())
    x = np.column_stack([np.ones(len(df))] + [df[k].to_numpy() for k in names])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    se = newey_west_se(x, resid, lags)
    tss = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / tss if tss > 0 else np.nan
    out = {
        "年化alpha": float(beta[0] * TRADING_DAYS),
        "alpha_t(NW)": float(beta[0] / se[0]) if se[0] > 0 else np.nan,
        "R2": float(r2),
        "样本天数": int(len(df)),
    }
    for i, k in enumerate(names, start=1):
        out[f"beta_{k}"] = float(beta[i])
        out[f"t_{k}(NW)"] = float(beta[i] / se[i]) if se[i] > 0 else np.nan
    out["alpha_p值(双侧)"] = float(2 * (1 - _norm_cdf(abs(out["alpha_t(NW)"]))))
    return out


# ------------------------------------------------------------------ DSR
def deflated_sharpe(ret: pd.Series, n_trials: int, trial_sharpe_var: float,
                    periods: int = TRADING_DAYS) -> dict:
    """Deflated Sharpe Ratio。n_trials 是实际尝试过的策略配置数量。"""
    r = ret.dropna().to_numpy()
    t = len(r)
    if t < 60 or r.std() == 0:
        return {}
    sr = r.mean() / r.std()                       # 日频夏普
    g3 = float(pd.Series(r).skew())
    g4 = float(pd.Series(r).kurt()) + 3.0
    n = max(int(n_trials), 2)
    gamma = 0.5772156649
    from statistics import NormalDist
    ppf = NormalDist().inv_cdf
    sr0 = math.sqrt(max(trial_sharpe_var, 1e-12) / periods) * (
        (1 - gamma) * ppf(1 - 1.0 / n) + gamma * ppf(1 - 1.0 / (n * math.e)))
    denom = 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return {"DSR": None, "备注": "收益分布过于极端，DSR 不可用"}
    z = (sr - sr0) * math.sqrt(t - 1) / math.sqrt(denom)
    dsr = _norm_cdf(z)
    return {
        "试验次数": n,
        "试验夏普方差": round(float(trial_sharpe_var), 4),
        "实际夏普(年化)": round(float(sr * math.sqrt(periods)), 3),
        "纯运气可达夏普(年化)": round(float(sr0 * math.sqrt(periods)), 3),
        "偏度": round(g3, 3), "峰度": round(g4, 3), "样本天数": t,
        "DSR": round(float(dsr), 4),
        "判定": ("显著 (DSR≥0.95)" if dsr >= 0.95 else
                 "偏弱 (0.90≤DSR<0.95)" if dsr >= 0.90 else
                 "不显著 —— 大概率是搜出来的运气"),
    }


# ------------------------------------------------------------------ 自助重采样
def block_bootstrap(ret: pd.Series, iters: int = 5000, block: int = 10,
                    seed: int = 7) -> dict:
    """分块自助法。block 保留一定的序列相关性，比逐日重采样保守。"""
    r = ret.dropna().to_numpy()
    n = len(r)
    if n < 60:
        return {}
    rng = np.random.default_rng(seed)
    finals = np.empty(iters)
    starts_max = max(1, n - block + 1)
    for k in range(iters):
        idx = []
        while len(idx) < n:
            s = int(rng.integers(0, starts_max))
            idx.extend(range(s, min(s + block, n)))
        finals[k] = np.prod(1.0 + r[np.asarray(idx[:n])])
    p5, p50, p95 = np.percentile(finals, [5, 50, 95])
    return {
        "重采样次数": iters, "块长": block,
        "实际累计": round(float(np.prod(1.0 + r)), 4),
        "盈利路径占比": round(float((finals > 1.0).mean()), 4),
        "P5": round(float(p5), 4), "P50": round(float(p50), 4), "P95": round(float(p95), 4),
    }


# ------------------------------------------------------------------ 随机组合
def random_scores(mask: pd.DataFrame, rb_dates, seed: int) -> pd.DataFrame:
    """给股票池里的每只票在每个调仓日分配一个随机分数（池外为 NaN）。"""
    rng = np.random.default_rng(seed)
    rows = {}
    for d in rb_dates:
        if d not in mask.index:
            continue
        m = mask.loc[d]
        vals = pd.Series(np.nan, index=mask.columns)
        cols = m[m].index
        vals[cols] = rng.random(len(cols))
        rows[d] = vals
    return pd.DataFrame(rows).T


def year_jackknife(ret: pd.Series, factors: dict[str, pd.Series]) -> dict:
    """逐年剔除检验：每次去掉一整年重算 alpha，看结论是不是靠某一年撑着。

    多年回测里最常见的假象是「某一年赚够了，其余年份贴地飞行」。年度贡献
    极度不均时，全期 alpha 的统计意义会被严重高估 —— 有效样本其实只有几年。
    """
    years = sorted(set(ret.index.year))
    full = alpha_beta(ret, factors)
    rows = []
    for y in years:
        m = ret.index.year != y
        sub = alpha_beta(ret[m], {k: v[v.index.year != y] for k, v in factors.items()})
        if sub:
            rows.append({"剔除年份": int(y),
                         "年化alpha": round(sub["年化alpha"], 4),
                         "alpha_t": round(sub["alpha_t(NW)"], 2)})
    alphas = [r["年化alpha"] for r in rows]
    return {
        "全样本alpha": round(full.get("年化alpha", float("nan")), 4),
        "全样本t": round(full.get("alpha_t(NW)", float("nan")), 2),
        "逐年剔除": rows,
        "最低alpha": round(min(alphas), 4) if alphas else None,
        "最低t": min(r["alpha_t"] for r in rows) if rows else None,
        "最不利年份": int(rows[alphas.index(min(alphas))]["剔除年份"]) if alphas else None,
    }


def percentile_rank(value: float, sample: np.ndarray) -> float:
    return float((sample < value).mean())


def permutation_p(value: float, sample: np.ndarray) -> float:
    """置换检验单侧 p 值：(1 + #{随机 >= 实际}) / (N + 1)。

    加 1 是标准做法 —— N 次随机里没有一次超过实际值，也不能宣称 p = 0，
    最小只能到 1/(N+1)。
    """
    sample = np.asarray(sample, dtype=float)
    sample = sample[np.isfinite(sample)]
    if sample.size == 0:
        return float("nan")
    return float((1 + (sample >= value).sum()) / (sample.size + 1))
