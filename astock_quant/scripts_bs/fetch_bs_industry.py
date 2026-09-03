"""行业分类（一次性全量拉取）。

注意：baostock 的 query_stock_industry 返回的是**当前快照**（带 updateDate），
不是 point-in-time 的历史归属。行业归属变动极少，但这仍是一处未来信息，
用到它的策略（s08 行业中性化、s13 注意力向量）必须在报告里标注。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data_bs", "industry.csv")


def main():
    import baostock as bs
    bs.login()
    rs = bs.query_stock_industry()
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    bs.logout()
    df = pd.DataFrame(rows, columns=rs.fields)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} 条 -> {OUT}", flush=True)
    print("分类体系:", df["industryClassification"].value_counts().to_dict(), flush=True)
    print("行业数:", df["industry"].nunique(), flush=True)
    print(df["industry"].value_counts().head(8).to_dict(), flush=True)


if __name__ == "__main__":
    main()
