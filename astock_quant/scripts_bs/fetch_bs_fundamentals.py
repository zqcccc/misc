"""PIT 财报：带**公告日**的季度盈利数据（totalShare / roeAvg / netProfit）。

上一版有个真 bug：把 baostock 的错误码当成「这家公司没数据」静默跳过，
限流全被吞掉，5470 只里只有 707 只拿到了内容（茅台、平安、宁德都是空的）。
这一版：
  1. error_code != '0' 视为失败，退避重试，重试耗尽才记 err；
  2. 只有确认「服务器正常响应但该季度无数据」才跳过；
  3. 只拉 profit（40 次/只），不拉 dupont（原来 92 次/只把服务打挂了）；
  4. 空结果不落盘，避免把失败固化成「已完成」。

字段：pubDate（公告日）statDate（报告期）roeAvg netProfit epsTTM totalShare liqaShare
  - totalShare → 总市值 = 不复权收盘价 × 该日**已公告**的最新总股本
  - roeAvg     → 搅屎棍选股层的 ROE > 0.15

用法：python3 scripts_bs/fetch_bs_fundamentals.py --workers 3   # 可中断续跑
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BS_DIR = os.path.join(BASE, "data_bs")
FUND_DIR = os.path.join(BS_DIR, "fundamentals")
QUARTERS = [(y, q) for y in range(2017, 2027) for q in (1, 2, 3, 4)]
MAX_RETRY = 5


def _path(code: str) -> str:
    return os.path.join(FUND_DIR, code.replace(".", "_") + ".csv")


def _query(bs, code, y, q):
    """返回 (rows, ok)。ok=False 表示服务端出错（需要重试），不是「无数据」。"""
    rs = bs.query_profit_data(code=code, year=y, quarter=q)
    if rs.error_code != "0":
        return [], False
    rows = []
    while rs.next():
        rows.append(dict(zip(rs.fields, rs.get_row_data())))
    return rows, True


def _worker(args) -> tuple[int, int, int]:
    codes, wid = args
    import baostock as bs
    bs.login()
    ok = skip = err = 0
    for n, code in enumerate(codes):
        if os.path.exists(_path(code)):
            skip += 1
            continue
        rows, failed = [], False
        for y, q in QUARTERS:
            for attempt in range(MAX_RETRY):
                try:
                    r, good = _query(bs, code, y, q)
                    if good:
                        rows.extend(r)
                        break
                except Exception:
                    good = False
                time.sleep(min(1.0 * (2 ** attempt), 20.0) + random.random())
                try:
                    bs.logout()
                except Exception:
                    pass
                try:
                    bs.login()
                except Exception:
                    pass
            else:
                failed = True
                break
        if failed or not rows:
            err += 1                       # 不落盘，下次续跑会重试
            continue
        pd.DataFrame(rows).to_csv(_path(code), index=False)
        ok += 1
        if wid == 0 and (n + 1) % 50 == 0:
            print(f"  worker0 {n + 1}/{len(codes)}  ok={ok} err={err}", flush=True)
    bs.logout()
    return ok, skip, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(FUND_DIR, exist_ok=True)
    univ = pd.read_csv(os.path.join(BS_DIR, "universe.csv"))
    codes = univ["code"].tolist()
    todo = [c for c in codes if not os.path.exists(_path(c))]
    print(f"宇宙 {len(codes)} 只，待抓 {len(todo)} 只 × {len(QUARTERS)} 季度，"
          f"{args.workers} 进程", flush=True)
    t0 = time.time()
    chunks = [(todo[i::args.workers], i) for i in range(args.workers)]
    with Pool(args.workers) as pool:
        res = pool.map(_worker, chunks)
    ok, skip, err = (sum(r[i] for r in res) for i in range(3))
    print(f"完成：新抓 {ok}，跳过 {skip}，**失败 {err}（未落盘，重跑本脚本会续）**，"
          f"耗时 {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
