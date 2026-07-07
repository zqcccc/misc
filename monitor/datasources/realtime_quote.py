"""
新浪/腾讯 港股实时报价适配器 (盘中实时, 非 K 线数据源).
用于在 daemon 主循环中补充"未到收盘"的现价探针.
"""
import re
import time
import requests

_SINA_URL = "https://hq.sinajs.cn/list=hk{code}"
_TENCENT_URL = "https://qt.gtimg.cn/q=hk{code}"
_HEADERS = {"Referer": "https://finance.sina.com.cn"}

# sina/腾讯港股实时报价是国内 API, 不应走系统代理.
# 用 trust_env=False 的 Session 屏蔽 HTTPS_PROXY/HTTP_PROXY 环境变量,
# 避免 daemon 继承父 shell 的失效代理端口 (如 127.0.0.1:57076).
_SESSION = requests.Session()
_SESSION.trust_env = False


def _normalize_symbol(symbol):
    """支持 0700.HK / 00700.HK / 00700 全写法 → 5 位代码 (00700)."""
    s = str(symbol).upper().replace(".HK", "").replace("-", "")
    while s.startswith("0") and len(s) > 5:
        s = s[1:]  # "0700" -> "700" wait... 港股代码本身允许前导 0
    # 港股代码通常 5 位 (00001~09999), 不够补 0
    s = s.zfill(5)
    return s


def fetch_realtime(symbol, source="sina", timeout=5):
    """返回 {symbol, name, prev_close, open, high, low, last, change, change_pct,
            bid, ask, volume, amount, datetime}.
    盘外时段返回最后一个收盘价 (字段不变, 时间为最后成交时间).
    source: 'sina' (推荐, 40ms) 或 'tencent' (备用, 250ms).
    """
    code = _normalize_symbol(symbol)
    if source == "sina":
        url = _SINA_URL.format(code=code)
        h = _HEADERS
    else:
        url = _TENCENT_URL.format(code=code)
        h = {}
    t0 = time.time()
    r = _SESSION.get(url, headers=h, timeout=timeout)
    r.encoding = "gbk"
    m = re.search(r'"([^"]+)"', r.text)
    if not m or not m.group(1):
        raise RuntimeError(f"实时报价返回空: {symbol} ({r.text[:80]})")
    fields = m.group(1).split(",")
    if source == "sina" and len(fields) >= 19:
        return {
            "source": "sina",
            "symbol": f"{code}.HK",
            "name_en": fields[0],
            "name": fields[1],
            "prev_close": float(fields[2]),
            "open": float(fields[3]),
            "high": float(fields[4]),
            "low": float(fields[5]),
            "last": float(fields[6]),
            "change": float(fields[7]),
            "change_pct": float(fields[8]),
            "bid": float(fields[9]) if fields[9] else 0.0,
            "ask": float(fields[10]) if fields[10] else 0.0,
            "amount": float(fields[11]) if fields[11] else 0.0,
            "volume": float(fields[12]) if fields[12] else 0.0,
            "date": fields[17],
            "time": fields[18],
            "latency_ms": int((time.time() - t0) * 1000),
        }
    elif source == "tencent" and len(fields) >= 30:
        return {
            "source": "tencent",
            "symbol": f"{code}.HK",
            "name": fields[1],
            "prev_close": float(fields[4]),
            "open": float(fields[5]),
            "high": float(fields[33]) if len(fields) > 33 else 0.0,
            "low": float(fields[34]) if len(fields) > 34 else 0.0,
            "last": float(fields[3]),
            "change": float(fields[31]) if len(fields) > 31 else 0.0,
            "change_pct": float(fields[32]) if len(fields) > 32 else 0.0,
            "volume": float(fields[36]) if len(fields) > 36 else 0.0,
            "amount": float(fields[37]) if len(fields) > 37 else 0.0,
            "datetime": fields[30] if len(fields) > 30 else "",
            "latency_ms": int((time.time() - t0) * 1000),
        }
    raise RuntimeError(f"字段数不足: {symbol} source={source} fields={len(fields)}")


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "0700.HK"
    print(f"== 测试 {sym} 实时报价 ==")
    for src in ["sina", "tencent"]:
        try:
            q = fetch_realtime(sym, source=src)
            print(f"\n[{src}] 延时 {q['latency_ms']}ms")
            for k in ["symbol", "name", "last", "change", "change_pct",
                     "high", "low", "prev_close", "open", "volume", "amount",
                     "date", "time" if src == "sina" else "datetime"]:
                if k in q:
                    print(f"  {k:<14} {q[k]}")
        except Exception as e:
            print(f"[{src}] ERR: {e}")
