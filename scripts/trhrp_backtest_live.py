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
    return t.replace("^", "IDX_").replace("=", "_").replace("/", "_").replace(":", "_")


def compact_ts(ts_rows: list) -> list:
    out = []
    for r in ts_rows:
        out.append({
            "d": r["date"],
            "s": r["strategy_nav"],
            "b": r["benchmark_nav"],
            "c": r["cash_nav"],
            "e": r["extreme_nav"],
            "ro": r["ronly_nav"],
            "v": r["vol_21"],
            "r": r["regime"],
            "o": r["operation"],
            "we": r["weight_equity"],
            "dw": r["equity_weight_delta"],
            "p": r["equity_close"],
        })
    return out


_REGIME_CN_LOCAL = {"risk_on": "风险偏好", "moderate": "中性", "risk_off": "风险规避"}
# 三档基础股票权重 (与 eng.REGIME_WEIGHTS 一致); overlay 微调不影响"黏性投影"的方向判断
_EQ_WEIGHT = {"risk_on": 0.80, "moderate": 0.50, "risk_off": 0.20}


def compute_regime_outlook(current_regime, vol, vol_p60, vol_med, mom):
    """基于最新一日信号分量, 推演"接下来风险偏好"与"明日操作".

    重要边界: 回测是历史快照, 无 T+1 数据, 故 next_regime / next_operation 是
    **按当前信号黏性外推的"预计"**, 非确定事实. 仅当最新信号分量已临近切换阈值
    (10% 缓冲内) 时才把 next 推到相邻档, 否则 next = 当前 (维持/持有).

    返回 dict:
      regime_outlook: 'stable' | 'watch_risk_off' | 'watch_risk_on' | 'unknown'
      next_regime:    str | None  (预计下一档; 黏性=当前, 临近切换时取相邻档)
      next_operation: 'hold' | 'add' | 'reduce'
      outlook_note:    str  (中文说明, 含分量与阈值对比)
      outlook_dist:    float (0~1, 越小越临近切换; stable/unknown 时为 1.0)
    """
    if current_regime is None or vol is None or vol_p60 is None or vol_med is None or mom is None:
        return {
            "regime_outlook": "unknown",
            "next_regime": current_regime,
            "next_operation": "hold",
            "outlook_note": "最新信号分量不足 (warm-up 未跑完或数据缺失), 无法推演",
            "outlook_dist": 1.0,
        }

    WATCH = 0.10  # 距阈值 10% 内视为"临近切换"

    # 到 risk_off 的距离: 需 (vol > vol_p60) 且 (mom < 0). 两约束都要满足,
    # 取"更不紧迫"的那个 (max of normalized gaps).
    vol_gap_off = (vol_p60 - vol) / vol_p60 if vol_p60 > 0 else 1.0
    mom_gap_off = mom  # 动量需 <0; 当前 >0 表示还差这么远
    dist_off = max(vol_gap_off, mom_gap_off)
    # 到 risk_on 的距离: 需 (vol <= vol_med) 且 (mom > 0) (crash 已含在 regime 里)
    vol_gap_on = (vol - vol_med) / vol_med if vol_med > 0 else 1.0
    mom_gap_on = -mom  # 动量需 >0
    dist_on = max(vol_gap_on, mom_gap_on)

    candidates = []
    if current_regime != "risk_off":
        candidates.append(("risk_off", dist_off))
    if current_regime != "risk_on":
        candidates.append(("risk_on", dist_on))

    best = None
    for tgt, dist in candidates:
        d = max(0.0, dist)
        if d < WATCH and (best is None or d < best[1]):
            best = (tgt, d)

    if best is None:
        return {
            "regime_outlook": "stable",
            "next_regime": current_regime,
            "next_operation": "hold",
            "outlook_note": (f"信号稳定 ({_REGIME_CN_LOCAL.get(current_regime, current_regime)}), "
                             f"距切换阈值尚远, 预计明日维持"),
            "outlook_dist": 1.0,
        }

    tgt, dist = best
    # risk_on<->risk_off 之间必经 moderate, 投影下一档取其相邻档
    next_r = "moderate" if {current_regime, tgt} == {"risk_on", "risk_off"} else tgt
    next_w = _EQ_WEIGHT[next_r]
    cur_w = _EQ_WEIGHT[current_regime]
    next_op = "add" if next_w > cur_w + 1e-6 else ("reduce" if next_w < cur_w - 1e-6 else "hold")
    if tgt == "risk_off":
        line_name, line_val = "风险规避线 vol_p60", vol_p60
        vol_pp = (vol - vol_p60) * 100.0
        mom_cond = "需动量<0"
    else:  # risk_on
        line_name, line_val = "风险偏好线 vol_med", vol_med
        vol_pp = (vol - vol_med) * 100.0
        mom_cond = "需动量>0"
    via = "" if next_r == tgt else "（经中性）"
    note = (
        f"临近切换至 {_REGIME_CN_LOCAL.get(tgt, tgt)}{via}（距触发约 {max(0.0, dist)*100:.0f}%）："
        f"vol {vol*100:.0f}%（{line_name} {line_val*100:.0f}%，{vol_pp:+.1f}pp），"
        f"动量 {mom*100:.1f}%（{mom_cond}）"
    )
    return {
        "regime_outlook": f"watch_{tgt}",
        "next_regime": next_r,
        "next_operation": next_op,
        "outlook_note": note,
        "outlook_dist": max(0.0, dist),
    }


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
    # 「risk-on 满仓」: 只在 risk_on 时满仓(1.0)进标的, 其余情况(moderate+risk_off)全 SGOV 不进.
    # 即最严格的二元择时: 非风险偏好时段一律空仓(防御腿), 只看"risk_on 信号"是否值得满仓跟随.
    _RONLY_EQ = {"risk_on": 1.0, "moderate": 0.0, "risk_off": 0.0}
    ronly_close = [initial_capital]
    ronly_current_weights = {
        "equity": _RONLY_EQ[str(target_regime.iloc[0])],
        "GLD": 0.0,
        "SGOV": 1.0 - _RONLY_EQ[str(target_regime.iloc[0])],
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

        # risk-on 满仓: 仅 risk_on 满仓(1.0), moderate+risk_off 全 SGOV 不进, 同口径扣成本
        ronly_eq_next = _RONLY_EQ[state]
        ronly_next_weights = {"equity": ronly_eq_next, "GLD": 0.0, "SGOV": 1.0 - ronly_eq_next}
        ronly_nav_before = float(ronly_close[-1])
        ronly_trade_cost = eng.calc_trade_cost(spec.market, ronly_nav_before,
                                               ronly_current_weights, ronly_next_weights, prices)
        ronly_nav_after_cost = max(ronly_nav_before - ronly_trade_cost, 0.0)
        ronly_current_weights = ronly_next_weights
        ronly_day_close = (ronly_eq_next * float(equity_ret.loc[date, "close"])
                           + (1.0 - ronly_eq_next) * float(sgov_ret.loc[date, "close"]))
        ronly_close.append(ronly_nav_after_cost * (1.0 + ronly_day_close))
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
            "ronly_nav": round(ronly_close[-1] / initial_capital, 6),
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
    rcc = pd.Series(ronly_close[1:], index=frame.index)
    strat_total = float(sc.iloc[-1] / initial_capital - 1.0)
    bench_total = float(bc.iloc[-1] / initial_capital - 1.0)
    timing_total = float(cc.iloc[-1] / initial_capital - 1.0)
    extreme_total = float(ec.iloc[-1] / initial_capital - 1.0)
    ronly_total = float(rcc.iloc[-1] / initial_capital - 1.0)
    years = max(len(frame) / 252.0, 1e-9)
    strat_cagr = float(sc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    bench_cagr = float(bc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    timing_cagr = float(cc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    extreme_cagr = float(ec.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    ronly_cagr = float(rcc.iloc[-1] / initial_capital) ** (1.0 / years) - 1.0
    strat_mdd, sp_d, st_d = eng.scan_max_drawdown(sh / initial_capital, sl / initial_capital)
    bench_mdd, bp, bt = eng.scan_max_drawdown(bh / initial_capital, bl / initial_capital)
    # 纯择时只有 close 序列, 用 close 自身做 peak/through 近似 MDD (与策略同口径的 close-only MDD)
    timing_mdd, tp_d, tt_d = eng.scan_max_drawdown(cc / initial_capital, cc / initial_capital)
    extreme_mdd, ep_d, et_d = eng.scan_max_drawdown(ec / initial_capital, ec / initial_capital)
    ronly_mdd, rp_d, rt_d = eng.scan_max_drawdown(rcc / initial_capital, rcc / initial_capital)
    n_ops = sum(1 for r in daily_records if r["operation"] != "hold")
    n_add = sum(1 for r in daily_records if r["operation"] == "add")
    n_reduce = sum(1 for r in daily_records if r["operation"] == "reduce")
    summary = {
        "strategy_total_return": strat_total, "benchmark_total_return": bench_total,
        "timing_total_return": timing_total,
        "extreme_total_return": extreme_total,
        "ronly_total_return": ronly_total,
        "excess_total_return": float(strat_total - bench_total),
        "timing_excess_total_return": float(strat_total - timing_total),
        "extreme_excess_total_return": float(strat_total - extreme_total),
        "ronly_excess_total_return": float(strat_total - ronly_total),
        "strategy_cagr": strat_cagr, "benchmark_cagr": bench_cagr,
        "timing_cagr": timing_cagr,
        "extreme_cagr": extreme_cagr,
        "ronly_cagr": ronly_cagr,
        "excess_cagr": float(strat_cagr - bench_cagr),
        "strategy_max_drawdown": float(strat_mdd), "benchmark_max_drawdown": float(bench_mdd),
        "timing_max_drawdown": float(timing_mdd),
        "extreme_max_drawdown": float(extreme_mdd),
        "ronly_max_drawdown": float(ronly_mdd),
        "strategy_peak_date": sp_d, "strategy_trough_date": st_d,
        "benchmark_peak_date": bp, "benchmark_trough_date": bt,
        "timing_peak_date": tp_d, "timing_trough_date": tt_d,
        "extreme_peak_date": ep_d, "extreme_trough_date": et_d,
        "ronly_peak_date": rp_d, "ronly_trough_date": rt_d,
        "target_regime_changes": target_regime_changes, "rebalance_days": rebalance_days,
        "avg_turnover_per_day": float(turnover_sum / max(len(frame), 1)),
        "strategy_total_commission": float(total_commission),
        "strategy_commission_drag": float(total_commission / initial_capital),
        "benchmark_total_commission": float(bench_entry_cost),
        "risk_on_days": int(regime_days["risk_on"]), "moderate_days": int(regime_days["moderate"]),
        "risk_off_days": int(regime_days["risk_off"]),
        "operation_days": n_ops, "add_days": n_add, "reduce_days": n_reduce,
    }

    # —— 当前/接下来风险偏好 + 明日操作 推演 (详见 compute_regime_outlook 边界说明) ——
    last_rec = daily_records[-1]
    last_date = last_rec["date"]
    current_regime = last_rec["regime"]
    current_operation = last_rec["operation"]
    current_equity_weight = last_rec["weight_equity"]
    try:
        _ls = sig_frame.loc[frame.index[-1]]
    except (KeyError, IndexError):
        _ls = sig_frame.iloc[-1]
    vol_T = None if pd.isna(_ls.get("vol")) else float(_ls["vol"])
    vol_p60_T = None if pd.isna(_ls.get("vol_p60")) else float(_ls["vol_p60"])
    vol_med_T = None if pd.isna(_ls.get("vol_med")) else float(_ls["vol_med"])
    mom_T = None if pd.isna(_ls.get("mom")) else float(_ls["mom"])
    outlook = compute_regime_outlook(current_regime, vol_T, vol_p60_T, vol_med_T, mom_T)
    summary["last_date"] = last_date
    summary["current_regime"] = current_regime
    summary["current_operation"] = current_operation
    summary["current_equity_weight"] = current_equity_weight
    summary["regime_outlook"] = outlook["regime_outlook"]
    summary["next_regime"] = outlook["next_regime"]
    summary["next_operation"] = outlook["next_operation"]
    summary["outlook_note"] = outlook["outlook_note"]
    summary["outlook_dist"] = outlook["outlook_dist"]
    # 最新一日信号分量 (与 outlook_note 同源, 显式列出供前端详情区展示)
    summary["latest_vol"] = vol_T
    summary["latest_vol_p60"] = vol_p60_T
    summary["latest_vol_med"] = vol_med_T
    summary["latest_mom"] = mom_T
    # 交易时段: crypto 7×24 连续交易无 T+1 延迟; 其余为日内收盘 T+1 生效
    summary["trading_hours"] = "7x24" if spec.market == "crypto" else "daily"

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
            "ronly_total": s["ronly_total_return"],
            "excess": s["excess_total_return"], "timing_excess": s["timing_excess_total_return"],
            "extreme_excess": s["extreme_excess_total_return"],
            "ronly_excess": s["ronly_excess_total_return"],
            "strat_cagr": s["strategy_cagr"], "bench_cagr": s["benchmark_cagr"],
            "strat_mdd": s["strategy_max_drawdown"], "bench_mdd": s["benchmark_max_drawdown"],
            "timing_mdd": s["timing_max_drawdown"],
            "extreme_mdd": s["extreme_max_drawdown"],
            "ronly_mdd": s["ronly_max_drawdown"],
            "risk_on": s["risk_on_days"], "moderate": s["moderate_days"], "risk_off": s["risk_off_days"],
            "ops": s["operation_days"], "adds": s["add_days"], "reduces": s["reduce_days"], "rebalances": s["rebalance_days"],
            # —— 当前/接下来风险偏好 + 明日操作 (供 Sidebar/详情展示) ——
            "last_date": s["last_date"], "current_regime": s["current_regime"],
            "current_operation": s["current_operation"], "current_equity_weight": s["current_equity_weight"],
            "regime_outlook": s["regime_outlook"], "next_regime": s["next_regime"],
            "next_operation": s["next_operation"], "outlook_note": s["outlook_note"],
            "outlook_dist": s["outlook_dist"],
            "trading_hours": s.get("trading_hours", "daily"),
            "quality": bool(m.get("quality", False)),
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
