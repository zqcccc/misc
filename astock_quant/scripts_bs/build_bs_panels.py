"""把 baostock 的逐股 CSV 拼成宽表面板，对齐到既有的交易日历与代码空间。

产出的每个字段都是「当日收盘后可知」的量：
  turn          当日换手率(%)
  is_st         当日是否 ST（PIT，交易所口径）
  amount_bs     当日真实成交额(元)  —— 替掉原来「成交量×收盘价」的估算
  close_raw_bs  不复权收盘价
  float_shares  流通股本 = 成交量 / (换手率/100)，停牌日按上一有效值前向填充
  float_mktcap  流通市值 = 流通股本 × 不复权收盘价

前向填充只用过去的值，不含未来；股本是缓慢变化的状态量，ffill 是正确的做法。

用法：python3 scripts_bs/build_bs_panels.py
产物：data/panel_bs/*.parquet + data_bs/qa_report.json
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import config, panel  # noqa: E402

BASE = config.BASE_DIR
DAILY_DIR = os.path.join(BASE, "data_bs", "daily")
OUT_DIR = os.path.join(BASE, "data", "panel_bs")
QA = os.path.join(BASE, "data_bs", "qa_report.json")

# 流通股本的离群保护：换手率极小时 volume/turn 会炸，用中位数做上下限
SHARE_REL_BOUND = 5.0


def code_from_path(p: str) -> str:
    return os.path.basename(p)[:-4].replace("_", "")     # sh_600000.csv -> sh600000


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ref = panel.load_panels(["close", "close_raw"])
    dates = ref["close"].index
    cols = list(ref["close"].columns)
    colset = set(cols)

    files = sorted(glob.glob(os.path.join(DAILY_DIR, "*.csv")))
    print(f"读取 {len(files)} 个 baostock 日线文件，对齐到 {len(dates)} 个交易日 × {len(cols)} 只",
          flush=True)

    series = {k: {} for k in ("turn", "is_st", "amount_bs", "close_raw_bs", "volume_bs")}
    extra_codes = 0
    for i, f in enumerate(files):
        code = code_from_path(f)
        if code not in colset:
            extra_codes += 1
            continue
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if df.empty or "date" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates(subset="date").set_index("date")
        num = lambda c: pd.to_numeric(df[c], errors="coerce")   # noqa: E731
        halted = pd.to_numeric(df.get("tradestatus"), errors="coerce") != 1
        series["turn"][code] = num("turn").mask(halted)
        series["is_st"][code] = pd.to_numeric(df.get("isST"), errors="coerce")
        series["amount_bs"][code] = num("amount").mask(halted)
        series["close_raw_bs"][code] = num("close")
        series["volume_bs"][code] = num("volume").mask(halted)
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(files)}", flush=True)

    panels = {}
    for k, d in series.items():
        df = pd.DataFrame(d)
        df.index = pd.to_datetime(df.index)
        panels[k] = df.sort_index().reindex(index=dates, columns=cols).astype(np.float32)

    # 流通股本：换手率是 %，volume 是股
    turn = panels["turn"].replace(0.0, np.nan)
    shares = panels["volume_bs"] / (turn / 100.0)
    med = shares.median(axis=0)
    lo, hi = med / SHARE_REL_BOUND, med * SHARE_REL_BOUND
    shares = shares.where((shares.ge(lo, axis=1)) & (shares.le(hi, axis=1)))
    shares = shares.ffill()                       # 只向后填，不含未来
    panels["float_shares"] = shares.astype(np.float32)
    panels["float_mktcap"] = (shares * panels["close_raw_bs"]).astype(np.float32)

    for k, df in panels.items():
        out = df.copy()
        out.index.name = "date"
        out.to_parquet(os.path.join(OUT_DIR, f"{k}.parquet"))

    # ---------------- 数据质量核对 ----------------
    tx_ret = ref["close"] / ref["close"].shift(1) - 1.0            # 腾讯后复权日收益
    bs_ret = panels["close_raw_bs"] / panels["close_raw_bs"].shift(1) - 1.0
    both = tx_ret.notna() & bs_ret.notna()
    diff = (tx_ret - bs_ret).abs().where(both)
    # 除权日两边会不一致（一个复权一个不复权），只看不含除权的绝大多数日子
    agree = float((diff < 0.005).sum().sum() / both.sum().sum())
    cov = float(panels["float_mktcap"].notna().sum().sum() / ref["close"].notna().sum().sum())
    mc = panels["float_mktcap"]
    qa = {
        "对齐后股票数": int(panels["turn"].notna().any().sum()),
        "baostock 独有(不在腾讯面板)": extra_codes,
        "流通市值覆盖率(占腾讯有K线的格子)": round(cov, 4),
        "两源日收益一致率(<0.5%)": round(agree, 4),
        "ST 标记的股票-日占比": round(float(
            (panels["is_st"] == 1).sum().sum() / panels["is_st"].notna().sum().sum()), 4),
        "流通市值中位数(亿元)_2019": round(float(
            mc.loc["2019"].stack().median() / 1e8), 2),
        "流通市值中位数(亿元)_2026": round(float(
            mc.loc["2026"].stack().median() / 1e8), 2),
    }
    json.dump(qa, open(QA, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(qa, ensure_ascii=False, indent=1), flush=True)
    print(f"已写 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
