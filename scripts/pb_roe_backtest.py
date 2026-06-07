"""
PB + ROE 双打分选股策略回测 v3
================================
核心改进:
  1. 排除B股(200/900开头)，只选A股
  2. 用全年数据获取年末价格，大幅提升数据覆盖
  3. 每年5月初再平衡，等权持仓
  4. 输出完整持股明细（股票名称、ROE、PB、持仓收益）
  5. ROE >= 10% 质量门槛，PB 0.5~5.0 合理范围

策略逻辑:
  - 全市场A股，ROE >= 10%，PB 在 0.5~5.0
  - ROE排名百分位 + (1 - PB排名百分位) = 综合得分
  - 选 Top 30，等权，每年5月初调仓
"""

import akshare as ak
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import time
import os
import json
import warnings
warnings.filterwarnings("ignore")

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False

TOP_N = 30
ROE_MIN = 10.0
PB_MIN = 0.5
PB_MAX = 5.0
REBALANCE_MONTH = 5
START_YEAR = 2015
END_YEAR = 2024
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache_pb_roe_v3")
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(name):
    return os.path.join(CACHE_DIR, name)


def load_cache(name):
    p = _cache_path(name)
    if os.path.exists(p):
        return pd.read_csv(p)
    return None


def save_cache(df, name):
    df.to_csv(_cache_path(name), index=False)


def symbol_to_sina(symbol):
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    elif symbol.startswith(("0", "2", "3")):
        return f"sz{symbol}"
    return f"sh{symbol}"


def fetch_yjbb(year):
    cache_name = f"yjbb_{year}.csv"
    cache = load_cache(cache_name)
    if cache is not None:
        return cache
    date_str = f"{year}1231"
    print(f"  获取 {year} 年业绩报表...")
    for attempt in range(3):
        try:
            df = ak.stock_yjbb_em(date=date_str)
            if df is not None and not df.empty:
                save_cache(df, cache_name)
                time.sleep(1)
                return df
        except Exception as e:
            print(f"    重试 {attempt+1}: {e}")
            time.sleep(5 * (attempt + 1))
    return pd.DataFrame()


def parse_yjbb(raw_df):
    if raw_df.empty:
        return pd.DataFrame()
    cols = raw_df.columns.tolist()
    symbol_col = [c for c in cols if "代码" in str(c)][0]
    name_col = [c for c in cols if "简称" in str(c)][0]
    roe_col = None
    bps_col = None
    for c in cols:
        if "净资产收益率" in str(c):
            if "加权" in str(c) or roe_col is None:
                roe_col = c
        if "每股净资产" in str(c):
            bps_col = c

    result = raw_df[[symbol_col, name_col]].copy()
    result = result.rename(columns={symbol_col: "symbol", name_col: "name"})
    result["symbol"] = result["symbol"].astype(str).str.zfill(6)

    if roe_col:
        result["roe"] = pd.to_numeric(raw_df[roe_col], errors="coerce")
    else:
        result["roe"] = np.nan
    if bps_col:
        result["bps"] = pd.to_numeric(raw_df[bps_col], errors="coerce")
    else:
        result["bps"] = np.nan

    result = result[~result["name"].str.contains("ST|退", na=False)]
    result = result[~result["symbol"].str.startswith(("4", "8", "9", "2"))]
    result = result[result["symbol"].str.match(r"^\d{6}$")]
    return result


def fetch_year_end_price_batch(symbols, year):
    """批量获取年末收盘价，用全年数据确保覆盖"""
    prices = {}
    for sym in symbols:
        cache_name = f"yep_{sym}_{year}.csv"
        cache = load_cache(cache_name)
        if cache is not None and not cache.empty:
            prices[sym] = float(cache.iloc[0]["close"])
            continue

        sina_sym = symbol_to_sina(sym)
        start = f"{year}0101"
        end = f"{year}1231"
        for attempt in range(2):
            try:
                df = ak.stock_zh_a_daily(
                    symbol=sina_sym, start_date=start, end_date=end, adjust="qfq"
                )
                if df is not None and not df.empty:
                    close = float(df.iloc[-1]["close"])
                    save_cache(pd.DataFrame({"close": [close]}), cache_name)
                    prices[sym] = close
                    break
            except Exception:
                time.sleep(0.15)
        if sym not in prices:
            prices[sym] = np.nan
        time.sleep(0.06)
    return prices


