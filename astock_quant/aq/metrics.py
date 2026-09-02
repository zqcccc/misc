"""绩效与因子评价指标。"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 244


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1.0).min())


def perf_stats(ret: pd.Series, bench: pd.Series = None, name: str = "") -> dict:
    ret = ret.dropna()
    if ret.empty:
        return {}
    nav = (1 + ret).cumprod()
    years = len(ret) / TRADING_DAYS
    cagr = nav.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = ret.std() * np.sqrt(TRADING_DAYS)
    out = {
        "名称": name,
        "年化收益": cagr,
        "年化波动": vol,
        "夏普(rf=0)": cagr / vol if vol > 0 else np.nan,
        "最大回撤": max_drawdown(nav),
        "卡玛": cagr / abs(max_drawdown(nav)) if max_drawdown(nav) < 0 else np.nan,
        "日胜率": float((ret > 0).mean()),
        "累计净值": float(nav.iloc[-1]),
    }
    if bench is not None:
        b = bench.reindex(ret.index).fillna(0.0)
        excess = ret - b
        out["超额年化"] = ((1 + excess).cumprod().iloc[-1]) ** (1 / years) - 1 if years > 0 else np.nan
        out["超额最大回撤"] = max_drawdown((1 + excess).cumprod())
        out["信息比率"] = (excess.mean() * TRADING_DAYS) / (excess.std() * np.sqrt(TRADING_DAYS)) \
            if excess.std() > 0 else np.nan
        cov = np.cov(ret.values, b.values)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
        out["beta"] = beta
        out["年化alpha"] = cagr - beta * (((1 + b).cumprod().iloc[-1]) ** (1 / years) - 1)
    return out


def stats_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([r for r in rows if r])
    pct_cols = [c for c in df.columns if c in
                ("年化收益", "年化波动", "最大回撤", "日胜率", "超额年化", "超额最大回撤", "年化alpha")]
    for c in pct_cols:
        df[c] = (df[c] * 100).round(2)
    for c in ("夏普(rf=0)", "卡玛", "信息比率", "beta", "累计净值"):
        if c in df.columns:
            df[c] = df[c].round(3)
    return df


# ------------------------------------------------------------------ 因子评价
def forward_return(close: pd.DataFrame, horizon: int, exec_lag: int = 1) -> pd.DataFrame:
    """t 日信号对应的前瞻收益：从 t+exec_lag 的价格算到 t+exec_lag+horizon。

    exec_lag=1 表示信号次日才能建仓，这一条是 IC 计算里最容易出错的地方：
    直接用 close(t+h)/close(t)-1 会把"信号当天收盘就能成交"偷偷算进去。
    """
    fwd = close.shift(-(exec_lag + horizon)) / close.shift(-exec_lag) - 1.0
    return fwd


def rank_ic(factor: pd.DataFrame, fwd: pd.DataFrame, mask: pd.DataFrame = None,
            min_stocks: int = 50) -> pd.Series:
    """逐日 Spearman 秩相关（Rank IC）。"""
    f, r = factor.align(fwd, join="inner")
    if mask is not None:
        m = mask.reindex_like(f).fillna(False)
        f = f.where(m)
        r = r.where(m)
    fr = f.rank(axis=1)
    rr = r.rank(axis=1)
    valid = fr.notna() & rr.notna()
    counts = valid.sum(axis=1)
    fr, rr = fr.where(valid), rr.where(valid)
    fm, rm = fr.mean(axis=1), rr.mean(axis=1)
    cov = ((fr.sub(fm, axis=0)) * (rr.sub(rm, axis=0))).sum(axis=1)
    den = np.sqrt((fr.sub(fm, axis=0) ** 2).sum(axis=1) * (rr.sub(rm, axis=0) ** 2).sum(axis=1))
    ic = cov / den.replace(0, np.nan)
    return ic.where(counts >= min_stocks)


def ic_stats(ic: pd.Series, periods_per_year: float = TRADING_DAYS) -> dict:
    ic = ic.dropna()
    if len(ic) < 10:
        return {}
    mean, std = ic.mean(), ic.std()
    icir = mean / std if std > 0 else np.nan
    return {
        "IC均值": round(float(mean), 4),
        "IC标准差": round(float(std), 4),
        "ICIR": round(float(icir), 3),
        "IC>0占比": round(float((ic > 0).mean()), 3),
        "t统计量": round(float(icir * np.sqrt(len(ic))), 2),
        "样本数": int(len(ic)),
    }
