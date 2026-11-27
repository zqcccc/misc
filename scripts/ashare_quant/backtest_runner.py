"""
A股量化策略回测运行器与 EP004 深度评估集成 (区间右端点由基准实际行情动态推导)
===================================================================
区间划分 (不再硬编码数据截止日, 由 derive_backtest_windows 从基准最新行情推导):
- 全样本 (Full Sample): 2019-01-01 ~ 基准行情最新交易日
- 历史样本内 (In-Sample): 2019-01-01 ~ 2023-12-31 (固定训练分界, 沿用原设计)
- 样本外盲测 (Out-of-Sample): 2024-01-01 ~ 最新绝密段前一交易日
- 最新绝密测试段 (Ultra-Recent OOS): 基准最新交易日前推 6 个自然月后的首个交易日 ~ 最新交易日
"""

import calendar
import json
import os
from bisect import bisect_right
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from scripts.ashare_quant.data_feed import (
    load_all_universe,
    UNIVERSE,
    BENCHMARK_SYMBOL,
    BENCHMARK_NAME
)
from scripts.ashare_quant.engine import BacktestEngine, calculate_performance_metrics
from scripts.ashare_quant.strategy_v2 import RelativeStrengthAlphaStrategy
from scripts.ashare_quant.ep004_evaluator import (
    decompose_alpha_beta,
    compute_deflated_sharpe,
    run_monte_carlo_block_bootstrap
)

DELIVERABLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "deliverables")
os.makedirs(DELIVERABLES_DIR, exist_ok=True)
OUT_JSON = os.path.join(DELIVERABLES_DIR, "ashare_strategy_backtest.json")

# ---------------------------------------------------------------------------
# 日期边界推导与 JSON 原子发布 (纯函数, 便于单测)
# ---------------------------------------------------------------------------

# 固定区间边界沿用原设计 (属策略设计常量, 非数据截止日)
FULL_SAMPLE_START = "2019-01-01"   # 全样本/样本内起点
IN_SAMPLE_END = "2023-12-31"       # 训练段分界
OOS_START = "2024-01-01"           # 样本外起点
# 最新绝密段长度 (原设计: 近半年最新行情检验)
ULTRA_RECENT_MONTHS = 6
# 基准行情最新交易日相对运行日期的最大容忍滞后 (自然日, 覆盖国庆/春节长假)
MAX_DATA_LAG_DAYS = 14


def subtract_months(d: date, months: int) -> date:
    """d 往前推 months 个自然月; 目标月没有对应日时收敛到该月最后一天 (如 2/29 -> 2/28)。"""
    total = d.year * 12 + (d.month - 1) - months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def first_date_on_or_after(dates: List[str], target: str) -> str:
    """返回升序日期序列中第一个 >= target 的日期; 不存在则明确报错。"""
    for d in dates:
        if d >= target:
            return d
    raise ValueError(f"行情日期序列中不存在 >= {target} 的交易日 (最后日期: {dates[-1] if dates else '无'})")


def last_date_before(dates: List[str], target: str) -> str:
    """返回升序日期序列中最后一个 < target 的日期; 不存在则明确报错。"""
    prev = None
    for d in dates:
        if d >= target:
            break
        prev = d
    if prev is None:
        raise ValueError(f"行情日期序列中不存在 < {target} 的交易日 (最早日期: {dates[0] if dates else '无'})")
    return prev


