"""
BTC 5分钟 剥头皮策略 —— 参数网格搜索
=====================================
搜索维度:
  1. TP (止盈): 0.2% ~ 1.0%
  2. SL (止损): 0.3% ~ 1.5%
  3. 是否启用 C_WeakTrend 策略
  4. WeakTrend 过滤强度 (宽松/中等/严格)

数据和基础指标只计算一次，信号+回测按参数组合批量跑。
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
import json
import time
import itertools
import warnings
warnings.filterwarnings("ignore")

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False

# ── 导入主脚本的数据获取和指标计算 ──
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from btc_scalping_backtest import (
    fetch_ohlcv, compute_indicators,
    CACHE_DIR, INITIAL_CAPITAL, COMMISSION_RATE, SLIPPAGE_RATE,
    RANGE_LOOKBACK, TREND_LOOKBACK,
    STRONG_TREND_BODY_RATIO, DOJI_BODY_RATIO,
)

# ============================================================
# 参数网格定义
# ============================================================
TP_GRID = [0.002, 0.003, 0.004, 0.005, 0.008, 0.010]
SL_GRID = [0.003, 0.004, 0.006, 0.008, 0.010, 0.015]

# WeakTrend 过滤模式:
#   "off"    = 禁用 C_WeakTrend
#   "strict" = 更严格入场 (要求前两根都是 doji/反向)
#   "normal" = 原版条件
WEAK_TREND_MODES = ["off", "strict", "normal"]

TOTAL_FRICTION_FUNC = lambda: (COMMISSION_RATE + SLIPPAGE_RATE) * 2


# ============================================================
# 参数化信号生成
# ============================================================
def generate_signals_parameterized(df, weak_trend_mode="normal"):
    """根据不同 weak_trend_mode 生成信号"""
    n = len(df)
    signals = np.zeros(n, dtype=np.int8)
    strategy_names = np.full(n, "", dtype=object)

    state = df["market_state"].values
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    is_bullish = df["is_bullish"].values
    is_bearish = df["is_bearish"].values
    body_ratio = df["body_ratio"].values
    close_pos = df["close_position"].values
    is_doji = df["is_doji"].values
    range_high = df["range_high"].values
    range_low = df["range_low"].values
    range_size = df["range_size"].values

    start = max(RANGE_LOOKBACK, TREND_LOOKBACK) + 2  # +2 for strict mode lookback

    # ── 策略 A: 震荡区间 ──
    idx_range = np.where((np.arange(n) >= start) & (state == "range"))[0]
    if len(idx_range) > 0:
        rh = range_high[idx_range]
        rl = range_low[idx_range]
        rs = range_size[idx_range]
        valid = rs > 0
        upper_thresh = rh - rs * 0.05
        lower_thresh = rl + rs * 0.05
        prev_close = close[idx_range - 1]
        curr_close = close[idx_range]

        short_cond = valid & (prev_close > upper_thresh) & (curr_close < rh)
        long_cond = valid & (prev_close < lower_thresh) & (curr_close > rl)

        signals[idx_range[short_cond]] = -1
        strategy_names[idx_range[short_cond]] = "A_Range"
        signals[idx_range[long_cond]] = 1
        strategy_names[idx_range[long_cond]] = "A_Range"

    # ── 策略 B: 强趋势 ──
    idx_su = np.where((np.arange(n) >= start) & (state == "strong_up"))[0]
    if len(idx_su) > 0:
        cond = (is_bullish[idx_su] == 1) & (body_ratio[idx_su] > 0.5) & (close_pos[idx_su] > 0.6)
        signals[idx_su[cond]] = 1
        strategy_names[idx_su[cond]] = "B_StrongTrend"

    idx_sd = np.where((np.arange(n) >= start) & (state == "strong_down"))[0]
    if len(idx_sd) > 0:
        cond = (is_bearish[idx_sd] == 1) & (body_ratio[idx_sd] > 0.5) & (close_pos[idx_sd] < 0.4)
        signals[idx_sd[cond]] = -1
        strategy_names[idx_sd[cond]] = "B_StrongTrend"

    # ── 策略 C: 弱趋势 ──
    if weak_trend_mode != "off":
        # weak_up
        idx_wu = np.where((np.arange(n) >= start) & (state == "weak_up"))[0]
        if len(idx_wu) > 0:
            if weak_trend_mode == "normal":
                prev_doji_or_bear = (is_doji[idx_wu - 1] == 1) | (is_bearish[idx_wu - 1] == 1)
                curr_bull = is_bullish[idx_wu] == 1
                close_ok = (close[idx_wu] > low[idx_wu - 1]) & (low[idx_wu] <= low[idx_wu - 1] * 1.001)
                cond = prev_doji_or_bear & curr_bull & close_ok
            elif weak_trend_mode == "strict":
                # 严格: 前两根都是 doji/反向，且 body_ratio 当前根 > 0.5
                prev1_ok = (is_doji[idx_wu - 1] == 1) | (is_bearish[idx_wu - 1] == 1)
                prev2_ok = (is_doji[idx_wu - 2] == 1) | (is_bearish[idx_wu - 2] == 1)
                curr_bull = is_bullish[idx_wu] == 1
                curr_strong = body_ratio[idx_wu] > 0.5
                close_ok = (close[idx_wu] > low[idx_wu - 1]) & (low[idx_wu] <= low[idx_wu - 1] * 1.001)
                cond = prev1_ok & prev2_ok & curr_bull & curr_strong & close_ok

            signals[idx_wu[cond]] = 1
            strategy_names[idx_wu[cond]] = "C_WeakTrend"

        # weak_down
        idx_wd = np.where((np.arange(n) >= start) & (state == "weak_down"))[0]
        if len(idx_wd) > 0:
            if weak_trend_mode == "normal":
                prev_doji_or_bull = (is_doji[idx_wd - 1] == 1) | (is_bullish[idx_wd - 1] == 1)
                curr_bear = is_bearish[idx_wd] == 1
                close_ok = (close[idx_wd] < high[idx_wd - 1]) & (high[idx_wd] >= high[idx_wd - 1] * 0.999)
                cond = prev_doji_or_bull & curr_bear & close_ok
            elif weak_trend_mode == "strict":
                prev1_ok = (is_doji[idx_wd - 1] == 1) | (is_bullish[idx_wd - 1] == 1)
                prev2_ok = (is_doji[idx_wd - 2] == 1) | (is_bullish[idx_wd - 2] == 1)
                curr_bear = is_bearish[idx_wd] == 1
                curr_strong = body_ratio[idx_wd] > 0.5
                close_ok = (close[idx_wd] < high[idx_wd - 1]) & (high[idx_wd] >= high[idx_wd - 1] * 0.999)
                cond = prev1_ok & prev2_ok & curr_bear & curr_strong & close_ok

            signals[idx_wd[cond]] = -1
            strategy_names[idx_wd[cond]] = "C_WeakTrend"

    return signals, strategy_names


# ============================================================
# 快速回测引擎 (纯 numpy，无 DataFrame 开销)
# ============================================================
def fast_backtest(closes, highs, lows, signals, tp_pct, sl_pct):
    """
    极简回测，只返回关键指标。
    返回: (total_return, win_rate, total_trades, max_dd, profit_factor, avg_pnl)
    """
    friction = TOTAL_FRICTION_FUNC()
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0.0
    n = len(closes)

    wins = 0
    losses = 0
    total_win_pnl = 0.0
    total_loss_pnl = 0.0
    peak_capital = capital
    max_dd = 0.0
    total_net_pnl = 0.0

    for i in range(n):
        # 检查止盈止损
        if position != 0:
            h = highs[i]
            l = lows[i]
            exit_price = 0.0
            exited = False

            if position == 1:
                if (entry_price - l) / entry_price >= sl_pct:
                    exit_price = entry_price * (1 - sl_pct)
                    exited = True
                elif (h - entry_price) / entry_price >= tp_pct:
                    exit_price = entry_price * (1 + tp_pct)
                    exited = True
            else:
                if (h - entry_price) / entry_price >= sl_pct:
                    exit_price = entry_price * (1 + sl_pct)
                    exited = True
                elif (entry_price - l) / entry_price >= tp_pct:
                    exit_price = entry_price * (1 - tp_pct)
                    exited = True

            if exited:
                if position == 1:
                    gross = (exit_price - entry_price) / entry_price
                else:
                    gross = (entry_price - exit_price) / entry_price
                net = gross - friction
                capital += capital * net
                total_net_pnl += net

                if net > 0:
                    wins += 1
                    total_win_pnl += net
                else:
                    losses += 1
                    total_loss_pnl += net

                if capital > peak_capital:
                    peak_capital = capital
                dd = (capital - peak_capital) / peak_capital if peak_capital > 0 else 0
                if dd < max_dd:
                    max_dd = dd

                position = 0
                entry_price = 0.0

        # 开仓
        if position == 0 and signals[i] != 0:
            position = int(signals[i])
            entry_price = closes[i]

    # 强制平仓
    if position != 0:
        exit_price = closes[-1]
        if position == 1:
            gross = (exit_price - entry_price) / entry_price
        else:
            gross = (entry_price - exit_price) / entry_price
        net = gross - friction
        capital += capital * net
        if net > 0:
            wins += 1
            total_win_pnl += net
        else:
            losses += 1
            total_loss_pnl += net

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0
    total_return = (capital / INITIAL_CAPITAL) - 1
    avg_pnl = total_net_pnl / total_trades if total_trades > 0 else 0
    pf = abs(total_win_pnl / total_loss_pnl) if total_loss_pnl != 0 else float("inf")

    return {
        "total_return": total_return,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "max_drawdown": max_dd,
        "profit_factor": pf,
        "avg_pnl": avg_pnl,
        "final_capital": capital,
    }


# ============================================================
# 网格搜索主流程
# ============================================================
def main():
    print("=" * 70)
    print("  BTC 5分钟 剥头皮策略 —— 参数网格搜索")
    print("=" * 70)

    # 1. 加载数据 (一次性)
    df = fetch_ohlcv(days=365)
    print("\n  计算基础指标...")
    df = compute_indicators(df)

    closes = df["close"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)

    # 2. 预生成各模式的信号 (一次性)
    print("  预生成各模式信号...")
    signal_cache = {}
    for mode in WEAK_TREND_MODES:
        signals, strat_names = generate_signals_parameterized(df, weak_trend_mode=mode)
        signal_cache[mode] = signals
        n_signals = np.count_nonzero(signals)
        print(f"    {mode:<10} → {n_signals:>6} 个信号")

    # 3. 网格搜索
    combos = list(itertools.product(TP_GRID, SL_GRID, WEAK_TREND_MODES))
    total_combos = len(combos)
    print(f"\n  参数组合总数: {total_combos}")
    print(f"  TP: {TP_GRID}")
    print(f"  SL: {SL_GRID}")
    print(f"  WeakTrend: {WEAK_TREND_MODES}")
    print()

    results = []
    t0 = time.time()

    for idx, (tp, sl, wt_mode) in enumerate(combos):
        signals = signal_cache[wt_mode]
        stats = fast_backtest(closes, highs, lows, signals, tp, sl)

        ratio_str = f"1:{sl/tp:.1f}" if tp > 0 else "N/A"
        results.append({
            "tp": tp,
            "sl": sl,
            "rr_ratio": ratio_str,
            "weak_trend": wt_mode,
            **stats,
        })

        if (idx + 1) % 20 == 0 or idx == total_combos - 1:
            elapsed = time.time() - t0
            print(f"  [{idx+1}/{total_combos}] 已完成 ({elapsed:.1f}s)")

    elapsed = time.time() - t0
    print(f"\n  网格搜索完成，耗时 {elapsed:.1f}s")

    # 4. 结果排序
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("total_return", ascending=False).reset_index(drop=True)

    # 5. 输出 Top 20
    print("\n" + "=" * 120)
    print("  📊 参数网格搜索结果 (按总收益排序 Top 20)")
    print("=" * 120)
    print(f"  {'#':<4}{'TP':>6}{'SL':>6}{'R:R':>8}{'WeakTrend':>12}{'收益率':>10}{'胜率':>8}{'交易数':>8}{'最大回撤':>10}{'PF':>8}{'平均盈亏':>10}{'最终资金':>12}")
    print("  " + "-" * 108)

    for i, row in results_df.head(20).iterrows():
        print(
            f"  {i+1:<4}"
            f"{row['tp']:.3%}"
            f"{row['sl']:.3%}"
            f"{row['rr_ratio']:>8}"
            f"{row['weak_trend']:>12}"
            f"{row['total_return']:>10.2%}"
            f"{row['win_rate']:>7.1%}"
            f"{row['total_trades']:>8}"
            f"{row['max_drawdown']:>10.2%}"
            f"{row['profit_factor']:>8.2f}"
            f"{row['avg_pnl']:>10.4%}"
            f"${row['final_capital']:>11,.2f}"
        )

    # 6. 按分类找最佳
    print("\n" + "=" * 120)
    print("  📌 各 WeakTrend 模式最佳参数")
    print("=" * 120)
    for mode in WEAK_TREND_MODES:
        sub = results_df[results_df["weak_trend"] == mode]
        if sub.empty:
            continue
        best = sub.iloc[0]
        print(f"  [{mode}] TP={best['tp']:.3%} SL={best['sl']:.3%} "
              f"收益={best['total_return']:.2%} 胜率={best['win_rate']:.1%} "
              f"交易={best['total_trades']} PF={best['profit_factor']:.2f} "
              f"回撤={best['max_drawdown']:.2%}")

    # 7. 找盈利组合
    profitable = results_df[results_df["total_return"] > 0]
    print(f"\n  盈利组合数: {len(profitable)} / {total_combos}")
    if len(profitable) > 0:
        print("  所有盈利组合:")
        for i, row in profitable.iterrows():
            print(
                f"    TP={row['tp']:.3%} SL={row['sl']:.3%} {row['rr_ratio']:>6} "
                f"WT={row['weak_trend']:<8} "
                f"收益={row['total_return']:>8.2%} 胜率={row['win_rate']:.1%} "
                f"交易={row['total_trades']:>5} PF={row['profit_factor']:.2f}"
            )

    # 8. 绘制热力图
    plot_heatmaps(results_df)

    # 9. 保存结果
    save_path = os.path.join(CACHE_DIR, "grid_search_results.csv")
    results_df.to_csv(save_path, index=False)
    print(f"\n  📄 完整结果已保存: {save_path}")

    return results_df


def plot_heatmaps(results_df):
    """为每种 WeakTrend 模式绘制 TP×SL 热力图"""
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    for ax_idx, mode in enumerate(WEAK_TREND_MODES):
        ax = axes[ax_idx]
        sub = results_df[results_df["weak_trend"] == mode]

        # 构建 pivot table
        pivot = sub.pivot_table(
            values="total_return", index="sl", columns="tp", aggfunc="first"
        )
        pivot_pct = pivot * 100  # 转为百分比

        # 绘制热力图
        im = ax.imshow(pivot_pct.values, cmap="RdYlGn", aspect="auto",
                       vmin=pivot_pct.values.min(), vmax=max(pivot_pct.values.max(), 0))

        # 标注数值
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot_pct.values[i, j]
                color = "white" if abs(val) > 50 else "black"
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                        fontsize=8, color=color, fontweight="bold")

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{v:.2%}" for v in pivot.columns], rotation=45)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{v:.2%}" for v in pivot.index])
        ax.set_xlabel("止盈 (TP)")
        ax.set_ylabel("止损 (SL)")
        ax.set_title(f"WeakTrend={mode}\n总收益率 (%)", fontsize=12, fontweight="bold")

        fig.colorbar(im, ax=ax, shrink=0.8)

    plt.suptitle("BTC 5分钟剥头皮策略 参数网格搜索 (总收益率热力图)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    out_path = os.path.join(CACHE_DIR, "grid_search_heatmap.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  📈 热力图已保存: {out_path}")

    # ── 胜率热力图 ──
    fig2, axes2 = plt.subplots(1, 3, figsize=(20, 6))
    for ax_idx, mode in enumerate(WEAK_TREND_MODES):
        ax = axes2[ax_idx]
        sub = results_df[results_df["weak_trend"] == mode]
        pivot = sub.pivot_table(values="win_rate", index="sl", columns="tp", aggfunc="first")
        pivot_pct = pivot * 100

        im = ax.imshow(pivot_pct.values, cmap="YlOrRd", aspect="auto")
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot_pct.values[i, j]
                color = "white" if val > 70 else "black"
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                        fontsize=8, color=color, fontweight="bold")

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{v:.2%}" for v in pivot.columns], rotation=45)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{v:.2%}" for v in pivot.index])
        ax.set_xlabel("止盈 (TP)")
        ax.set_ylabel("止损 (SL)")
        ax.set_title(f"WeakTrend={mode}\n胜率 (%)", fontsize=12, fontweight="bold")
        fig2.colorbar(im, ax=ax, shrink=0.8)

    plt.suptitle("BTC 5分钟剥头皮策略 参数网格搜索 (胜率热力图)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    out_path2 = os.path.join(CACHE_DIR, "grid_search_winrate.png")
    plt.savefig(out_path2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  📈 胜率热力图已保存: {out_path2}")


if __name__ == "__main__":
    main()
