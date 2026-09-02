#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚宽 & 果仁网经典 A 股策略端到端严谨量化回测评估
================================================
依据 /quant-rigorous-backtest 技能铁律：
1. 绝对因果律：信号 T 收盘确定，T+1 开盘成交，强制 shift(1)，机器验证无未来函数
2. 物理三段划分：TRAIN (2019-2021) / VALID (2022-2023) / TEST (2024-2026.09 压力揭盲)
3. 真实交易成本：佣金万 2.5 + 印花税（动态历史税率）+ 滑点 0.1% + 涨跌停/停牌限制
4. 纯 Alpha 剥离与日资金曲线夏普（严禁 closed trades 夏普虚高）
5. DSR 试错惩罚 + 5000 次分块蒙特卡洛检验 + TEST 压力测试揭盲
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Any, Dict

import numpy as np
import pandas as pd

# 加入路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, AQ_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from aq import backtest, config, factors, metrics, panel, strategy, universe, validate

TRADING_DAYS = 244


def calc_daily_sharpe(ret: pd.Series, periods: int = TRADING_DAYS) -> float:
    """日资金曲线年化夏普比率"""
    r = ret.dropna()
    if len(r) < 30 or r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * math.sqrt(periods))


def calc_max_drawdown(equity: pd.Series) -> float:
    """最大回撤"""
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def calc_annual_return(ret: pd.Series, periods: int = TRADING_DAYS) -> float:
    """年化复合收益率"""
    r = ret.dropna()
    if len(r) < 10:
        return 0.0
    tot = float((1.0 + r).prod())
    years = len(r) / periods
    return float(tot ** (1.0 / years) - 1.0) if years > 0 and tot > 0 else 0.0


def run_strategy_pipeline(
    name: str,
    weights: dict[str, float],
    fp: dict[str, pd.DataFrame],
    panels: dict[str, pd.DataFrame],
    inv_mask: pd.DataFrame,
    top_n: int = 30,
    freq: int = 10,
    buffer_mult: float = 2.0,
    scheme: str = "equal",
    inv_vol: pd.DataFrame = None,
    start: str = "2019-01-02",
    end: str = "2026-09-02",
) -> dict:
    """构建策略并执行因果回测"""
    close = panels["close"]
    dates = close.index

    # 1. 因子合成与截面排名
    score = strategy.composite(fp, weights, inv_mask)
    
    # 2. 调仓日生成与带滞后带选股（防手续费过拟合）
    rb_dates = strategy.rebalance_dates(dates, freq, start=start, end=end)
    signals = strategy.top_n_signals_buffered(
        score=score,
        rb_dates=rb_dates,
        top_n=top_n,
        buffer_mult=buffer_mult,
        scheme=scheme,
        inv_vol=inv_vol,
    )

    # 3. 真实交易成本回测（信号 T，成交 T+1 开盘）
    res = backtest.run(panels, signals, start=start, end=end, zero_cost=False)
    res_gross = backtest.run(panels, signals, start=start, end=end, zero_cost=True)

    return {
        "name": name,
        "signals": signals,
        "res_net": res,
        "res_gross": res_gross,
    }


def evaluate_period(
    res_net: backtest.BacktestResult,
    res_gross: backtest.BacktestResult,
    hs300_ret: pd.Series,
    small_style: pd.Series,
    start_date: str,
    end_date: str,
) -> dict:
    """评估特定时间段的指标与风格归因"""
    r = res_net.ret.loc[start_date:end_date]
    rg = res_gross.ret.loc[start_date:end_date]
    eq = res_net.equity.loc[start_date:end_date]
    to = res_net.turnover.loc[start_date:end_date]

    if len(r) < 20:
        return {}

    sharpe = calc_daily_sharpe(r)
    ann_ret = calc_annual_return(r)
    max_dd = calc_max_drawdown(eq)
    ann_turnover = float(to.mean() * TRADING_DAYS)

    # Alpha/Beta 归因（Newey-West HAC 修正）
    mkt = hs300_ret.loc[r.index]
    sty = small_style.loc[r.index]

    reg_hs300 = validate.alpha_beta(r, {"沪深300": mkt})
    reg_style = validate.alpha_beta(r, {"沪深300": mkt, "小盘风格": sty})

    return {
        "days": len(r),
        "annual_return": round(ann_ret * 100, 2),
        "daily_sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "annual_turnover": round(ann_turnover, 2),
        "alpha_vs_hs300": round(reg_hs300.get("年化alpha", 0.0) * 100, 2),
        "alpha_t_hs300": round(reg_hs300.get("alpha_t(NW)", 0.0), 2),
        "alpha_vs_style": round(reg_style.get("年化alpha", 0.0) * 100, 2),
        "alpha_t_style": round(reg_style.get("alpha_t(NW)", 0.0), 2),
        "beta_hs300": round(reg_style.get("beta_沪深300", 0.0), 2),
        "beta_style": round(reg_style.get("beta_小盘风格", 0.0), 2),
        "r_squared": round(reg_style.get("R2", 0.0), 3),
    }


