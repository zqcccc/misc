"""量价因子库。

铁律：任何因子在 t 日的取值只能用到 <= t 日收盘的数据。所有实现都是
`rolling(...)` 形式（pandas 的 rolling 是右闭窗口，天然只看过去），不出现
`shift(-n)`、`rolling(...).shift(-k)`、`bfill()` 这类会把未来搬到过去的写法。
tests/test_no_lookahead.py 用"截断数据后重算"的方式对每个因子做机器校验。

因子方向已统一为"数值越大越好"（预期收益越高），便于合成。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ 预处理


def winsorize_mad(df: pd.DataFrame, n: float = 5.0) -> pd.DataFrame:
    """按截面做 MAD 去极值。只用当期截面信息，不跨期。"""
    med = df.median(axis=1)
    mad = (df.sub(med, axis=0)).abs().median(axis=1)
    upper = med + n * 1.4826 * mad
    lower = med - n * 1.4826 * mad
    return df.clip(lower=lower, upper=upper, axis=0)


def cs_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """截面标准化。"""
    mu = df.mean(axis=1)
    sd = df.std(axis=1).replace(0.0, np.nan)
    return df.sub(mu, axis=0).div(sd, axis=0)


def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
    """截面百分位排名，落在 [0, 1]，对极值不敏感。"""
    return df.rank(axis=1, pct=True)


def neutralize(df: pd.DataFrame, control: pd.DataFrame) -> pd.DataFrame:
    """逐日把 df 对 control 做截面回归，取残差（如剔除规模/流动性暴露）。"""
    out = pd.DataFrame(np.nan, index=df.index, columns=df.columns)
    ctrl = control.reindex_like(df)
    for dt in df.index:
        y, x = df.loc[dt], ctrl.loc[dt]
        mask = y.notna() & x.notna()
        if mask.sum() < 30:
            continue
        yv, xv = y[mask].values, x[mask].values
        xm = np.column_stack([np.ones(len(xv)), xv])
        beta, *_ = np.linalg.lstsq(xm, yv, rcond=None)
        out.loc[dt, y[mask].index] = yv - xm @ beta
    return out


# ------------------------------------------------------------------ 基础量
def daily_return(close: pd.DataFrame) -> pd.DataFrame:
    return close / close.shift(1) - 1.0


def overnight_return(open_: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    return open_ / close.shift(1) - 1.0


def intraday_return(open_: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    return close / open_ - 1.0


# ------------------------------------------------------------------ 因子
def rev(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """短期反转：过去 n 日涨得多的，未来跌回来。取负号后越大越好。"""
    return -(close / close.shift(n) - 1.0)


def mom(close: pd.DataFrame, long: int, skip: int) -> pd.DataFrame:
    """中期动量，跳过最近 skip 日以避开短期反转的污染。"""
    return close.shift(skip) / close.shift(long) - 1.0


def volatility(ret: pd.DataFrame, n: int) -> pd.DataFrame:
    """低波动因子：波动率取负，低波越大越好。"""
    return -ret.rolling(n, min_periods=int(n * 0.6)).std()


def max_ret(ret: pd.DataFrame, n: int) -> pd.DataFrame:
    """彩票偏好：过去 n 日单日最大涨幅越高，未来越差（取负）。"""
    return -ret.rolling(n, min_periods=int(n * 0.6)).max()


def amihud(ret: pd.DataFrame, amount: pd.DataFrame, n: int) -> pd.DataFrame:
    """Amihud 非流动性：单位成交额推动的价格变动，越高越"难交易"，
    理论上有流动性溢价（取正号）。"""
    illiq = (ret.abs() / amount.replace(0.0, np.nan)) * 1e10
    return np.log1p(illiq.rolling(n, min_periods=int(n * 0.6)).mean())


def liquidity_size(amount: pd.DataFrame, n: int) -> pd.DataFrame:
    """成交额规模代理：日均成交额取负 ≈ 小盘因子（A 股无 PIT 股本数据，
    用成交额做代理，见 README 的局限说明）。"""
    return -np.log(amount.rolling(n, min_periods=int(n * 0.6)).mean().replace(0.0, np.nan))


def volume_shock(volume: pd.DataFrame, short: int = 5, long: int = 60) -> pd.DataFrame:
    """量能异动：近期放量相对长期均量，A 股里放量后短期偏负（取负）。"""
    s = volume.rolling(short, min_periods=short).mean()
    l = volume.rolling(long, min_periods=int(long * 0.6)).mean().replace(0.0, np.nan)
    return -np.log((s / l).replace(0.0, np.nan))


def overnight_mom(ovn: pd.DataFrame, n: int) -> pd.DataFrame:
    """隔夜动量：隔夜收益累计（信息驱动），A 股里隔夜与日内收益的截面
    定价方向相反，是一组经典的分解因子。"""
    return ovn.rolling(n, min_periods=int(n * 0.6)).sum()


def intraday_rev(intra: pd.DataFrame, n: int) -> pd.DataFrame:
    """日内反转：日内收益累计取负。"""
    return -intra.rolling(n, min_periods=int(n * 0.6)).sum()


def bias(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """乖离率取负：偏离均线越远越回归。"""
    ma = close.rolling(n, min_periods=int(n * 0.6)).mean()
    return -(close / ma - 1.0)


def skewness(ret: pd.DataFrame, n: int) -> pd.DataFrame:
    """收益偏度取负：右偏（彩票型）股票预期收益更低。"""
    return -ret.rolling(n, min_periods=int(n * 0.6)).skew()


def idio_vol(ret: pd.DataFrame, n: int = 60) -> pd.DataFrame:
    """特质波动率取负：先用滚动 beta 剥掉市场，再算残差波动。

    市场收益用当日截面等权收益（截面内可得，不含未来）。滚动 beta 与残差
    都只用过去 n 日窗口。
    """
    mkt = ret.mean(axis=1)
    mp = int(n * 0.6)
    var_m = mkt.rolling(n, min_periods=mp).var()
    cov = ret.mul(mkt, axis=0).rolling(n, min_periods=mp).mean()         - ret.rolling(n, min_periods=mp).mean().mul(mkt.rolling(n, min_periods=mp).mean(), axis=0)
    beta = cov.div(var_m.replace(0.0, np.nan), axis=0)
    resid = ret - beta.mul(mkt, axis=0)
    return -resid.rolling(n, min_periods=mp).std()


def high_52w(close: pd.DataFrame, n: int = 244) -> pd.DataFrame:
    """52 周高点接近度：越接近前高，动量越强。"""
    hi = close.rolling(n, min_periods=int(n * 0.5)).max()
    return close / hi - 1.0


def rsrs(high: pd.DataFrame, low: pd.DataFrame, n: int = 18, m: int = 250) -> pd.DataFrame:
    """RSRS 阻力支撑相对强度（光大证券研报 / 聚宽经典量化因子）。
    
    使用滚动 n 日 High 对 Low 的 OLS 回归斜率 beta，并以滚动 m 日历史窗口计算 Z-Score，
    最后以决定系数 R2 进行修正，完全严格因果右闭 rolling。
    """
    min_p = int(n * 0.7)
    mean_h = high.rolling(n, min_periods=min_p).mean()
    mean_l = low.rolling(n, min_periods=min_p).mean()
    mean_hl = (high * low).rolling(n, min_periods=min_p).mean()
    mean_l2 = (low ** 2).rolling(n, min_periods=min_p).mean()
    mean_h2 = (high ** 2).rolling(n, min_periods=min_p).mean()

    cov_hl = mean_hl - mean_h * mean_l
    var_l = mean_l2 - mean_l ** 2
    var_h = mean_h2 - mean_h ** 2

    beta = cov_hl / var_l.replace(0.0, np.nan)
    r2 = (cov_hl ** 2) / (var_l * var_h).replace(0.0, np.nan)
    r2 = r2.clip(lower=0.0, upper=1.0)

    min_m = int(m * 0.6)
    beta_mean = beta.rolling(m, min_periods=min_m).mean()
    beta_std = beta.rolling(m, min_periods=min_m).std().replace(0.0, np.nan)
    z = (beta - beta_mean) / beta_std
    return z * r2


def build_all(panels: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """一次性算出全部因子面板（值 = 该日收盘后可知）。"""
    close, open_ = panels["close"], panels["open"]
    high, low = panels["high"], panels["low"]
    volume, amount = panels["volume"], panels["amount"]
    ret = daily_return(close)
    ovn = overnight_return(open_, close)
    intra = intraday_return(open_, close)
    return {
        "rev5": rev(close, 5),
        "rev20": rev(close, 20),
        "mom120_20": mom(close, 120, 20),
        "mom60_20": mom(close, 60, 20),
        "vol60": volatility(ret, 60),
        "vol20": volatility(ret, 20),
        "maxret20": max_ret(ret, 20),
        "amihud20": amihud(ret, amount, 20),
        "liqsize20": liquidity_size(amount, 20),
        "volshock": volume_shock(volume),
        "ovnmom20": overnight_mom(ovn, 20),
        "intrarev20": intraday_rev(intra, 20),
        "bias20": bias(close, 20),
        "skew60": skewness(ret, 60),
        "ivol60": idio_vol(ret, 60),
        "high52w": high_52w(close),
        "mom244_20": mom(close, 244, 20),
        "rsrs": rsrs(high, low),
    }


FACTOR_DESC = {
    "rev5": "5 日反转", "rev20": "20 日反转",
    "mom120_20": "120 日动量(跳过近 20 日)", "mom60_20": "60 日动量(跳过近 20 日)",
    "vol60": "60 日低波动", "vol20": "20 日低波动",
    "maxret20": "20 日最大单日涨幅(负)", "amihud20": "Amihud 非流动性",
    "liqsize20": "成交额规模(负,小盘)", "volshock": "量能异动(负)",
    "ovnmom20": "20 日隔夜动量", "intrarev20": "20 日日内反转",
    "bias20": "20 日乖离率(负)",
    "skew60": "60 日收益偏度(负)", "ivol60": "60 日特质波动率(负)",
    "high52w": "52 周高点接近度", "mom244_20": "244 日长期动量",
    "rsrs": "RSRS 阻力支撑相对强度修正值",
}
