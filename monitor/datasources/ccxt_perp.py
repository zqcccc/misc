"""
Binance USDT-M 永续合约 K 线适配器.
单次最多 1500 根, 用 since 分页拉取足够 EMA warmup 的大窗口.
"""
import time
import pandas as pd

_EXCHANGE = None


def _get_exchange():
    global _EXCHANGE
    if _EXCHANGE is None:
        import ccxt
        _EXCHANGE = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
    return _EXCHANGE


_TF_MS = {
    "1m": 60 * 1000, "5m": 5 * 60 * 1000, "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000, "1h": 60 * 60 * 1000, "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def fetch_recent(symbol, timeframe="15m", limit=1500, warmup_target=None, timeout=30, **_kw):
    """
    分页拉取, 至少返回 limit 根. warmup_target 给定时强制拉满 (≥ EMA_SPAN*3).
    """
    ex = _get_exchange()
    tf_ms = _TF_MS.get(timeframe, 15 * 60 * 1000)
    n_target = max(limit, warmup_target or 0)
    per_page = 1500
    n_target = max(n_target, per_page)

    now_ms = int(time.time() * 1000)
    since_ms = now_ms - n_target * tf_ms
    rows = []
    cur = since_ms
    max_iter = 30
    while cur < now_ms and len(rows) < n_target + 200 and max_iter > 0:
        try:
            ohlcv = ex.fetch_ohlcv(symbol, timeframe, since=cur, limit=per_page)
        except Exception as e:
            time.sleep(2)
            max_iter -= 1
            continue
        if not ohlcv:
            break
        rows.extend(ohlcv)
        last_ts = ohlcv[-1][0]
        if last_ts <= cur:
            break
        cur = last_ts + tf_ms
        time.sleep(ex.rateLimit / 1000.0)
        max_iter -= 1

    if not rows:
        raise RuntimeError(f"ccxt_perp 拉取为空: {symbol} {timeframe}")
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return df.tail(n_target).reset_index(drop=True)
