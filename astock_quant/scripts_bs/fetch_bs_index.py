"""PIT 指数成分股：沪深300 / 中证500（中证800 = 两者并集）。

上一轮用「20 日均成交额前 800 名」代理中证800，那不是原策略的股票池。
baostock 的 query_hs300_stocks(date) / query_zz500_stocks(date) 返回的是
「截至该日最近一次调样后的成分股」，正是 point-in-time 的定义。

指数半年调样一次（6 月、12 月），按月取一次快照再向后填充即可，不会漏掉调样。
用法：python3 scripts_bs/fetch_bs_index.py
产物：data_bs/index_members.csv （date, index, code）
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data_bs", "index_members.csv")


def main():
    import baostock as bs
    bs.login()
    dates = pd.date_range("2015-01-01", "2026-09-02", freq="MS").strftime("%Y-%m-%d")
    rows = []
    t0 = time.time()
    for i, d in enumerate(dates):
        for name, fn in (("hs300", bs.query_hs300_stocks), ("zz500", bs.query_zz500_stocks)):
            rs = fn(date=d)
            n = 0
            while rs.error_code == "0" and rs.next():
                r = rs.get_row_data()
                rows.append({"date": d, "index": name, "updateDate": r[0], "code": r[1]})
                n += 1
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(dates)}  累计 {len(rows)} 行  {time.time() - t0:.0f}s", flush=True)
    bs.logout()
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"完成：{len(df)} 行，{df['date'].nunique()} 个快照日 -> {OUT}", flush=True)
    print(df.groupby("index")["code"].nunique().to_dict(), flush=True)


if __name__ == "__main__":
    main()
