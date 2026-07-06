"""
yfinance 适配器 — 用于 A 股 / 美股 / 贵贵金属现货等非永续标的 (如 XAGUSD=X, AAPL 等).
注意 yfinance 的 15m 数据仅保留 60 天, 1h 730 天, 1d 全部.
"""
import pandas as pd

_TF_MAP = {"15m": "15m", "5m": "5m", "1m": "1m", "30m": "30m", "1h": "60m", "1d": "1d"}
_PERIOD_MAP = {"15m": "60d", "5m": "60d", "1m": "7d", "30m": "60d", "1h": "730d", "1d": "max"}


def fetch_recent(symbol, timeframe="15m", limit=1500, **_kw):
    import yfinance as yf
    interval = _TF_MAP.get(timeframe, "15m")
    period = _PERIOD_MAP.get(timeframe, "60d")
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance 返回空: {symbol} {timeframe}")
    df = df.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    df = df.rename(columns={"datetime": "timestamp"})
    if "timestamp" not in df.columns:
        df["timestamp"] = df.iloc[:, 0]
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.tail(limit).reset_index(drop=True)
