"""
BTC 5分钟剥头皮 —— 好盈亏比专项搜索
====================================
重点测试 TP >= SL 的组合 (R:R >= 1:1)
搜索更宽的 TP 范围 (到 3%)
用三种费率: 零摩擦 / Maker(0.02%) / Taker(0.05%)
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os, sys, time, itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from btc_scalping_backtest import fetch_ohlcv, compute_indicators, CACHE_DIR, INITIAL_CAPITAL
from btc_scalping_grid_search import generate_signals_parameterized

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False

SLIPPAGE = 0.0001

# 更宽的 TP 范围，重点覆盖好盈亏比
TP_GRID = [0.003, 0.005, 0.008, 0.010, 0.015, 0.020, 0.025, 0.030]
SL_GRID = [0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.010]
MODES = ["off", "strict", "normal"]

FEE_LEVELS = {
    "零摩擦":     0.0,
    "Maker0.02%": 0.0002,
    "Taker0.05%": 0.0005,
}


def fast_backtest(closes, highs, lows, signals, tp, sl, fee_single, slippage):
    friction = (fee_single + slippage) * 2
    capital = INITIAL_CAPITAL
    position = 0
    entry_price = 0.0
    wins = losses = 0
    total_win = total_loss = 0.0
    peak = capital
    max_dd = 0.0

    for i in range(len(closes)):
        if position != 0:
            h, l = highs[i], lows[i]
            exited = False
            ep = 0.0
            if position == 1:
                if (entry_price - l) / entry_price >= sl:
                    ep = entry_price * (1 - sl); exited = True
                elif (h - entry_price) / entry_price >= tp:
                    ep = entry_price * (1 + tp); exited = True
            else:
                if (h - entry_price) / entry_price >= sl:
                    ep = entry_price * (1 + sl); exited = True
                elif (entry_price - l) / entry_price >= tp:
                    ep = entry_price * (1 - tp); exited = True
            if exited:
                gross = position * (ep - entry_price) / entry_price
                net = gross - friction
                capital += capital * net
                if net > 0: wins += 1; total_win += net
                else: losses += 1; total_loss += net
                if capital > peak: peak = capital
                dd = (capital - peak) / peak if peak > 0 else 0
                if dd < max_dd: max_dd = dd
                position = 0

        if position == 0 and signals[i] != 0:
            position = int(signals[i])
            entry_price = closes[i]

    if position != 0:
        gross = position * (closes[-1] - entry_price) / entry_price
        net = gross - friction
        capital += capital * net
        if net > 0: wins += 1; total_win += net
        else: losses += 1; total_loss += net

    t = wins + losses
    return {
        "total_return": capital / INITIAL_CAPITAL - 1,
        "win_rate": wins / t if t > 0 else 0,
        "trades": t,
        "max_dd": max_dd,
        "pf": abs(total_win / total_loss) if total_loss != 0 else float("inf"),
        "capital": capital,
        "wins": wins,
        "losses": losses,
        "avg_win": total_win / wins if wins > 0 else 0,
        "avg_loss": total_loss / losses if losses > 0 else 0,
    }


def main():
    print("=" * 80)
    print("  BTC 5分钟剥头皮 —— 好盈亏比 (TP≥SL) 专项搜索")
    print("=" * 80)

    df = fetch_ohlcv(days=365)
    print("\n  计算指标...")
    df = compute_indicators(df)
    closes = df["close"].values.astype(np.float64)
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)

    btc_ret = closes[-1] / closes[0] - 1
    print(f"  BTC Buy & Hold: {btc_ret:+.2%}")

    # 预生成信号
    print("  预生成信号...")
    sig_cache = {}
    for m in MODES:
        sigs, _ = generate_signals_parameterized(df, weak_trend_mode=m)
        sig_cache[m] = sigs
        print(f"    {m:<8} → {np.count_nonzero(sigs):>6} 信号")

    # 只保留 TP >= SL 的组合 (好盈亏比)
    good_rr = [(tp, sl) for tp, sl in itertools.product(TP_GRID, SL_GRID) if tp >= sl]
    all_combos = [(tp, sl, m) for tp, sl in good_rr for m in MODES]
    print(f"\n  好盈亏比组合 (TP≥SL): {len(good_rr)} 对 × {len(MODES)} 模式 = {len(all_combos)} 组")

    # 跑所有组合 × 所有费率
    all_results = []
    t0 = time.time()
    for idx, (tp, sl, mode) in enumerate(all_combos):
        sigs = sig_cache[mode]
        for fee_name, fee_val in FEE_LEVELS.items():
            st = fast_backtest(closes, highs, lows, sigs, tp, sl, fee_val, SLIPPAGE)
            rr = tp / sl
            all_results.append({
                "tp": tp, "sl": sl, "rr": rr, "rr_str": f"{rr:.1f}:1",
                "mode": mode, "fee": fee_name,
                **st, "alpha": st["total_return"] - btc_ret,
            })
        if (idx + 1) % 50 == 0:
            print(f"  [{idx+1}/{len(all_combos)}] ({time.time()-t0:.1f}s)")

    print(f"  完成 {len(all_results)} 次回测 ({time.time()-t0:.1f}s)")

    rdf = pd.DataFrame(all_results)

    # ============================================================
    # 1. 各费率下盈利组合
    # ============================================================
    for fee_name in FEE_LEVELS:
        sub = rdf[rdf["fee"] == fee_name].sort_values("total_return", ascending=False)
        profitable = sub[sub["total_return"] > 0]

        print(f"\n{'='*90}")
        print(f"  {fee_name} 下盈利组合: {len(profitable)} / {len(sub)}")
        print(f"{'='*90}")

        if len(profitable) > 0:
            print(f"  {'TP':>6}{'SL':>6}{'R:R':>6}{'Mode':>8}{'收益':>9}{'胜率':>7}{'交易':>6}{'PF':>6}{'回撤':>8}{'alpha':>8}{'平均赢':>9}{'平均亏':>9}")
            print("  " + "-" * 89)
            for _, r in profitable.head(20).iterrows():
                print(
                    f"  {r['tp']:.2%}{r['sl']:.2%}{r['rr_str']:>6}{r['mode']:>8}"
                    f"{r['total_return']:>+8.1%}{r['win_rate']:>6.1%}{r['trades']:>6}"
                    f"{r['pf']:>6.2f}{r['max_dd']:>8.1%}{r['alpha']:>+8.1%}"
                    f"{r['avg_win']:>9.4%}{r['avg_loss']:>9.4%}"
                )
        else:
            print("  无盈利组合")

        # Top 5 不管盈亏
        print(f"\n  Top 5 (亏损最少):")
        print(f"  {'TP':>6}{'SL':>6}{'R:R':>6}{'Mode':>8}{'收益':>9}{'胜率':>7}{'交易':>6}{'PF':>6}{'回撤':>8}{'alpha':>8}")
        print("  " + "-" * 73)
        for _, r in sub.head(5).iterrows():
            print(
                f"  {r['tp']:.2%}{r['sl']:.2%}{r['rr_str']:>6}{r['mode']:>8}"
                f"{r['total_return']:>+8.1%}{r['win_rate']:>6.1%}{r['trades']:>6}"
                f"{r['pf']:>6.2f}{r['max_dd']:>8.1%}{r['alpha']:>+8.1%}"
            )

    # ============================================================
    # 2. 盈亏比 vs 收益率 散点图
    # ============================================================
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))

    for ax_idx, fee_name in enumerate(FEE_LEVELS):
        ax = axes[ax_idx]
        sub = rdf[rdf["fee"] == fee_name]

        for mode, marker, color in [("off", "o", "#2196F3"), ("strict", "s", "#FF9800"), ("normal", "^", "#F44336")]:
            ms = sub[sub["mode"] == mode]
            ax.scatter(ms["rr"], ms["total_return"] * 100, c=color, marker=marker,
                       alpha=0.6, s=40, label=mode, edgecolors="none")

        ax.axhline(y=0, color="black", linewidth=1)
        ax.axhline(y=btc_ret * 100, color="orange", linewidth=1.5, linestyle="--",
                   label=f"BTC B&H ({btc_ret:.1%})")
        ax.set_xlabel("盈亏比 (TP/SL)", fontsize=11)
        ax.set_ylabel("总收益率 (%)", fontsize=11)
        ax.set_title(f"{fee_name}", fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    plt.suptitle("好盈亏比 (TP≥SL) 下的策略收益率", fontsize=14, fontweight="bold")
    plt.tight_layout()
    out1 = os.path.join(CACHE_DIR, "good_rr_scatter.png")
    plt.savefig(out1, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  📈 散点图: {out1}")

    # ============================================================
    # 3. 热力图: off 模式下 TP×SL（好盈亏比区域）
    # ============================================================
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    for ax_idx, fee_name in enumerate(FEE_LEVELS):
        ax = axes[ax_idx]
        sub = rdf[(rdf["fee"] == fee_name) & (rdf["mode"] == "off")]
        if sub.empty:
            continue

        pivot = sub.pivot_table(values="total_return", index="sl", columns="tp", aggfunc="first")
        pivot_pct = pivot * 100

        vmax = max(abs(pivot_pct.values.min()), abs(pivot_pct.values.max()), 1)
        im = ax.imshow(pivot_pct.values, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)

        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot_pct.values[i, j]
                if np.isnan(val):
                    continue
                color = "white" if abs(val) > vmax * 0.6 else "black"
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                        fontsize=7, color=color, fontweight="bold")

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{v:.1%}" for v in pivot.columns], rotation=45, fontsize=8)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{v:.1%}" for v in pivot.index], fontsize=8)
        ax.set_xlabel("止盈 (TP)")
        ax.set_ylabel("止损 (SL)")
        ax.set_title(f"WeakTrend=off  |  {fee_name}", fontsize=11, fontweight="bold")
        fig.colorbar(im, ax=ax, shrink=0.8)

    plt.suptitle("好盈亏比区域热力图 (收益率 %, 仅显示 TP≥SL 的格子)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out2 = os.path.join(CACHE_DIR, "good_rr_heatmap.png")
    plt.savefig(out2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  📈 热力图: {out2}")

    # ============================================================
    # 4. 关键对比: 好盈亏比 vs 差盈亏比
    # ============================================================
    print(f"\n{'='*90}")
    print(f"  📊 好盈亏比 vs 差盈亏比 对比 (Maker 0.02% 费率)")
    print(f"{'='*90}")

    maker = rdf[rdf["fee"] == "Maker0.02%"]
    good = maker[maker["rr"] >= 1.0].sort_values("total_return", ascending=False)
    bad = maker[maker["rr"] < 1.0]  # 不会有，因为我们只搜了 TP>=SL

    # 按盈亏比分组看平均收益
    print(f"\n  按盈亏比区间的平均收益 (Maker费率, off模式):")
    off_maker = maker[maker["mode"] == "off"]
    bins = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 20.0)]
    print(f"  {'R:R区间':<12}{'组合数':>6}{'平均收益':>10}{'最佳收益':>10}{'平均胜率':>10}{'平均PF':>8}")
    print("  " + "-" * 56)
    for lo, hi in bins:
        b = off_maker[(off_maker["rr"] >= lo) & (off_maker["rr"] < hi)]
        if len(b) == 0:
            continue
        print(
            f"  {lo:.1f}~{hi:.1f}x     {len(b):>6}"
            f"{b['total_return'].mean():>10.1%}"
            f"{b['total_return'].max():>10.1%}"
            f"{b['win_rate'].mean():>10.1%}"
            f"{b['pf'].mean():>8.2f}"
        )

    # 保存
    save_path = os.path.join(CACHE_DIR, "good_rr_results.csv")
    rdf.to_csv(save_path, index=False)
    print(f"\n  📄 结果: {save_path}")


if __name__ == "__main__":
    main()
