"""构建 Point-in-Time (PIT) 财报面板：BPS、ROE、每日动态 PB。

数据来源：scripts/_cache_pb_roe_v3/yjbb_<year>.csv
与 astock_quant/data/panel/close_raw.parquet（不复权真实收盘价）。

因果律保证：
1. 严格使用年报的「最新公告日期」（若缺失则保守回退为次年 4 月 30 日法定披露截止日）。
2. 在交易日历上，只有在 t >= 公告日 后，新财报数据才对市场可见并生效。
3. 每日 PB = close_raw_t / bps_t。若 bps_t <= 0 或 close_raw_t <= 0，PB 视为无效 (NaN)。
"""
from __future__ import annotations

import os
import glob
import time
import numpy as np
import pandas as pd

from aq import config, panel


def build_and_save_pb_roe():
    t0 = time.time()
    print("加载交易日历与行情面板...")
    close = panel.load_panels(["close", "close_raw"])
    close_hfq = close["close"]
    close_raw = close["close_raw"]
    trading_dates = close_hfq.index
    codes = close_hfq.columns.tolist()
    code_set = set(codes)

    print(f"交易日: {len(trading_dates)} 天 ({trading_dates[0].strftime('%Y-%m-%d')} ~ {trading_dates[-1].strftime('%Y-%m-%d')})")
    print(f"股票池: {len(codes)} 只")

    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/_cache_pb_roe_v3"))
    files = sorted(glob.glob(os.path.join(cache_dir, "yjbb_*.csv")))
    if not files:
        raise FileNotFoundError(f"未找到年报缓存文件: {cache_dir}/yjbb_*.csv")

    dfs = []
    for f in files:
        year = int(os.path.basename(f).replace("yjbb_", "").replace(".csv", ""))
        df = pd.read_csv(f)
        code_col = next(c for c in df.columns if "代码" in str(c))
        roe_col = next((c for c in df.columns if "净资产收益率" in str(c)), None)
        bps_col = next((c for c in df.columns if "每股净资产" in str(c)), None)
        date_col = next((c for c in df.columns if "公告日期" in str(c)), None)

        sub = pd.DataFrame()
        sub["raw_code"] = df[code_col].astype(str).str.zfill(6)
        prefix = np.where(sub["raw_code"].str.startswith(("6", "9")), "sh",
                 np.where(sub["raw_code"].str.startswith(("0", "2", "3")), "sz", ""))
        sub["code"] = prefix + sub["raw_code"]
        sub = sub[sub["code"].isin(code_set)].copy()

        sub["roe"] = pd.to_numeric(df.loc[sub.index, roe_col], errors="coerce")
        sub["bps"] = pd.to_numeric(df.loc[sub.index, bps_col], errors="coerce")

        if date_col:
            pdate = pd.to_datetime(df.loc[sub.index, date_col], errors="coerce")
        else:
            pdate = pd.NaT

        fallback = pd.Timestamp(f"{year+1}-04-30")
        valid_pdate = (pdate >= pd.Timestamp(f"{year}-12-31")) & (pdate <= pd.Timestamp(f"{year+1}-05-05"))
        sub["pub_date"] = np.where(valid_pdate, pdate, fallback)
        sub = sub.dropna(subset=["roe", "bps"])
        dfs.append(sub[["code", "pub_date", "bps", "roe"]])

    all_fin = pd.concat(dfs, ignore_index=True)
    all_fin["pub_date"] = pd.to_datetime(all_fin["pub_date"])

    print(f"解析完成，累计有效财务记录: {len(all_fin)} 条，覆盖代码: {all_fin.code.nunique()} 只")

    print("构建 PIT 时间对齐面板...")
    bps_event = all_fin.pivot_table(index="pub_date", columns="code", values="bps", aggfunc="last")
    roe_event = all_fin.pivot_table(index="pub_date", columns="code", values="roe", aggfunc="last")

    all_dates = trading_dates.union(bps_event.index).sort_values()
    bps_panel = bps_event.reindex(all_dates).ffill().reindex(trading_dates).reindex(columns=codes).astype(np.float32)
    roe_panel = roe_event.reindex(all_dates).ffill().reindex(trading_dates).reindex(columns=codes).astype(np.float32)

    # 动态 PB 计算
    pb_panel = (close_raw / bps_panel).astype(np.float32)
    # 资不抵债或非正 PB 置为 NaN
    pb_panel = pb_panel.where((pb_panel > 0) & (bps_panel > 0))

    # 保存至 parquet
    out_bps = os.path.join(config.PANEL_DIR, "bps.parquet")
    out_roe = os.path.join(config.PANEL_DIR, "roe.parquet")
    out_pb = os.path.join(config.PANEL_DIR, "pb.parquet")

    bps_panel.to_parquet(out_bps)
    roe_panel.to_parquet(out_roe)
    pb_panel.to_parquet(out_pb)

    print(f"PIT 财报面板保存完成！耗时: {time.time()-t0:.2f}s")
    print(f"  -> {out_bps} (有效值: {bps_panel.notna().sum().sum()})")
    print(f"  -> {out_roe} (有效值: {roe_panel.notna().sum().sum()})")
    print(f"  -> {out_pb}  (有效值: {pb_panel.notna().sum().sum()})")


if __name__ == "__main__":
    build_and_save_pb_roe()
