#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
causality_check.py · 未来函数主闸（全量 vs 截断对照）
=====================================================
原理：对同一时点 t，分别用【全量数据】和【只截断到 t 的数据】算一遍策略在 t 的决策。
      两次一致 → 决策前缀稳定；不一致 → 用了未来数据，整份回测作废。

重要边界：本脚本不证明成交可行。即使 `shift(1)` 和前缀检查都通过，策略仍可能把
信号产生前已经发生的 overnight 收益记到自己名下。候选晋级还必须验证
information_time → decision_time → execution_time → pnl_start → pnl_end。

比任何框架自带的 lookahead 检查都可靠，且对横截面策略不误报
（框架自带的检查常把边界那根 K 线的排名变化当成偏差）。

两种模式
--------
single  单标的：func(df) -> Series（每根 K 线一个决策值）
panel   横截面：func({sym: df}) -> {sym: Series}（截断按【日期】统一切）
        横截面策略必须用 panel 模式——单标的模式测不出「用了未来的全池排名/z-score」。

用法
----
  # 单标的：my_strategy.py 里有 def signal(df) -> pd.Series
  python causality_check.py --mode single \
      --fn my_strategy.py:signal --data data/BTCUSDT_4h.csv --points 12

  # 横截面：my_strategy.py 里有 def panel_signal(dfs: dict) -> dict
  python causality_check.py --mode panel \
      --fn my_strategy.py:panel_signal --data-dir data/ --glob "*.csv" --points 12

被测函数的约定
--------------
* 入参是「到目前为止能看到的全部数据」，出参是等长（或同 index）的决策序列。
* 决策序列可以是因子分、目标仓位、或把 enter/exit 几个布尔位打包成的一个数
  （v = 1*enter_long + 2*enter_short + 4*exit_long + 8*exit_short）——
  只要是「这一刻策略要干什么」的完整表达即可。
* 函数内部不许读全局缓存/落盘的中间结果，否则截断跑会偷到全量算好的值。

退出码：0 = PASS，1 = 检出未来函数，2 = 样本不足/无法判定。
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

DATE_COLS = ["date", "datetime", "time", "timestamp", "trade_date"]


def load_fn(spec: str):
    """'path/to/mod.py:func' 或 'pkg.mod:func' → callable"""
    if ":" not in spec:
        sys.exit("[causality] --fn 格式应为 文件.py:函数名 或 包.模块:函数名")
    mod_part, fn_name = spec.rsplit(":", 1)
    if mod_part.endswith(".py"):
        name = os.path.splitext(os.path.basename(mod_part))[0]
        sp = importlib.util.spec_from_file_location(name, mod_part)
        mod = importlib.util.module_from_spec(sp)
        sys.modules[name] = mod
        sp.loader.exec_module(mod)
    else:
        mod = importlib.import_module(mod_part)
    fn = getattr(mod, fn_name, None)
    if fn is None:
        sys.exit(f"[causality] {mod_part} 里没有 {fn_name}")
    return fn


def read_df(path: str) -> pd.DataFrame:
    df = (pd.read_feather(path) if path.endswith(".feather")
          else pd.read_parquet(path) if path.endswith(".parquet")
          else pd.read_csv(path))
    for c in df.columns:
        if c.lower().strip() in DATE_COLS:
            df[c] = pd.to_datetime(df[c], errors="coerce")
            return df.sort_values(c).reset_index(drop=True).rename(columns={c: "date"})
    return df.reset_index(drop=True)


def as_vector(x, n: int) -> np.ndarray:
    """把返回值统一成长度 n 的一维 float 向量。"""
    if isinstance(x, pd.DataFrame):
        # 多列（如 enter/exit 四列）→ 打包成一个数
        v = np.zeros(len(x), dtype="float64")
        for i, c in enumerate(x.columns):
            v += (2 ** i) * pd.to_numeric(x[c], errors="coerce").fillna(0).to_numpy(float)
        arr = v
    else:
        arr = np.asarray(pd.Series(np.asarray(x).ravel()), dtype="float64")
    if len(arr) != n:
        sys.exit(f"[causality] 被测函数返回长度 {len(arr)} != 输入长度 {n}，无法逐点对照")
    return arr


