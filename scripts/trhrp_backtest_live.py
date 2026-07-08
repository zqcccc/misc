#!/usr/bin/env python3
"""TRHRP 多市场回测 — 用「真实 monitor/trhrp_strategy.py 口径」跑全部 21 个标的.

与旧 trhrp_backtest_all.py 的唯一区别: regime 信号改用 monitor 的
trhrp_strategy.build_signal_frame (当日 regime, 与 monitor 显示的 currentRegime 一致),
而不是 skill 引擎的 build_equity_signal(其内部对信号 shift(1), 导致标签比 monitor 晚一天).

NAV 数学(日频全再平衡)复用 skill 引擎的辅助函数, 以保证与既有看板/报告结构兼容.

数据全部离线:
  - 股票腿 = monitor/caches/TRHRP/yf_cache/<safe>.csv
  - 防御腿 = GLD.csv (干净) + SHY.csv (SGOV_combined.csv 已损坏, 用 SHY 等价替代)
FX 约定: 全部 USD 计价 (沿用 trhrp_ema_batch.py).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

# 路径可经环境变量覆盖, 默认沿用本机布局(本地运行行为不变).
# 部署到容器时由 docker/trhrp-data 设置:
#   TRHRP_ROOT / TRHRP_CFG / TRHRP_OUT / TRHRP_YF_CACHE / TRHRP_DEF_CACHE / TRHRP_STRATEGY
SKILL_SCRIPTS = os.environ.get(
    "TRHRP_SKILL_SCRIPTS",
    "/Users/gongzhao/.workbuddy/skills/trhrp-backtest/scripts",
)
MON_ROOT = os.environ.get("TRHRP_ROOT", "/Users/gongzhao/code/misc")
CFG_PATH = Path(os.environ.get("TRHRP_CFG", Path(MON_ROOT) / "monitor/strategies_trhrp.json"))
YF_CACHE = Path(os.environ.get("TRHRP_YF_CACHE", Path(MON_ROOT) / "monitor/caches/TRHRP/yf_cache"))
DEF_CACHE = Path(os.environ.get("TRHRP_DEF_CACHE", Path(MON_ROOT) / "scripts/_trhrp_def_cache"))
OUT_ROOT = Path(os.environ.get("TRHRP_OUT", Path(MON_ROOT) / "deliverables/trhrp_backtest_all"))

# 内置 helper 优先(随仓库部署, 不依赖本机 WorkBuddy skill 目录);
# 仅当内置缺失时回退到本地 skill 目录.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "trhrp_lib"))
try:
    import backtest_trhrp as eng  # noqa: E402
except ImportError:
    sys.path.insert(0, SKILL_SCRIPTS)
    import backtest_trhrp as eng  # noqa: E402

sys.path.insert(0, str(Path(os.environ.get("TRHRP_STRATEGY", Path(MON_ROOT) / "monitor"))))
import trhrp_strategy as ts  # noqa: E402

REGIME_CN = {"risk_on": "风险偏好", "moderate": "中性", "risk_off": "风险规避"}


def safe_name(t: str) -> str:
    return t.replace("^", "IDX_").replace("=", "_").replace("/", "_")


def compact_ts(ts_rows: list) -> list:
    out = []
    for r in ts_rows:
        out.append({
            "d": r["date"],
            "s": r["strategy_nav"],
            "b": r["benchmark_nav"],
            "c": r["cash_nav"],
            "e": r["extreme_nav"],
            "v": r["vol_21"],
            "r": r["regime"],
            "o": r["operation"],
            "we": r["weight_equity"],
            "dw": r["equity_weight_delta"],
            "p": r["equity_close"],
        })
    return out


def run_backtest_live(spec, usd_equity, usd_gld, usd_sgov, scenario, overlay,
                      commission_mode, initial_capital, sp):
    """与 skill 的 run_backtest 等价, 但 regime 用 live build_signal_frame (当日)."""
    frame = eng.build_calendar_frame(usd_equity, usd_gld, usd_sgov).copy()
    # 剔除被 ffill 造出的权益休市假交易日(如 HK 国庆), 只保留原始 equity 真实交易日
    frame = frame.loc[frame.index.isin(usd_equity.index)]

    # —— 关键: regime 必须在「原始权益序列」上算 (与 monitor 一致) ——
    # build_calendar_frame 的 .ffill() 会把休市日(如 HK 国庆)前向填充成假交易日,
    # 若在其上算 regime 会导致标签错位一天. 故先用原始 equity 算, 再对齐回 frame.
    sig_frame = ts.build_signal_frame(usd_equity["Close"], sp)
    raw_regime = sig_frame["regime"]
    # vol_21 (年化波动率) 同样在原始权益序列上算, 再对齐回 frame; 不 ffill, 早期 NaN 留空
    raw_vol = sig_frame["vol"]
    target_regime = raw_regime.reindex(frame.index).ffill().fillna("moderate")
    vol_series = raw_vol.reindex(frame.index)

    if overlay:
        weights_df = eng.apply_overlay(target_regime, frame["equity_Close"],
                                       overlay["buy_z"], overlay["sell_z"],
                                       overlay["delta"], int(overlay["window"]))
    else:
        weights_df = target_regime.map(lambda r: dict(eng.REGIME_WEIGHTS[r])).apply(pd.Series)

    equity_ret = eng.calc_component_returns(frame, "equity")
    gld_ret = eng.calc_component_returns(frame, "GLD")
    sgov_ret = eng.calc_component_returns(frame, "SGOV")
    valid = equity_ret["close"].notna() & gld_ret["close"].notna() & sgov_ret["close"].notna()
    frame = frame.loc[valid].copy()
    target_regime = target_regime.loc[valid]
    weights_df = weights_df.loc[valid]
    equity_ret = equity_ret.loc[valid]
    gld_ret = gld_ret.loc[valid]
    sgov_ret = sgov_ret.loc[valid]
    vol_series = vol_series.loc[valid]

    strat_close = [initial_capital]
    strat_high, strat_low = [], []
    bench_close = [initial_capital]
    bench_high, bench_low = [], []
    # 平行「现金防御腿」净值: 沿用策略每日 equity 权重, 非标的部分全部换成 SGOV (不持有 GLD).
    # 与策略同口径扣除 equity 再平衡的交易成本, 用于 isolates GLD 防御腿的边际贡献.
    cash_close = [initial_capital]
    cash_current_weights = {
        "equity": float(eng.REGIME_WEIGHTS[str(target_regime.iloc[0])]["equity"]),
        "GLD": 0.0,
        "SGOV": 1.0 - float(eng.REGIME_WEIGHTS[str(target_regime.iloc[0])]["equity"]),
    }
    # 「极致纯择时」: risk_on=满仓(1.0), risk_off=空仓(0.0), moderate=半仓(0.5). 非标的全 SGOV.
    # 用于看「最激进的二元择时」相对「策略温和调仓」的增益.
    _EXTREME_EQ = {"risk_on": 1.0, "moderate": 0.5, "risk_off": 0.0}
    extreme_close = [initial_capital]
    extreme_current_weights = {
        "equity": _EXTREME_EQ[str(target_regime.iloc[0])],
        "GLD": 0.0,
        "SGOV": 1.0 - _EXTREME_EQ[str(target_regime.iloc[0])],
    }
    target_regime_changes = int((target_regime != target_regime.shift(1)).sum())
    rebalance_days = 0
    turnover_sum = 0.0
    total_commission = 0.0
    current_weights = dict(eng.REGIME_WEIGHTS[str(target_regime.iloc[0])])
    regime_days = {"risk_on": 0, "moderate": 0, "risk_off": 0}
    daily_records = []
    prev_regime = None
    prev_equity_weight = None

    bench_entry_cost = 0.0
    if commission_mode == "cnhk":
        bench_entry_cost = initial_capital * eng.CN_HK_ONE_WAY_RATE
    elif commission_mode == "us":
        bench_entry_cost = eng.calc_us_commission(initial_capital, float(frame["equity_Close"].iloc[0]))
    bench_close[0] -= bench_entry_cost

    for date in frame.index:
        state = str(target_regime.loc[date])
        regime_days[state] += 1
        target_weights = {k: float(v) for k, v in weights_df.loc[date].items()}
        next_weights = target_weights if scenario == "daily_full_rebalance" else target_weights
        nav_before = float(strat_close[-1])
        prices = {
            "equity": float(frame.loc[date, "equity_Close"]),
            "GLD": float(frame.loc[date, "GLD_Close"]),
            "SGOV": float(frame.loc[date, "SGOV_Close"]),
        }
        trade_cost = eng.calc_trade_cost(spec.market, nav_before, current_weights, next_weights, prices)
        if trade_cost > eng.EPS:
            rebalance_days += 1
            turnover_sum += eng.turnover_distance(current_weights, next_weights)
            total_commission += trade_cost
        nav_after_cost = max(nav_before - trade_cost, 0.0)
        current_weights = next_weights
        day_close = (current_weights["equity"] * float(equity_ret.loc[date, "close"])
                     + current_weights["GLD"] * float(gld_ret.loc[date, "close"])
                     + current_weights["SGOV"] * float(sgov_ret.loc[date, "close"]))
        day_high = (current_weights["equity"] * float(equity_ret.loc[date, "high"])
                    + current_weights["GLD"] * float(gld_ret.loc[date, "high"])
                    + current_weights["SGOV"] * float(sgov_ret.loc[date, "high"]))
        day_low = (current_weights["equity"] * float(equity_ret.loc[date, "low"])
                   + current_weights["GLD"] * float(gld_ret.loc[date, "low"])
                   + current_weights["SGOV"] * float(sgov_ret.loc[date, "low"]))
        strat_high.append(nav_after_cost * (1.0 + day_high))
        strat_low.append(nav_after_cost * (1.0 + day_low))
        strat_close.append(nav_after_cost * (1.0 + day_close))

        # 平行现金防御腿: equity 权重与策略一致, 其余全部 SGOV, 同口径扣再平衡成本
        cash_eq_next = float(next_weights["equity"])
        cash_next_weights = {"equity": cash_eq_next, "GLD": 0.0, "SGOV": 1.0 - cash_eq_next}
        cash_nav_before = float(cash_close[-1])
        cash_trade_cost = eng.calc_trade_cost(spec.market, cash_nav_before,
                                              cash_current_weights, cash_next_weights, prices)
        cash_nav_after_cost = max(cash_nav_before - cash_trade_cost, 0.0)
        cash_current_weights = cash_next_weights
        cash_day_close = (cash_eq_next * float(equity_ret.loc[date, "close"])
                          + (1.0 - cash_eq_next) * float(sgov_ret.loc[date, "close"]))
        cash_close.append(cash_nav_after_cost * (1.0 + cash_day_close))

        # 极致纯择时: 按 regime 二元/三元切换 equity 权重, 非标的全 SGOV, 同口径扣成本
        ext_eq_next = _EXTREME_EQ[state]
        ext_next_weights = {"equity": ext_eq_next, "GLD": 0.0, "SGOV": 1.0 - ext_eq_next}
        ext_nav_before = float(extreme_close[-1])
        ext_trade_cost = eng.calc_trade_cost(spec.market, ext_nav_before,
                                             extreme_current_weights, ext_next_weights, prices)
        ext_nav_after_cost = max(ext_nav_before - ext_trade_cost, 0.0)
        extreme_current_weights = ext_next_weights
        ext_day_close = (ext_eq_next * float(equity_ret.loc[date, "close"])
                         + (1.0 - ext_eq_next) * float(sgov_ret.loc[date, "close"]))
        extreme_close.append(ext_nav_after_cost * (1.0 + ext_day_close))
        prev_bench = float(bench_close[-1])
        bench_high.append(prev_bench * (1.0 + float(equity_ret.loc[date, "high"])))
        bench_low.append(prev_bench * (1.0 + float(equity_ret.loc[date, "low"])))
        bench_close.append(prev_bench * (1.0 + float(equity_ret.loc[date, "close"])))
        eq_w = float(current_weights["equity"])
        op = "hold"
        op_delta = 0.0
        if prev_equity_weight is not None:
            d = eq_w - prev_equity_weight
            if d > eng.EPS:
                op = "add"
                op_delta = d
            elif d < -eng.EPS:
                op = "reduce"
                op_delta = d
        prev_equity_weight = eq_w
        vol_val = vol_series.loc[date]
        daily_records.append({
            "date": str(date.date()),
            "strategy_nav": round(strat_close[-1] / initial_capital, 6),
            "benchmark_nav": round(bench_close[-1] / initial_capital, 6),
            "cash_nav": round(cash_close[-1] / initial_capital, 6),
            "extreme_nav": round(extreme_close[-1] / initial_capital, 6),
            "vol_21": None if pd.isna(vol_val) else round(float(vol_val), 6),
            "regime": state,
            "regime_changed": prev_regime is not None and state != prev_regime,
            "rebalanced": trade_cost > eng.EPS,
            "operation": op,
            "equity_weight_delta": round(op_delta, 6),
            "weight_equity": round(eq_w, 6),
            "weight_gld": round(float(current_weights["GLD"]), 6),
            "weight_sgov": round(float(current_weights["SGOV"]), 6),
            "equity_close": round(float(prices["equity"]), 6),
        })
        prev_regime = state

    sc = pd.Series(strat_close[1:], index=frame.index)
    sh = pd.Series(strat_high, index=frame.index)
    sl = pd.Series(strat_low, index=frame.index)
    bc = pd.Series(bench_close[1:], index=frame.index)
    bh = pd.Series(bench_high, index=frame.index)
    bl = pd.Series(bench_low, index=frame.index)
    cc = pd.Series(cash_close[1:], index=frame.index)
    ec = pd.Series(extreme_close[1:], index=frame.index)
    strat_total = float(sc.iloc[-1] / initial_capital - 1.0)
    bench_total = float(bc.iloc[-1] / initial_capital - 1.0)
    timing_total = float(cc.iloc[-1] / initial_capital - 1.0)
    extreme_total = float(ec.iloc[-1] / initial_capital - 1.0)
    years = max(len(frame) / 252.0, 1e-9)
    strat_cagr = float(sc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    bench_cagr = float(bc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    timing_cagr = float(cc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    extreme_cagr = float(ec.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    strat_mdd, sp_d, st_d = eng.scan_max_drawdown(sh / initial_capital, sl / initial_capital)
    bench_mdd, bp, bt = eng.scan_max_drawdown(bh / initial_capital, bl / initial_capital)
    # 纯择时只有 close 序列, 用 close 自身做 peak/through 近似 MDD (与策略同口径的 close-only MDD)
    timing_mdd, tp_d, tt_d = eng.scan_max_drawdown(cc / initial_capital, cc / initial_capital)
    extreme_mdd, ep_d, et_d = eng.scan_max_drawdown(ec / initial_capital, ec / initial_capital)
    n_ops = sum(1 for r in daily_records if r["operation"] != "hold")
    n_add = sum(1 for r in daily_records if r["operation"] == "add")
    n_reduce = sum(1 for r in daily_records if r["operation"] == "reduce")
    summary = {
        "strategy_total_return": strat_total, "benchmark_total_return": bench_total,
        "timing_total_return": timing_total,
        "extreme_total_return": extreme_total,
        "excess_total_return": float(strat_total - bench_total),
        "timing_excess_total_return": float(strat_total - timing_total),
        "extreme_excess_total_return": float(strat_total - extreme_total),
        "strategy_cagr": strat_cagr, "benchmark_cagr": bench_cagr,
        "timing_cagr": timing_cagr,
        "extreme_cagr": extreme_cagr,
        "excess_cagr": float(strat_cagr - bench_cagr),
        "strategy_max_drawdown": float(strat_mdd), "benchmark_max_drawdown": float(bench_mdd),
        "timing_max_drawdown": float(timing_mdd),
        "extreme_max_drawdown": float(extreme_mdd),
        "strategy_peak_date": sp_d, "strategy_trough_date": st_d,
        "benchmark_peak_date": bp, "benchmark_trough_date": bt,
        "timing_peak_date": tp_d, "timing_trough_date": tt_d,
        "extreme_peak_date": ep_d, "extreme_trough_date": et_d,
        "target_regime_changes": target_regime_changes, "rebalance_days": rebalance_days,
        "avg_turnover_per_day": float(turnover_sum / max(len(frame), 1)),
        "strategy_total_commission": float(total_commission),
        "strategy_commission_drag": float(total_commission / initial_capital),
        "benchmark_total_commission": float(bench_entry_cost),
        "risk_on_days": int(regime_days["risk_on"]), "moderate_days": int(regime_days["moderate"]),
        "risk_off_days": int(regime_days["risk_off"]),
        "operation_days": n_ops, "add_days": n_add, "reduce_days": n_reduce,
    }
    return {
        "meta": {"market": spec.market, "label": spec.label, "ticker": spec.ticker,
                 "proxy": spec.proxy, "scenario": scenario, "currency": spec.currency,
                 "start": str(frame.index[0].date()), "end": str(frame.index[-1].date()),
                 "days": int(len(frame)), "initial_capital": initial_capital,
                 "generated_at": datetime.now(timezone.utc).isoformat(),
                 "source": "monitor/trhrp_strategy.build_signal_frame (当日 regime)"},
        "params": {"regime_weights": eng.REGIME_WEIGHTS, "signal_params": sp,
                   "overlay": overlay, "scenario": scenario, "commission_mode": commission_mode},
        "summary": summary, "timeseries": daily_records,
    }


def main() -> None:
    import pandas as pd  # noqa: F401
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    markets = cfg["markets"]
    overlay_rules = cfg.get("overlay_rules") or {}
    sp_base = ts._sp_from_cfg(cfg)
    out_root = OUT_ROOT
    out_root.mkdir(parents=True, exist_ok=True)

    # 额外标的 (不经过生产 config, 避免影响 live daemon): 海力士作为高波动个股,
    # 用 relative_zscore 崩盘判定 (与 crypto/SOXL/KORU 同口径). eq_path 直接指向 USD 折算 csv.
    EXTRA_MARKETS = [
        {"label": "海力士", "ticker": "000660.KS", "marketGroup": "韩国个股",
         "crashMode": "relative_zscore", "crashZscore": 2.5,
         "proxy": "SK Hynix 高波动个股 (USD折算)",
         "eq_path": str(YF_CACHE / "000660.KS.usd.csv")},
    ]

    all_results, summary_rows = [], []
    for m in markets + EXTRA_MARKETS:
        label, ticker, grp = m["label"], m["ticker"], m["marketGroup"]
        crash_mode = m.get("crashMode", "absolute")
        crash_z = float(m.get("crashZscore", 2.5))
        rule = overlay_rules.get(grp)
        if rule and rule.get("buy_threshold") is not None:
            overlay = {"buy_z": float(rule["buy_threshold"]), "sell_z": float(rule["sell_threshold"]),
                       "delta": float(rule["delta"]), "window": 252}
            overlay_label = rule.get("label", grp)
        else:
            overlay, overlay_label = None, "无"
        commission = "cnhk" if grp in ("A股", "港股") else "us"

        eq_path = Path(m["eq_path"]) if m.get("eq_path") else YF_CACHE / (safe_name(ticker) + ".csv")
        if not eq_path.exists():
            print(f"SKIP {label} ({ticker}): 股票腿缓存缺失")
            continue

        usd_equity = eng.load_price_csv(eq_path)
        usd_gld = eng.load_price_csv(DEF_CACHE / "GLD.csv")
        usd_sgov = eng.load_price_csv(DEF_CACHE / "SHY.csv")

        # 把该标的的 crash_mode 写进 sp, 与 monitor daemon 一致
        sp = dict(sp_base)
        sp["crash_mode"] = crash_mode
        sp["crash_zscore"] = crash_z
        # 短历史标的 (如新上市 ETF) 可在 market 配置里加 signal_overrides 缩短窗口
        if m.get("signal_overrides"):
            sp.update(m["signal_overrides"])

        spec = eng.Spec(market=grp, label=label, ticker=ticker, currency="USD", proxy=m.get("proxy", ""))
        res = run_backtest_live(spec, usd_equity, usd_gld, usd_sgov,
                                "daily_full_rebalance", overlay, commission, 10000.0, sp)

        folder = out_root / label
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "trhrp_backtest_result.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")

        s = res["summary"]
        summary_rows.append({
            "label": label, "ticker": ticker, "group": grp, "crash_mode": crash_mode, "crash_z": crash_z,
            "overlay": overlay_label, "start": res["meta"]["start"], "end": res["meta"]["end"], "days": res["meta"]["days"],
            "strat_total": s["strategy_total_return"], "bench_total": s["benchmark_total_return"],
            "timing_total": s["timing_total_return"],
            "extreme_total": s["extreme_total_return"],
            "excess": s["excess_total_return"], "timing_excess": s["timing_excess_total_return"],
            "extreme_excess": s["extreme_excess_total_return"],
            "strat_cagr": s["strategy_cagr"], "bench_cagr": s["benchmark_cagr"],
            "strat_mdd": s["strategy_max_drawdown"], "bench_mdd": s["benchmark_max_drawdown"],
            "timing_mdd": s["timing_max_drawdown"],
            "extreme_mdd": s["extreme_max_drawdown"],
            "risk_on": s["risk_on_days"], "moderate": s["moderate_days"], "risk_off": s["risk_off_days"],
            "ops": s["operation_days"], "adds": s["add_days"], "reduces": s["reduce_days"], "rebalances": s["rebalance_days"],
        })
        all_results.append({"meta": res["meta"], "params": res["params"], "summary": res["summary"],
                            "timeseries": compact_ts(res["timeseries"])})
        print(f"OK {label:10s} ({ticker:10s}) [{grp}] crash={crash_mode} "
              f"strat {s['strategy_total_return']*100:+7.1f}% vs BH {s['benchmark_total_return']*100:+7.1f}% "
              f"MDD {s['strategy_max_drawdown']*100:6.1f}% ops {s['operation_days']} (加{s['add_days']}/减{s['reduce_days']})")

    combined = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "monitor/trhrp_strategy.build_signal_frame (当日 regime) + SHY 防御腿",
                "regime_cn": REGIME_CN, "markets": summary_rows, "results": all_results}
    (out_root / "_all.json").write_text(json.dumps(combined, ensure_ascii=False), encoding="utf-8")
    print(f"\n完成: {len(all_results)} 个标的 -> {out_root}")


if __name__ == "__main__":
    main()
