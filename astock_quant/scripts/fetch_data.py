"""全市场日线下载（含已退市股票），支持断点续跑。

用法：python3 scripts/fetch_data.py [--workers 10] [--limit N]
产物：data/kline_hfq/<code>.csv、data/kline_raw/<code>.csv、data/meta.csv
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aq import config, datasource as ds  # noqa: E402

MISSING_FILE = os.path.join(config.DATA_DIR, "missing.txt")
META_FILE = os.path.join(config.DATA_DIR, "meta.csv")
_lock = threading.Lock()


def load_missing() -> set[str]:
    if not os.path.exists(MISSING_FILE):
        return set()
    with open(MISSING_FILE) as f:
        return {ln.strip() for ln in f if ln.strip()}


def mark_missing(code: str) -> None:
    with _lock, open(MISSING_FILE, "a") as f:
        f.write(code + "\n")


def append_meta(row: str) -> None:
    with _lock, open(META_FILE, "a") as f:
        f.write(row + "\n")


def handle(code: str) -> str:
    hfq = ds.load_local(code, "hfq")
    if hfq is None:
        hfq, name = ds.fetch_history(code, "hfq")
        if hfq.empty:
            mark_missing(code)
            return "missing"
        ds.save_local(code, hfq, "hfq")
        append_meta(f"{code},{(name or '').replace(',', '')},"
                    f"{hfq.date.iloc[0]},{hfq.date.iloc[-1]},{len(hfq)}")
    if ds.load_local(code, "raw") is None:
        raw, _ = ds.fetch_history(code, "")
        if not raw.empty:
            ds.save_local(code, raw, "raw")
    return "ok"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not os.path.exists(META_FILE):
        append_meta("code,name,first_date,last_date,bars")

    missing = load_missing()
    codes = [c for c in ds.candidate_codes() if c not in missing]
    codes = [c for c in codes
             if not (os.path.exists(os.path.join(config.KLINE_HFQ_DIR, f"{c}.csv"))
                     and os.path.exists(os.path.join(config.KLINE_RAW_DIR, f"{c}.csv")))]
    if args.limit:
        codes = codes[:args.limit]
    print(f"待处理 {len(codes)} 个代码，{args.workers} 并发", flush=True)

    t0, done, ok = time.time(), 0, 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(handle, c): c for c in codes}
        for fut in as_completed(futs):
            done += 1
            try:
                if fut.result() == "ok":
                    ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[fut]}: {exc}", flush=True)
            if done % 200 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(codes)} 命中 {ok}  {el:.0f}s  "
                      f"eta {el / done * (len(codes) - done) / 60:.1f}min", flush=True)
    print(f"完成：{done} 个代码，命中 {ok}，耗时 {(time.time() - t0) / 60:.1f} 分钟", flush=True)


if __name__ == "__main__":
    main()
