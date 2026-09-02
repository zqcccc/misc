"""
全量刷新股票池日线数据至最新日期 (2026-09-02)
"""

import os
import time
import pandas as pd
import yfinance as yf
from scripts.ashare_quant.data_feed import UNIVERSE, BENCHMARK_SYMBOL, CACHE_DIR, get_cache_path

all_symbols = list(UNIVERSE.keys()) + [BENCHMARK_SYMBOL]

print(f"正在全量刷新 {len(all_symbols)} 只标的数据至 2026-09-02...")
for sym in all_symbols:
    p = get_cache_path(sym)
    print(f"-> 刷新 {sym} ({UNIVERSE.get(sym, '基准')})...", end=" ", flush=True)
    success = False
    for attempt in range(3):
        try:
            raw = yf.download(sym, start="2018-01-01", end="2026-09-05", auto_adjust=True, progress=False)
            if raw is not None and len(raw) > 50:
                if hasattr(raw.columns, "levels"):
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

                raw.to_csv(p, index=False)
                last_dt = raw["date"].iloc[-1].strftime("%Y-%m-%d")
                print(f"完成! 共 {len(raw)} 根K线, 最新日期: {last_dt}")
                success = True
                break
        except Exception as e:
            time.sleep(1)
    if not success:
        print(f"失败!")

print("全部标的最新数据刷新完成!")