def check_single(fn, df: pd.DataFrame, points: int, tol: float, warmup: float):
    full = as_vector(fn(df.copy()), len(df))
    L = len(df)
    idxs = np.unique(np.linspace(int(L * warmup), L - 2, points).astype(int))
    n_cmp, max_diff, leak = 0, 0.0, None
    for t in idxs:
        vf = full[t]
        if not np.isfinite(vf):
            continue
        trunc = as_vector(fn(df.iloc[: t + 1].copy()), t + 1)
        vt = trunc[t]
        if not np.isfinite(vt):
            leak = (int(t), "截断数据上算不出该点（全量能）→ 该值需要未来数据")
            break
        n_cmp += 1
        d = abs(float(vf) - float(vt))
        max_diff = max(max_diff, d)
        if d > tol:
            leak = (int(t), f"全量={vf:.6g} != 截断={vt:.6g}")
            break
    return n_cmp, max_diff, leak


def check_panel(fn, dfs: dict, points: int, tol: float, warmup: float):
    """横截面：按统一日期切片，逐个标的比对同一时点的决策。"""
    dates = sorted(set().union(*[set(pd.to_datetime(d["date"])) for d in dfs.values()]))
    L = len(dates)
    if L < 100:
        sys.exit(f"[causality] 面板长度太短 L={L}")
    full = {k: as_vector(v, len(dfs[k])) for k, v in fn({k: d.copy() for k, d in dfs.items()}).items()}
    idxs = np.unique(np.linspace(int(L * warmup), L - 2, points).astype(int))
    n_cmp, max_diff, leak = 0, 0.0, None
    for ti in idxs:
        cut = dates[ti]
        sub = {k: d[pd.to_datetime(d["date"]) <= cut].copy() for k, d in dfs.items()}
        out = fn(sub)
        for k, d in dfs.items():
            pos_full = np.where(pd.to_datetime(d["date"]) == cut)[0]
            pos_tr = np.where(pd.to_datetime(sub[k]["date"]) == cut)[0]
            if len(pos_full) == 0 or len(pos_tr) == 0 or k not in out:
                continue
            vf = full[k][pos_full[0]]
            vt = as_vector(out[k], len(sub[k]))[pos_tr[0]]
            if not np.isfinite(vf):
                continue
            if not np.isfinite(vt):
                leak = (str(cut), f"{k}: 截断算不出（全量能）→ 需要未来数据")
                break
            n_cmp += 1
            diff = abs(float(vf) - float(vt))
            max_diff = max(max_diff, diff)
            if diff > tol:
                leak = (str(cut), f"{k}: 全量={vf:.6g} != 截断={vt:.6g}")
                break
        if leak:
            break
    return n_cmp, max_diff, leak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fn", required=True, help="被测决策函数 文件.py:函数名")
    ap.add_argument("--mode", default="single", choices=["single", "panel"])
    ap.add_argument("--data", help="single 模式：单个行情文件")
    ap.add_argument("--data-dir", help="panel 模式：行情目录")
    ap.add_argument("--glob", default="*.csv")
    ap.add_argument("--points", type=int, default=12, help="抽查几个时点")
    ap.add_argument("--tol", type=float, default=1e-9)
    ap.add_argument("--warmup", type=float, default=0.35, help="从样本的百分之多少开始抽查")
    a = ap.parse_args()

    fn = load_fn(a.fn)
    if a.mode == "single":
        if not a.data:
            sys.exit("[causality] single 模式需要 --data")
        n_cmp, max_diff, leak = check_single(fn, read_df(a.data), a.points, a.tol, a.warmup)
    else:
        if not a.data_dir:
            sys.exit("[causality] panel 模式需要 --data-dir")
        files = sorted(glob.glob(os.path.join(a.data_dir, a.glob)))
        if len(files) < 2:
            sys.exit(f"[causality] 面板至少需要 2 个标的，实际 {len(files)}")
        dfs = {os.path.splitext(os.path.basename(f))[0]: read_df(f) for f in files}
        n_cmp, max_diff, leak = check_panel(fn, dfs, a.points, a.tol, a.warmup)

    print(f"[{a.mode}] 有效对比点={n_cmp}  max|full-truncated|={max_diff:.3e}")
    if leak:
        print(f"VERDICT: 用了未来数据（look-ahead）！@{leak[0]}: {leak[1]}  → 本次回测作废")
        sys.exit(1)
    if n_cmp < 8:
        print("[WARN] 有效对比点太少（因子 NaN 太多？），结论不可靠——手动复核")
        sys.exit(2)
    print("VERDICT: 决策前缀稳定、未检出未来数据；仍需单独验证成交与 PnL 时序  [PASS]")
    sys.exit(0)


if __name__ == "__main__":
    main()
