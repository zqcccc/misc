"""
富途 OpenAPI 适配器 (OpenD 网关).

需要:
  1. OpenD GUI 运行并登录富途账号 (默认监听 127.0.0.1:11111)
  2. futu-api SDK 已安装 (pip install futu-api)

支持两个能力:
  - fetch_recent(symbol, timeframe, limit): 用 request_history_kline 拉 K 线
  - fetch_realtime(symbol): 用 get_market_snapshot 拉实时快照 (无需订阅, 30s 60次)

代码格式自动转换:
  - HK.00700 (富途原生) → 原样
  - 0700.HK (yfinance 风格) → HK.00700
  - US.AAPL → 原样

OpenD 地址可用环境变量覆盖:
  FUTU_OPEND_HOST (默认 127.0.0.1)
  FUTU_OPEND_PORT (默认 11111)
"""
import os
import time

import pandas as pd

_OPEND_HOST = os.getenv("FUTU_OPEND_HOST", "127.0.0.1")
_OPEND_PORT = int(os.getenv("FUTU_OPEND_PORT", "11111"))

# timeframe → KLType 枚举名
_TF_MAP = {
    "1m": "K_1M", "3m": "K_3M", "5m": "K_5M", "15m": "K_15M",
    "30m": "K_30M", "60m": "K_60M", "1h": "K_60M",
    "1d": "K_DAY", "1w": "K_WEEK", "1M": "K_MON",
}

# 代码前缀 → 富途本地时区 (用于把 time_key 转 UTC)
_TZ_MAP = {
    "HK": "Asia/Hong_Kong",
    "US": "America/New_York",
    "SH": "Asia/Shanghai",
    "SZ": "Asia/Shanghai",
    "SG": "Asia/Singapore",
    "MY": "Asia/Kuala_Lumpur",
    "JP": "Asia/Tokyo",
}

_FUTU_PREFIXES = ("HK", "US", "SH", "SZ", "SG", "MY", "JP", "CC")


def _to_futu_code(symbol):
    """0700.HK → HK.00700; HK.00700 原样; US.AAPL 原样."""
    s = str(symbol).strip().upper()
    if "." not in s:
        raise ValueError(f"富途代码必须带市场前缀 (如 HK.00700 / US.AAPL): {symbol}")
    prefix, code = s.split(".", 1)
    if prefix in _FUTU_PREFIXES:
        # 已是富途格式 (HK.00700 / US.AAPL); 港股补 5 位
        if prefix == "HK" and code.isdigit():
            code = code.zfill(5)
        return f"{prefix}.{code}"
    # yfinance 风格: 0700.HK / AAPL.US → 反转
    if code in _FUTU_PREFIXES:
        if code == "HK" and prefix.isdigit():
            prefix = prefix.zfill(5)
        return f"{code}.{prefix}"
    raise ValueError(f"无法识别的代码格式: {symbol} (支持 HK.00700 / 0700.HK / US.AAPL)")


def _parse_timestamp(time_key, prefix):
    """富途 time_key (本地时间) → UTC tz-aware Timestamp."""
    ts = pd.to_datetime(time_key)
    tz = _TZ_MAP.get(prefix)
    if tz is None:
        return ts.tz_localize("UTC")
    return ts.tz_localize(tz).tz_convert("UTC")


def _get_ctx():
    """创建 OpenQuoteContext. 不导 SDK, 失败时给出清晰错误."""
    try:
        from futu import OpenQuoteContext
    except ImportError as e:
        raise RuntimeError(
            f"futu-api 未安装: {e}. 请运行: pip install futu-api"
        ) from e
    return OpenQuoteContext(host=_OPEND_HOST, port=_OPEND_PORT)


