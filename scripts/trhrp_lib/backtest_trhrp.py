#!/usr/bin/env python3
"""TRHRP generalized backtest engine.

TRHRP = Tail Risk Hedged Rotation Portfolio
Combines three classic ideas:
  - GTAA        : trend rotation (12m momentum flavour, here 21d momentum)
  - All Weather : multi-asset allocation with a risk-off parking leg
  - Tail Hedging: cut equity exposure when volatility spikes / crash

This engine is the *reusable* form of the strategy. It takes ANY risky
"equity leg" (the instrument you want to backtest) and rotates its exposure
between that leg and two defense legs (GLD + short-duration bonds, default
SGOV with SHY pre-launch proxy). It therefore works for equities, indices,
ETFs, commodities, crypto (via a price CSV), etc.

Signals (on the equity leg):
  - mom_21 : 21-trading-day return
  - vol_21 : 21d realized volatility, annualized
Regime:
  - risk_off : vol_21 > 252d 60th pctile AND mom_21 < 0, OR crash (vol_21 > 0.30)
  - risk_on  : vol_21 <= 126d median AND mom_21 > 0 AND not crash
  - moderate : otherwise
Target weights (equity / GLD / SGOV):
  - risk_on  : 0.80 / 0.10 / 0.10
  - moderate : 0.50 / 0.25 / 0.25
  - risk_off : 0.20 / 0.20 / 0.60
Optional mean-reversion z-score overlay nudges equity weight at extremes.

Execution: T-day signal -> T+1 effective. Two scenarios:
  - daily_full_rebalance : rebalance fully to target next day
  - daily_one_order_limit: at most one leg order per day (vs SGOV)
Benchmark (the "static curve"): buy & hold the equity leg.
Commission-aware (A-share/HK 5bps one-way; US IBKR per-share).

Add/reduce (buy/sell) operation = change in equity weight vs prior day.

Outputs:
  <out>/trhrp_backtest_result.json
  <out>/trhrp_backtest_report.html   (data embedded, open in browser)

Usage:
  # via yfinance ticker (needs network)
  backtest_trhrp.py --ticker SPY --scenario daily_full_rebalance

  # via offline price CSV (equity leg only; defense legs from cache/yfinance)
  backtest_trhrp.py --price-csv prices.csv --label "My Asset" \
      --gld-csv GLD.csv --sgov-csv SGOV.csv --out ./out
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:  # network path only; import lazily so offline CSV mode still runs
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR.parent / "assets" / "report_template.html"

INITIAL_CAPITAL = 10_000.0
CN_HK_ONE_WAY_RATE = 5.0 / 10_000.0
US_IBKR_PER_SHARE = 0.0035
US_IBKR_MIN_PER_ORDER = 0.35
US_IBKR_MAX_NOTIONAL_RATE = 0.01
EPS = 1e-12

START_DATE = "2010-01-01"
END_DATE = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
CACHE_MAX_AGE = pd.Timedelta(hours=12)

REGIME_WEIGHTS: Dict[str, Dict[str, float]] = {
    "risk_on": {"equity": 0.80, "GLD": 0.10, "SGOV": 0.10},
    "moderate": {"equity": 0.50, "GLD": 0.25, "SGOV": 0.25},
    "risk_off": {"equity": 0.20, "GLD": 0.20, "SGOV": 0.60},
}

REGIME_LABELS = {"risk_on": "风险偏好", "moderate": "中性", "risk_off": "风险规避"}

# Default defense leg tickers (downloaded via yfinance when not supplied as CSV)
DEFENSE_TICKERS = {"GLD": "GLD", "SGOV": "SGOV", "SHY_PROXY": "SHY"}
FX_TICKERS = {"CNY": "USDCNY=X", "HKD": "USDHKD=X"}

# Default mean-reversion overlay (mirrors the project's A/H & US rules).
# Only applied when the user passes --overlay-buy-z / --overlay-sell-z / --overlay-delta.
OVERLAY_DEFAULTS = {
    "buy_z": -2.0,
    "sell_z": 2.0,
    "delta": 0.10,
    "window": 252,
}


# --------------------------------------------------------------------------- #
# Small IO helpers
# --------------------------------------------------------------------------- #
def _flatten_columns(columns: Any) -> List[str]:
    out: List[str] = []
    for column in columns:
        if isinstance(column, tuple):
            parts = [str(p) for p in column if str(p) != ""]
            out.append("_".join(parts))
        else:
            out.append(str(column))
    return out


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    normalized = df.copy()
    normalized.columns = _flatten_columns(normalized.columns)
    rename_map: Dict[str, str] = {}
    for column in normalized.columns:
        lower = column.lower()
        if lower.startswith("open"):
            rename_map[column] = "Open"
        elif lower.startswith("high"):
            rename_map[column] = "High"
        elif lower.startswith("low"):
            rename_map[column] = "Low"
        elif lower.startswith("close"):
            rename_map[column] = "Close"
    normalized = normalized.rename(columns=rename_map)
    needed = ["Open", "High", "Low", "Close"]
    missing = [n for n in needed if n not in normalized.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    normalized.index = pd.to_datetime(normalized.index).tz_localize(None)
    normalized = normalized[needed].sort_index()
    normalized = normalized[~normalized.index.duplicated(keep="last")]
    return normalized


def _cache_path(cache_dir: Path, ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace("^", "IDX_").replace("=", "_")
    return cache_dir / f"{safe}.csv"


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = pd.Timestamp.now(tz="UTC") - pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC")
    return age <= CACHE_MAX_AGE


def download_ohlc(ticker: str, cache_dir: Optional[Path] = None) -> pd.DataFrame:
    if cache_dir is not None:
        path = _cache_path(cache_dir, ticker)
        if _is_cache_fresh(path):
            cached = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
            if not cached.empty:
                return cached
    if yf is None:
        raise RuntimeError("yfinance not available and no cached/offline data for %s" % ticker)
    raw = yf.download(
        ticker, start=START_DATE, end=END_DATE,
        auto_adjust=False, progress=False, threads=False,
    )
    normalized = _normalize_ohlc(raw)
    if cache_dir is not None:
        try:
            _write_csv_atomic(normalized, _cache_path(cache_dir, ticker))
        except OSError:
            pass
    return normalized


def _write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as tf:
            df.to_csv(tf, index_label="Date")
            tmp = tf.name
        os.replace(tmp, path)
    except OSError:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise


def load_price_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
    df = _normalize_ohlc(df)
    return df


def build_sgov_proxy(sgov: pd.DataFrame, shy_proxy: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([shy_proxy, sgov]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    first_sgov_date = sgov.index.min()
    if first_sgov_date is not None:
        before = combined.index < first_sgov_date
        combined.loc[before] = shy_proxy.reindex(combined.index[before]).ffill()
    return combined.sort_index().dropna()


# --------------------------------------------------------------------------- #
# Strategy signals
# --------------------------------------------------------------------------- #
def build_equity_signal(close: pd.Series, crash_mode: str = "absolute",
                        crash_zscore: float = 2.5) -> pd.Series:
    """TRHRP regime 信号.

    crash_mode:
      - "absolute" (默认): 崩盘触发 = vol_21 > 0.30 (按股票指数 ~15-20% vol 调的,
        对加密/商品 vol 50-60% 会永远触发 risk_off -> 误校准).
      - "relative_zscore": 崩盘触发 = vol 相对自身 252d 历史偏离 > crash_zscore 个标准差.
        对高波动资产更合理 (误校准修复). 与 monitor/trhrp_strategy.build_signal_frame_rel 同口径.
    """
    ret = close.pct_change()
    mom_21 = close.pct_change(21)
    vol_21 = ret.rolling(21).std() * math.sqrt(252)
    vol_p60 = vol_21.rolling(252).apply(
        lambda v: np.nanpercentile(v, 60) if np.isfinite(v).sum() >= 60 else np.nan, raw=True
    )
    vol_med = vol_21.rolling(126).median()
    if crash_mode == "relative_zscore":
        # 相对自身历史: vol 相对 252d 滚动均值偏离 > crash_zscore 个标准差 -> 崩盘
        vol_mean = vol_21.rolling(252, min_periods=126).mean()
        vol_std = vol_21.rolling(252, min_periods=126).std()
        vol_z = (vol_21 - vol_mean) / vol_std.replace(0.0, np.nan)
        crash_trigger = vol_z > crash_zscore
    else:
        vol_z = None
        crash_trigger = vol_21 > 0.30
    risk_off = ((vol_21 > vol_p60) & (mom_21 < 0)) | crash_trigger
    risk_on = (vol_21 <= vol_med) & (mom_21 > 0) & (~crash_trigger)
    signal = pd.Series("moderate", index=close.index, dtype="object")
    signal.loc[risk_off.fillna(False)] = "risk_off"
    signal.loc[risk_on.fillna(False)] = "risk_on"
    nan_mask = mom_21.isna() | vol_21.isna()
    if crash_mode == "relative_zscore" and vol_z is not None:
        nan_mask = nan_mask | vol_z.isna()
    signal.loc[nan_mask] = np.nan
    return signal


def build_mean_reversion_zscore(close: pd.Series, window: int = 252) -> pd.Series:
    log_price = np.log(close.astype(float))
    rolling_mean = log_price.rolling(window, min_periods=max(60, window // 2)).mean()
    rolling_std = log_price.rolling(window, min_periods=max(60, window // 2)).std()
    zscore = (log_price - rolling_mean) / rolling_std.replace(0.0, np.nan)
    return zscore.replace([np.inf, -np.inf], np.nan)


def apply_overlay(
    target_regime: pd.Series,
    close: pd.Series,
    buy_z: float,
    sell_z: float,
    delta: float,
    window: int,
) -> pd.DataFrame:
    """Return a DataFrame of target weights per day, with z-score overlay applied."""
    z = build_mean_reversion_zscore(close, window)
    weights = target_regime.map(lambda r: dict(REGIME_WEIGHTS[r]))
    records: List[Dict[str, float]] = []
    for date in target_regime.index:
        w = dict(weights.loc[date])
        zv = z.get(date, np.nan)
        if pd.notna(zv):
            if zv <= buy_z:
                w["equity"] = min(w["equity"] + delta, 1.0)
            elif zv >= sell_z:
                w["equity"] = max(w["equity"] - delta, 0.0)
            w["SGOV"] = max(0.0, 1.0 - w["equity"] - w["GLD"])
        records.append(w)
    return pd.DataFrame(records, index=target_regime.index)


# --------------------------------------------------------------------------- #
# Calendar / returns
# --------------------------------------------------------------------------- #
def build_calendar_frame(equity: pd.DataFrame, gld: Optional[pd.DataFrame],
                         sgov: Optional[pd.DataFrame]) -> pd.DataFrame:
    pieces = {"equity": equity}
    if gld is not None:
        pieces["GLD"] = gld
    if sgov is not None:
        pieces["SGOV"] = sgov
    combined: List[pd.DataFrame] = []
    for prefix, df in pieces.items():
        combined.append(df.rename(columns=lambda n: f"{prefix}_{n}"))
    frame = pd.concat(combined, axis=1, sort=True).sort_index().ffill().dropna()
    # ensure defense legs exist even if not provided (cash proxy -> 0 daily return)
    for leg in ["GLD", "SGOV"]:
        if f"{leg}_Close" not in frame:
            for f in ["Open", "High", "Low", "Close"]:
                frame[f"{leg}_{f}"] = 1.0
    return frame


def calc_component_returns(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    prev = frame[f"{prefix}_Close"].shift(1)
    returns = pd.DataFrame(index=frame.index)
    returns["close"] = frame[f"{prefix}_Close"] / prev - 1.0
    returns["high"] = frame[f"{prefix}_High"] / prev - 1.0
    returns["low"] = frame[f"{prefix}_Low"] / prev - 1.0
    return returns.replace([np.inf, -np.inf], np.nan)


def scan_max_drawdown(high_nav: pd.Series, low_nav: pd.Series) -> Tuple[float, Optional[str], Optional[str]]:
    peak = 1.0
    peak_date: Optional[pd.Timestamp] = None
    trough_date: Optional[pd.Timestamp] = None
    worst = 0.0
    wp: Optional[pd.Timestamp] = None
    wt: Optional[pd.Timestamp] = None
    for date in high_nav.index:
        day_high = float(high_nav.loc[date])
        day_low = float(low_nav.loc[date])
        if day_high > peak:
            peak = day_high
            peak_date = date
        drawdown = day_low / peak - 1.0
        if drawdown < worst:
            worst = drawdown
            trough_date = date
            wp = peak_date
            wt = trough_date
    peak_text = str(wp.date()) if wp is not None else None
    trough_text = str(wt.date()) if wt is not None else None
    return worst, peak_text, trough_text


# --------------------------------------------------------------------------- #
# Commission
# --------------------------------------------------------------------------- #
def turnover_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = sorted(set(a) | set(b))
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) / 2.0


def calc_us_commission(trade_value: float, price: float) -> float:
    if trade_value <= EPS or price <= EPS:
        return 0.0
    shares = trade_value / price
    raw = shares * US_IBKR_PER_SHARE
    bounded = max(raw, US_IBKR_MIN_PER_ORDER)
    capped = min(bounded, trade_value * US_IBKR_MAX_NOTIONAL_RATE)
    return float(capped)


def calc_trade_cost(market: str, nav_before: float, cur: Dict[str, float],
                    nxt: Dict[str, float], prices: Dict[str, float]) -> float:
    if market in {"A股", "港股"}:
        ratio = sum(abs(float(nxt[k]) - float(cur[k])) for k in ["equity", "GLD", "SGOV"])
        return nav_before * ratio * CN_HK_ONE_WAY_RATE
    total = 0.0
    for asset in ["equity", "GLD", "SGOV"]:
        delta = abs(float(nxt[asset]) - float(cur[asset]))
        if delta <= EPS:
            continue
        total += calc_us_commission(nav_before * delta, prices[asset])
    return total


def step_one_order_limit(cur: Dict[str, float], target: Dict[str, float]) -> Dict[str, float]:
    eq_gap = float(target["equity"]) - float(cur["equity"])
    gld_gap = float(target["GLD"]) - float(cur["GLD"])
    if abs(eq_gap) <= EPS and abs(gld_gap) <= EPS:
        return dict(cur)
    chosen = "equity"
    if abs(gld_gap) > abs(eq_gap) + EPS:
        chosen = "GLD"
    updated = dict(cur)
    other = "GLD" if chosen == "equity" else "equity"
    upper = 1.0 - float(updated[other])
    tgt = float(target[chosen])
    if tgt > float(updated[chosen]):
        updated[chosen] = min(tgt, upper)
    else:
        updated[chosen] = tgt
    updated["SGOV"] = max(0.0, 1.0 - float(updated["equity"]) - float(updated["GLD"]))
    return updated


# --------------------------------------------------------------------------- #
# Core backtest
# --------------------------------------------------------------------------- #
@dataclass
class Spec:
    market: str
    label: str
    ticker: str
    currency: str
    proxy: str = ""


def run_backtest(spec: Spec, usd_equity: pd.DataFrame, usd_gld: Optional[pd.DataFrame],
                 usd_sgov: Optional[pd.DataFrame], scenario: str,
                 overlay: Optional[Dict[str, float]], commission_mode: str,
                 initial_capital: float = INITIAL_CAPITAL,
                 crash_mode: str = "absolute",
                 crash_zscore: float = 2.5) -> Dict[str, Any]:
    frame = build_calendar_frame(usd_equity, usd_gld, usd_sgov)
    frame = frame.copy()

    signal = build_equity_signal(frame["equity_Close"], crash_mode, crash_zscore)
    target_regime = signal.shift(1).ffill().fillna("moderate")

    if overlay:
        weights_df = apply_overlay(target_regime, frame["equity_Close"],
                                   overlay["buy_z"], overlay["sell_z"],
                                   overlay["delta"], int(overlay["window"]))
    else:
        weights_df = target_regime.map(lambda r: dict(REGIME_WEIGHTS[r])).apply(pd.Series)

    equity_ret = calc_component_returns(frame, "equity")
    gld_ret = calc_component_returns(frame, "GLD")
    sgov_ret = calc_component_returns(frame, "SGOV")
    valid = equity_ret["close"].notna() & gld_ret["close"].notna() & sgov_ret["close"].notna()
    frame = frame.loc[valid].copy()
    target_regime = target_regime.loc[valid]
    weights_df = weights_df.loc[valid]
    equity_ret = equity_ret.loc[valid]
    gld_ret = gld_ret.loc[valid]
    sgov_ret = sgov_ret.loc[valid]

    strat_close = [initial_capital]
    strat_high: List[float] = []
    strat_low: List[float] = []
    bench_close = [initial_capital]
    bench_high: List[float] = []
    bench_low: List[float] = []

    target_regime_changes = int((target_regime != target_regime.shift(1)).sum())
    rebalance_days = 0
    turnover_sum = 0.0
    total_commission = 0.0
    current_weights = dict(REGIME_WEIGHTS[str(target_regime.iloc[0])])
    regime_days = {"risk_on": 0, "moderate": 0, "risk_off": 0}
    daily_records: List[Dict[str, Any]] = []
    prev_regime: Optional[str] = None
    prev_equity_weight: Optional[float] = None

    bench_entry_cost = 0.0
    if commission_mode == "cnhk":
        bench_entry_cost = initial_capital * CN_HK_ONE_WAY_RATE
    elif commission_mode == "us":
        bench_entry_cost = calc_us_commission(initial_capital, float(frame["equity_Close"].iloc[0]))
    bench_close[0] -= bench_entry_cost
    bench_cash_drag = bench_entry_cost

    for date in frame.index:
        state = str(target_regime.loc[date])
        regime_days[state] += 1
        target_weights = {k: float(v) for k, v in weights_df.loc[date].items()}

        if scenario == "daily_full_rebalance":
            next_weights = target_weights
        elif scenario == "daily_one_order_limit":
            next_weights = step_one_order_limit(current_weights, target_weights)
        else:
            raise ValueError(f"unknown scenario: {scenario}")

        nav_before = float(strat_close[-1])
        prices = {
            "equity": float(frame.loc[date, "equity_Close"]),
            "GLD": float(frame.loc[date, "GLD_Close"]),
            "SGOV": float(frame.loc[date, "SGOV_Close"]),
        }
        trade_cost = calc_trade_cost(spec.market, nav_before, current_weights, next_weights, prices)
        if trade_cost > EPS:
            rebalance_days += 1
            turnover_sum += turnover_distance(current_weights, next_weights)
            total_commission += trade_cost

        nav_after_cost = max(nav_before - trade_cost, 0.0)
        current_weights = next_weights

        day_close = (
            current_weights["equity"] * float(equity_ret.loc[date, "close"])
            + current_weights["GLD"] * float(gld_ret.loc[date, "close"])
            + current_weights["SGOV"] * float(sgov_ret.loc[date, "close"])
        )
        day_high = (
            current_weights["equity"] * float(equity_ret.loc[date, "high"])
            + current_weights["GLD"] * float(gld_ret.loc[date, "high"])
            + current_weights["SGOV"] * float(sgov_ret.loc[date, "high"])
        )
        day_low = (
            current_weights["equity"] * float(equity_ret.loc[date, "low"])
            + current_weights["GLD"] * float(gld_ret.loc[date, "low"])
            + current_weights["SGOV"] * float(sgov_ret.loc[date, "low"])
        )

        strat_high.append(nav_after_cost * (1.0 + day_high))
        strat_low.append(nav_after_cost * (1.0 + day_low))
        strat_close.append(nav_after_cost * (1.0 + day_close))

        prev_bench = float(bench_close[-1])
        bench_day_close = float(equity_ret.loc[date, "close"])
        bench_high.append(prev_bench * (1.0 + float(equity_ret.loc[date, "high"])))
        bench_low.append(prev_bench * (1.0 + float(equity_ret.loc[date, "low"])))
        bench_close.append(prev_bench * (1.0 + bench_day_close))

        eq_w = float(current_weights["equity"])
        op = "hold"
        op_delta = 0.0
        if prev_equity_weight is not None:
            d = eq_w - prev_equity_weight
            if d > EPS:
                op = "add"
                op_delta = d
            elif d < -EPS:
                op = "reduce"
                op_delta = d
        prev_equity_weight = eq_w

        daily_records.append({
            "date": str(date.date()),
            "strategy_nav": round(strat_close[-1] / INITIAL_CAPITAL, 6),
            "benchmark_nav": round(bench_close[-1] / INITIAL_CAPITAL, 6),
            "regime": state,
            "regime_changed": prev_regime is not None and state != prev_regime,
            "rebalanced": trade_cost > EPS,
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

    strat_total = float(sc.iloc[-1] / INITIAL_CAPITAL - 1.0)
    bench_total = float(bc.iloc[-1] / INITIAL_CAPITAL - 1.0)
    years = max(len(frame) / 252.0, 1e-9)
    strat_cagr = float(sc.iloc[-1] / INITIAL_CAPITAL) ** (1.0 / years) - 1.0
    bench_cagr = float(bc.iloc[-1] / INITIAL_CAPITAL) ** (1.0 / years) - 1.0
    strat_mdd, sp, st = scan_max_drawdown(sh / INITIAL_CAPITAL, sl / INITIAL_CAPITAL)
    bench_mdd, bp, bt = scan_max_drawdown(bh / INITIAL_CAPITAL, bl / INITIAL_CAPITAL)

    n_ops = sum(1 for r in daily_records if r["operation"] != "hold")
    n_add = sum(1 for r in daily_records if r["operation"] == "add")
    n_reduce = sum(1 for r in daily_records if r["operation"] == "reduce")

    summary = {
        "strategy_total_return": strat_total,
        "benchmark_total_return": bench_total,
        "excess_total_return": float(strat_total - bench_total),
        "strategy_cagr": strat_cagr,
        "benchmark_cagr": bench_cagr,
        "excess_cagr": float(strat_cagr - bench_cagr),
        "strategy_max_drawdown": float(strat_mdd),
        "benchmark_max_drawdown": float(bench_mdd),
        "strategy_peak_date": sp,
        "strategy_trough_date": st,
        "benchmark_peak_date": bp,
        "benchmark_trough_date": bt,
        "target_regime_changes": target_regime_changes,
        "rebalance_days": rebalance_days,
        "avg_turnover_per_day": float(turnover_sum / max(len(frame), 1)),
        "strategy_total_commission": float(total_commission),
        "strategy_commission_drag": float(total_commission / initial_capital),
        "benchmark_total_commission": float(bench_cash_drag),
        "risk_on_days": int(regime_days["risk_on"]),
        "moderate_days": int(regime_days["moderate"]),
        "risk_off_days": int(regime_days["risk_off"]),
        "operation_days": n_ops,
        "add_days": n_add,
        "reduce_days": n_reduce,
    }

    return {
        "meta": {
            "market": spec.market,
            "label": spec.label,
            "ticker": spec.ticker,
            "proxy": spec.proxy,
            "scenario": scenario,
            "currency": spec.currency,
            "start": str(frame.index[0].date()),
            "end": str(frame.index[-1].date()),
            "days": int(len(frame)),
            "initial_capital": initial_capital,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "trhrp-backtest-skill",
        },
        "params": {
            "regime_weights": REGIME_WEIGHTS,
            "signal": {"momentum_window": 21, "vol_window": 21, "vol_p60_window": 252,
                       "vol_median_window": 126, "crash_vol": 0.30,
                       "crash_mode": crash_mode, "crash_zscore": crash_zscore},
            "overlay": overlay,
            "scenario": scenario,
            "commission_mode": commission_mode,
            "t_plus": 1,
        },
        "summary": summary,
        "timeseries": daily_records,
    }


# --------------------------------------------------------------------------- #
# HTML report
# --------------------------------------------------------------------------- #
def build_html_report(result: Dict[str, Any], out_path: Path) -> None:
    if not TEMPLATE_PATH.exists():
        sys.stderr.write("warning: report template missing, skip HTML\n")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    payload = json.dumps(result, ensure_ascii=False)
    try:
        html = template.replace("/*__TRHRP_DATA__*/", payload)
    except Exception:
        # fallback: append a data script before </body>
        html = template.replace("</body>", f"<script>window.TRHRP_DATA={payload};</script></body>")
    out_path.write_text(html, encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def infer_market_currency(ticker: str) -> Tuple[str, str]:
    t = ticker.upper()
    if t.endswith(".SS") or t.endswith(".SZ"):
        return "A股", "CNY"
    if t.endswith(".HK"):
        return "港股", "HKD"
    return "美股", "USD"


def resolve_commission_mode(mode: str, currency: str) -> str:
    if mode != "auto":
        return mode
    if currency in {"CNY", "HKD"}:
        return "cnhk"
    return "us"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generalized TRHRP backtest engine")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ticker", help="yfinance ticker (needs network)")
    src.add_argument("--price-csv", help="equity-leg price CSV (Date,Open,High,Low,Close)")
    ap.add_argument("--gld-csv", help="GLD price CSV (optional; else yfinance)")
    ap.add_argument("--sgov-csv", help="SGOV price CSV (optional; else yfinance+SHY proxy)")
    ap.add_argument("--label", help="display label for the instrument")
    ap.add_argument("--market", help="A股 / 港股 / 美股 / other")
    ap.add_argument("--currency", help="CNY / HKD / USD")
    ap.add_argument("--start", default=START_DATE)
    ap.add_argument("--end", default=END_DATE)
    ap.add_argument("--scenario", default="daily_full_rebalance",
                    choices=["daily_full_rebalance", "daily_one_order_limit"])
    ap.add_argument("--initial-capital", type=float, default=INITIAL_CAPITAL)
    ap.add_argument("--overlay-buy-z", type=float, help="enable overlay: z below this -> add")
    ap.add_argument("--overlay-sell-z", type=float, help="enable overlay: z above this -> reduce")
    ap.add_argument("--overlay-delta", type=float, help="enable overlay: equity weight nudge (frac)")
    ap.add_argument("--overlay-window", type=int, default=OVERLAY_DEFAULTS["window"])
    ap.add_argument("--commission-mode", default="auto", choices=["auto", "cnhk", "us", "none"])
    ap.add_argument("--crash-mode", default="absolute",
                    choices=["absolute", "relative_zscore"],
                    help="absolute: vol>0.30 崩盘线(默认, 按股票指数调); "
                         "relative_zscore: vol 相对自身252d历史偏离>zscore 个标准差(高波动资产用)")
    ap.add_argument("--crash-zscore", type=float, default=2.5,
                    help="relative_zscore 模式下的崩盘 z 阈值 (默认 2.5)")
    ap.add_argument("--out", default="./trhrp_output")
    ap.add_argument("--no-html", action="store_true")
    ap.add_argument("--cache-dir", help="directory for yfinance cache")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir) if args.cache_dir else (out_dir / "cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    overlay: Optional[Dict[str, float]] = None
    if args.overlay_buy_z is not None and args.overlay_sell_z is not None and args.overlay_delta is not None:
        overlay = {
            "buy_z": args.overlay_buy_z,
            "sell_z": args.overlay_sell_z,
            "delta": args.overlay_delta,
            "window": args.overlay_window,
        }

    # --- load equity leg ---
    if args.ticker:
        ticker = args.ticker
        mkt, cur = infer_market_currency(ticker)
        market = args.market or mkt
        currency = args.currency or cur
        label = args.label or ticker
        raw = download_ohlc(ticker, cache_dir)
        # FX convert to USD like the project
        if currency != "USD":
            fx = download_ohlc(FX_TICKERS[currency], cache_dir).rename(columns=lambda n: f"FX_{n}")
            merged = raw.join(fx, how="outer").sort_index().ffill().dropna()
            usd_equity = pd.DataFrame(index=merged.index)
            for f in ["Open", "High", "Low", "Close"]:
                usd_equity[f] = merged[f] / merged[f"FX_{f}"]
            usd_equity = usd_equity.dropna()
        else:
            usd_equity = raw
    else:
        csv_path = Path(args.price_csv)
        label = args.label or csv_path.stem
        market = args.market or "自定义"
        currency = args.currency or "USD"
        usd_equity = load_price_csv(csv_path)
        ticker = csv_path.stem

    usd_equity = usd_equity.loc[args.start:args.end]

    # --- load defense legs ---
    usd_gld = None
    usd_sgov = None
    try:
        if args.gld_csv:
            usd_gld = load_price_csv(Path(args.gld_csv)).loc[args.start:args.end]
        else:
            usd_gld = download_ohlc(DEFENSE_TICKERS["GLD"], cache_dir).loc[args.start:args.end]
    except Exception as exc:
        sys.stderr.write(f"warning: GLD unavailable ({exc}); using cash proxy\n")
        usd_gld = None
    try:
        if args.sgov_csv:
            usd_sgov = load_price_csv(Path(args.sgov_csv)).loc[args.start:args.end]
        else:
            sgov = download_ohlc(DEFENSE_TICKERS["SGOV"], cache_dir)
            shy = download_ohlc(DEFENSE_TICKERS["SHY_PROXY"], cache_dir)
            usd_sgov = build_sgov_proxy(sgov, shy).loc[args.start:args.end]
    except Exception as exc:
        sys.stderr.write(f"warning: SGOV unavailable ({exc}); using cash proxy\n")
        usd_sgov = None

    commission_mode = resolve_commission_mode(args.commission_mode, currency)

    spec = Spec(market=market, label=label, ticker=ticker, currency=currency)
    result = run_backtest(spec, usd_equity, usd_gld, usd_sgov, args.scenario, overlay,
                          commission_mode, float(args.initial_capital),
                          args.crash_mode, args.crash_zscore)

    json_path = out_dir / "trhrp_backtest_result.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.no_html:
        build_html_report(result, out_dir / "trhrp_backtest_report.html")

    s = result["summary"]
    print(f"=== TRHRP backtest: {label} ({ticker}) [{args.scenario}] ===")
    print(f"区间           : {result['meta']['start']} -> {result['meta']['end']} ({result['meta']['days']} 天)")
    print(f"策略总收益     : {s['strategy_total_return']*100:+.2f}%  (CAGR {s['strategy_cagr']*100:+.2f}%)")
    print(f"基准总收益     : {s['benchmark_total_return']*100:+.2f}%  (CAGR {s['benchmark_cagr']*100:+.2f}%)")
    print(f"超额收益       : {s['excess_total_return']*100:+.2f}%")
    print(f"策略最大回撤   : {s['strategy_max_drawdown']*100:.2f}%  (峰值 {s['strategy_peak_date']} -> 谷 {s['strategy_trough_date']})")
    print(f"基准最大回撤   : {s['benchmark_max_drawdown']*100:.2f}%")
    print(f"调仓/加减仓日  : {s['rebalance_days']} / {s['operation_days']} (加 {s['add_days']}, 减 {s['reduce_days']})")
    print(f"regime 天数    : risk_on {s['risk_on_days']} / moderate {s['moderate_days']} / risk_off {s['risk_off_days']}")
    print(f"Wrote -> {json_path}")
    if not args.no_html:
        print(f"Wrote -> {out_dir / 'trhrp_backtest_report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
