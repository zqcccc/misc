"""A 股小微盘策略的生产增量数据与信号计算。

研究代码保留完整历史面板和全量回测；线上只持久化最近一段滚动窗口，
每天追加全市场最新截面，并只计算生产策略实际使用的三个因子。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import factors, panel, strategy, universe

ROLLING_DAYS = 400
CONFIG_SIZES = (7, 8, 6, 5, 10, 30)
# 2026-09-08 由 10 改为 20（月频）。依据 astock_quant/scripts/freq_rigorous_*.py：
#   · 机理：合成信号主体是 liqsize20 + ivol60 慢变量，rank IC 随持有期单调升至 h≈60~90 才饱和
#   · 成本：年换手 44.8x -> 23.7x，年成本 6.76% -> 3.57%（确定性省 3.19pp/年）
#   · 收益：多相位平均后 vs freq=10，TEST 段 -11.87pp(p=0.016)、全段 10.7 年 -4.95pp(p=0.004)，两段显著
#   · 60（季频）已排除：多相位 + 全段下效应 +0.22pp(p=0.93)，优势是调仓日历运气
REBALANCE_FREQUENCY = 20
FACTOR_WEIGHTS = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}

LEGACY_REBALANCE_FREQUENCY = 10  # 2026-09-08 之前的旧调仓周期，只用于一次性迁移判定


def state_rebalance_frequency(state: dict) -> int:
    """状态当前周期适用的调仓频率。

    新建/已迁移状态带 rebalance_frequency 字段；没有字段的旧状态按 10 日计数，
    在它既有的下一调仓日（计数达到 10）触发一次性迁移，之后按 REBALANCE_FREQUENCY。
    """
    value = state.get("rebalance_frequency")
    return int(value) if value else LEGACY_REBALANCE_FREQUENCY


def rebalance_tick(days_since_rebalance: int, frequency: int) -> tuple[int, bool]:
    """推进一个交易日的调仓时钟，返回 (新计数, 是否到达调仓日)。"""
    days = int(days_since_rebalance) + 1
    return days, days >= frequency


def settle_rebalance_state(state: dict) -> None:
    """调仓触发后的状态收尾：计数清零，并把频率一次性迁移到 REBALANCE_FREQUENCY。"""
    state["trading_days_since_rebalance"] = 0
    if state_rebalance_frequency(state) != REBALANCE_FREQUENCY:
        state["rebalance_frequency"] = REBALANCE_FREQUENCY


FACTOR_META = {
    "liqsize20": {
        "label": "20 日成交额规模",
        "short_label": "小盘规模（成交额代理）",
        "direction": "过去 20 日平均成交额越小，得分越高",
        "formula": "-ln(mean(成交额, 20日))",
    },
    "rev5": {
        "label": "5 日短期反转",
        "short_label": "短期反转",
        "direction": "过去 5 日涨幅越低，得分越高",
        "formula": "-(收盘价_t / 收盘价_t-5 - 1)",
    },
    "ivol60": {
        "label": "60 日低特质波动",
        "short_label": "低特质波动",
        "direction": "剔除全 A 等权市场波动后，残差波动越低，得分越高",
        "formula": "-std(日收益 - beta × 全A等权收益, 60日)",
    },
}


def factor_methodology() -> dict[str, Any]:
    """前端可直接展示的生产因子口径；与实际计算常量共用同一来源。"""
    weight_sum = sum(abs(weight) for weight in FACTOR_WEIGHTS.values())
    return {
        "score_range": [-0.5, 0.5],
        "weight_sum": weight_sum,
        "formula": (
            "[1.0×(小盘百分位-0.5) + 0.5×(反转百分位-0.5) "
            "+ 0.5×(低特质波动百分位-0.5)] / 2.0"
        ),
        "ranking": "每个交易日只在当日可投资股票池内做截面百分位排名；百分位越高越好",
        "timing": "T 日收盘后计算，T+1 日开盘执行",
        "selection": (
            f"每 {REBALANCE_FREQUENCY} 个交易日调仓；已持仓进入前 2N 名即可保留，"
            f"再用高分股补足 N 只"
        ),
        "factors": {
            name: {**FACTOR_META[name], "weight": weight}
            for name, weight in FACTOR_WEIGHTS.items()
        },
    }


def parse_tencent_snapshot_parts(parts: list[str]) -> dict[str, Any]:
    """解析 qt.gtimg.cn 快照字段，避免把 parts[5] 的开盘价误当涨跌幅。"""
    if len(parts) <= 45:
        raise ValueError(f"腾讯行情字段不足: {len(parts)}")

    def number(index: int) -> float:
        try:
            return float(parts[index]) if parts[index] else 0.0
        except (TypeError, ValueError):
            return 0.0

    price = number(3)
    previous_close = number(4)
    change_pct = number(32)
    if not parts[32] and previous_close > 0:
        change_pct = (price / previous_close - 1.0) * 100.0
    return {
        "name": parts[1].replace(" ", ""),
        "raw_code": parts[2],
        "price": price,
        "previous_close": previous_close,
        "open": number(5),
        "change_pct": change_pct,
        "quote_time": parts[30],
        "float_cap_billion": round(number(44), 2),
        "total_cap_billion": round(number(45), 2),
    }


def atomic_write_json(path: str | Path, value: Any) -> None:
    """同目录临时文件 + replace，避免读者看到半份 JSON。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_parquet(path: str | Path, frame: pd.DataFrame) -> None:
    """同目录临时文件 + replace；保留调用方原有的 index.name，round-trip 不改名。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(fd)
    try:
        frame.copy().to_parquet(tmp_name)
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def cache_paths(cache_dir: str | Path) -> tuple[Path, Path, Path, Path, Path]:
    root = Path(cache_dir)
    return (
        root / "close.parquet",
        root / "amount.parquet",
        root / "close_raw.parquet",
        root / "open.parquet",
        root / "open_raw.parquet",
    )


def _active_cache_dir(cache_dir: str | Path) -> Path:
    root = Path(cache_dir)
    pointer = root / "current.json"
    if pointer.exists():
        try:
            generation = json.loads(pointer.read_text(encoding="utf-8"))["generation"]
            candidate = root / "generations" / generation
            if candidate.is_dir():
                return candidate
        except Exception:  # noqa: BLE001 - 旧格式/损坏时走兼容路径
            pass
    return root


def save_market_cache(
    cache_dir: str | Path,
    close: pd.DataFrame,
    amount: pd.DataFrame,
    close_raw: pd.DataFrame,
    open_panel: pd.DataFrame,
    open_raw_panel: pd.DataFrame,
    rolling_days: int = ROLLING_DAYS,
) -> None:
    """保存生产信号所需的滚动宽表；open（复权）与 open_raw 同代原子切换。"""
    dates = close.index.union(amount.index).sort_values()[-rolling_days:]
    columns = close.columns.union(amount.columns).union(close_raw.columns)
    columns = columns.union(open_panel.columns).union(open_raw_panel.columns).sort_values()
    panels = [
        frame.reindex(index=dates, columns=columns).astype(np.float32)
        for frame in (close, amount, close_raw, open_panel, open_raw_panel)
    ]
    root = Path(cache_dir)
    generation = f"{time.time_ns()}-{os.getpid()}"
    generation_dir = root / "generations" / generation
    generation_dir.mkdir(parents=True, exist_ok=False)
    paths = cache_paths(generation_dir)
    for path, frame in zip(paths, panels):
        atomic_write_parquet(path, frame)
    atomic_write_json(root / "current.json", {"generation": generation})

    # 指针切换成功后只保留当前和上一代，避免每日缓存无限增长。
    generations = sorted(
        (item for item in (root / "generations").iterdir() if item.is_dir()),
        key=lambda item: item.name,
        reverse=True,
    )
    for stale in generations[2:]:
        shutil.rmtree(stale, ignore_errors=True)


def load_market_cache(cache_dir: str | Path) -> dict[str, pd.DataFrame | None] | None:
    """读当前代缓存；open/open_raw 缺失（旧版缓存）时返回 None，由调用方显式降级，
    绝不拿 close 冒充。"""
    paths = cache_paths(_active_cache_dir(cache_dir))
    if not paths[0].exists() or not paths[1].exists():
        return None
    frames: dict[str, pd.DataFrame | None] = {
        "close": pd.read_parquet(paths[0]),
        "amount": pd.read_parquet(paths[1]),
        "close_raw": None,
        "open": None,
        "open_raw": None,
    }
    for key, path in (("close_raw", paths[2]), ("open", paths[3]), ("open_raw", paths[4])):
        if path.exists():
            frames[key] = pd.read_parquet(path)
    base = frames["close"]
    dates = pd.to_datetime(base.index)
    columns = base.columns
    for key, frame in frames.items():
        if frame is None:
            continue
        frame.index = pd.to_datetime(frame.index)
        frames[key] = frame.reindex(index=dates, columns=columns).astype(np.float32)
    return frames


def bootstrap_from_full_panels(
    full_panels: dict[str, pd.DataFrame],
    cache_dir: str | Path,
    rolling_days: int = ROLLING_DAYS,
) -> dict[str, pd.DataFrame]:
    """从研究面板生成小体积生产种子（close/amount/close_raw/open/open_raw 同代）。"""
    close = full_panels["close"].iloc[-rolling_days:].copy()
    amount = full_panels["amount"].reindex_like(close).copy()
    close_raw = full_panels["close_raw"].reindex_like(close).copy()
    open_panel = full_panels["open"].reindex_like(close).copy()
    open_raw = full_panels["open_raw"].reindex_like(close).copy()
    save_market_cache(
        cache_dir, close, amount, close_raw, open_panel, open_raw,
        rolling_days=rolling_days,
    )
    return {
        "close": close.astype(np.float32),
        "amount": amount.astype(np.float32),
        "close_raw": close_raw.astype(np.float32),
        "open": open_panel.astype(np.float32),
        "open_raw": open_raw.astype(np.float32),
    }


def merge_market_rows(
    cached: dict[str, pd.DataFrame] | None,
    close_rows: pd.DataFrame,
    amount_rows: pd.DataFrame,
    raw_rows: pd.DataFrame | None = None,
    open_rows: pd.DataFrame | None = None,
    open_raw_rows: pd.DataFrame | None = None,
    rolling_days: int = ROLLING_DAYS,
) -> dict[str, pd.DataFrame]:
    """合并最近若干日修订数据；重复日期以新抓取结果为准。

    open/open_raw 没有历史或新数据时保持全 NaN（不伪造），current_period 据此
    给出明确的降级标记。
    """
    if cached is None:
        olds = {key: pd.DataFrame() for key in
                ("close", "amount", "close_raw", "open", "open_raw")}
    else:
        olds = {
            "close": cached["close"],
            "amount": cached["amount"],
            "close_raw": cached.get("close_raw") if cached.get("close_raw") is not None else pd.DataFrame(),
            "open": cached.get("open") if cached.get("open") is not None else pd.DataFrame(),
            "open_raw": cached.get("open_raw") if cached.get("open_raw") is not None else pd.DataFrame(),
        }

    news = {
        "close": close_rows,
        "amount": amount_rows,
        "close_raw": close_rows if raw_rows is None else raw_rows,
        "open": open_rows if open_rows is not None else pd.DataFrame(),
        "open_raw": open_raw_rows if open_raw_rows is not None else pd.DataFrame(),
    }

    all_columns = pd.Index([])
    for frame in list(olds.values()) + list(news.values()):
        all_columns = all_columns.union(frame.columns)
    columns = all_columns.sort_values()

    merged: dict[str, pd.DataFrame] = {}
    for key in olds:
        old = olds[key].reindex(columns=columns)
        new = news[key].reindex(columns=columns)
        dates = old.index.union(new.index).sort_values()
        base = old.reindex(index=dates, columns=columns).copy()
        base.update(new.reindex(index=dates, columns=columns))
        merged[key] = base
    span = (
        merged["close"].index.union(merged["amount"].index)
        .union(merged["close_raw"].index).sort_values()[-rolling_days:]
    )
    return {key: frame.reindex(span).astype(np.float32) for key, frame in merged.items()}


def validate_latest_cross_section(
    cached: dict[str, pd.DataFrame] | None,
    merged: dict[str, pd.DataFrame],
    expected_date: str | pd.Timestamp,
    min_coverage: float = 0.95,
) -> dict[str, float | int | str]:
    """验证当天截面覆盖率；不完整时由调用方拒绝发布。"""
    expected = pd.Timestamp(expected_date)
    close = merged["close"]
    amount = merged["amount"]
    if expected not in close.index:
        raise ValueError(f"最新交易日 {expected.date()} 没有任何个股行情")

    valid = close.loc[expected].notna() & amount.loc[expected].notna()
    current_count = int(valid.sum())
    baseline = 0
    if cached is not None and not cached["close"].empty:
        previous_dates = cached["close"].index[cached["close"].index < expected]
        if len(previous_dates):
            prev = previous_dates[-1]
            baseline = int(
                (cached["close"].loc[prev].notna() & cached["amount"].loc[prev].notna()).sum()
            )
    if baseline <= 0 and len(close.index) > 1:
        previous_dates = close.index[close.index < expected]
        if len(previous_dates):
            prev = previous_dates[-1]
            baseline = int((close.loc[prev].notna() & amount.loc[prev].notna()).sum())

    coverage = current_count / baseline if baseline else 1.0
    if baseline and coverage < min_coverage:
        raise ValueError(
            f"{expected.date()} 行情覆盖不足: {current_count}/{baseline}="
            f"{coverage:.1%}，门槛 {min_coverage:.1%}"
        )
    return {
        "expected_date": str(expected.date()),
        "valid_stocks": current_count,
        "baseline_stocks": baseline,
        "coverage": round(coverage, 6),
    }


def production_score_breakdown(
    panels: dict[str, pd.DataFrame],
    mature_codes: set[str] | None = None,
    factor_valid: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """返回复合总分、三个原始因子及其居中截面百分位。

    factor_valid[date, code] = False（复权未确认窗口）的个股当日不进截面排名。
    """
    close = panels["close"]
    amount = panels["amount"]
    minimal = {"close": close, "amount": amount}
    mask = universe.investable(
        minimal,
        min_listed=0 if mature_codes else 250,
        exclude_st=True,
        liquidity_top_pct=1.0,
    )
    if mature_codes:
        listed = universe.listed_days(close) >= 250
        known_mature = close.columns.intersection(sorted(mature_codes))
        if len(known_mature):
            listed.loc[:, known_mature] = True
        mask &= listed
    if factor_valid is not None:
        mask = mask & factor_valid.reindex_like(mask).fillna(False).astype(bool)
    ret = factors.daily_return(close)
    selected = {
        "liqsize20": factors.liquidity_size(amount, 20),
        "rev5": factors.rev(close, 5),
        "ivol60": factors.idio_vol(ret, 60),
    }
    ranked = {
        name: strategy.masked_rank_score(factor, mask)
        for name, factor in selected.items()
    }
    return strategy.composite(selected, FACTOR_WEIGHTS, mask), selected, ranked


def production_scores(
    panels: dict[str, pd.DataFrame],
    mature_codes: set[str] | None = None,
) -> pd.DataFrame:
    """只计算线上策略使用的三个因子，口径与全量研究实现完全一致。"""
    scores, _, _ = production_score_breakdown(panels, mature_codes=mature_codes)
    return scores


def factor_breakdown_at(
    raw_factors: dict[str, pd.DataFrame],
    ranked_factors: dict[str, pd.DataFrame],
    date: str | pd.Timestamp,
    code: str,
) -> dict[str, Any]:
    """把一个标的在指定交易日的因子拆解成可审计的 JSON。"""
    timestamp = pd.Timestamp(date)
    weight_sum = sum(abs(weight) for weight in FACTOR_WEIGHTS.values())
    items = []
    total_score = 0.0
    for name, weight in FACTOR_WEIGHTS.items():
        raw_value = float(raw_factors[name].at[timestamp, code])
        centered_score = float(ranked_factors[name].at[timestamp, code])
        raw_is_valid = np.isfinite(raw_value)
        score_is_valid = np.isfinite(centered_score)
        contribution = centered_score * weight / weight_sum if score_is_valid else 0.0
        total_score += contribution
        items.append({
            "key": name,
            **FACTOR_META[name],
            "weight": weight,
            "raw_value": round(raw_value, 8) if raw_is_valid else None,
            "percentile": round((centered_score + 0.5) * 100.0, 2) if score_is_valid else None,
            "centered_score": round(centered_score, 6) if score_is_valid else None,
            "contribution": round(contribution, 6),
        })
    return {
        "as_of": str(timestamp.date()),
        "total_score": round(total_score, 6),
        "items": items,
    }


ENTRY_BASIS_T1_OPEN = "t1_open"
ENTRY_BASIS_SIGNAL_CLOSE = "signal_close"
PERIOD_STATUS_PENDING = "pending"
PERIOD_STATUS_RUNNING = "running"
ENTRY_BASIS_META = {
    ENTRY_BASIS_T1_OPEN: "T+1 开盘价（与回测撮合价一致）",
    ENTRY_BASIS_SIGNAL_CLOSE: "信号日收盘价（该数据源无开盘价，含 T+1 隔夜跳空偏差）",
}


def current_period_summary(
    close: pd.DataFrame,
    codes: list[str],
    signal_date: str | pd.Timestamp,
    latest_date: str | pd.Timestamp,
    close_raw: pd.DataFrame | None = None,
    open_panel: pd.DataFrame | None = None,
    frequency: int = REBALANCE_FREQUENCY,
    unresolved_events: dict[str, pd.DatetimeIndex] | None = None,
) -> dict[str, Any]:
    """本期（上一调仓信号之后）的持仓收益，口径与 T+1 开盘执行的实盘一致。

    信号在 T 日收盘生成，实际建仓在 T+1 开盘，因此 T 日当天本期收益还不存在，
    此时返回 pending 状态，让前端明确区分"已下单持有"和"明早才买"。
    建仓价优先取 T+1 开盘价；open 面板缺失时置 entry_basis_degraded=True 并退回
    信号日收盘口径，绝不冒充开盘价口径。建仓到最新收盘之间跨过未确认公司行动
    的标的，剔除出组合收益并在 codes_excluded 写明原因，不用被污染的复权价凑数。
    """
    dates = pd.DatetimeIndex(close.index)
    signal_ts = pd.Timestamp(signal_date)
    latest_ts = pd.Timestamp(latest_date)
    after_signal = dates[(dates > signal_ts) & (dates <= latest_ts)]
    elapsed = int(len(after_signal))

    summary: dict[str, Any] = {
        "signal_date": str(signal_ts.date()),
        "execution_date": str(after_signal[0].date()) if elapsed else None,
        "as_of": str(latest_ts.date()),
        "status": PERIOD_STATUS_RUNNING if elapsed else PERIOD_STATUS_PENDING,
        "trading_days_elapsed": elapsed,
        "trading_days_total": frequency,
        "trading_days_remaining": max(frequency - elapsed, 0),
        "entry_date": None,
        "entry_basis": None,
        "entry_basis_label": None,
        "entry_basis_degraded": None,
        "codes_excluded": {},
        "return_pct": None,
        "returns_by_code": {},
    }
    if not elapsed:
        return summary

    execution_ts = after_signal[0]
    use_open = (
        open_panel is not None
        and execution_ts in open_panel.index
        and not open_panel.loc[execution_ts, open_panel.columns.intersection(codes)].isna().all()
    )
    basis = ENTRY_BASIS_T1_OPEN if use_open else ENTRY_BASIS_SIGNAL_CLOSE
    summary["entry_basis"] = basis
    summary["entry_basis_label"] = ENTRY_BASIS_META[basis]
    summary["entry_basis_degraded"] = not use_open

    # 回退口径要落在面板真实存在的交易日上：滚动缓存截断或调仓日停市时，
    # 直接 .loc[signal_ts] 会抛 KeyError 把守护进程带崩。
    prior_dates = dates[dates <= signal_ts]
    entry_ts = execution_ts if use_open else (prior_dates[-1] if len(prior_dates) else dates[0])
    summary["entry_date"] = str(pd.Timestamp(entry_ts).date())
    entry_adjusted = (open_panel if use_open else close).loc[entry_ts]
    excluded: dict[str, str] = {}
    returns = []
    for code in codes:
        if code not in close.columns:
            continue
        ev = pd.DatetimeIndex((unresolved_events or {}).get(code, []))
        if len(ev[(ev > entry_ts) & (ev <= latest_ts)]):
            excluded[code] = "corporate_action_unconfirmed"
            continue
        entry_price = float(entry_adjusted.get(code, np.nan))
        last_price = float(close.at[latest_ts, code])
        if not np.isfinite(entry_price) or entry_price <= 0:
            excluded[code] = "missing_entry_price"
            continue
        if not np.isfinite(last_price):
            excluded[code] = "missing_last_price"
            continue
        ret_pct = (last_price / entry_price - 1.0) * 100.0
        returns.append(ret_pct)
        # 后复权价没有实盘含义，另外给一份未复权的委托参考价。
        display_price = None
        if close_raw is not None and code in close_raw.columns:
            adjusted_close = float(close.at[entry_ts, code])
            raw_close = float(close_raw.at[entry_ts, code])
            if np.isfinite(adjusted_close) and np.isfinite(raw_close) and adjusted_close > 0:
                display_price = round(entry_price * raw_close / adjusted_close, 2)
        summary["returns_by_code"][code] = {
            "entry_price": display_price,
            "return_pct": round(ret_pct, 2),
        }

    if returns:
        summary["return_pct"] = round(float(np.mean(returns)), 2)
    summary["codes_excluded"] = excluded
    return summary


def signal_holdings_at(sig: pd.DataFrame, date: str | pd.Timestamp | None = None) -> list[str]:
    """指定调仓日（默认最后一个调仓日）缓冲后的持仓，与回测引擎目标持仓同源。

    seed 交付物的 current_holdings 必须取自这里，而不是从原始分 Top100 重新
    截补 —— 后者没有滞后带状态，会与回测末期实际持仓不一致。
    """
    ts = sig.index[-1] if date is None else pd.Timestamp(date)
    return sig.loc[ts].dropna().index.tolist()


def buffered_select(score: pd.Series, held: list[str], top_n: int, buffer_mult: float = 2.0) -> list[str]:
    """单个调仓截面的迟滞选股，等价于 top_n_signals_buffered 的一步状态转移。"""
    clean = score.dropna()
    if clean.empty:
        return []
    order = clean.rank(ascending=False, method="first")
    keep_rank = int(top_n * buffer_mult)
    keep = [code for code in held if code in order.index and order[code] <= keep_rank]
    if len(keep) > top_n:
        keep = sorted(keep, key=lambda code: order[code])[:top_n]
    need = top_n - len(keep)
    if need > 0:
        keep.extend(order[~order.index.isin(keep)].nsmallest(need).index.tolist())
    return keep


def rebalance_dates_after(
    trading_dates: pd.DatetimeIndex,
    last_rebalance_date: str | pd.Timestamp,
    through_date: str | pd.Timestamp,
    frequency: int = REBALANCE_FREQUENCY,
) -> list[pd.Timestamp]:
    """沿用上一调仓日锚点，避免滚动窗口截短后调仓相位漂移。"""
    last_rb = pd.Timestamp(last_rebalance_date)
    through = pd.Timestamp(through_date)
    later = trading_dates[(trading_dates > last_rb) & (trading_dates <= through)]
    return [pd.Timestamp(dt) for i, dt in enumerate(later, start=1) if i % frequency == 0]


def normalise_volume(code: str, volume: pd.Series) -> pd.Series:
    """统一成手；腾讯科创板成交量返回股。"""
    return volume / (100.0 if panel._is_share_unit(code) else 1.0)
