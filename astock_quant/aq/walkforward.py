"""滚动样本外（walk-forward）：因子权重每年用**过去**若干年的数据重新估一次。

单次 IS/OOS 切分只能证明"这组权重在后半段还行"，但权重毕竟是人挑的。滚动
样本外把"挑因子"这个动作也纳入回测：在每个再估日 T，只允许看 <= T 的数据，
估出的权重用于 (T, T+1年] 的交易，然后整段拼起来。拼出来的净值曲线上，每一
天的持仓都只依赖当天之前的信息。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics, strategy


def estimate_weights(fp: dict[str, pd.DataFrame], mask: pd.DataFrame, close: pd.DataFrame,
                     lo: pd.Timestamp, hi: pd.Timestamp, horizon: int = 20,
                     t_min: float = 1.5, max_factors: int = 8) -> dict[str, float]:
    """用 [lo, hi] 区间的 ICIR 估因子权重。hi 之后的数据一概不看。"""
    fwd = metrics.forward_return(close.loc[:hi], horizon=horizon, exec_lag=1)
    stats = {}
    for name, f in fp.items():
        ic = metrics.rank_ic(f.loc[lo:hi], fwd.loc[lo:hi], mask.loc[lo:hi])
        s = metrics.ic_stats(ic.iloc[::horizon])          # 非重叠子样本
        if s and s.get("ICIR", 0) > 0 and s.get("t统计量", 0) >= t_min:
            stats[name] = s["ICIR"]
    if not stats:
        return {}
    top = dict(sorted(stats.items(), key=lambda kv: -kv[1])[:max_factors])
    total = sum(top.values())
    return {k: round(v / total, 4) for k, v in top.items()}


def build_signals(fp: dict[str, pd.DataFrame], mask: pd.DataFrame, close: pd.DataFrame,
                  start: str, end: str, freq: int, top_n: int, buffer_mult: float = 2.0,
                  est_years: int = 3, refit_months: int = 12,
                  scheme: str = "equal", inv_vol: pd.DataFrame = None,
                  verbose: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """滚动估权重 + 生成目标权重表。"""
    dates = close.index
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    segments, schedule = [], []
    held: list[str] = []
    keep_rank = int(top_n * buffer_mult)

    fit_end = start - pd.Timedelta(days=1)
    while fit_end < end:
        seg_start = fit_end + pd.Timedelta(days=1)
        seg_end = min(seg_start + pd.DateOffset(months=refit_months) - pd.Timedelta(days=1), end)
        fit_start = seg_start - pd.DateOffset(years=est_years)
        w = estimate_weights(fp, mask, close, fit_start, fit_end)
        schedule.append({"生效区间": f"{seg_start.date()}~{seg_end.date()}",
                         "估计窗口": f"{fit_start.date()}~{fit_end.date()}", "权重": w})
        if verbose:
            print(f"  {seg_start.date()}~{seg_end.date()} 用 "
                  f"{fit_start.date()}~{fit_end.date()} 估：{w}", flush=True)
        if w:
            score = strategy.composite(fp, w, mask).loc[seg_start:seg_end]
            rb = strategy.rebalance_dates(dates, freq, start=start, end=end)
            rb = rb[(rb >= seg_start) & (rb <= seg_end)]
            rows = {}
            for d in rb:
                if d not in score.index:
                    continue
                s = score.loc[d].dropna()
                if s.empty:
                    continue
                order = s.rank(ascending=False, method="first")
                keep = [c for c in held if c in order.index and order[c] <= keep_rank]
                if len(keep) > top_n:
                    keep = sorted(keep, key=lambda c: order[c])[:top_n]
                need = top_n - len(keep)
                if need > 0:
                    keep += order[~order.index.isin(keep)].nsmallest(need).index.tolist()
                held = keep
                rows[d] = strategy._weights_for(held, d, scheme, inv_vol)
            if rows:
                segments.append(pd.DataFrame(rows).T)
        fit_end = seg_end

    sig = pd.concat(segments).sort_index() if segments else pd.DataFrame()
    return sig, schedule