def fetch_hold_period_return(symbol, start_date, end_date):
    cache_name = f"price_{symbol}.csv"
    cache = load_cache(cache_name)
    if cache is not None:
        cache["date"] = pd.to_datetime(cache["date"])
        mask = (cache["date"] >= start_date) & (cache["date"] <= end_date)
        sub = cache.loc[mask].sort_values("date")
        if len(sub) >= 2:
            return sub["close"].iloc[-1] / sub["close"].iloc[0] - 1
        return np.nan

    sina_sym = symbol_to_sina(symbol)
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_daily(
                symbol=sina_sym,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"
            )
            if df is not None and not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                df = df[["date", "close"]].copy()
                save_cache(df, cache_name)
                sub = df.sort_values("date")
                if len(sub) >= 2:
                    return sub["close"].iloc[-1] / sub["close"].iloc[0] - 1
                return np.nan
        except Exception:
            time.sleep(0.15)
    return np.nan


def fetch_index_data():
    cache_name = "index_hs300.csv"
    cache = load_cache(cache_name)
    if cache is not None:
        cache["date"] = pd.to_datetime(cache["date"])
        return cache
    for attempt in range(3):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000300")
            if df is not None and not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                df = df[["date", "close"]].copy()
                save_cache(df, cache_name)
                return df
        except Exception as e:
            print(f"    沪深300重试 {attempt+1}: {e}")
            time.sleep(3)
    return pd.DataFrame()


def score_and_select(candidates_df, top_n=TOP_N):
    """
    candidates_df: columns = [symbol, name, roe, pb]
    PB越低分越高，ROE越高分越高
    """
    df = candidates_df.copy()
    df = df.dropna(subset=["roe", "pb"])
    df = df[(df["pb"] >= PB_MIN) & (df["pb"] <= PB_MAX)]
    df = df[df["roe"] >= ROE_MIN]

    if len(df) < top_n:
        top_n = len(df)
    if top_n == 0:
        return pd.DataFrame()

    df["roe_score"] = df["roe"].rank(pct=True)
    df["pb_score"] = 1 - df["pb"].rank(pct=True)
    df["total_score"] = df["roe_score"] + df["pb_score"]
    df = df.sort_values("total_score", ascending=False).head(top_n)
    return df


