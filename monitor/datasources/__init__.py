"""
数据源适配器统一接口.
每个 adapter 提供 fetch_recent(symbol, timeframe, limit) -> pd.DataFrame[timestamp,open,high,low,close,volume].
timestamp 列为 UTC tz-aware. 加新数据源: 新建 <name>.py 实现 fetch_recent, 在 REGISTRY 注册.

realtime_quote.py 是盘中实时报价适配器 (单值 fast snapshot), 不参与 K 线历史.
"""
from . import ccxt_perp
from . import yfinance as yf_adapter
from . import realtime_quote as rt_quote
from . import futu as futu_adapter

REGISTRY = {
    "ccxt_perp": ccxt_perp,
    "yfinance": yf_adapter,
    "futu": futu_adapter,
}


def get_adapter(name):
    if name not in REGISTRY:
        raise ValueError(f"未知 data_source: {name!r}, 已注册: {list(REGISTRY)}")
    return REGISTRY[name]


def fetch_recent(name, symbol, timeframe, limit, **kw):
    """K 线历史. name 支持逗号分隔多源 fallback (如 "futu,yfinance"),
    按顺序尝试, 第一个成功就返回. 全部失败抛最后一个错误."""
    names = [s.strip() for s in str(name).split(",") if s.strip()]
    if not names:
        raise ValueError(f"data_source 为空: {name!r}")
    last_err = None
    for n in names:
        try:
            return get_adapter(n).fetch_recent(symbol, timeframe, limit, **kw)
        except Exception as e:
            last_err = e
            if len(names) > 1:
                # 多源模式: 记录失败但继续尝试下一个
                import sys
                print(f"[datasources] {n} 拉取失败, 尝试下一个: {e}", file=sys.stderr)
    raise RuntimeError(f"所有数据源都失败 {names}: {last_err}")


def fetch_realtime(quote_source, symbol, timeout=5):
    """盘中实时报价 (现价快照). quote_source 支持逗号分隔多源 fallback
    (如 "futu,sina"), 按顺序尝试, 第一个成功就返回. 全部失败抛最后一个错误.
    单源: sina / tencent / eastmoney / futu."""
    sources = [s.strip() for s in str(quote_source).split(",") if s.strip()]
    if not sources:
        raise ValueError(f"realtime_quote 为空: {quote_source!r}")
    last_err = None
    for src in sources:
        try:
            if src == "futu":
                return futu_adapter.fetch_realtime(symbol, timeout=timeout)
            return rt_quote.fetch_realtime(symbol, source=src, timeout=timeout)
        except Exception as e:
            last_err = e
            if len(sources) > 1:
                import sys
                print(f"[datasources] {src} 实时报价失败, 尝试下一个: {e}", file=sys.stderr)
    raise RuntimeError(f"所有实时报价源都失败 {sources}: {last_err}")