def derive_backtest_windows(bm_df: pd.DataFrame, today: Optional[date] = None) -> Dict[str, str]:
    """
    从基准实际行情推导回测四段区间 (替代旧版写死在代码里的全样本/最新段数据截止日):
    - 全样本: FULL_SAMPLE_START ~ 基准最新交易日 (data_end)
    - 样本内: FULL_SAMPLE_START ~ IN_SAMPLE_END (固定训练分界)
    - 样本外: OOS_START ~ 最新绝密段前一交易日 (oos_end)
    - 最新绝密段: data_end 前推 ULTRA_RECENT_MONTHS 个自然月后的首个交易日 ~ data_end
    空数据 / 日期乱序 / 行情滞后或超前于运行日期时明确抛错, 不回退到任何硬编码截止日。
    """
    if bm_df is None or bm_df.empty or "date" not in bm_df.columns:
        raise ValueError(f"基准行情 {BENCHMARK_SYMBOL} 为空或缺少 date 列, 无法推导回测区间")
    dates = bm_df["date"].dt.strftime("%Y-%m-%d").tolist()
    if any(later <= earlier for earlier, later in zip(dates, dates[1:])):
        raise ValueError("基准行情日期未按升序唯一排列, 缓存数据异常")
    data_end = dates[-1]
    data_end_day = date.fromisoformat(data_end)

    today_eff = today or date.today()
    lag_days = (today_eff - data_end_day).days
    if lag_days < 0:
        raise ValueError(f"基准行情最新日期 {data_end} 晚于运行日期 {today_eff.isoformat()}, 行情数据异常")
    if lag_days > MAX_DATA_LAG_DAYS:
        raise ValueError(
            f"基准行情停滞: 最新日期 {data_end} 距运行日期 {today_eff.isoformat()} 已滞后 {lag_days} 天"
            f" (> {MAX_DATA_LAG_DAYS} 天), 请先运行 refresh_all_data.py 刷新数据"
        )

    ultra_recent_start = first_date_on_or_after(
        dates, subtract_months(data_end_day, ULTRA_RECENT_MONTHS).isoformat()
    )
    oos_end = last_date_before(dates, ultra_recent_start)
    if oos_end < OOS_START:
        raise ValueError(f"样本外区间为空: 最新绝密段之前的交易日早于 {OOS_START} (oos_end={oos_end})")
    if dates[0] > FULL_SAMPLE_START:
        raise ValueError(f"基准行情起始日 {dates[0]} 晚于全样本起点 {FULL_SAMPLE_START}, 全样本区间不成立")

    return {
        "data_end": data_end,
        "full_start": FULL_SAMPLE_START,
        "full_end": data_end,
        "in_sample_end": IN_SAMPLE_END,
        "oos_start": OOS_START,
        "oos_end": oos_end,
        "ultra_recent_start": ultra_recent_start,
        "ultra_recent_end": data_end,
    }


