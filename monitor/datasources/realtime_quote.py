"""
港股实时报价适配器 (盘中实时, 非 K 线数据源).
用于在 daemon 主循环中补充"未到收盘"的现价探针.

支持三个公开免费源 (按推荐顺序):
  - sina       新浪 hq.sinajs.cn       (40ms, GBK, 逗号分隔)
  - tencent    腾讯 qt.gtimg.cn        (250ms, GBK, ~ 分隔, 78 字段)
  - eastmoney  东方财富 push2.eastmoney.com (JSON, 字段前缀 f43/f44/...)

均为国内 API, 不应走系统代理. 用 trust_env=False 的 Session 屏蔽
HTTPS_PROXY/HTTP_PROXY 环境变量, 避免 daemon 继承父 shell 失效代理端口
(如 127.0.0.1:57076).
"""
import re
import time
import requests

_SINA_URL = "https://hq.sinajs.cn/list=hk{code}"
_TENCENT_URL = "https://qt.gtimg.cn/q=hk{code}"
_EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/stock/get?secid=116.{code}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f170"
_SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}

_SESSION = requests.Session()
_SESSION.trust_env = False


def _normalize_symbol(symbol):
    """支持 0700.HK / 00700.HK / 00700 全写法 → 5 位代码 (00700)."""
    s = str(symbol).upper().replace(".HK", "").replace("-", "")
    while s.startswith("0") and len(s) > 5:
        s = s[1:]
    s = s.zfill(5)
    return s


def _parse_sina(text, code, t0):
    m = re.search(r'"([^"]+)"', text)
    if not m or not m.group(1):
        raise RuntimeError(f"sina 返回空: {text[:80]}")
    f = m.group(1).split(",")
    if len(f) < 19:
        raise RuntimeError(f"sina 字段不足: {len(f)}")
    return {
        "source": "sina",
        "symbol": f"{code}.HK",
        "name_en": f[0], "name": f[1],
        "prev_close": float(f[2]), "open": float(f[3]),
        "high": float(f[4]), "low": float(f[5]),
        "last": float(f[6]),
        "change": float(f[7]), "change_pct": float(f[8]),
        "bid": float(f[9]) if f[9] else 0.0,
        "ask": float(f[10]) if f[10] else 0.0,
        "amount": float(f[11]) if f[11] else 0.0,
        "volume": float(f[12]) if f[12] else 0.0,
        "date": f[17], "time": f[18],
        "latency_ms": int((time.time() - t0) * 1000),
    }


def _parse_tencent(text, code, t0):
    """腾讯接口字段用 ~ 分隔 (不是逗号), 共 78 字段."""
    m = re.search(r'"([^"]+)"', text)
    if not m or not m.group(1):
        raise RuntimeError(f"tencent 返回空: {text[:80]}")
    f = m.group(1).split("~")
    if len(f) < 35:
        raise RuntimeError(f"tencent 字段不足: {len(f)}")
    def _num(idx):
        try: return float(f[idx]) if f[idx] else 0.0
        except (ValueError, IndexError): return 0.0
    return {
        "source": "tencent",
        "symbol": f"{code}.HK",
        "name": f[1],
        "prev_close": _num(4), "open": _num(5),
        "high": _num(33), "low": _num(34),
        "last": _num(3),
        "change": _num(31), "change_pct": _num(32),
        "volume": _num(36), "amount": _num(37),
        "datetime": f[30] if len(f) > 30 else "",
        "latency_ms": int((time.time() - t0) * 1000),
    }


def _parse_eastmoney(text, code, t0):
    """东方财富 push2 接口, JSON 格式. 港股 secid 前缀 116.
    价格字段需 / 100, 涨跌幅字段 / 100."""
    import json
    try:
        obj = json.loads(text)
    except Exception as e:
        raise RuntimeError(f"eastmoney JSON 解析失败: {e}; body={text[:80]}")
    d = obj.get("data") or {}
    if not d:
        raise RuntimeError(f"eastmoney 数据为空: {obj}")
    def _price(k):
        v = d.get(k)
        return float(v) / 100.0 if v is not None else 0.0
    return {
        "source": "eastmoney",
        "symbol": f"{code}.HK",
        "name": d.get("f58", ""),
        "prev_close": _price("f60"), "open": _price("f46"),
        "high": _price("f44"), "low": _price("f45"),
        "last": _price("f43"),
        "change_pct": _price("f170"),
        "volume": float(d.get("f47") or 0),
        "amount": float(d.get("f48") or 0),
        "latency_ms": int((time.time() - t0) * 1000),
    }


_PARSERS = {
    "sina": (_SINA_URL, _SINA_HEADERS, _parse_sina),
    "tencent": (_TENCENT_URL, {}, _parse_tencent),
    "eastmoney": (_EASTMONEY_URL, {}, _parse_eastmoney),
}


def fetch_realtime(symbol, source="sina", timeout=5):
    """返回 dict: source/symbol/name/last/change/change_pct/high/low/...
    source: sina (默认) / tencent / eastmoney.
    失败抛 RuntimeError."""
    if source not in _PARSERS:
        raise ValueError(f"未知 realtime 源: {source!r}, 可选: {list(_PARSERS)}")
    code = _normalize_symbol(symbol)
    url, headers, parser = _PARSERS[source]
    url = url.format(code=code)
    t0 = time.time()
    r = _SESSION.get(url, headers=headers, timeout=timeout)
    r.encoding = "gbk"
    return parser(r.text, code, t0)


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "0700.HK"
    print(f"== 测试 {sym} 实时报价 ==")
    for src in ["sina", "tencent", "eastmoney"]:
        try:
            q = fetch_realtime(sym, source=src)
            print(f"\n[{src}] 延时 {q['latency_ms']}ms")
            for k in ["symbol", "name", "last", "change_pct",
                     "high", "low", "prev_close", "open", "volume", "amount",
                     "date", "time", "datetime"]:
                if k in q:
                    print(f"  {k:<14} {q[k]}")
        except Exception as e:
            print(f"[{src}] ERR: {e}")
