"""
数据源适配器统一接口.
每个 adapter 提供 fetch_recent(symbol, timeframe, limit) -> pd.DataFrame[timestamp,open,high,low,close,volume].
timestamp 列为 UTC tz-aware. 加新数据源: 新建 <name>.py 实现 fetch_recent, 在 REGISTRY 注册.

realtime_quote.py 是盘中实时报价适配器 (单值 fast snapshot), 不参与 K 线历史.
"""
from . import ccxt_perp
from . import yfinance as yf_adapter
from . import realtime_quote as rt_quote

REGISTRY = {
    "ccxt_perp": ccxt_perp,
    "yfinance": yf_adapter,
}


def get_adapter(name):
    if name not in REGISTRY:
        raise ValueError(f"未知 data_source: {name!r}, 已注册: {list(REGISTRY)}")
    return REGISTRY[name]


def fetch_recent(name, symbol, timeframe, limit, **kw):
    return get_adapter(name).fetch_recent(symbol, timeframe, limit, **kw)


def fetch_realtime(quote_source, symbol, timeout=5):
    """盘中实时报价 (现价快照). quote_source: sina / tencent.
    返回 dict: source/symbol/name/last/change/change_pct/high/low/...
    失败抛 RuntimeError."""
    return rt_quote.fetch_realtime(symbol, source=quote_source, timeout=timeout)
