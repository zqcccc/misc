"""
TRHRP 多市场 regime 策略 — monitor 端原生实现.

口径与 /Users/gongzhao/code/ba/scripts/trhrp_daily_multi_signal.py 同源:
  - 21d momentum + 21d realized vol
  - risk_off: vol > 252 日窗口 p60 且 mom < 0, 或者 crash_trigger (vol > 0.30)
  - risk_on: vol <= 126 日中位 且 mom > 0, 且非 crash
  - moderate: 其它
  - z-score 252 日 log 价均值回归; 按 marketGroup 应用 overlay (A/H vs 美股 vs 无)
  - 配比: regime 决定 equity/GLD/SGOV 基础表; overlay 触发则 equity ± delta pp, SGOV 反向

deployment: monitor 这边独立维护 (与 ba 脚本脱节). 加减品种/调参数都改 monitor/strategies_trhrp.json.
本模块纯函数式, 不发通知不写状态. daemon_trhrp.py 调用并管循环.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

REGIME_EMOJI = {"risk_on": "🟢", "moderate": "🟡", "risk_off": "🔴"}
ALLOCATION_BASE_TEXT = {
    "risk_on":  "股票80% / GLD10% / SGOV10%",
    "moderate": "股票50% / GLD25% / SGOV25%",
    "risk_off": "股票20% / GLD20% / SGOV60%",
}


@dataclass(frozen=True)
class MarketSpec:
    label: str
    market_group: str
    ticker: str
    proxy: str = ""
    crash_mode: str = "absolute"          # absolute | relative_zscore
    crash_zscore: float = 2.5             # 仅 relative_zscore 模式用


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, encoding="utf-8") as f:
        return __import__("json").load(f)


def _markets_from_cfg(cfg: Dict[str, Any]) -> List[MarketSpec]:
    out = []
    for m in cfg.get("markets") or []:
        out.append(MarketSpec(
            label=str(m.get("label", "?")),
            market_group=str(m.get("marketGroup", "?")),
            ticker=str(m.get("ticker", "")),
            proxy=str(m.get("proxy", "") or ""),
            crash_mode=str(m.get("crashMode", "absolute") or "absolute"),
            crash_zscore=float(m.get("crashZscore", 2.5) or 2.5),
        ))
    return out


def _sp_from_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg.get("signal_params") or {}


def _cache_path(ticker: str, cache_dir: Path) -> Path:
    safe = ticker.replace("^", "IDX_").replace("=", "_").replace("/", "_")
    return cache_dir / f"{safe}.csv"


def _is_cache_fresh(path: Path, max_age_hours: float) -> bool:
    if not path.exists():
        return False
    age = pd.Timestamp.now(tz="UTC") - pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC")
    return age <= pd.Timedelta(hours=max_age_hours)


def _flatten_columns(columns: List[Any]) -> List[str]:
    out = []
    for c in columns:
        if isinstance(c, tuple):
            out.append("_".join(str(x) for x in c if str(x) != ""))
        else:
            out.append(str(c))
    return out


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = _flatten_columns(list(df.columns))
    rename = {}
    for c in df.columns:
        low = c.lower()
        if low.startswith("open"):
            rename[c] = "Open"
        elif low.startswith("high"):
            rename[c] = "High"
        elif low.startswith("low"):
            rename[c] = "Low"
        elif low.startswith("close"):
            rename[c] = "Close"
    df = df.rename(columns=rename)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def download_ohlc(spec: MarketSpec, cache_dir: Path, sp: Dict[str, Any],
                  warnings: Optional[List[str]] = None,
                  max_retries: int = 3, retry_backoff: float = 3.0) -> pd.DataFrame:
    """拉 OHLC. 带重试 + 缓存回退, 避免 yfinance 间歇性限频/空返回导致整市场 null.

    - 缓存新鲜则直接返回 (不碰 yfinance).
    - 缓存过期/缺失: 重试 yf.download (指数退避), 任一成功即用.
    - 全部重试仍空: 若本地存在(即使过期)的缓存 CSV, 回退用之并写一条 warning,
      这样至少能算出 regime, 而不是让该市场变成 null 引发下游崩溃.
    - 既无重试成功也无任何缓存: 才 raise (真正的硬失败).
    """
    import yfinance as yf
    path = _cache_path(spec.ticker, cache_dir)
    max_age = float(sp.get("cache_max_age_hours", 12))
    if _is_cache_fresh(path, max_age):
        try:
            cached = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
            if not cached.empty:
                return cached
        except Exception:
            pass
    start = str(sp.get("start_date", "2010-01-01"))
    end = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    # 加密(-USD)与期货(含 '=' 如 GC=F/CL=F/SI=F)在 auto_adjust=False 下 yfinance 返回空,
    # 必须用 auto_adjust=True 才能拉到数据; 常规 ETF/指数保持原行为不变.
    auto_adjust = bool(spec.ticker.endswith("-USD") or "=" in spec.ticker)
    raw = None
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = yf.download(spec.ticker, start=start, end=end, auto_adjust=auto_adjust,
                              progress=False, threads=False)
        except Exception as e:  # yfinance 偶尔会直接抛 (429/连接重置), 当作空处理并重试
            last_err = e
            raw = None
        if raw is not None and not raw.empty:
            break
        if attempt < max_retries:
            time.sleep(retry_backoff * attempt)
    if raw is None or raw.empty:
        # 重试仍空 -> 回退到已存在的本地缓存 (即使过期), 保证不出现 null regime
        if path.exists():
            try:
                cached = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
                if not cached.empty:
                    if warnings is not None:
                        warnings.append(
                            f"{spec.label} ({spec.ticker}): yfinance 连续 {max_retries} 次返回空/异常"
                            f"{(' (' + str(last_err) + ')') if last_err else ''}, 回退到本地缓存(可能过期)")
                    return cached
            except Exception:
                pass
        raise RuntimeError(f"yfinance 返回空: {spec.ticker}")
    norm = _normalize_ohlc(raw)
    norm = _clean_ohlc_prices(norm)
    norm.to_csv(path, index_label="Date")
    return norm


def _clean_ohlc_prices(df: pd.DataFrame) -> pd.DataFrame:
    """防御性清洗: 期货/商品偶发负价(如 WTI 2020-04-20 = -37.63, 当日 Low=-40.32, 次日 Low=-16.74)
    会让日内 Low NAV 变负、回撤被算成 < -100%、收益(pct_change 基数变负)崩坏.
    负价/非正价是合约交割异动, 非真实可实现的长期持有亏损; 用上一个有效正价 carry-forward
    抹平整行(该日收益记 0), 并修正 High/Low 一致性. 任一 OHLC 列非正即判定整行为脏."""
    ohlc = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    if not ohlc:
        return df
    bad = (df[ohlc] <= 0).any(axis=1)
    if bad.any():
        last_good = df["Close"].where(~bad).ffill()
        if last_good.isna().any():
            last_good = last_good.bfill()
        df = df.copy()
        for c in ohlc:
            df[c] = df[c].mask(bad, last_good)
        df["High"] = df[["High", "Low", "Close"]].max(axis=1)
        df["Low"] = df[["Low", "Close"]].min(axis=1)
    return df


def _mean_reversion_zscore(close: pd.Series, window: int, min_periods: int) -> pd.Series:
    log_price = np.log(close.astype(float))
    mean = log_price.rolling(window, min_periods=min_periods).mean()
    std = log_price.rolling(window, min_periods=min_periods).std()
    z = (log_price - mean) / std.replace(0.0, np.nan)
    return z.replace([np.inf, -np.inf], np.nan)


def _safe_num(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass
    v = float(x)
    return v if math.isfinite(v) else None


def _safe_pct(x: Any) -> Optional[float]:
    v = _safe_num(x)
    return None if v is None else v * 100.0


def build_signal_frame(close: pd.Series, sp: Dict[str, Any]) -> pd.DataFrame:
    mom_w = int(sp.get("mom_window", 21))
    vol_w = int(sp.get("vol_window", 21))
    p60_w = int(sp.get("vol_p60_rolling_window", 252))
    med_w = int(sp.get("vol_median_rolling_window", 126))
    zs_w  = int(sp.get("zscore_rolling_window", 252))
    zs_mp = int(sp.get("zscore_min_periods", 126))
    crash = float(sp.get("crash_trigger_vol", 0.30))
    dpy   = int(sp.get("trading_days_per_year", 252))
    crash_mode = str(sp.get("crash_mode", "absolute") or "absolute")
    crash_z = float(sp.get("crash_zscore", 2.5) or 2.5)

    ret = close.pct_change()
    mom = close.pct_change(mom_w)
    vol = ret.rolling(vol_w).std() * math.sqrt(dpy)
    zscore = _mean_reversion_zscore(close, zs_w, zs_mp)
    vol_p60 = vol.rolling(p60_w).apply(
        lambda v: np.nanpercentile(v, 60) if np.isfinite(v).sum() >= 60 else np.nan,
        raw=True,
    )
    vol_med = vol.rolling(med_w).median()
    vol_z = None
    if crash_mode == "relative_zscore":
        # 崩盘 = vol 相对自身 252d 历史偏离 > crash_z 个标准差 (高波动资产用, 避免绝对 0.30 误校准)
        vol_mean = vol.rolling(252, min_periods=126).mean()
        vol_std = vol.rolling(252, min_periods=126).std()
        vol_z = (vol - vol_mean) / vol_std.replace(0.0, np.nan)
        crash_trig = vol_z > crash_z
    else:
        crash_trig = vol > crash
    risk_off = ((vol > vol_p60) & (mom < 0)) | crash_trig
    risk_on = (vol <= vol_med) & (mom > 0) & (~crash_trig)
    regime = pd.Series("moderate", index=close.index, dtype="object")
    regime.loc[risk_off.fillna(False)] = "risk_off"
    regime.loc[risk_on.fillna(False)] = "risk_on"
    nan_mask = mom.isna() | vol.isna()
    if crash_mode == "relative_zscore" and vol_z is not None:
        nan_mask = nan_mask | vol_z.isna()
    regime.loc[nan_mask] = np.nan
    return pd.DataFrame({
        "close": close, "mom": mom, "vol": vol, "vol_p60": vol_p60,
        "vol_med": vol_med, "zscore": zscore, "regime": regime,
    })


def _overlay_rule_for(group: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    rules = cfg.get("overlay_rules") or {}
    if group in rules:
        return rules[group]
    return cfg.get("_defaults_for_unmatched_group") or {
        "buy_threshold": None, "sell_threshold": None, "delta": 0.0, "label": "无叠加",
    }


def build_overlay_recommendation(group: str, z: Optional[float], cfg: Dict[str, Any]) -> Dict[str, Any]:
    rule = _overlay_rule_for(group, cfg)
    buy = rule.get("buy_threshold")
    sell = rule.get("sell_threshold")
    delta = float(rule.get("delta", 0.0) or 0.0)
    label = rule.get("label", "")
    base = {
        "rule_label": label,
        "buy_threshold": buy,
        "sell_threshold": sell,
        "action": "none",
        "equity_delta_pct": 0.0,
        "text": f"{label}额外规则: 未触发, 维持基础仓位",
    }
    if z is None:
        base["action"] = "unavailable"
        base["text"] = f"{label}额外规则: 标准差偏离暂无有效值, 维持基础仓位"
        return base
    zs = f"z={z:.2f}"
    pp = delta * 100.0
    if buy is not None and z <= float(buy):
        base["action"] = "buy"
        base["equity_delta_pct"] = pp
        base["text"] = f"{label}极端偏离: {zs}, 抄底加仓, 股票仓位+{pp:.0f}pp, SGOV-{pp:.0f}pp"
        return base
    if sell is not None and z >= float(sell):
        base["action"] = "sell"
        base["equity_delta_pct"] = -pp
        base["text"] = f"{label}极端偏离: {zs}, 高位减仓, 股票仓位-{pp:.0f}pp, SGOV+{pp:.0f}pp"
        return base
    base["text"] = f"{label}额外规则: {zs}, 未触发, 维持基础仓位"
    return base


def _allocation_text_with_delta(regime: str, equity_delta: float, cfg: Dict[str, Any]) -> str:
    weights = dict((cfg.get("regime_weights") or {}).get(regime, {}))
    base_eq = float(weights.get("equity", 0.5))
    gld = float(weights.get("GLD", 0.25))
    equity = min(max(base_eq + equity_delta, 0.0), 1.0 - gld)
    sgov = max(0.0, 1.0 - equity - gld)
    return f"股票{equity*100:.0f}% / GLD{gld*100:.0f}% / SGOV{sgov*100:.0f}%"


def explain_regime(regime: str, vol: Optional[float], mom: Optional[float],
                   vol_p60: Optional[float], vol_med: Optional[float],
                   crash_trigger: float,
                   crash_mode: str = "absolute", crash_zscore: float = 2.5) -> Dict[str, Any]:
    """对单市场按当前 regime 反推 "为什么判定为这档", 返回:
       {
         "primary": "crash_trigger"|"mom+vol_offensive"|"mom+vol_safe_on"|"moderate_default",
         "text": "一句话说明",
         "drivers": [{name, value, threshold, passed: bool, note}],  // 各判据当前值与阈值的对比
         "next_trigger": "切换到 risk_on 需要什么 / 切换到 risk_off 需要什么 / 维持 moderate 条件",
       }

    口径与 build_signal_frame 一致:
      risk_off = (vol > vol_p60 且 mom < 0) 或 vol > crash_trigger
      risk_on  = (vol <= vol_med) 且 mom > 0 且 非 crash
      moderate = 其它

    注意 mom/vol 此处接受的是 "百分数 (0.05=5%) 还是 小数" 必须和 build_signal_frame 内部口径一致.
    本函数约定: mom/vol/vol_p60/vol_med 都是 ratio (5% 传 0.05), 与 build_signal_frame 内部完全一致;
    crash_trigger 也是 ratio (0.30).
    """
    drivers = []
    if crash_mode == "relative_zscore":
        crash_desc = (f"波动率相对自身252d历史 z-score > {crash_zscore}σ "
                      f"(非绝对 {crash_trigger*100:.0f}% 崩盘线)")
        exit_cond = f"波动率 z-score 退到 < {crash_zscore}σ"
    else:
        crash_desc = f"波动率 > {crash_trigger*100:.0f}% 崩盘线"
        exit_cond = f"vol 退到 < {crash_trigger*100:.0f}%"
    if regime == "risk_off":
        # 优先级: crash trigger > mom+vol_offensive
        if vol is not None and vol > crash_trigger:
            primary = "crash_trigger"
            text = f"{crash_desc} → 强制 risk_off"
            drivers.append({
                "name": "vol_crash",
                "value": vol, "threshold": crash_trigger,
                "passed": True,
                "note": f"{crash_desc}, 强制 risk_off",
            })
            drivers.append({
                "name": "mom_vol_p60",
                "value": {"vol": vol, "mom": mom},
                "threshold": {"vol_p60": vol_p60, "mom_sign": "negative"},
                "passed": bool(vol is not None and vol_p60 is not None and vol > vol_p60 and mom is not None and mom < 0),
                "note": (f"同时 vol {vol*100:.2f}% > p60 {vol_p60*100:.2f}% 且 mom {mom*100:+.2f}%<0"
                         if (vol is not None and mom is not None and vol_p60 is not None) else
                         "另: 同时满足 vol>p60 且 mom<0 也可触发 risk_off"),
            })
            next_trigger = (f"切回 risk_on: 需 vol <= vol_med (中位 vol) 且 mom>0 且 {exit_cond}; "
                            f"当前仍超崩盘触发线")
        elif vol is not None and mom is not None and vol_p60 is not None and vol > vol_p60 and mom < 0:
            primary = "mom_vol_offensive"
            text = (f"波动率 {vol*100:.2f}% > 252日 p60 {vol_p60*100:.2f}% 且 21d 动量 {mom*100:+.2f}% < 0 → risk_off")
            drivers.append({
                "name": "vol_vs_p60",
                "value": vol, "threshold": vol_p60,
                "passed": True,
                "note": f"vol {vol*100:.2f}% > p60 {vol_p60*100:.2f}%",
            })
            drivers.append({
                "name": "mom_negative",
                "value": mom, "threshold": 0.0,
                "passed": True,
                "note": f"mom {mom*100:+.2f}% < 0",
            })
            drivers.append({
                "name": "vol_crash",
                "value": vol, "threshold": crash_trigger,
                "passed": False,
                "note": f"vol {vol*100:.2f}% 未超崩盘线 {crash_trigger*100:.0f}% (非 crash 触发)",
            })
            need_vol_drop = (vol_p60 - vol) * 100 if vol is not None else None
            next_trigger = (f"切回 risk_on: 需 vol <= vol_med {vol_med*100:.2f}% 且 mom>0 转正 且 vol 不超崩盘线. "
                            f"当前 vol 距 p60 还需降 {need_vol_drop:+.2f}% 才不再满足 'vol>p60'; "
                            f"或 mom 转正 (当前 {mom*100:+.2f}%)")
        else:
            primary = "mom_vol_offensive_incomplete"
            text = "risk_off 但当前指标不足以解释 (数据缺失?), 建议检查信号计算"
            next_trigger = "-"
    elif regime == "risk_on":
        primary = "mom_vol_safe_on"
        text = (f"波动率 {vol*100:.2f}% <= 126日中位 {vol_med*100:.2f}% 且 21d 动量 {mom*100:+.2f}% > 0, "
                f"vol 不超崩盘线 → risk_on")
        drivers.append({
            "name": "vol_vs_median", "value": vol, "threshold": vol_med,
            "passed": True, "note": f"vol {vol*100:.2f}% <= 中位 {vol_med*100:.2f}%",
        })
        drivers.append({
            "name": "mom_positive", "value": mom, "threshold": 0.0,
            "passed": True, "note": f"mom {mom*100:+.2f}% > 0",
        })
        drivers.append({
            "name": "vol_crash", "value": vol, "threshold": crash_trigger,
            "passed": False, "note": f"vol {vol*100:.2f}% 未超崩盘线 {crash_trigger*100:.0f}% (保持 risk_on 的前提)",
        })
        next_trigger = (f"切到 risk_off 任一即可: vol>{vol_p60*100:.2f}%(p60)且mom转负, "
                        f"或 vol>{crash_trigger*100:.0f}%(崩盘线)")
    else:  # moderate
        primary = "moderate_default"
        if vol is None or mom is None or vol_p60 is None or vol_med is None:
            text = "数据不全, 默认 moderate"
            next_trigger = "-"
        elif crash_mode != "relative_zscore" and vol is not None and vol >= crash_trigger:
            # 理论情景: vol 超崩盘线应该被 risk_off 覆盖; 但万一命中 moderate 说明口径有异常
            text = f"{crash_desc}, 但仍被判定为 moderate (异常, 需排查)"
            next_trigger = "(异常排查)"
        else:
            conditions = []
            if mom >= 0:
                # 没 risk_on: 要么 mom>0 但 vol 超中位
                if vol > vol_med:
                    conditions.append(f"mom {mom*100:+.2f}%>0 但 vol {vol*100:.2f}% 仍 > 中位 {vol_med*100:.2f}% (不满足 risk_on 的 vol 收敛条件)")
                else:
                    conditions.append(f"mom {mom*100:+.2f}%>=0 但未同时满足 vol<=中位 + mom>0 (临界值)")
            if vol > vol_p60:
                # 没 risk_off (因 mom≥0 不能 match mom<0)
                conditions.append(f"vol {vol*100:.2f}% > p60 {vol_p60*100:.2f}% 但 mom {mom*100:+.2f}%>=0 (不满足 risk_off 的 mom<0 条件)")
            if not conditions:
                conditions.append(f"两档触发条件均未达成: vol {vol*100:.2f}% / mom {mom*100:+.2f}% / p60 {vol_p60*100:.2f}% / 中位 {vol_med*100:.2f}%")
            text = "moderate: " + "; ".join(conditions)
            next_trigger_on = (f"切到 risk_on: 需 vol <= {vol_med*100:.2f}%(中位) 且 mom>0 (当前 mom {mom*100:+.2f}%, vol {vol*100:.2f}%)")
            next_trigger_off = (f"切到 risk_off: 需 vol > {vol_p60*100:.2f}%(p60) 且 mom<0, 或 vol>{crash_trigger*100:.0f}%(崩盘线)")
            next_trigger = next_trigger_on + "  |  " + next_trigger_off

    return {
        "primary": primary,
        "text": text,
        "drivers": drivers,
        "next_trigger": next_trigger,
    }


def summarize_market(spec: MarketSpec, cfg: Dict[str, Any], cache_dir: Path,
                     warnings: Optional[List[str]] = None,
                     max_retries: int = 3, retry_backoff: float = 3.0) -> Dict[str, Any]:
    sp = _sp_from_cfg(cfg)
    # 合并该市场的崩盘阈值覆盖 (高波动资产用相对 z-score 模式, 其余走全局默认)
    sp = dict(sp)
    sp["crash_mode"] = spec.crash_mode
    sp["crash_zscore"] = spec.crash_zscore
    df = download_ohlc(spec, cache_dir, sp, warnings=warnings,
                       max_retries=max_retries, retry_backoff=retry_backoff)
    sf = build_signal_frame(df["Close"], sp)
    valid = sf.dropna(subset=["regime"])
    if valid.empty:
        raise RuntimeError(f"{spec.ticker} (={spec.label}) 缺有效信号窗口")
    latest_idx = valid.index[-1]
    prev_idx = valid.index[-2] if len(valid.index) > 1 else latest_idx
    cur_row = valid.loc[prev_idx]
    nxt_row = valid.loc[latest_idx]
    cur_regime = str(cur_row["regime"])
    nxt_regime = str(nxt_row["regime"])
    z = _safe_num(nxt_row["zscore"])
    overlay = build_overlay_recommendation(spec.market_group, z, cfg)
    eq_delta = float(overlay.get("equity_delta_pct") or 0.0) / 100.0
    adj_text = _allocation_text_with_delta(nxt_regime, eq_delta, cfg)
    base_text = ALLOCATION_BASE_TEXT.get(nxt_regime, "-")
    crash_trigger = float(sp.get("crash_trigger_vol", 0.30))
    # 解释 curRegime 和 nextRegime "为什么是这一档"
    cur_explain = explain_regime(
        cur_regime,
        _safe_num(cur_row["vol"]), _safe_num(cur_row["mom"]),
        _safe_num(cur_row["vol_p60"]), _safe_num(cur_row["vol_med"]),
        crash_trigger, crash_mode=spec.crash_mode, crash_zscore=spec.crash_zscore,
    )
    nxt_explain = explain_regime(
        nxt_regime,
        _safe_num(nxt_row["vol"]), _safe_num(nxt_row["mom"]),
        _safe_num(nxt_row["vol_p60"]), _safe_num(nxt_row["vol_med"]),
        crash_trigger, crash_mode=spec.crash_mode, crash_zscore=spec.crash_zscore,
    )
    return {
        "marketGroup": spec.market_group,
        "label": spec.label,
        "ticker": spec.ticker,
        "proxy": spec.proxy or "",
        "currentRegime": cur_regime,
        "nextRegime": nxt_regime,
        "currentEmoji": REGIME_EMOJI.get(cur_regime),
        "nextEmoji": REGIME_EMOJI.get(nxt_regime),
        "currentRegimeReason": cur_explain.get("text"),
        "currentRegimeNextTrigger": cur_explain.get("next_trigger"),
        "nextRegimeReason": nxt_explain.get("text"),
        "nextRegimeNextTrigger": nxt_explain.get("next_trigger"),
        "signalDate": str(latest_idx.date()),
        "price": _safe_num(nxt_row["close"]),
        "volPct": _safe_pct(nxt_row["vol"]),
        "volP60Pct": _safe_pct(nxt_row["vol_p60"]),
        "medianVolPct": _safe_pct(nxt_row["vol_med"]),
        "momPct": _safe_pct(nxt_row["mom"]),
        "crashTriggerVolPct": _safe_pct(crash_trigger),
        "crashMode": spec.crash_mode,
        "crashZscore": spec.crash_zscore,
        "priceZScore252": z,
        "overlayRuleLabel": overlay.get("rule_label"),
        "overlayAction": overlay.get("action"),
        "overlayEquityDeltaPct": overlay.get("equity_delta_pct"),
        "overlayRecommendationText": overlay.get("text"),
        "overlayAdjustedAllocationText": adj_text,
        "allocationText": base_text,
        "changed": cur_regime != nxt_regime,
    }


def build_snapshot(cfg: Dict[str, Any], cache_dir: Path,
                   max_retries: int = 3, retry_backoff: float = 3.0,
                   inter_ticker_delay: float = 1.5) -> Dict[str, Any]:
    markets = _markets_from_cfg(cfg)
    rows = []
    errors = []
    warnings: List[str] = []
    for i, spec in enumerate(markets):
        try:
            rows.append(summarize_market(spec, cfg, cache_dir, warnings=warnings,
                                         max_retries=max_retries, retry_backoff=retry_backoff))
        except Exception as e:
            rows.append({
                "marketGroup": spec.market_group, "label": spec.label,
                "ticker": spec.ticker, "proxy": spec.proxy,
                "currentRegime": None, "nextRegime": None,
                "currentEmoji": None, "nextEmoji": None,
                "signalDate": None, "price": None, "volPct": None,
                "volP60Pct": None, "medianVolPct": None, "momPct": None,
                "priceZScore252": None, "overlayRuleLabel": None,
                "overlayAction": "unavailable", "overlayEquityDeltaPct": 0.0,
                "overlayRecommendationText": f"summarize_market 失败: {e}",
                "overlayAdjustedAllocationText": None, "allocationText": None,
                "changed": False, "_error": str(e),
            })
            errors.append(f"{spec.label} ({spec.ticker}): {e}")
        # 品种间轻微间隔, 降低 yahoo 把连续请求当限频的风险
        if inter_ticker_delay and i < len(markets) - 1:
            time.sleep(inter_ticker_delay)
    signal_dates = sorted({r.get("signalDate") for r in rows if r.get("signalDate")})
    as_of = signal_dates[-1] if len(signal_dates) == 1 else None
    risk_on = sum(1 for r in rows if r.get("nextRegime") == "risk_on")
    moderate = sum(1 for r in rows if r.get("nextRegime") == "moderate")
    risk_off = sum(1 for r in rows if r.get("nextRegime") == "risk_off")
    changed = sum(1 for r in rows if r.get("changed"))
    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "source": "monitor_trhrp_local",
        "asOfDate": as_of,
        "riskOnCount": risk_on,
        "moderateCount": moderate,
        "riskOffCount": risk_off,
        "changedMarkets": changed,
        "telegramEnabled": False,  # monitor 端不自带 TG, 通知由 notifiers 框架统一发
        "stale": bool(warnings),   # 只要有缓存回退即视为数据可能过期
        "error": "\n".join(errors) if errors else None,
        "warnings": warnings,
        "markets": rows,
    }


def render_message(snapshot: Dict[str, Any]) -> str:
    lines = [
        f"TRHRP 多市场信号 — {snapshot.get('asOfDate') or '-'}",
        "▸ 口径: T 日收盘信号, T+1 生效",
        f"▸ 市场: {', '.join(m.get('label','-') for m in (snapshot.get('markets') or []))}",
        f"🟢 risk_on: {snapshot.get('riskOnCount',0)} | 🟡 moderate: {snapshot.get('moderateCount',0)} | 🔴 risk_off: {snapshot.get('riskOffCount',0)}",
    ]
    if snapshot.get("changedMarkets"):
        lines.append(f"⚠️ 有 {snapshot['changedMarkets']} 个市场次日信号已变化")
    else:
        lines.append("✅ 各市场次日信号均未变化")
    last_group = None
    for m in snapshot.get("markets") or []:
        if m.get("marketGroup") != last_group:
            last_group = m.get("marketGroup")
            lines.append("")
            lines.append(f"{last_group}")
        marker = " ⚠️" if m.get("changed") else ""
        cur_r = (m.get("currentRegime") or "-").upper()
        nxt_r = (m.get("nextRegime") or "-").upper()
        lines.append(f"- {m.get('label','-')} [{cur_r} → {nxt_r}]{marker}")
        lines.append(f"  信号日 {m.get('signalDate','-')} 价格 {m.get('price'):.2f}" if isinstance(m.get('price'), (int, float)) else f"  信号日 {m.get('signalDate','-')} 价格 -")
        lines.append(f"  波动率 {m.get('volPct'):.2f}% (p60={m.get('volP60Pct'):.2f}% 中位={m.get('medianVolPct'):.2f}%)"
                     if isinstance(m.get('volPct'), (int, float)) else "  波动率 -")
        z = m.get("priceZScore252")
        z_str = f"{z:+.2f}σ" if isinstance(z, (int, float)) else "-"
        lines.append(f"  z-score {z_str}  次日 {m.get('allocationText','-')}")
        lines.append(f"  叠加 {m.get('overlayRecommendationText','-')} → {m.get('overlayAdjustedAllocationText') or m.get('allocationText','-')}")
    if snapshot.get("error"):
        lines.append("")
        lines.append(f"⚠️ error: {snapshot['error']}")
    return "\n".join(lines)
