"""
BTC 5分钟剥头皮策略 —— 多费率场景对比 + BTC Buy&Hold 基准
=========================================================
对比场景:
  1. 零摩擦 (理想)
  2. 合约 Maker only (0.02% 单边)
  3. 合约 Taker only (0.05% 单边)
  4. 合约 BNB/OKB 折扣 (0.018% maker / 0.045% taker, 按 taker 算)
  5. 现货普通用户 (0.1% 单边)
  6. 原始设定 (0.04% + 0.01% 滑点)

同时计算 BTC Buy & Hold 作为 alpha 基准
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from btc_scalping_backtest import (
    fetch_ohlcv, compute_indicators, CACHE_DIR, INITIAL_CAPITAL,
    RANGE_LOOKBACK, TREND_LOOKBACK,
)
from btc_scalping_grid_search import generate_signals_parameterized

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False

# ============================================================
# 费率场景
# ============================================================
SLIPPAGE = 0.0001  # 固定滑点 0.01%

FEE_SCENARIOS = {
    "零摩擦 (理想)":              {"maker": 0.0,    "taker": 0.0,    "slippage": 0.0},
    "合约Maker挂单 (0.02%)":      {"maker": 0.0002, "taker": 0.0002, "slippage": SLIPPAGE},
    "合约BNB折扣 (0.018%)":       {"maker": 0.00018,"taker": 0.00018,"slippage": SLIPPAGE},
    "合约Taker吃单 (0.05%)":      {"maker": 0.0005, "taker": 0.0005, "slippage": SLIPPAGE},
    "现货普通 (0.1%)":            {"maker": 0.001,  "taker": 0.001,  "slippage": SLIPPAGE},
    "原始设定 (0.04%+滑点)":      {"maker": 0.0004, "taker": 0.0004, "slippage": SLIPPAGE},
}

# 用最佳参数组合: off模式, TP=0.5%, SL=1.5%
BEST_TP = 0.005
BEST_SL = 0.015
BEST_MODE = "off"

# 也测试几组其他参数
PARAM_SETS = [
    ("最佳: TP=0.5% SL=1.5% off",  0.005, 0.015, "off"),
    ("TP=0.8% SL=0.8% off (1:1)",  0.008, 0.008, "off"),
    ("TP=1.0% SL=1.5% strict",     0.010, 0.015, "strict"),
    ("TP=0.3% SL=0.6% normal(原版)", 0.003, 0.006, "normal"),
]


def fast_backtest_with_equity(closes, highs, lows, signals, tp, sl, fee_single, slippage):
    """回测并返回净值曲线"""
    friction = (fee_single + slippage) * 2
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0.0
    n = len(closes)

    wins = 0
    losses = 0
    total_win_pnl = 0.0
    total_loss_pnl = 0.0
    total_gross_pnl = 0.0

    # 每100根记一次净值
    eq_capital = [capital]
    eq_idx = [0]
    sample = 100

    for i in range(n):
        if position != 0:
            h, l = highs[i], lows[i]
            exited = False
            exit_price = 0.0

            if position == 1:
                if (entry_price - l) / entry_price >= sl:
                    exit_price = entry_price * (1 - sl); exited = True
                elif (h - entry_price) / entry_price >= tp:
                    exit_price = entry_price * (1 + tp); exited = True
            else:
                if (h - entry_price) / entry_price >= sl:
                    exit_price = entry_price * (1 + sl); exited = True
                elif (entry_price - l) / entry_price >= tp:
                    exit_price = entry_price * (1 - tp); exited = True

            if exited:
                gross = ((exit_price - entry_price) / entry_price) * position
                net = gross - friction
                capital += capital * net
                total_gross_pnl += gross
                if net > 0: wins += 1; total_win_pnl += net
                else: losses += 1; total_loss_pnl += net
                position = 0

        if position == 0 and signals[i] != 0:
            position = int(signals[i])
            entry_price = closes[i]

        if i % sample == 0:
            eq = capital
            if position != 0:
                unr = position * (closes[i] - entry_price) / entry_price
                eq = capital * (1 + unr)
            eq_capital.append(eq)
            eq_idx.append(i)

    # 强制平仓
    if position != 0:
        gross = position * (closes[-1] - entry_price) / entry_price
        net = gross - friction
        capital += capital * net
        if net > 0: wins += 1; total_win_pnl += net
        else: losses += 1; total_loss_pnl += net

    eq_capital.append(capital)
    eq_idx.append(n - 1)

    total_trades = wins + losses
    return {
        "total_return": capital / INITIAL_CAPITAL - 1,
        "win_rate": wins / total_trades if total_trades > 0 else 0,
        "total_trades": total_trades,
        "final_capital": capital,
        "profit_factor": abs(total_win_pnl / total_loss_pnl) if total_loss_pnl != 0 else float("inf"),
        "total_friction": friction * total_trades,
        "total_gross_pnl": total_gross_pnl,
        "friction_per_trade": friction,
        "equity_curve": np.array(eq_capital),
        "equity_idx": np.array(eq_idx),
    }


def main():
    print("=" * 80)
    print("  BTC 5分钟剥头皮 —— 多费率场景对比 + Alpha 分析")
    print("=" * 80)

    # 加载数据
    df = fetch_ohlcv(days=365)
    print("\n  计算指标...")
    df = compute_indicators(df)

    closes = df["close"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)
    timestamps = df["timestamp"].values

    # BTC Buy & Hold
    btc_start = closes[0]
    btc_end = closes[-1]
    btc_return = btc_end / btc_start - 1
    btc_equity = closes / btc_start * INITIAL_CAPITAL

    print(f"\n  ── BTC Buy & Hold 基准 ──────────────────────")
    print(f"  起始价: ${btc_start:,.2f}")
    print(f"  结束价: ${btc_end:,.2f}")
    print(f"  收益率: {btc_return:.2%}")
    print(f"  最终资金: ${INITIAL_CAPITAL * (1 + btc_return):,.2f}")

    # 预生成信号
    signal_cache = {}
    for _, tp, sl, mode in PARAM_SETS:
        if mode not in signal_cache:
            signals, _ = generate_signals_parameterized(df, weak_trend_mode=mode)
            signal_cache[mode] = signals

    # ============================================================
    # Part 1: 最佳参数下的多费率对比
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  Part 1: 最佳参数 (TP={BEST_TP:.1%} SL={BEST_SL:.1%} WeakTrend={BEST_MODE})")
    print(f"  不同费率场景对比")
    print(f"{'='*80}")

    best_signals = signal_cache[BEST_MODE]
    fee_results = {}

    print(f"\n  {'场景':<28}{'单边费率':>10}{'双边摩擦':>10}{'总交易':>8}{'收益率':>10}{'胜率':>8}{'PF':>8}{'vs BTC':>10}")
    print("  " + "-" * 92)

    for name, fees in FEE_SCENARIOS.items():
        fee_single = fees["maker"]
        slip = fees["slippage"]
        stats = fast_backtest_with_equity(
            closes, highs, lows, best_signals, BEST_TP, BEST_SL, fee_single, slip
        )
        fee_results[name] = stats
        alpha = stats["total_return"] - btc_return
        print(
            f"  {name:<28}"
            f"{fee_single:.4%}"
            f"{stats['friction_per_trade']:.4%}"
            f"{stats['total_trades']:>8}"
            f"{stats['total_return']:>10.2%}"
            f"{stats['win_rate']:>7.1%}"
            f"{stats['profit_factor']:>8.2f}"
            f"{alpha:>+10.2%}"
        )

    # ============================================================
    # Part 2: 零摩擦下各参数组合表现
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  Part 2: 零摩擦 (理想状态) 下各参数组合")
    print(f"{'='*80}")

    print(f"\n  {'参数组合':<35}{'交易数':>8}{'收益率':>10}{'胜率':>8}{'PF':>8}{'vs BTC':>10}")
    print("  " + "-" * 79)

    zero_fee_results = {}
    for label, tp, sl, mode in PARAM_SETS:
        signals = signal_cache[mode]
        stats = fast_backtest_with_equity(closes, highs, lows, signals, tp, sl, 0, 0)
        zero_fee_results[label] = stats
        alpha = stats["total_return"] - btc_return
        print(
            f"  {label:<35}"
            f"{stats['total_trades']:>8}"
            f"{stats['total_return']:>10.2%}"
            f"{stats['win_rate']:>7.1%}"
            f"{stats['profit_factor']:>8.2f}"
            f"{alpha:>+10.2%}"
        )

    # ============================================================
    # Part 3: 合约Maker费率下各参数组合
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  Part 3: 合约 Maker 挂单费率 (0.02% 单边) 下各参数组合")
    print(f"{'='*80}")

    print(f"\n  {'参数组合':<35}{'交易数':>8}{'收益率':>10}{'胜率':>8}{'PF':>8}{'vs BTC':>10}")
    print("  " + "-" * 79)

    maker_results = {}
    for label, tp, sl, mode in PARAM_SETS:
        signals = signal_cache[mode]
        stats = fast_backtest_with_equity(closes, highs, lows, signals, tp, sl, 0.0002, SLIPPAGE)
        maker_results[label] = stats
        alpha = stats["total_return"] - btc_return
        print(
            f"  {label:<35}"
            f"{stats['total_trades']:>8}"
            f"{stats['total_return']:>10.2%}"
            f"{stats['win_rate']:>7.1%}"
            f"{stats['profit_factor']:>8.2f}"
            f"{alpha:>+10.2%}"
        )

    # ============================================================
    # Part 4: 摩擦成本盈亏平衡分析
    # ============================================================
    print(f"\n{'='*80}")
    print(f"  Part 4: 摩擦成本盈亏平衡分析")
    print(f"{'='*80}")

    # 找到使最佳参数打平的最大费率
    print("\n  逐步提高费率，找到盈亏平衡点...")
    for fee_bps in range(0, 20):
        fee = fee_bps * 0.00005  # 0.005% 步长
        stats = fast_backtest_with_equity(
            closes, highs, lows, best_signals, BEST_TP, BEST_SL, fee, SLIPPAGE
        )
        marker = " ← 平衡点附近" if abs(stats["total_return"]) < 0.03 else ""
        if stats["total_return"] > 0:
            marker = " ✅ 盈利"
        print(f"    单边费率 {fee:.4%} → 收益 {stats['total_return']:>8.2%} (PF={stats['profit_factor']:.2f}){marker}")
        if stats["total_return"] < -0.30:
            break

    # ============================================================
    # 绘图
    # ============================================================
    fig, axes = plt.subplots(2, 1, figsize=(16, 12), gridspec_kw={"height_ratios": [2, 1.5]})

    # 图1: 净值曲线对比
    ax1 = axes[0]
    # BTC buy & hold (采样)
    sample_idx = np.arange(0, len(closes), 100)
    ax1.plot(pd.to_datetime(timestamps[sample_idx]), btc_equity[sample_idx],
             color="orange", linewidth=2, label=f"BTC Buy&Hold ({btc_return:+.1%})", linestyle="--")

    colors = ["#4CAF50", "#2196F3", "#00BCD4", "#9C27B0", "#F44336", "#795548"]
    for (name, stats), color in zip(fee_results.items(), colors):
        eq = stats["equity_curve"]
        idx = stats["equity_idx"]
        ts = pd.to_datetime(timestamps[np.minimum(idx, len(timestamps) - 1)])
        ax1.plot(ts, eq, color=color, linewidth=1.2,
                 label=f"{name} ({stats['total_return']:+.1%})", alpha=0.8)

    ax1.axhline(y=INITIAL_CAPITAL, color="gray", linestyle=":", alpha=0.3)
    ax1.set_title(
        f"BTC 5分钟剥头皮 多费率场景对比  |  最佳参数: TP={BEST_TP:.1%} SL={BEST_SL:.1%} WT=off",
        fontsize=13, fontweight="bold"
    )
    ax1.set_ylabel("资金 (USDT)")
    ax1.legend(fontsize=9, loc="center left", bbox_to_anchor=(0.01, 0.5))
    ax1.grid(True, alpha=0.3)
    ax1.set_yscale("log")

    # 图2: 各费率场景的收益率柱状图
    ax2 = axes[1]
    scenario_names = list(fee_results.keys())
    returns = [fee_results[n]["total_return"] * 100 for n in scenario_names]
    bar_colors = ["#4CAF50" if r > 0 else "#F44336" for r in returns]

    bars = ax2.barh(range(len(scenario_names)), returns, color=bar_colors, alpha=0.7)
    ax2.axvline(x=btc_return * 100, color="orange", linewidth=2, linestyle="--",
                label=f"BTC B&H ({btc_return:.1%})")
    ax2.axvline(x=0, color="black", linewidth=0.5)

    ax2.set_yticks(range(len(scenario_names)))
    ax2.set_yticklabels(scenario_names, fontsize=10)
    ax2.set_xlabel("总收益率 (%)")
    ax2.set_title("各费率场景收益率对比", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, axis="x")

    # 在柱子上标注数值
    for i, (bar, ret) in enumerate(zip(bars, returns)):
        ax2.text(ret + (1 if ret >= 0 else -1), i, f"{ret:.1f}%",
                 va="center", ha="left" if ret >= 0 else "right", fontsize=9, fontweight="bold")

    plt.tight_layout()
    out_path = os.path.join(CACHE_DIR, "fee_comparison.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  📈 对比图已保存: {out_path}")

    # ---- 总结 ----
    print(f"\n{'='*80}")
    print(f"  📋 总结")
    print(f"{'='*80}")
    print(f"\n  BTC Buy & Hold 过去1年收益: {btc_return:+.2%}")
    print(f"\n  最佳策略表现:")
    for name, stats in fee_results.items():
        alpha = stats["total_return"] - btc_return
        has_alpha = "✅ 有alpha" if alpha > 0 else "❌ 无alpha"
        profitable = "✅ 盈利" if stats["total_return"] > 0 else "❌ 亏损"
        print(f"    {name:<28} {stats['total_return']:>+8.2%}  alpha={alpha:>+8.2%}  {profitable}  {has_alpha}")

    return fee_results


if __name__ == "__main__":
    main()