def _check_opend_alive():
    """快速检测 OpenD 端口, 不可连接时给清晰错误."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect((_OPEND_HOST, _OPEND_PORT))
    except (ConnectionRefusedError, OSError) as e:
        raise RuntimeError(
            f"无法连接 OpenD ({_OPEND_HOST}:{_OPEND_PORT}): {e}. "
            f"请先启动 OpenD GUI 并登录富途账号."
        ) from e
    finally:
        sock.close()


def fetch_recent(symbol, timeframe="1d", limit=1000, warmup_target=None, **_kw):
    """拉历史 K 线. 用 request_history_kline 自动翻页, 返回 UTC tz-aware DataFrame.

    限制: 单次 max_count=1000, 历史额度 100 只/30 天 (同股不重复计).
    request_history_kline 按时间正序返回 + 翻页, 所以策略是:
      1. 按 timeframe 估算 start/end 范围 (略大于 real_target)
      2. 一直翻页拉到范围内全部数据
      3. tail(real_target) 取最近 N 根
    """
    from futu import RET_OK, AuType
    _check_opend_alive()
    code = _to_futu_code(symbol)
    prefix = code.split(".")[0]
    ktype_name = _TF_MAP.get(timeframe)
    if ktype_name is None:
        raise ValueError(f"futu 不支持 timeframe: {timeframe}")
    ktype = getattr(__import__("futu", fromlist=["KLType"]).KLType, ktype_name)

    real_target = max(limit, warmup_target or 0)
    # 按 timeframe 估算需要拉多少天的历史 (保守 1.5x 容错, 宁可多拉)
    if timeframe == "1d":
        days_back = int(real_target * 1.5) + 10
    elif timeframe in ("1w", "1M"):
        days_back = real_target * 7 + 30
    else:
        tf_min = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "60m": 60, "1h": 60}.get(timeframe, 15)
        days_back = int(real_target * tf_min / 360 * 1.5) + 10
    end = pd.Timestamp.utcnow().normalize() + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=days_back)

    ctx = _get_ctx()
    try:
        all_rows = []
        page_key = None
        # 一直翻页直到没有 page_key; 安全上限 20 页 (20000 根) 避免异常无限循环
        for _ in range(20):
            kwargs = dict(
                code=code, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
                ktype=ktype, autype=AuType.QFQ, max_count=1000,
            )
            if page_key:
                kwargs["page_req_key"] = page_key
            ret, data, page_key = ctx.request_history_kline(**kwargs)
            if ret != RET_OK:
                raise RuntimeError(f"futu request_history_kline 失败: {data}")
            if data is None or len(data) == 0:
                break
            all_rows.append(data)
            if not page_key:
                break
        if not all_rows:
            raise RuntimeError(f"futu 返回空 K 线: {symbol} {timeframe}")
        df = pd.concat(all_rows, ignore_index=True)
        df = df.rename(columns={"time_key": "timestamp"})
        df["timestamp"] = df["timestamp"].apply(lambda x: _parse_timestamp(x, prefix))
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        return df.tail(real_target).reset_index(drop=True)
    finally:
        try: ctx.close()
        except Exception: pass


def fetch_realtime(symbol, timeout=5):
    """实时快照 (无需订阅). 返回与 realtime_quote.py 一致的 dict 结构."""
    from futu import RET_OK
    _check_opend_alive()
    code = _to_futu_code(symbol)
    ctx = _get_ctx()
    try:
        t0 = time.time()
        ret, data = ctx.get_market_snapshot([code])
        if ret != RET_OK:
            raise RuntimeError(f"futu get_market_snapshot 失败: {data}")
        if data is None or len(data) == 0:
            raise RuntimeError(f"futu snapshot 返回空: {symbol}")
        row = data.iloc[0]
        last = float(row.get("last_price", 0) or 0)
        prev_close = float(row.get("prev_close_price", 0) or 0)
        change = last - prev_close if prev_close else 0.0
        change_pct = (change / prev_close * 100.0) if prev_close else 0.0
        return {
            "source": "futu",
            "symbol": symbol,
            "name": str(row.get("name", "") or ""),
            "last": last,
            "prev_close": prev_close,
            "open": float(row.get("open_price", 0) or 0),
            "high": float(row.get("high_price", 0) or 0),
            "low": float(row.get("low_price", 0) or 0),
            "volume": float(row.get("volume", 0) or 0),
            "amount": float(row.get("turnover", 0) or 0),
            "change": change,
            "change_pct": change_pct,
            "latency_ms": int((time.time() - t0) * 1000),
        }
    finally:
        try: ctx.close()
        except Exception: pass


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "0700.HK"
    print(f"== 测试 {sym} 富途实时快照 ==")
    print(f"  OpenD: {_OPEND_HOST}:{_OPEND_PORT}")
    try:
        q = fetch_realtime(sym)
        for k in ["symbol", "name", "last", "change_pct", "high", "low",
                 "prev_close", "open", "volume", "amount", "latency_ms"]:
            if k in q:
                print(f"  {k:<14} {q[k]}")
    except Exception as e:
        print(f"  ERR: {e}")
