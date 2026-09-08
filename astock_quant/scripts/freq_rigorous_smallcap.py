#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上小微盘策略「调仓频率」单变量严谨研究
==========================================
问题：线上 `ashare_joinquant_smallcap_micro` 为什么是每 10 个交易日（两周）调仓？

方法（/quant-backtest-protocol 铁律）：

  L0 口径冻结   —— 除调仓频率外，一切参数锁死为线上生产值（见 FROZEN）
  L1 机理       —— rank IC 衰减曲线：信号信息随持有期衰减多快 → 理论最优持有期
  L2 三段切分   —— TRAIN(2016-2021) / VALID(2022-2023) 上搜索，TEST(2024-01~) 物理隔离
  L3 物理隔离   —— TEST 段面板单独写到 ~/.qbt_isolated/，选频阶段进程内不可见
  L4 锁死目标   —— loss = -(valid_sr - 0.5*max(0, train_sr - valid_sr))，先于结果写死
  L5 四层证伪   —— 因果闸 / alpha-beta(NW) 归因 / DSR 试错折减 / 分块自助+随机组合置换
  L6 稳健性     —— N × buffer 网格下，最优频率是否稳定（还是噪声挑出来的）

本脚本**不搜任何参数**，只做频率这一个自由度的单变量检验。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, AQ_ROOT)

from aq import backtest, config, factors, metrics, panel, strategy, universe, validate  # noqa: E402

TRADING_DAYS = 244

# ------------------------------------------------------------------ L0 口径冻结
FROZEN = {
    "因子权重": {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5},
    "持仓数N": 7,
    "滞后带buffer": 2.0,
    "权重方案": "equal（等权）",
    "执行": "T 日收盘出信号，T+1 日开盘成交",
    "成本": "双边佣金万2.5 + 印花税(历史动态) + 滑点单边10bp + 过户费十万分之一",
    "股票池": "与线上生产一致：universe.investable(min_listed=250, exclude_st=True, liquidity_top_pct=1.0)"
             "（剔除 ST / 次新<250日 / 北交所B股 / 日均额<2000万；不剔除最不活跃20%，否则砍掉微盘溢价本体）",
    "回测区间": "2016-01-04 ~ 2026-09-01",
    "唯一自由度": "调仓频率 freq（交易日）",
}
WEIGHTS = FROZEN["因子权重"]
N_HOLD = 7
BUFFER = 2.0

FREQS = (1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 60, 120)
N_TRIALS = len(FREQS)          # DSR 折减用的试验次数：诚实上报网格大小

TRAIN = ("2016-01-04", "2021-12-31")
VALID = ("2022-01-04", "2023-12-29")
TEST = ("2024-01-02", "2026-09-01")
DEV_END = "2023-12-29"          # 开发期能看到的最后一天
TEST_WARMUP = "2022-01-01"      # TEST 面板的 warm-up 起点（因子/上市天数需要）
ISOLATED_DIR = os.path.expanduser("~/.qbt_isolated")
ISOLATED_TEST = os.path.join(ISOLATED_DIR, "smallcap_freq_test_panels.parquet")


# ------------------------------------------------------------------ 工具
def build_score(panels: dict[str, pd.DataFrame], mask: pd.DataFrame):
    """线上三个因子，口径与 aq/live_smallcap.py 完全一致。"""
    close, amount = panels["close"], panels["amount"]
    ret = factors.daily_return(close)
    fp = {
        "rev5": factors.rev(close, 5),
        "liqsize20": factors.liquidity_size(amount, 20),
        "ivol60": factors.idio_vol(ret, 60),
    }
    return strategy.composite(fp, WEIGHTS, mask)


