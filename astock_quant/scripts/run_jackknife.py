"""逐年剔除稳健性检验：结论是不是靠某一年撑起来的。

用法：python3 scripts/run_jackknife.py
把结果并入 reports/validation.json 的「逐年剔除」字段。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from aq import config, metrics, validate  # noqa: E402


def main():
    wf = json.load(open(os.path.join(config.REPORT_DIR, "walkforward.json")))
    d = pd.to_datetime(wf["净值"]["日期"])
    nav = {k: pd.Series(v, index=d) for k, v in wf["净值"].items() if k != "日期"}
    r = nav["策略"].pct_change().fillna(0.0)
    ew = nav["等权全A(可投池)"].pct_change().fillna(0.0)
    hs = nav["沪深300"].pct_change().fillna(0.0)

    jk = validate.year_jackknife(r, {"沪深300": hs, "小盘风格": ew - hs})
    print(f"全样本 alpha {jk['全样本alpha'] * 100:.2f}%  t={jk['全样本t']}")
    print("\n剔除年份   剩余 alpha%   t")
    for row in jk["逐年剔除"]:
        print(f"  {row['剔除年份']}      {row['年化alpha'] * 100:8.2f}   {row['alpha_t']:5.2f}")
    print(f"\n最不利：剔除 {jk['最不利年份']} 年后 alpha 只剩 "
          f"{jk['最低alpha'] * 100:.2f}%，t={jk['最低t']}")

    # 逐年超额，看正负年份分布
    yearly = []
    for y in sorted(set(d.year)):
        m = d.year == y
        yearly.append({"年份": int(y),
                       "策略%": round(float((1 + r[m]).prod() - 1) * 100, 2),
                       "等权全A%": round(float((1 + ew[m]).prod() - 1) * 100, 2),
                       "超额%": round(float((1 + r[m]).prod() - (1 + ew[m]).prod()) * 100, 2)})
    pos = sum(1 for x in yearly if x["超额%"] > 0)
    print(f"超额为正的年份：{pos}/{len(yearly)}")

    vp = os.path.join(config.REPORT_DIR, "validation.json")
    va = json.load(open(vp))
    va["逐年剔除"] = jk
    va["逐年超额"] = {"明细": yearly, "正年数": pos, "总年数": len(yearly)}
    with open(vp, "w") as f:
        json.dump(va, f, ensure_ascii=False, indent=1)
    print(f"已并入 {vp}")


if __name__ == "__main__":
    main()
