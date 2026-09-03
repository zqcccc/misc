"""补齐平台策略真正需要的数据：日频换手率 / PIT ST 标志 / 真实成交额 / 不复权价。

为什么要这一步：上一轮用「20 日均成交额」代理总市值、用「成交额前 N 名」代理指数成分股，
跑出来的不是原策略，是另一条策略。本脚本从 baostock 取回真实字段：

  turn（换手率%）  → 流通股本 = volume / (turn/100) → 流通市值 = 流通股本 × 不复权收盘价
  isST             → PIT 的 ST 标志（替掉「过去 60 日涨跌幅上限反推」的启发式）
  amount           → 真实成交额（替掉「成交量 × 收盘价」的估算）
  tradestatus      → 停牌标志

宇宙用 query_stock_basic() 全量枚举，含 337 只已退市股票，不产生幸存者偏差。

用法：python3 scripts_bs/fetch_bs_daily.py --workers 8        # 可中断续跑
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BS_DIR = os.path.join(BASE, "data_bs")
DAILY_DIR = os.path.join(BS_DIR, "daily")
UNIV_CSV = os.path.join(BS_DIR, "universe.csv")
START, END = "2015-01-01", "2026-09-02"
FIELDS = "date,close,volume,amount,turn,pctChg,isST,tradestatus"


def build_universe() -> pd.DataFrame:
    import baostock as bs
    bs.login()
    rs = bs.query_stock_basic()
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    bs.logout()
    df = pd.DataFrame(rows, columns=rs.fields)
    df = df[df["type"] == "1"]                              # 1 = 股票
    df = df[~df["code"].str.startswith("bj.")]              # 北交所不在本项目范围
    ipo = pd.to_datetime(df["ipoDate"], errors="coerce")
    out = pd.to_datetime(df["outDate"], errors="coerce")
    keep = (ipo <= pd.Timestamp(END)) & (out.isna() | (out >= pd.Timestamp(START)))
    df = df[keep].copy()
    df.to_csv(UNIV_CSV, index=False)
    return df


def _path(code: str) -> str:
    return os.path.join(DAILY_DIR, code.replace(".", "_") + ".csv")


def _worker(codes: list[str]) -> tuple[int, int, int]:
    import baostock as bs
    bs.login()
    ok = skip = err = 0
    for code in codes:
        p = _path(code)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            skip += 1
            continue
        for attempt in range(4):
            try:
                rs = bs.query_history_k_data_plus(
                    code, FIELDS, start_date=START, end_date=END,
                    frequency="d", adjustflag="3")          # 3 = 不复权
                if rs.error_code != "0":
                    raise RuntimeError(rs.error_msg)
                rows = []
                while rs.next():
                    rows.append(rs.get_row_data())
                pd.DataFrame(rows, columns=rs.fields).to_csv(p, index=False)
                ok += 1
                break
            except Exception:
                time.sleep(1.5 * (attempt + 1))
                try:
                    bs.logout()
                except Exception:
                    pass
                bs.login()
        else:
            err += 1
    bs.logout()
    return ok, skip, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--refresh-universe", action="store_true")
    args = ap.parse_args()
    os.makedirs(DAILY_DIR, exist_ok=True)

    if args.refresh_universe or not os.path.exists(UNIV_CSV):
        print("枚举全市场（含退市股）...", flush=True)
        univ = build_universe()
    else:
        univ = pd.read_csv(UNIV_CSV)
    codes = univ["code"].tolist()
    todo = [c for c in codes if not (os.path.exists(_path(c)) and os.path.getsize(_path(c)) > 0)]
    print(f"宇宙 {len(codes)} 只（已退市 {(univ['status'].astype(str) == '0').sum()} 只），"
          f"待下载 {len(todo)} 只，{args.workers} 进程", flush=True)

    t0 = time.time()
    chunks = [todo[i::args.workers] for i in range(args.workers)]
    with Pool(args.workers) as pool:
        res = pool.map(_worker, chunks)
    ok = sum(r[0] for r in res); skip = sum(r[1] for r in res); err = sum(r[2] for r in res)
    print(f"完成：新下载 {ok}，跳过 {skip}，失败 {err}，耗时 {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