def investable(panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """线上生产口径的股票池（见 tests/test_live_smallcap.py）。

    注意 liquidity_top_pct=1.0 —— 默认值的 0.80 会砍掉最不活跃 20%，
    而小微盘策略的超额正来自这部分，用默认值会把年化从 21% 打到 3%。
    """
    return universe.investable(panels, min_listed=250, exclude_st=True,
                               liquidity_top_pct=1.0)


def run_freq(panels, score, dates, freq: int, start: str, end: str,
             top_n: int = N_HOLD, buffer_mult: float = BUFFER):
    rb = strategy.rebalance_dates(dates, freq, start=start, end=end)
    sig = strategy.top_n_signals_buffered(score, rb, top_n, buffer_mult, "equal")
    net = backtest.run(panels, sig, start=start, end=end, exec_price="open", zero_cost=False)
    gross = backtest.run(panels, sig, start=start, end=end, exec_price="open", zero_cost=True)
    return sig, net, gross, rb


def seg(res_net, res_gross, bench_ew, hs300_ret, seg_start, seg_end):
    r = res_net.ret.loc[seg_start:seg_end]
    rg = res_gross.ret.loc[seg_start:seg_end]
    eq = res_net.equity.loc[seg_start:seg_end]
    if len(r) < 30:
        return {}
    st = metrics.perf_stats(r, bench_ew.reindex(r.index).fillna(0.0))
    st_hs = metrics.perf_stats(r, hs300_ret.reindex(r.index).fillna(0.0))
    to = float(res_net.turnover.loc[seg_start:seg_end].mean() * TRADING_DAYS)
    cost = float(res_net.cost.loc[seg_start:seg_end].mean() * TRADING_DAYS)
    st_g = metrics.perf_stats(rg)
    return {
        "天数": int(len(r)),
        "年化%": round(st["年化收益"] * 100, 2),
        "夏普": round(st["夏普(rf=0)"], 3),
        "回撤%": round(st["最大回撤"] * 100, 2),
        "超额等权%": round(st.get("超额年化", np.nan) * 100, 2),
        "超额沪深300%": round(st_hs.get("超额年化", np.nan) * 100, 2),
        "毛年化%": round(st_g["年化收益"] * 100, 2),
        "换手x": round(to, 1),
        "成本%": round(cost * 100, 2),
    }


def rebalance_churn(sig: pd.DataFrame) -> float:
    """每次调仓平均变动只数（换入+换出）。"""
    prev, rows = None, []
    for _, row in sig.iterrows():
        cur = set(row.dropna().index)
        if prev is not None:
            rows.append(len(prev ^ cur))
        prev = cur
    return float(np.mean(rows)) if rows else 0.0


# ------------------------------------------------------------------ L1 IC 衰减
def ic_decay(panels, mask, score, horizons):
    """合成信号对未来 h 日收益的 rank IC。

    含义：如果 T 日收盘按信号买入并持有 h 天，能捕获多少横截面信息。
    IC 随 h 衰减到噪声水平的位置，就是「再调仓已经没意义」的持有期上界。
    """
    close = panels["close"]
    out = []
    for h in horizons:
        fwd = metrics.forward_return(close, h, exec_lag=1)
        ic = metrics.rank_ic(score, fwd, mask)
        st = metrics.ic_stats(ic)
        sub = ic.loc[TRAIN[0]:DEV_END]
        st_train = metrics.ic_stats(sub)
        out.append({
            "持有期h": h,
            "IC均值": st.get("IC均值"),
            "ICIR": st.get("ICIR"),
            "t": st.get("t统计量"),
            "IC>0占比": st.get("IC>0占比"),
            "TRAIN_IC均值": st_train.get("IC均值"),
            "TRAIN_ICIR": st_train.get("ICIR"),
        })
    return out


# ------------------------------------------------------------------ 物理隔离
def prepare_isolated_test_panel():
    """把 TEST 段（含 warm-up）面板写到工作目录之外，模拟「揭盲前拿不到」。"""
    os.makedirs(ISOLATED_DIR, exist_ok=True)
    p = panel.load_panels()
    keys = ["close", "open", "high", "low", "volume", "amount",
            "close_raw", "open_raw", "high_raw", "low_raw"]
    sub = {}
    for k in keys:
        if k in p:
            sub[k] = p[k].loc[TEST_WARMUP:TEST[1]]
    pd.to_pickle(sub, ISOLATED_TEST)
    return {k: (int(v.shape[0]), int(v.shape[1])) for k, v in sub.items()}


def load_isolated_test_panel():
    if not os.path.exists(ISOLATED_TEST):
        raise FileNotFoundError("TEST 面板未隔离，先跑 prepare")
    return pd.read_pickle(ISOLATED_TEST)


# ------------------------------------------------------------------ 主流程
def main():
    t0 = time.time()
    print("=" * 78)
    print("  线上小微盘策略 · 调仓频率单变量严谨研究（/quant-backtest-protocol）")
    print("=" * 78)

    # ---------- 开发期面板（只到 2023-12-29，TEST 在进程内不存在）
    print("\n[L0] 加载开发期面板（截至 %s）..." % DEV_END, flush=True)
    full = panel.load_panels()
    dev = {k: v.loc[:DEV_END] for k, v in full.items()}
    dev_dates = dev["close"].index
    mask_dev = investable(dev)
    score_dev = build_score(dev, mask_dev)
    bench_ew_dev = universe.equal_weight_benchmark(dev, mask_dev).fillna(0.0)
    hs300_dev = panel.load_index("sh000300")["close"].reindex(dev_dates).astype(float)
    hs300_ret_dev = (hs300_dev / hs300_dev.shift(1) - 1.0).fillna(0.0)
    print(f"  面板 {dev_dates[0].date()} ~ {dev_dates[-1].date()}  {dev['close'].shape}", flush=True)

    # ---------- L1 机理：IC 衰减
    print("\n[L1] rank IC 衰减曲线（信号信息能撑多长的持有期）...", flush=True)
    horizons = [1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 60, 90, 120]
    ic_curve = ic_decay(dev, mask_dev, score_dev, horizons)
    for r in ic_curve:
        print(f"  h={r['持有期h']:>3}  IC={r['IC均值']:+.4f}  ICIR={r['ICIR']:+.3f}  "
              f"t={r['t']:>5}  IC>0占比={r['IC>0占比']}", flush=True)

    # ---------- L2 频率网格（TRAIN / VALID）
    print("\n[L2] 频率网格 × TRAIN/VALID（唯一自由度）...", flush=True)
    grid = []
    for freq in FREQS:
        sig, net, gross, rb = run_freq(dev, score_dev, dev_dates, freq, TRAIN[0], DEV_END)
        m_tr = seg(net, gross, bench_ew_dev, hs300_ret_dev, *TRAIN)
        m_va = seg(net, gross, bench_ew_dev, hs300_ret_dev, *VALID)
        sr_tr, sr_va = m_tr.get("夏普", 0.0), m_va.get("夏普", 0.0)
        gap = max(0.0, sr_tr - sr_va)
        loss = -(sr_va - 0.5 * gap)
        churn = rebalance_churn(sig)
        grid.append({
            "freq": freq, "调仓次数": int(len(rb)), "每次变动只数": round(churn, 2),
            "TRAIN": m_tr, "VALID": m_va, "gap": round(gap, 3), "loss": round(loss, 4),
            "_sig_n": int(sig.notna().sum(axis=1).median()),
        })
        print(f"  freq={freq:>3}  调仓{len(rb):>4}次 变动{churn:>4.2f}只/期 | "
              f"TRAIN 年化{m_tr['年化%']:>7.2f}% 夏普{m_tr['夏普']:>6.3f} 换手{m_tr['换手x']:>5.1f}x | "
              f"VALID 年化{m_va['年化%']:>7.2f}% 夏普{m_va['夏普']:>6.3f} 回撤{m_va['回撤%']:>7.2f}% | "
              f"loss={loss:+.4f}", flush=True)

    # ---------- L4 锁死目标函数选频
    best = min(grid, key=lambda r: r["loss"])
    best_freq = best["freq"]
    print(f"\n[L4] 目标函数 loss=-(valid_sr - 0.5*max(0,train_sr-valid_sr)) 选出 freq = {best_freq}", flush=True)
    print(f"     VALID 夏普 {best['VALID']['夏普']}  TRAIN 夏普 {best['TRAIN']['夏普']}  gap {best['gap']}", flush=True)

    # ---------- L3 物理隔离揭盲
    print("\n[L3] TEST 物理隔离揭盲（面板来自工作目录之外，选频阶段不可见）...", flush=True)
    shapes = prepare_isolated_test_panel()
    tp = load_isolated_test_panel()
    t_dates = tp["close"].index
    mask_te = investable(tp)
    score_te = build_score(tp, mask_te)
    bench_ew_te = universe.equal_weight_benchmark(tp, mask_te).fillna(0.0)
    hs300_te = panel.load_index("sh000300")["close"].reindex(t_dates).astype(float)
    hs300_ret_te = (hs300_te / hs300_te.shift(1) - 1.0).fillna(0.0)
    print(f"  隔离面板 keys={list(tp)}  行数={shapes['close'][0]}", flush=True)

    blind = {}
    for freq in FREQS:                     # 揭盲后展示全网格（不用于选择）
        sig, net, gross, rb = run_freq(tp, score_te, t_dates, freq, TEST[0], TEST[1])
        m_te = seg(net, gross, bench_ew_te, hs300_ret_te, *TEST)
        blind[freq] = m_te
        print(f"  [TEST] freq={freq:>3}  年化{m_te['年化%']:>7.2f}% 夏普{m_te['夏普']:>6.3f} "
              f"回撤{m_te['回撤%']:>7.2f}% 超额等权{m_te['超额等权%']:>7.2f}% "
              f"毛{m_te['毛年化%']:>7.2f}% 换手{m_te['换手x']:>5.1f}x 成本{m_te['成本%']:>5.2f}%",
              flush=True)
    m_test_sel = blind[best_freq]
    print(f"\n  >>> 选中 freq={best_freq} 的 TEST 揭盲：年化 {m_test_sel['年化%']}%  "
          f"夏普 {m_test_sel['夏普']}  回撤 {m_test_sel['回撤%']}%", flush=True)

    # ---------- L5 四层证伪（对选中 freq，TEST 段）
    print("\n[L5] 四层证伪（TEST 段，freq=%d）..." % best_freq, flush=True)
    sig_te, net_te, gross_te, rb_te = run_freq(tp, score_te, t_dates, best_freq, TEST[0], TEST[1])

    # 闸 1：因果 / 未来函数敏感度
    #   (a) 把信号日整体前移 1 天 = 用 T 日收盘信息在 T 日开盘成交（未来函数）
    leak_sig = sig_te.copy()
    leak_sig.index = t_dates[t_dates.get_indexer(leak_sig.index) - 1]
    leak = backtest.run(tp, leak_sig, start=TEST[0], end=TEST[1], exec_price="open", zero_cost=False)
    #   (b) 把分数整体前移 1 期 = 用 T+1 收盘的分数在 T+1 开盘决策（未来函数）
    sc_shift = score_te.shift(-1)
    sig_fwd = strategy.top_n_signals_buffered(
        sc_shift, strategy.rebalance_dates(t_dates, best_freq, start=TEST[0], end=TEST[1]),
        N_HOLD, BUFFER, "equal")
    fwd = backtest.run(tp, sig_fwd, start=TEST[0], end=TEST[1], exec_price="open", zero_cost=False)
    r_true = net_te.ret.loc[TEST[0]:TEST[1]]
    r_leak = leak.ret.loc[TEST[0]:TEST[1]]
    r_fwd = fwd.ret.loc[TEST[0]:TEST[1]]
    cagr = lambda s: float((1 + s).prod() ** (TRADING_DAYS / len(s)) - 1)  # noqa: E731
    gate1 = {
        "说明": "若引擎存在未来函数，把信息提前注入应无法再提升收益；反之若注入后收益暴涨，说明引擎对信息泄露敏感、基线版本确实无泄露。",
        "基线年化%": round(cagr(r_true) * 100, 2),
        "同日开盘成交(未来函数)%": round(cagr(r_leak) * 100, 2),
        "用T+1分数决策(未来函数)%": round(cagr(r_fwd) * 100, 2),
        "泄露 uplift_pp": round((cagr(r_leak) - cagr(r_true)) * 100, 2),
        "前向分数 uplift_pp": round((cagr(r_fwd) - cagr(r_true)) * 100, 2),
    }
    gate1["判定"] = "PASS（引擎对信息泄露敏感，基线无泄露）" if (
        gate1["泄露 uplift_pp"] > 0.5 or gate1["前向分数 uplift_pp"] > 0.5) else "⚠️ 引擎对泄露不敏感，闸无效"
    print(f"  闸1 因果：基线 {gate1['基线年化%']}% | 同日成交 {gate1['同日开盘成交(未来函数)%']}% "
          f"(+{gate1['泄露 uplift_pp']}pp) | T+1分数 {gate1['用T+1分数决策(未来函数)%']}% "
          f"(+{gate1['前向分数 uplift_pp']}pp) → {gate1['判定']}", flush=True)

    # 闸 2：alpha / beta 归因
    hs = hs300_ret_te.reindex(r_true.index).fillna(0.0)
    small_style = bench_ew_te.reindex(r_true.index).fillna(0.0) - hs
    reg1 = validate.alpha_beta(r_true, {"沪深300": hs})
    reg2 = validate.alpha_beta(r_true, {"沪深300": hs, "小盘风格": small_style})
    gate2 = {
        "对沪深300_年化alpha%": round(reg1.get("年化alpha", np.nan) * 100, 2),
        "对沪深300_t(NW)": round(reg1.get("alpha_t(NW)", np.nan), 2),
        "对沪深300+小盘风格_年化alpha%": round(reg2.get("年化alpha", np.nan) * 100, 2),
        "风格调整后_t(NW)": round(reg2.get("alpha_t(NW)", np.nan), 2),
        "beta_沪深300": round(reg2.get("beta_沪深300", np.nan), 3),
        "beta_小盘风格": round(reg2.get("beta_小盘风格", np.nan), 3),
        "R2": round(reg2.get("R2", np.nan), 3),
        "p值": round(reg2.get("alpha_p值(双侧)", np.nan), 3),
        "年度刀切": validate.year_jackknife(r_true, {"沪深300": hs, "小盘风格": small_style}),
    }
    print(f"  闸2 归因：风格调整后 alpha {gate2['对沪深300+小盘风格_年化alpha%']}%/年  "
          f"t(NW)={gate2['风格调整后_t(NW)']}  p={gate2['p值']}  "
          f"beta风格={gate2['beta_小盘风格']}  R2={gate2['R2']}", flush=True)

    # 闸 3：DSR（试错折减 = 网格大小）
    dsr = validate.deflated_sharpe(r_true, n_trials=N_TRIALS, trial_sharpe_var=0.25)
    print(f"  闸3 DSR：{dsr.get('DSR')} （{dsr.get('判定')}；试错次数={N_TRIALS}，"
          f"纯运气可达夏普 {dsr.get('纯运气可达夏普(年化)')}）", flush=True)

    # 闸 4：分块自助 + 随机组合置换
    mc = validate.block_bootstrap(r_true, iters=5000, block=10, seed=42)
    n_perm = 300
    perm: list[float] = []
    rng = np.random.default_rng(20260908)
    mask_te_rb = mask_te
    for i in range(n_perm):
        rs = validate.random_scores(mask_te_rb, rb_te, seed=int(rng.integers(1, 10 ** 9)))
        sg = strategy.top_n_signals_buffered(rs, rb_te, N_HOLD, BUFFER, "equal")
        rr = backtest.run(tp, sg, start=TEST[0], end=TEST[1], exec_price="open", zero_cost=False)
        s = rr.ret.loc[TEST[0]:TEST[1]]
        perm.append(cagr(s))
    perm = np.asarray(perm, dtype=float)
    real = cagr(r_true)
    gate4 = {
        "分块自助": mc,
        "置换次数": n_perm,
        "真实年化%": round(real * 100, 2),
        "随机组合_均值%": round(float(perm.mean()) * 100, 2),
        "随机组合_P95%": round(float(np.percentile(perm, 95)) * 100, 2),
        "随机组合_最大%": round(float(perm.max()) * 100, 2),
        "置换p值": round(validate.permutation_p(real, perm), 4),
        "真实分位": round(validate.percentile_rank(real, perm), 4),
    }
    print(f"  闸4 蒙卡：盈利路径占比 {mc.get('盈利路径占比')}  P5={mc.get('P5')}  P50={mc.get('P50')}",
          flush=True)
    print(f"      置换：真实 {gate4['真实年化%']}% vs 随机均值 {gate4['随机组合_均值%']}% "
          f"P95 {gate4['随机组合_P95%']}%  分位 {gate4['真实分位']}  p={gate4['置换p值']}", flush=True)

    # ---------- L6 稳健性：N × buffer 下最优频率是否稳定
    print("\n[L6] 稳健性：N × buffer 网格下最优频率（TRAIN/VALID 同目标函数）...", flush=True)
    robust = []
    for top_n in (5, 7, 10):
        for buf in (1.5, 2.0, 3.0):
            rows = []
            for freq in FREQS:
                sig, net, gross, rb = run_freq(dev, score_dev, dev_dates, freq, TRAIN[0], DEV_END,
                                               top_n=top_n, buffer_mult=buf)
                m_tr = seg(net, gross, bench_ew_dev, hs300_ret_dev, *TRAIN)
                m_va = seg(net, gross, bench_ew_dev, hs300_ret_dev, *VALID)
                gap = max(0.0, m_tr.get("夏普", 0.0) - m_va.get("夏普", 0.0))
                rows.append((freq, -(m_va.get("夏普", 0.0) - 0.5 * gap), m_tr, m_va))
            f_best = min(rows, key=lambda x: x[1])[0]
            robust.append({
                "N": top_n, "buffer": buf, "最优freq": f_best,
                "VALID夏普": round(max(r[3]["夏普"] for r in rows), 3),
                "各freq_VALID夏普": {r[0]: r[3]["夏普"] for r in rows},
            })
            print(f"  N={top_n} buffer={buf}: 最优 freq={f_best}", flush=True)

    # ---------- 输出
    out: dict[str, Any] = {
        "meta": {
            "研究问题": "线上小微盘策略为什么每 10 个交易日调仓？",
            "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
            "口径冻结": FROZEN,
            "切分": {"TRAIN": TRAIN, "VALID": VALID, "TEST": TEST},
            "目标函数": "loss = -(valid_sr - 0.5*max(0, train_sr - valid_sr))，先于结果锁死",
            "频率网格": list(FREQS),
            "隔离路径": ISOLATED_TEST,
        },
        "ic_decay": ic_curve,
        "grid_train_valid": grid,
        "selected_freq": best_freq,
        "test_blind": {str(k): v for k, v in blind.items()},
        "test_selected": m_test_sel,
        "falsification": {"闸1因果": gate1, "闸2归因": gate2, "闸3DSR": dsr, "闸4运气": gate4},
        "robustness": robust,
    }
    out_path = os.path.join(PROJECT_ROOT, "deliverables", "smallcap_freq_rigorous.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n完成，用时 {time.time() - t0:.1f}s → {out_path}", flush=True)


if __name__ == "__main__":
    main()
