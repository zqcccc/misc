"""行情数据源：腾讯财经日线（后复权 + 不复权）。

选它的原因：
  1. 东方财富接口在本机网络下返回空包，网易 chddata 常年 502，新浪只有当前
     快照列表；腾讯 fqkline 稳定且**保留已退市股票的历史**（如 sh600005 武钢
     股份数据止于 2017-01-23），这是构造无幸存者偏差股票池的前提。
  2. hfq（后复权）序列在新的分红送转发生时不会改写历史价位，而 qfq（前复权）
     会。用 qfq 做回测，历史价格会随未来分红被重写 —— 这是一种隐蔽的未来函数。
     本项目一律用 hfq 计算收益与因子，用不复权价还原成交额。

接口返回字段：[日期, 开, 收, 高, 低, 成交量(手)]
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd

from . import config

# 多个镜像域名轮换：单域名高频请求会被腾讯边缘节点限流（返回 HTTP 501），
# 轮换 + 指数退避后可稳定跑完全市场
HOSTS = [
    "https://ifzq.gtimg.cn/appstock/app/fqkline/get",
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get",
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
MAX_BARS = 800          # 单次请求上限，实测 800 可用、>800 报 param error
COLUMNS = ["date", "open", "close", "high", "low", "volume"]


def _http_json(path_qs: str, retries: int = 8, timeout: int = 20):
    """path_qs 是 query string，域名由 HOSTS 轮换选取。"""
    last = None
    start = random.randrange(len(HOSTS))
    for i in range(retries):
        host = HOSTS[(start + i) % len(HOSTS)]
        try:
            req = urllib.request.Request(host + path_qs, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except Exception as exc:  # noqa: BLE001 - 网络异常统一退避重试
            last = exc
            # 501/限流：指数退避，最长 ~13s
            time.sleep(min(0.5 * (2 ** i), 10.0) + random.random() * 0.5)
    raise RuntimeError(f"request failed: {path_qs} ({last})")


def fetch_chunk(code: str, end: str, count: int = MAX_BARS, fq: str = "hfq"):
    """取 code 在 end 之前（含）最多 count 根日线。返回 (bars, name)。

    腾讯的语义是"以 end 为右端点往前取 count 根"，start 参数几乎不起作用，
    所以历史要靠不断把 end 往前挪来分段拼接。
    """
    qs = (f"?param={code},day,{config.DATA_START},{end},{count},{fq}"
          f"&_var=&r={random.random():.6f}")
    data = _http_json(qs)
    node = (data or {}).get("data", {}).get(code)
    if not isinstance(node, dict):
        return [], None
    bars = node.get(f"{fq}day") or node.get("day") or []
    name = None
    qt = node.get("qt")
    if isinstance(qt, dict) and code in qt and len(qt[code]) > 1:
        name = qt[code][1]
    return bars, name


def _prev_day(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def fetch_history(code: str, fq: str = "hfq",
                  start: str = None, end: str = None) -> tuple[pd.DataFrame, str | None]:
    """分段回溯拼出 [start, end] 的完整日线。"""
    start = start or config.DATA_START
    end = end or config.DATA_END
    cursor, frames, name = end, [], None
    for _ in range(30):  # 30 * 800 根足够覆盖任何 A 股历史
        bars, nm = fetch_chunk(code, cursor, MAX_BARS, fq)
        name = name or nm
        if not bars:
            break
        frames.append(bars)
        first = bars[0][0]
        if first <= start or len(bars) < MAX_BARS:
            break
        cursor = _prev_day(first)
    if not frames:
        return pd.DataFrame(columns=COLUMNS), name
    rows = [b[:6] for chunk in frames for b in chunk]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df.drop_duplicates(subset="date").sort_values("date")
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    for c in COLUMNS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.reset_index(drop=True), name


# ------------------------------------------------------------------ 本地缓存
def _path(code: str, fq: str) -> str:
    d = config.KLINE_HFQ_DIR if fq == "hfq" else config.KLINE_RAW_DIR
    return os.path.join(d, f"{code}.csv")


def load_local(code: str, fq: str = "hfq") -> pd.DataFrame | None:
    p = _path(code, fq)
    if not os.path.exists(p):
        return None
    return pd.read_csv(p)


def save_local(code: str, df: pd.DataFrame, fq: str = "hfq") -> None:
    df.to_csv(_path(code, fq), index=False)


def download(code: str, fq: str = "hfq", force: bool = False) -> pd.DataFrame:
    if not force:
        cached = load_local(code, fq)
        if cached is not None:
            return cached
    df, _ = fetch_history(code, fq)
    if not df.empty:
        save_local(code, df, fq)
    return df


# ------------------------------------------------------------------ 代码空间
def candidate_codes() -> list[str]:
    """穷举沪深 A 股代码空间。

    不用"当前上市列表"是刻意为之：那样会天然剔除所有已退市公司，回测结果被
    幸存者偏差抬高。逐段扫描代码空间可以把退市股一并捞回来。
    """
    out = []
    for lo, hi in [(600000, 602000), (603000, 604000), (605000, 606000),
                   (688000, 689000), (689000, 689100)]:
        out += [f"sh{i:06d}" for i in range(lo, hi)]
    for lo, hi in [(1, 4000), (300000, 303000)]:
        out += [f"sz{i:06d}" for i in range(lo, hi)]
    return out


def is_tradable_board(code: str) -> bool:
    num = code[2:]
    if code.startswith("sh"):
        return num.startswith(("600", "601", "603", "605", "688", "689"))
    return num.startswith(("000", "001", "002", "003", "300", "301"))
