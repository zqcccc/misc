"""
yfinance 适配器 — 用于 A 股 / 美股 / 贵贵金属现货等非永续标的 (如 XAGUSD=X, AAPL 等).
注意 yfinance 的硬限制 (服务端控制, 无分页绕过):
  15m/30m/90m → 仅 60 天历史
  60m (1h)    → 仅 730 天历史
  1d          → 全部历史 (16+ 年, 可用 start/end 拉满)
warmup_target 与 ccxt_perp 接口一致, 但 yfinance 不能分页超期, 仅起参数透传作用.
"""
import pandas as pd

_TF_MAP = {"15m": "15m", "5m": "5m", "1m": "1m", "30m": "30m", "1h": "60m", "1d": "1d"}
# yfinance 硬上限 (服务端限制, 超过会返回空)。1d 用 start/end 拉满, 因此不用 period=1d。
_PERIOD_MAP = {"15m": "60d", "5m": "60d", "1m": "7d", "30m": "60d", "1h": "730d"}
# 1d 默认拉最长历史
_1D_START = "2008-01-01"


def fetch_recent(symbol, timeframe="15m", limit=1500, warmup_target=None, **_kw):
    import yfinance as yf
    interval = _TF_MAP.get(timeframe, "15m")
    if timeframe == "1d":
        # 1d 用 start/end 拉全历史 (无 Yahoo 限制)
        df = yf.download(symbol, start=_1D_START, end=pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
                         interval=interval, progress=False)
    else:
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
    # warmup_target 参数化 (即便 yfinance 不能拉更多, 让调用方能感知)
    real_target = max(limit, warmup_target or 0)
    return df.tail(real_target).reset_index(drop=True)