def main():
    parser = argparse.ArgumentParser(description="聚宽 & 果仁网 A 股严谨量化策略评测")
    parser.add_argument("--mc-iters", type=int, default=5000, help="蒙特卡洛分块重采样次数")
    parser.add_argument("--out", default="deliverables/rigorous_ashare_strategies.json", help="输出路径")
    args = parser.parse_args()

    print("================================================================")
    print("      聚宽 & 果仁网 A 股量化策略 /quant-rigorous-backtest 严谨评测")
    print("================================================================")
    t0 = time.time()

    # 1. 加载行情面板与基准
    print("[1/6] 加载 A 股全市场无幸存者偏差后复权面板 (2015-2026)...", flush=True)
    panels = panel.load_panels()
    close = panels["close"]
    dates = close.index

    hs300 = panel.load_index("sh000300")["close"].reindex(dates).astype(float)
    hs300_ret = (hs300 / hs300.shift(1) - 1.0).fillna(0.0)

    # 计算因果因子库（包含新增的 RSRS 因子）
    print("[2/6] 计算纯因果因子面板（严格右闭 rolling，无未来信息）...", flush=True)
    fp = {k: v.astype(np.float32) for k, v in factors.build_all(panels).items()}
    inv_vol = strategy.inverse_vol(close, n=60)

    # 2. 股票池构造
    # 全A微盘/小市值池：剔除 ST、次新、保留全市场流动性以便小微盘选拔
    mask_smallcap = universe.investable(panels, min_listed=250, exclude_st=True, liquidity_top_pct=1.0)
    # 果仁低估值蓝筹防御池：限定流动性前 50%
    mask_defensive = universe.investable(panels, min_listed=250, exclude_st=True, liquidity_top_pct=0.50)
    # 动量成长池：限定流动性前 70%
    mask_momentum = universe.investable(panels, min_listed=250, exclude_st=True, liquidity_top_pct=0.70)

    # 基准风格因子
    ew_mkt = universe.equal_weight_benchmark(panels, mask_smallcap).fillna(0.0)
    small_style = ew_mkt - hs300_ret

    # 3. 策略定义
    strategies_def = [
        {
            "id": "smallcap_momentum_value",
            "name": "聚宽顶流: 小市值微利轮动 (SmallCap Momentum & Value)",
            "platform": "聚宽 (JoinQuant)",
            "description": "市值最小排名前 30，结合 5 日短期防追高反转与低特质波动过滤，双周轮动",
            "weights": {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5},
            "mask": mask_smallcap,
            "top_n": 30,
            "freq": 10,
            "scheme": "equal",
            "buffer_mult": 2.0,
        },
        {
            "id": "dividend_lowvol_defensive",
            "name": "果仁王牌: 低估值高股息与低波动防御 (Dividend & Low Vol)",
            "platform": "果仁网 (Guoren)",
            "description": "流动性前 50% 优质池，低特质低波 + 低历史波动 + 均线负乖离，逆波动率加权，月频轮动",
            "weights": {"ivol60": 0.4, "vol60": 0.3, "bias20": 0.2, "maxret20": 0.1},
            "mask": mask_defensive,
            "top_n": 30,
            "freq": 20,
            "scheme": "invvol",
            "buffer_mult": 2.0,
        },
        {
            "id": "rsrs_momentum_rotation",
            "name": "聚宽/研报精选: RSRS 阻力支撑相对强度动量轮动 (RSRS Momentum)",
            "platform": "聚宽 (JoinQuant)",
            "description": "High 对 Low 滚动 OLS 斜率标准化 RSRS 修正值 + 量能异动 + 20 日反转，双周轮动",
            "weights": {"rsrs": 1.0, "volshock": 0.5, "rev20": 0.5},
            "mask": mask_momentum,
            "top_n": 30,
            "freq": 10,
            "scheme": "equal",
            "buffer_mult": 2.0,
        },
    ]

    # 三段划分日期
    train_start, train_end = "2019-01-02", "2021-12-31"
    valid_start, valid_end = "2022-01-04", "2023-12-29"
    test_start, test_end = "2024-01-02", "2026-09-02"

    print("\n[3/6] 执行 TRAIN (2019-2021) 与 VALID (2022-2023) 区间回测与落差惩罚评估...", flush=True)

    results_summary = []

    for sdef in strategies_def:
        sid = sdef["id"]
        sname = sdef["name"]
        print(f"\n---> 正在回测策略: {sname}")

        # 全期回测
        strat_res = run_strategy_pipeline(
            name=sname,
            weights=sdef["weights"],
            fp=fp,
            panels=panels,
            inv_mask=sdef["mask"],
            top_n=sdef["top_n"],
            freq=sdef["freq"],
            buffer_mult=sdef["buffer_mult"],
            scheme=sdef["scheme"],
            inv_vol=inv_vol,
            start=train_start,
            end=test_end,
        )

        res_net = strat_res["res_net"]
        res_gross = strat_res["res_gross"]

        # 1. 训练集
        m_train = evaluate_period(res_net, res_gross, hs300_ret, small_style, train_start, train_end)
        # 2. 验证集
        m_valid = evaluate_period(res_net, res_gross, hs300_ret, small_style, valid_start, valid_end)

        # 3. 落差惩罚 Loss
        sr_tr = m_train.get("daily_sharpe", 0.0)
        sr_va = m_valid.get("daily_sharpe", 0.0)
        gap = max(0.0, sr_tr - sr_va)
        loss = -(sr_va - 0.5 * gap)

        print(f"  [TRAIN] 年化: {m_train.get('annual_return')}% | 夏普: {sr_tr} | 回撤: {m_train.get('max_drawdown')}% | Alpha(NW): {m_train.get('alpha_vs_style')}% (t={m_train.get('alpha_t_style')})")
        print(f"  [VALID] 年化: {m_valid.get('annual_return')}% | 夏普: {sr_va} | 回撤: {m_valid.get('max_drawdown')}% | Alpha(NW): {m_valid.get('alpha_vs_style')}% (t={m_valid.get('alpha_t_style')})")
        print(f"  [落差惩罚] Gap = {gap:.3f} | 惩罚后 Loss = {loss:.4f}")

        # 4. 统计抗运气与显著性检验 (DSR + Block Bootstrap on Valid)
        print(f"  [Stage 4: 统计抗运气检验 (DSR & 蒙特卡洛)]...")
        valid_ret = res_net.ret.loc[valid_start:valid_end]
        
        # DSR 计算 (假设搜索 100 轮超参，方差 0.25)
        dsr_res = validate.deflated_sharpe(valid_ret, n_trials=100, trial_sharpe_var=0.25)
        
        # Block Bootstrap (5000 次分块重采样，保留局部序列相关性)
        mc_res = validate.block_bootstrap(valid_ret, iters=args.mc_iters, block=10, seed=42)

        print(f"    DSR: {dsr_res.get('DSR')} ({dsr_res.get('判定')})")
        print(f"    蒙特卡洛验证集盈利概率: {mc_res.get('盈利路径占比') * 100:.1f}% | P5 极端尾部: {mc_res.get('P5')} | P50 中位数: {mc_res.get('P50')}")

        # 5. 揭盲物理盲测集 (TEST: 2024-01 ~ 2026-09)
        print(f"  [Stage 5: 物理盲测集压力揭盲 (TEST: 2024-01 ~ 2026-09)]...")
        m_test = evaluate_period(res_net, res_gross, hs300_ret, small_style, test_start, test_end)
        
        # 专项考察 2024 年 1~2 月极端微盘踩踏期的最大回撤
        test_eq = res_net.equity.loc[test_start:test_end]
        test_dd = (test_eq - test_eq.cummax()) / test_eq.cummax()
        crash_2024_dd = float(test_dd.loc["2024-01-02":"2024-02-29"].min()) if len(test_dd.loc["2024-01-02":"2024-02-29"]) > 0 else 0.0

        print(f"  [TEST 揭盲结果]")
        print(f"    年化收益: {m_test.get('annual_return')}% | 夏普: {m_test.get('daily_sharpe')} | 最大回撤: {m_test.get('max_drawdown')}%")
        print(f"    2024初踩踏期极端下撤: {crash_2024_dd * 100:.2f}%")
        print(f"    对小盘风格剥离后纯 Alpha: {m_test.get('alpha_vs_style')}% (NW t = {m_test.get('alpha_t_style')})")

        # 完整资金曲线序列（用于交付报告及绘图）
        equity_dict = {str(d.date()): round(float(v), 2) for d, v in res_net.equity.items()}

        results_summary.append({
            "id": sid,
            "name": sname,
            "platform": sdef["platform"],
            "description": sdef["description"],
            "train_metrics": m_train,
            "valid_metrics": m_valid,
            "gap_penalty_loss": round(loss, 4),
            "dsr": dsr_res,
            "monte_carlo_valid": mc_res,
            "test_metrics": m_test,
            "crash_2024_max_dd": round(crash_2024_dd * 100, 2),
            "equity_sample": {
                "start": equity_dict.get("2019-01-02"),
                "end_train": equity_dict.get("2021-12-31"),
                "end_valid": equity_dict.get("2023-12-29"),
                "end_test": equity_dict.get(str(res_net.equity.index[-1].date())),
            }
        })

    # 保存交付物
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, ensure_ascii=False, indent=2)

    print(f"\n[6/6] 回测与严谨评测完成！总耗时: {time.time() - t0:.2f}s")
    print(f"交付物已保存至: {args.out}")


if __name__ == "__main__":
    main()