def atomic_write_json(path: str, payload: Any) -> None:
    """
    原子发布 JSON: 写同目录临时文件 -> flush/fsync -> os.replace 原子替换。
    任一步失败都清理临时文件并原样抛出, 不留下看似成功的新文件或半截文件。
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    tmp_path = os.path.join(dir_name, f".{os.path.basename(path)}.{os.getpid()}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def run_single_backtest(
    all_data: Dict[str, pd.DataFrame],
    strategy_params: dict,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000.0,
) -> Dict[str, Any]:
    engine = BacktestEngine(initial_capital=initial_capital)
    strategy = RelativeStrengthAlphaStrategy(**strategy_params)

    bm_df = all_data[BENCHMARK_SYMBOL]
    if bm_df is None or bm_df.empty:
        raise ValueError(f"基准行情 {BENCHMARK_SYMBOL} 无数据, 无法回测 {start_date} ~ {end_date}")
    all_dates = bm_df["date"].dt.strftime("%Y-%m-%d").tolist()

    try:
        start_idx = next(i for i, d in enumerate(all_dates) if d >= start_date)
    except StopIteration:
        raise ValueError(
            f"基准行情中不存在 >= {start_date} 的交易日 (数据范围 {all_dates[0]} ~ {all_dates[-1]}), 回测区间无效"
        ) from None
    warmup_idx = max(0, start_idx - 70)

    # 按日期预索引 (升序唯一校验 + bisect 位置索引), 消除逐日全表布尔过滤与增长切片复制
    date_index: Dict[str, List[str]] = {}
    bar_arrays: Dict[str, Dict[str, np.ndarray]] = {}
    for sym, df in all_data.items():
        d_list = df["date"].dt.strftime("%Y-%m-%d").tolist()
        if any(b <= a for a, b in zip(d_list, d_list[1:])):
            raise ValueError(f"{sym} 行情日期未按升序唯一排列, 缓存数据异常")
        date_index[sym] = d_list
        bar_arrays[sym] = {
            "open": df["open"].to_numpy(dtype=float),
            "high": df["high"].to_numpy(dtype=float),
            "low": df["low"].to_numpy(dtype=float),
            "close": df["close"].to_numpy(dtype=float),
        }

    equity_records = []
    positions_history = []

    for i in range(warmup_idx, len(all_dates)):
        cur_d = all_dates[i]
        if cur_d > end_date:
            break
        if i < start_idx:
            # 预热段只推进日期, 不撮合、不产生信号与结算 (行为与原实现一致)
            continue
        prev_d = all_dates[i - 1]

        daily_bars = {}
        prev_closes = {}
        daily_closes = {}
        slice_map = {}
        for sym, df in all_data.items():
            d_list = date_index[sym]
            hi = bisect_right(d_list, cur_d)
            if hi > 0:
                k = hi - 1
                arr = bar_arrays[sym]
                # iloc 切片共享底层数据, 内容等价于原 date_str <= cur_d 的全表过滤结果
                slice_map[sym] = df.iloc[:hi]
                daily_closes[sym] = float(arr["close"][k])
                if d_list[k] == cur_d:
                    daily_bars[sym] = {
                        "open": float(arr["open"][k]),
                        "high": float(arr["high"][k]),
                        "low": float(arr["low"][k]),
                        "close": float(arr["close"][k]),
                    }
            hp = bisect_right(d_list, prev_d)
            if hp > 0 and d_list[hp - 1] == prev_d:
                prev_closes[sym] = float(bar_arrays[sym]["close"][hp - 1])

        engine.execute_pending_orders(cur_d, daily_bars, prev_closes)

        if BENCHMARK_SYMBOL not in slice_map:
            raise ValueError(f"{cur_d} 基准行情 {BENCHMARK_SYMBOL} 缺失, 无法结算")
        strategy.on_bar_close(cur_d, slice_map, engine)
        regime_healthy = strategy.is_market_healthy(slice_map[BENCHMARK_SYMBOL])
        bm_close = daily_closes[BENCHMARK_SYMBOL]
        rec = engine.end_of_day_settlement(cur_d, daily_closes, bm_close)
        equity_records.append({
            "date": cur_d,
            "equity": rec["total_equity"],
            "cash": rec["cash"],
            "benchmark": bm_close,
            "num_positions": len(engine.positions),
        })
        pos_info = [
            {
                "symbol": s,
                "name": UNIVERSE.get(s, s),
                "shares": p.shares,
                "price": daily_closes.get(s, p.cost_price),
                "value": p.shares * daily_closes.get(s, p.cost_price),
                "weight": (p.shares * daily_closes.get(s, p.cost_price)) / rec["total_equity"]
            }
            for s, p in engine.positions.items()
        ]
        positions_history.append({
            "date": cur_d,
            "holdings": pos_info,
            "cash_weight": rec["cash"] / rec["total_equity"],
            "regime_healthy": regime_healthy,
        })

    eq_df = pd.DataFrame(equity_records)
    eq_df["strategy_net_value"] = eq_df["equity"] / initial_capital
    eq_df["benchmark_net_value"] = eq_df["benchmark"] / eq_df["benchmark"].iloc[0]
    
    eq_vals = eq_df["equity"].values
    running_max = np.maximum.accumulate(eq_vals)
    eq_df["drawdown"] = (eq_vals - running_max) / running_max
    
    bm_vals = eq_df["benchmark"].values
    bm_max = np.maximum.accumulate(bm_vals)
    eq_df["benchmark_drawdown"] = (bm_vals - bm_max) / bm_max

    metrics = calculate_performance_metrics(eq_df, benchmark_col="benchmark")

    # 已实现净盈亏序列: 引擎按 FIFO 批次配对 (成交价含滑点, 成本/费用含佣金印花税),
    # 胜率 / 盈亏比 / 蒙特卡洛共用同一序列, 可由 trades 输出逐笔重建
    closed_trades = [t for t in engine.trades if t.action == "SELL" and t.realized_basis > 0.0]
    realized_pnls = [t.realized_pnl for t in closed_trades]
    realized_rets = [t.realized_pnl / t.realized_basis for t in closed_trades]

    win_cnt = sum(1 for p in realized_pnls if p > 0)
    win_rate = win_cnt / len(realized_pnls) if realized_pnls else 0.0
    wins = [p for p in realized_rets if p > 0]
    losses = [abs(p) for p in realized_rets if p <= 0]
    pl_ratio = (np.mean(wins) / np.mean(losses)) if losses and wins else 0.0
    years = len(eq_df) / 250.0
    total_cost_turnover = sum(abs(t.total_cost) for t in engine.trades)
    turnover = (total_cost_turnover / initial_capital) / years

    metrics.update({
        "win_rate": float(win_rate),
        "profit_loss_ratio": float(pl_ratio),
        "total_trades": len(realized_pnls),
        "annual_turnover": float(turnover),
    })

    strat_daily_rets = np.diff(eq_df["strategy_net_value"]) / eq_df["strategy_net_value"].iloc[:-1]
    bm_daily_rets = np.diff(eq_df["benchmark_net_value"]) / eq_df["benchmark_net_value"].iloc[:-1]

    alpha_decomp = decompose_alpha_beta(strat_daily_rets, bm_daily_rets)
    dsr_result = compute_deflated_sharpe(strat_daily_rets, n_trials=30)
    mc_result = run_monte_carlo_block_bootstrap(realized_rets, iters=5000, block_size=6)

    # 2022 熊市压力测试
    eq_df["year"] = pd.to_datetime(eq_df["date"]).dt.year
    sub_2022 = eq_df[eq_df["year"] == 2022]
    bear_2022 = {}
    if not sub_2022.empty:
        s_2022 = sub_2022["equity"].iloc[-1] / sub_2022["equity"].iloc[0] - 1.0
        b_2022 = sub_2022["benchmark"].iloc[-1] / sub_2022["benchmark"].iloc[0] - 1.0
        mdd_2022 = float(np.min(sub_2022["drawdown"]))
        bear_2022 = {
            "strategy_return": float(s_2022),
            "benchmark_return": float(b_2022),
            "alpha": float(s_2022 - b_2022),
            "max_drawdown": float(mdd_2022),
        }

    yearly = []
    for y, g in eq_df.groupby("year"):
        sy = g["equity"].iloc[-1] / g["equity"].iloc[0] - 1.0
        by = g["benchmark"].iloc[-1] / g["benchmark"].iloc[0] - 1.0
        yearly.append({
            "year": int(y),
            "strategy_return": float(sy),
            "benchmark_return": float(by),
            "alpha": float(sy - by),
            "strategy_mdd": float(np.min(g["drawdown"])),
        })

    return {
        "metrics": metrics,
        "yearly": yearly,
        "alpha_decomp": alpha_decomp,
        "dsr": dsr_result,
        "monte_carlo": mc_result,
        "bear_stress_test": bear_2022,
        "equity_curve": eq_df[["date", "strategy_net_value", "benchmark_net_value", "drawdown", "benchmark_drawdown", "cash", "num_positions"]].to_dict(orient="records"),
        "positions_history": positions_history,
        "trades": [
            {
                "id": t.trade_id, "symbol": t.symbol, "name": UNIVERSE.get(t.symbol, t.symbol),
                "action": t.action, "shares": t.shares, "price": round(t.price, 2),
                "date": t.trade_date, "fee": round(t.fee, 2), "reason": t.reason,
                **({"realized_pnl": round(t.realized_pnl, 2)} if t.action == "SELL" else {})
            }
            for t in engine.trades
        ]
    }


def main():
    all_data = load_all_universe()
    wins = derive_backtest_windows(all_data[BENCHMARK_SYMBOL])
    data_end = wins["data_end"]

    print("=" * 70)
    print(f"开始执行 A 股量化策略回测与最新数据测试 (基准行情截止 {data_end})")
    print(f"区间: 全样本 {wins['full_start']}~{wins['full_end']} / 样本内 {wins['full_start']}~{wins['in_sample_end']} / "
          f"样本外 {wins['oos_start']}~{wins['oos_end']} / 最新绝密段 {wins['ultra_recent_start']}~{wins['ultra_recent_end']}")
    print("=" * 70)

    cfg_top3 = {
        "top_k": 3,
        "rebalance_interval_days": 20,
        "market_filter_ma": 60,
        "rs_window_fast": 20,
        "rs_window_slow": 60,
        "stop_loss_pct": 0.10,
        "trail_activation_pct": 0.15,
        "trail_pullback_pct": 0.08,
        "enable_market_filter": True,
    }

    # 1. 全样本 (2019-01-01 ~ 基准最新交易日)
    print(f"\n>>> 运行: 全样本 ({wins['full_start']} ~ {wins['full_end']})...")
    res_full = run_single_backtest(all_data, cfg_top3, wins["full_start"], wins["full_end"])

    # 2. 样本内 (2019-01-01 ~ 2023-12-31, 固定训练分界)
    print(f"\n>>> 运行: 历史样本内 ({wins['full_start']} ~ {wins['in_sample_end']})...")
    res_is = run_single_backtest(all_data, cfg_top3, wins["full_start"], wins["in_sample_end"])

    # 3. 样本外盲测 (2024-01-01 ~ 最新绝密段前一交易日)
    print(f"\n>>> 运行: 样本外盲测 ({wins['oos_start']} ~ {wins['oos_end']})...")
    res_oos = run_single_backtest(all_data, cfg_top3, wins["oos_start"], wins["oos_end"])

    # 4. 【核心关注】最新绝密测试段 (近半年最新行情检验)
    print(f"\n>>> 运行: 最新绝密测试段 (Ultra-Recent OOS: {wins['ultra_recent_start']} ~ {wins['ultra_recent_end']})...")
    res_recent = run_single_backtest(all_data, cfg_top3, wins["ultra_recent_start"], wins["ultra_recent_end"])

    payload = {
        "metadata": {
            "title": "A股核心赛道龙头截面相对强弱 Alpha 策略 (EP004 增强版)",
            "benchmark": "沪深300ETF (510300.SS)",
            "universe_size": len(UNIVERSE),
            "universe": UNIVERSE,
            "latest_date": data_end,
            "backtest_range": f"{wins['full_start']} ~ {data_end}",
            "oos_range": f"{wins['oos_start']} ~ {wins['oos_end']}",
            "ep004_evaluation": {
                "alpha_decomposition": res_full["alpha_decomp"],
                "deflated_sharpe": res_full["dsr"],
                "monte_carlo_bootstrap": res_full["monte_carlo"],
                "bear_stress_test_2022": res_full["bear_stress_test"],
                "ultra_recent_oos": {
                    "start_date": wins["ultra_recent_start"],
                    "end_date": wins["ultra_recent_end"],
                    "metrics": res_recent["metrics"],
                    "alpha_decomp": res_recent["alpha_decomp"],
                }
            },
        },
        "full_sample_top3": {
            "metrics": res_full["metrics"],
            "yearly_stats": res_full["yearly"],
            "equity_curve": res_full["equity_curve"],
            "recent_positions": res_full["positions_history"][-20:],
            "recent_trades": res_full["trades"][-50:],
        },
        "in_sample": {
            "metrics": res_is["metrics"],
            "yearly_stats": res_is["yearly"],
            "alpha_decomp": res_is["alpha_decomp"],
        },
        "out_of_sample": {
            "metrics": res_oos["metrics"],
            "yearly_stats": res_oos["yearly"],
            "alpha_decomp": res_oos["alpha_decomp"],
            "equity_curve": res_oos["equity_curve"],
        },
        "ultra_recent_oos": {
            "metrics": res_recent["metrics"],
            "yearly_stats": res_recent["yearly"],
            "alpha_decomp": res_recent["alpha_decomp"],
            "equity_curve": res_recent["equity_curve"],
        }
    }

    atomic_write_json(OUT_JSON, payload)

    print(f"\n[DONE] 最新回测数据更新完成，写入: {OUT_JSON}")


if __name__ == "__main__":
    main()
