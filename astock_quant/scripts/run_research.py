"""因子研究主流程：IC 检验 → 分层测试 → 样本内定权重 → 样本外验证 → 稳健性。

用法：python3 scripts/run_research.py [--top-n 50] [--freq 5]
产物：reports/research.json（供 build_report.py 生成 HTML）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import (backtest, config, factors, metrics, panel,  # noqa: E402
                quicktest, strategy, universe)


def log(msg):
    print(msg, flush=True)


def factor_report(fp, mask, close, rb_dates, period, q=5):
    """对每个因子做 IC 检验 + 分层测试，全部限定在给定时间段内。"""
    lo, hi = period
    rows, layers = [], {}
    fwd20 = metrics.forward_return(close, horizon=20, exec_lag=1)
    fwd5 = metrics.forward_return(close, horizon=5, exec_lag=1)
    for name, f in fp.items():
        f_p = f.loc[lo:hi]
        ic20 = metrics.rank_ic(f_p, fwd20.loc[lo:hi], mask.loc[lo:hi])
        ic5 = metrics.rank_ic(f_p, fwd5.loc[lo:hi], mask.loc[lo:hi])
        # t 统计量用非重叠子样本计算：20 日前瞻收益的日频 IC 序列高度自相关，
        # 直接用全部样本算 t 会把显著性放大好几倍
        s20 = metrics.ic_stats(ic20.iloc[::20])
        s20["IC均值"] = round(float(ic20.dropna().mean()), 4)
        s5 = metrics.ic_stats(ic5.iloc[::5])
        s5["IC均值"] = round(float(ic5.dropna().mean()), 4)
        lr = quicktest.layered_returns(
            strategy.masked_rank_score(f, mask).loc[lo:hi], close.loc[lo:hi],
            rb_dates[(rb_dates >= pd.Timestamp(lo)) & (rb_dates <= pd.Timestamp(hi))], q)
        ann = ((1 + lr).prod() ** (metrics.TRADING_DAYS / len(lr)) - 1) if len(lr) else pd.Series()
        ls = lr[q - 1] - lr[0] if len(lr) else pd.Series(dtype=float)
        rows.append({
            "因子": name, "说明": factors.FACTOR_DESC.get(name, ""),
            "IC20均值": s20.get("IC均值"), "ICIR20": s20.get("ICIR"), "t20": s20.get("t统计量"),
            "IC5均值": s5.get("IC均值"), "t5": s5.get("t统计量"),
            "多空年化": round(float((1 + ls).prod() ** (metrics.TRADING_DAYS / max(len(ls), 1)) - 1), 4)
            if len(ls) else None,
            "多空夏普": round(float(ls.mean() / ls.std() * np.sqrt(metrics.TRADING_DAYS)), 2)
            if len(ls) and ls.std() > 0 else None,
            "单调性": round(float(pd.Series(ann.values).corr(pd.Series(range(q)))), 3)
            if len(ann) == q else None,
            "分层年化": [round(float(x), 4) for x in ann.values] if len(ann) == q else [],
        })
        layers[name] = ann.tolist() if len(ann) == q else []
    return pd.DataFrame(rows).sort_values("t20", ascending=False), layers


def factor_correlation(fp, mask, lo, hi, step=20):
    """因子之间的平均截面秩相关：看合成打分到底押了几个独立的注。"""
    names = list(fp.keys())
    dates = [d for d in mask.loc[lo:hi].index[::step]]
    acc = np.zeros((len(names), len(names)))
    cnt = 0
    for d in dates:
        m = mask.loc[d]
        cols = m[m].index
        if len(cols) < 50:
            continue
        mat = pd.DataFrame({n: fp[n].loc[d, cols] for n in names}).rank()
        c = mat.corr().values
        if np.isnan(c).all():
            continue
        acc += np.nan_to_num(c)
        cnt += 1
    return names, (acc / max(cnt, 1)).round(3).tolist()


def pick_weights(df_is: pd.DataFrame, t_min: float = 2.0) -> dict:
    """样本内选因子定权重：|t| 达标且方向为正，按 ICIR 加权。

    只用样本内信息，权重定下来后样本外不再改动 —— 这是整个研究里最容易
    自欺欺人的地方（全样本挑因子 + 全样本回测 = 变相的未来函数）。
    """
    sel = df_is[(df_is["t20"] >= t_min) & (df_is["ICIR20"] > 0)]
    if sel.empty:
        sel = df_is.nlargest(3, "t20")
    w = sel.set_index("因子")["ICIR20"].clip(lower=0)
    if w.sum() <= 0:
        w = pd.Series(1.0, index=sel["因子"])
    return (w / w.sum()).round(4).to_dict()


def bench_returns(dates):
    out = {}
    for code, name in [("sh000300", "沪深300"), ("sh000905", "中证500")]:
        idx = panel.load_index(code)["close"].reindex(dates).astype(float)
        out[name] = (idx / idx.shift(1) - 1.0).fillna(0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--freq", type=int, default=5, help="每 N 个交易日调仓")
    ap.add_argument("--buffer", type=float, default=2.0, help="换手缓冲区倍数，1 表示不缓冲")
    args = ap.parse_args()
    t0 = time.time()

    log("加载面板 ...")
    p = panel.load_panels()
    close = p["close"]
    dates = close.index
    log(f"  {close.shape[0]} 交易日 × {close.shape[1]} 只股票")

    last_valid = close.apply(lambda col: col.last_valid_index())
    n_delisted = int((last_valid < pd.Timestamp(config.DATA_END) - pd.Timedelta(days=15)).sum())
    log(f"  其中样本期内退市/停止交易：{n_delisted} 只")

    mask = universe.investable(p)
    log(f"  可投资股票数：均值 {mask.loc[config.BACKTEST_START:].sum(axis=1).mean():.0f}")

    log("计算因子 ...")
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(p).items()}
    rb = strategy.rebalance_dates(dates, args.freq, start=config.BACKTEST_START,
                                  end=config.BACKTEST_END)
    log(f"  调仓日 {len(rb)} 个（每 {args.freq} 个交易日）")

    log("样本内因子检验 (%s ~ %s) ..." % (config.BACKTEST_START, config.IS_END))
    df_is, layers_is = factor_report(fp, mask, close, rb, (config.BACKTEST_START, config.IS_END))
    log(df_is[["因子", "说明", "IC20均值", "ICIR20", "t20", "多空年化", "多空夏普", "单调性"]]
        .to_string(index=False))

    weights = pick_weights(df_is)
    log(f"\n样本内选出的因子权重：{weights}")

    log("\n样本外因子检验 (%s ~ %s) ..." % (config.OOS_START, config.BACKTEST_END))
    df_oos, layers_oos = factor_report(fp, mask, close, rb, (config.OOS_START, config.BACKTEST_END))
    log(df_oos[["因子", "IC20均值", "ICIR20", "t20", "多空年化", "单调性"]].to_string(index=False))

    fnames, fcorr = factor_correlation(fp, mask, config.BACKTEST_START, config.BACKTEST_END)

    log("\n合成打分 + 正式回测（含成本/涨跌停/停牌/退市）...")
    score = strategy.composite(fp, weights, mask)
    sig = (strategy.top_n_signals_buffered(score, rb, args.top_n, args.buffer)
           if args.buffer > 1 else strategy.top_n_signals(score, rb, args.top_n))
    res = backtest.run(p, sig, start=config.BACKTEST_START, end=config.BACKTEST_END,
                       keep_holdings=True)

    benches = bench_returns(res.ret.index)
    eq_bench = universe.equal_weight_benchmark(p, mask).reindex(res.ret.index).fillna(0.0)
    benches["等权全A(可投池)"] = eq_bench

    rows = [metrics.perf_stats(res.ret, benches["沪深300"], f"策略 top{args.top_n}/{args.freq}日")]
    for k, v in benches.items():
        rows.append(metrics.perf_stats(v, benches["沪深300"], k))
    log("\n【全样本】")
    log(metrics.stats_frame(rows).to_string(index=False))

    def seg(lo, hi, label):
        r = res.ret.loc[lo:hi]
        rws = [metrics.perf_stats(r, benches["沪深300"].loc[lo:hi], f"策略({label})")]
        for k, v in benches.items():
            rws.append(metrics.perf_stats(v.loc[lo:hi], benches["沪深300"].loc[lo:hi], f"{k}({label})"))
        return metrics.stats_frame(rws)

    log("\n【样本内 %s~%s】" % (config.BACKTEST_START, config.IS_END))
    is_tbl = seg(config.BACKTEST_START, config.IS_END, "IS")
    log(is_tbl.to_string(index=False))
    log("\n【样本外 %s~%s】" % (config.OOS_START, config.BACKTEST_END))
    oos_tbl = seg(config.OOS_START, config.BACKTEST_END, "OOS")
    log(oos_tbl.to_string(index=False))

    log(f"\n年化双边换手：{res.turnover.mean() * metrics.TRADING_DAYS:.1f} 倍，"
        f"年化成本拖累：{res.cost.mean() * metrics.TRADING_DAYS * 100:.2f}%")

    out = {
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "股票数": int(close.shape[1]),
        "退市数": n_delisted,
        "退市说明": f"样本期内共 {n_delisted} 只股票退市或停止交易，全部保留在池中。",
        "交易日": int(close.shape[0]),
        "调仓频率": args.freq, "持股数": args.top_n,
        "因子权重": weights,
        "样本内因子表": json.loads(df_is.to_json(orient="records", force_ascii=False)),
        "样本外因子表": json.loads(df_oos.to_json(orient="records", force_ascii=False)),
        "因子相关": {"名称": [factors.FACTOR_DESC.get(n, n) for n in fnames], "矩阵": fcorr},
        "分层年化_IS": layers_is, "分层年化_OOS": layers_oos,
        "全样本": json.loads(metrics.stats_frame(rows).to_json(orient="records", force_ascii=False)),
        "样本内": json.loads(is_tbl.to_json(orient="records", force_ascii=False)),
        "样本外": json.loads(oos_tbl.to_json(orient="records", force_ascii=False)),
        "净值": {"日期": [d.strftime("%Y-%m-%d") for d in res.equity.index],
                 "策略": [round(float(x), 4) for x in (res.equity / res.equity.iloc[0])],
                 **{k: [round(float(x), 4) for x in (1 + v).cumprod()] for k, v in benches.items()}},
        "换手率年化": round(float(res.turnover.mean() * metrics.TRADING_DAYS), 2),
        "成本拖累年化": round(float(res.cost.mean() * metrics.TRADING_DAYS), 5),
        "持仓数中位数": int(res.n_holdings.median()),
    }
    os.makedirs(config.REPORT_DIR, exist_ok=True)
    with open(os.path.join(config.REPORT_DIR, "research.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"\n完成，用时 {time.time() - t0:.0f}s，结果写入 reports/research.json")


if __name__ == "__main__":
    main()