def run_backtest():
    print("=" * 60)
    print("  PB + ROE 双打分选股策略回测 v3")
    print(f"  回测区间: {START_YEAR} ~ {END_YEAR}")
    print(f"  选股数量: Top {TOP_N}")
    print(f"  ROE门槛: >= {ROE_MIN}%")
    print(f"  PB范围: {PB_MIN} ~ {PB_MAX}")
    print(f"  排除: B股、北交所、ST")
    print(f"  调仓: 每年5月初再平衡，等权持仓")
    print("=" * 60)

    index_df = fetch_index_data()

    yearly_returns = {}
    yearly_bench = {}
    portfolio_nav = [1.0]
    benchmark_nav = [1.0]
    nav_dates = [datetime(START_YEAR, REBALANCE_MONTH, 1)]
    all_holdings = {}

    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n{'='*50}")
        print(f"  {year} 年调仓 (基于 {year-1} 年报)")
        print(f"{'='*50}")

        raw_df = fetch_yjbb(year - 1)
        if raw_df.empty:
            print(f"  {year-1} 年报为空，跳过")
            yearly_returns[year] = 0.0
            yearly_bench[year] = 0.0
            portfolio_nav.append(portfolio_nav[-1])
            benchmark_nav.append(benchmark_nav[-1])
            nav_dates.append(datetime(year + 1, REBALANCE_MONTH, 1))
            continue

        fin_df = parse_yjbb(raw_df)
        roe_valid = fin_df.dropna(subset=["roe"])
        roe_valid = roe_valid[roe_valid["roe"] > 0]
        print(f"  有ROE数据的A股: {len(roe_valid)} 只")

        bps_valid = roe_valid.dropna(subset=["bps"])
        bps_valid = bps_valid[bps_valid["bps"] > 0]
        print(f"  有每股净资产的: {len(bps_valid)} 只")

        print(f"  获取 {len(bps_valid)} 只股票的年末收盘价...")
        prices = fetch_year_end_price_batch(bps_valid["symbol"].tolist(), year - 1)

        candidates = []
        for _, row in bps_valid.iterrows():
            sym = row["symbol"]
            price = prices.get(sym, np.nan)
            if np.isnan(price) or price <= 0:
                continue
            pb = price / row["bps"]
            candidates.append({
                "symbol": sym,
                "name": row["name"],
                "roe": row["roe"],
                "bps": row["bps"],
                "year_end_price": price,
                "pb": pb,
            })

        candidates_df = pd.DataFrame(candidates)
        print(f"  成功计算PB: {len(candidates_df)} 只")

        in_range = candidates_df[
            (candidates_df["pb"] >= PB_MIN) & (candidates_df["pb"] <= PB_MAX) &
            (candidates_df["roe"] >= ROE_MIN)
        ]
        print(f"  满足 ROE>={ROE_MIN}% & PB在{PB_MIN}~{PB_MAX}: {len(in_range)} 只")

        selected_df = score_and_select(candidates_df, TOP_N)
        if selected_df.empty:
            print(f"  选股失败，跳过")
            yearly_returns[year] = 0.0
            yearly_bench[year] = 0.0
            portfolio_nav.append(portfolio_nav[-1])
            benchmark_nav.append(benchmark_nav[-1])
            nav_dates.append(datetime(year + 1, REBALANCE_MONTH, 1))
            continue

        print(f"\n  📋 {year} 年持仓明细 (Top {len(selected_df)} 只)")
        print(f"  {'代码':<8}{'名称':<10}{'ROE':>8}{'PB':>8}{'综合分':>8}")
        print("  " + "-" * 46)
        for _, r in selected_df.iterrows():
            print(f"  {r['symbol']:<8}{r['name']:<10}{r['roe']:>7.1f}%{r['pb']:>8.2f}{r['total_score']:>8.3f}")

        hold_start = datetime(year, REBALANCE_MONTH, 1)
        hold_end = datetime(year + 1, REBALANCE_MONTH, 1)

        print(f"\n  计算持仓收益 ({hold_start.strftime('%Y-%m')} ~ {hold_end.strftime('%Y-%m')})...")
        holdings_detail = []
        for _, r in selected_df.iterrows():
            sym = r["symbol"]
            ret = fetch_hold_period_return(sym, hold_start, hold_end)
            holdings_detail.append({
                "symbol": sym,
                "name": r["name"],
                "roe": r["roe"],
                "pb": r["pb"],
                "total_score": r["total_score"],
                "hold_return": ret if not np.isnan(ret) else None,
            })

        valid_rets = [h["hold_return"] for h in holdings_detail if h["hold_return"] is not None]
        port_ret = np.mean(valid_rets) if valid_rets else 0.0
        yearly_returns[year] = port_ret

        if not index_df.empty:
            idx_s = index_df[(index_df["date"] >= hold_start) & (index_df["date"] <= hold_end)]
            if len(idx_s) >= 2:
                bench_ret = idx_s.iloc[-1]["close"] / idx_s.iloc[0]["close"] - 1
            else:
                bench_ret = 0.0
        else:
            bench_ret = 0.0
        yearly_bench[year] = bench_ret

        portfolio_nav.append(portfolio_nav[-1] * (1 + port_ret))
        benchmark_nav.append(benchmark_nav[-1] * (1 + bench_ret))
        nav_dates.append(hold_end)

        all_holdings[year] = holdings_detail

        n_valid = len(valid_rets)
        n_total = len(holdings_detail)
        print(f"\n  ✓ 组合: {port_ret:.2%}  |  沪深300: {bench_ret:.2%}  |  超额: {port_ret - bench_ret:.2%}  |  有效: {n_valid}/{n_total}")

        print(f"\n  📊 {year} 年个股收益明细:")
        print(f"  {'代码':<8}{'名称':<10}{'ROE':>8}{'PB':>8}{'持仓收益':>10}")
        print("  " + "-" * 48)
        for h in sorted(holdings_detail, key=lambda x: x.get("hold_return") or -999, reverse=True):
            ret_str = f"{h['hold_return']:.2%}" if h["hold_return"] is not None else "N/A"
            print(f"  {h['symbol']:<8}{h['name']:<10}{h['roe']:>7.1f}%{h['pb']:>8.2f}{ret_str:>10}")

    portfolio_nav = np.array(portfolio_nav)
    benchmark_nav = np.array(benchmark_nav)

    running_max = np.maximum.accumulate(portfolio_nav)
    drawdown = (portfolio_nav - running_max) / running_max
    max_dd = drawdown.min()

    bench_running_max = np.maximum.accumulate(benchmark_nav)
    bench_dd = (benchmark_nav - bench_running_max) / bench_running_max
    bench_max_dd = bench_dd.min()

    total_return = portfolio_nav[-1] / portfolio_nav[0] - 1
    bench_total_return = benchmark_nav[-1] / benchmark_nav[0] - 1

    years = END_YEAR - START_YEAR + 1
    annual_return = (1 + total_return) ** (1 / years) - 1
    bench_annual = (1 + bench_total_return) ** (1 / years) - 1

    ann_rets = np.array([portfolio_nav[i] / portfolio_nav[i - 1] - 1 for i in range(1, len(portfolio_nav))])
    sharpe = np.mean(ann_rets) / np.std(ann_rets) if np.std(ann_rets) > 0 else 0

    print("\n" + "=" * 60)
    print("  📊 回测结果汇总")
    print("=" * 60)
    print(f"  回测区间:       {START_YEAR} ~ {END_YEAR} ({years} 年)")
    print(f"  总收益率:       组合 {total_return:.2%}  |  沪深300 {bench_total_return:.2%}")
    print(f"  年化收益率:     组合 {annual_return:.2%}  |  沪深300 {bench_annual:.2%}")
    print(f"  最大回撤:       组合 {max_dd:.2%}  |  沪深300 {bench_max_dd:.2%}")
    print(f"  夏普比率:       {sharpe:.2f}")
    print()
    print(f"  {'年份':<8}{'组合':>10}{'沪深300':>10}{'超额':>10}")
    print("  " + "-" * 40)
    for y in range(START_YEAR, END_YEAR + 1):
        ex = yearly_returns.get(y, 0) - yearly_bench.get(y, 0)
        print(f"  {y:<8}{yearly_returns.get(y, 0):>10.2%}{yearly_bench.get(y, 0):>10.2%}{ex:>10.2%}")

    plot_results(nav_dates, portfolio_nav, benchmark_nav, drawdown, bench_dd,
                 yearly_returns, yearly_bench, annual_return, max_dd, sharpe)

    results = {
        "strategy": "PB+ROE 双打分 v3",
        "top_n": TOP_N,
        "roe_min": ROE_MIN,
        "pb_range": f"{PB_MIN}-{PB_MAX}",
        "period": f"{START_YEAR}-{END_YEAR}",
        "total_return": f"{total_return:.2%}",
        "annual_return": f"{annual_return:.2%}",
        "max_drawdown": f"{max_dd:.2%}",
        "sharpe": f"{sharpe:.2f}",
        "yearly_returns": {str(y): f"{yearly_returns.get(y, 0):.2%}" for y in range(START_YEAR, END_YEAR + 1)},
        "yearly_bench": {str(y): f"{yearly_bench.get(y, 0):.2%}" for y in range(START_YEAR, END_YEAR + 1)},
        "holdings": {
            str(y): [
                {
                    "symbol": h["symbol"],
                    "name": h["name"],
                    "roe": round(h["roe"], 2),
                    "pb": round(h["pb"], 2),
                    "score": round(h["total_score"], 3),
                    "hold_return": f"{h['hold_return']:.2%}" if h["hold_return"] is not None else "N/A",
                }
                for h in holdings
            ]
            for y, holdings in all_holdings.items()
        },
    }
    result_path = _cache_path("backtest_result.json")
    with open(result_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {result_path}")
    return results


def plot_results(dates, nav, bench_nav, dd, bench_dd,
                 yearly_ret, yearly_bench, annual_ret, max_dd, sharpe):
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={"height_ratios": [3, 1.5, 1.5]})

    ax1 = axes[0]
    ax1.plot(dates, nav, "b-", linewidth=2, label="PB+ROE 组合")
    ax1.plot(dates, bench_nav, "gray", linewidth=1.5, label="沪深300", alpha=0.7)
    ax1.set_title(f"PB+ROE 双打分策略 v3  |  年化 {annual_ret:.1%}  最大回撤 {max_dd:.1%}  夏普 {sharpe:.2f}",
                  fontsize=14, fontweight="bold")
    ax1.set_ylabel("净值")
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax2 = axes[1]
    ax2.fill_between(dates, dd, 0, color="red", alpha=0.4, label="组合回撤")
    ax2.fill_between(dates, bench_dd, 0, color="gray", alpha=0.3, label="沪深300回撤")
    ax2.set_title("回撤", fontsize=12)
    ax2.set_ylabel("回撤")
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax3 = axes[2]
    years_list = sorted(yearly_ret.keys())
    x = np.arange(len(years_list))
    w = 0.35
    ax3.bar(x - w / 2, [yearly_ret[y] for y in years_list], w, label="组合", color="steelblue", alpha=0.8)
    ax3.bar(x + w / 2, [yearly_bench.get(y, 0) for y in years_list], w, label="沪深300", color="gray", alpha=0.6)
    ax3.set_title("各年度收益率", fontsize=12)
    ax3.set_xticks(x)
    ax3.set_xticklabels(years_list)
    ax3.set_ylabel("收益率")
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3, axis="y")
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

    plt.tight_layout()
    out_path = _cache_path("pb_roe_backtest.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  图表已保存: {out_path}")


if __name__ == "__main__":
    run_backtest()
