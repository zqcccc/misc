"""
A股量化策略数据源模块
负责从 本地缓存 / yfinance 读取或下载 A 股日线数据，标准化并缓存到本地。
"""

import os
import time
import pandas as pd
import numpy as np
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 核心赛道白马与主线成长龙头池 (涵盖各核心赛道领袖) + 基准 510300.SS
UNIVERSE = {
    "600519.SS": "贵州茅台",
    "300750.SZ": "宁德时代",
    "002594.SZ": "比亚迪",
    "601088.SS": "中国神华",
    "600900.SS": "长江电力",
    "600036.SS": "招商银行",
    "601899.SS": "紫金矿业",
    "002475.SZ": "立讯精密",
    "300308.SZ": "中际旭创",
    "002371.SZ": "北方华创",
    "601127.SS": "赛力斯",
    "300274.SZ": "阳光电源",
    "600276.SS": "恒瑞医药",
    "600690.SS": "海尔智家",
    "600309.SS": "万华化学",
}

BENCHMARK_SYMBOL = "510300.SS"
BENCHMARK_NAME = "沪深300ETF"


def get_cache_path(symbol: str) -> str:
    clean_sym = symbol.replace(".", "_")
    return os.path.join(CACHE_DIR, f"{clean_sym}.csv")


def fetch_symbol_daily(symbol: str, start: str = "2018-01-01", end: str = "2026-03-01", force: bool = False) -> pd.DataFrame:
    cache_file = get_cache_path(symbol)
    if not force and os.path.exists(cache_file) and os.path.getsize(cache_file) > 1024:
        df = pd.read_csv(cache_file)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
        return df

    print(f"[data_feed] 从 yfinance 下载 {symbol} ({start} ~ {end})...", flush=True)
    last_err = None
    for attempt in range(3):
        try:
            raw = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
            if raw is not None and len(raw) > 50:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = [c[0].lower() for c in raw.columns]
                else:
                    raw.columns = [c.lower() for c in raw.columns]

                raw = raw.reset_index()
                date_col = next((c for c in raw.columns if "date" in c.lower()), raw.columns[0])
                raw = raw.rename(columns={date_col: "date"})
                raw["date"] = pd.to_datetime(raw["date"]).dt.tz_localize(None)

                cols = ["date", "open", "high", "low", "close", "volume"]
                raw = raw[[c for c in cols if c in raw.columns]].dropna()
                raw = raw.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

                raw.to_csv(cache_file, index=False)
                return raw
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"拉取 {symbol} 失败: {last_err}")


def load_all_universe(start: str = "2018-01-01", end: str = "2026-03-01", force: bool = False) -> dict[str, pd.DataFrame]:
    all_symbols = list(UNIVERSE.keys()) + [BENCHMARK_SYMBOL]
    data_map = {}
    for sym in all_symbols:
        df = fetch_symbol_daily(sym, start=start, end=end, force=force)
        data_map[sym] = df
    return data_map
