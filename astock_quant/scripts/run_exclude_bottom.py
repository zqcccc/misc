"""「剔除最差一档」策略：纯多头能吃到的那部分因子信息。

用法：python3 scripts/run_exclude_bottom.py
产物：reports/exclude_bottom.json
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import (backtest, config, factors, metrics, panel,  # noqa: E402
                strategy, universe, validate, walkforward)


def main():
    t0 = time.time()
    p = panel.load_panels()
    close = p["close"]
    dates = close.index
    mask = universe.investable(p)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(p).items()}
    start = "2019-01-02"

    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).fillna(0.0)
    ew_full = universe.equal_weight_benchmark(p, mask)

    # 因子权重的滚动重估只跟时间窗口有关，跟选股规则无关 —— 先算一次复用，
    # 否则 18 组配置要重复跑 144 次 IC 估计
    schedule = []
    fit_end = pd.Timestamp(start) - pd.Timedelta(days=1)
    end = pd.Timestamp(config.BACKTEST_END)
    while fit_end < end:
        seg_start = fit_end + pd.Timedelta(days=1)
        seg_end = min(seg_start + pd.DateOffset(months=12) - pd.Timedelta(days=1), end)
        w = walkforward.estimate_weights(fp, mask, close,
                                         seg_start - pd.DateOffset(years=3), fit_end)
        if w:
            schedule.append((seg_start, seg_end,
                             strategy.composite(fp, w, mask).loc[seg_start:seg_end]))
        print(f"  权重窗口 {seg_start.date()}~{seg_end.date()} 完成", flush=True)
        fit_end = seg_end

    rows, curves = [], {}
    # 加了上限之后 drop_pct 就不起作用了（取前 N 名本来就在门槛之上），
    # 所以只有"不限持仓"那两组需要区分 drop_pct
    combos = [(0.2, None), (0.4, None), (0.4, 200), (0.4, 400), (0.4, 800)]
    for freq in (20, 40, 60):
        for drop, cap in combos:
            if True:
                segs = []
                for seg_start, seg_end, score in schedule:
                    rb = strategy.rebalance_dates(dates, freq, start=start, end=end)
                    rb = rb[(rb >= seg_start) & (rb <= seg_end)]
                    sub = strategy.exclude_bottom_signals(score, rb, drop_pct=drop,
                                                          band=0.05, max_holdings=cap)
                    if not sub.empty:
                        segs.append(sub)
                if not segs:
                    continue
                sig = pd.concat(segs).sort_index()
                # 资金量要跟持仓宽度匹配：每只至少 20 万，否则单只仓位低于
                # 最小成交额，委托被静默跳过，回测会变成"拿着不动"
                width = int(sig.notna().sum(axis=1).median())
                cash = max(1e7, width * 2e5)
                res = backtest.run(p, sig, start=start, end=config.BACKTEST_END,
                                   init_cash=cash)
                r = res.ret
                ew = ew_full.reindex(r.index).fillna(0.0)
                h = hs300_ret.reindex(r.index).fillna(0.0)
                st = metrics.perf_stats(r, ew)
                ab = validate.alpha_beta(r, {"沪深300": h, "小盘风格": ew - h})
                label = f"剔除后{int(drop * 100)}% / {freq}日 / 上限{cap or '不限'}"
                rows.append({
                    "配置": label, "年化%": round(st["年化收益"] * 100, 2),
                    "对等权超额%": round(st["超额年化"] * 100, 2),
                    "信息比": round(st["信息比率"], 2),
                    "夏普": round(st["夏普(rf=0)"], 2),
                    "最大回撤%": round(st["最大回撤"] * 100, 1),
                    "持仓中位数": int(res.n_holdings.median()),
                    "所需资金(亿)": round(cash / 1e8, 2),
                    "委托被跳过%": round(res.blocked_frac * 100, 2),
                    "换手(年)": round(float(res.turnover.mean() * metrics.TRADING_DAYS), 1),
                    "成本%": round(float(res.cost.mean() * metrics.TRADING_DAYS * 100), 2),
                    "alpha%": round(ab.get("年化alpha", 0) * 100, 2),
                    "alpha_t": round(ab.get("alpha_t(NW)", 0), 2),
                })
                curves[label] = {"日期": [d.strftime("%Y-%m-%d") for d in res.equity.index],
                                 "净值": [round(float(x), 4)
                                          for x in res.equity / res.equity.iloc[0]]}
                print(f"  {rows[-1]}", flush=True)

    df = pd.DataFrame(rows).sort_values("对等权超额%", ascending=False)
    print("\n" + df.to_string(index=False))
    ew = ew_full.loc[start:]
    print(f"\n对照 等权全A(可投池)：年化 "
          f"{((1 + ew).prod() ** (metrics.TRADING_DAYS / len(ew)) - 1) * 100:.2f}%")
    with open(os.path.join(config.REPORT_DIR, "exclude_bottom.json"), "w") as f:
        json.dump({"结果": rows, "净值": curves}, f, ensure_ascii=False, indent=1)
    print(f"用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
