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
FACTOR_WEIGHTS = {"liqsize20": 1.0, "rev5": 0.5, "ivol60": 0.5}


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
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(fd)
    try:
        out = frame.copy()
        out.index.name = "date"
        out.to_parquet(tmp_name)
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def cache_paths(cache_dir: str | Path) -> tuple[Path, Path, Path]:
    root = Path(cache_dir)
    return root / "close.parquet", root / "amount.parquet", root / "close_raw.parquet"


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
    close_raw: pd.DataFrame | None = None,
    rolling_days: int = ROLLING_DAYS,
) -> None:
    """只保存生产信号所需的 close/amount 滚动宽表。"""
    dates = close.index.union(amount.index).sort_values()[-rolling_days:]
    source_raw = close if close_raw is None else close_raw
    columns = close.columns.union(amount.columns).union(source_raw.columns).sort_values()
    close = close.reindex(index=dates, columns=columns).astype(np.float32)
    amount = amount.reindex(index=dates, columns=columns).astype(np.float32)
    close_raw = source_raw.reindex(
        index=dates, columns=columns
    ).astype(np.float32)
    root = Path(cache_dir)
    generation = f"{time.time_ns()}-{os.getpid()}"
    generation_dir = root / "generations" / generation
    generation_dir.mkdir(parents=True, exist_ok=False)
    close_path, amount_path, raw_path = cache_paths(generation_dir)
    atomic_write_parquet(close_path, close)
    atomic_write_parquet(amount_path, amount)
    atomic_write_parquet(raw_path, close_raw)
    atomic_write_json(root / "current.json", {"generation": generation})

    # 指针切换成功后只保留当前和上一代，避免每日缓存无限增长。
    generations = sorted(
        (item for item in (root / "generations").iterdir() if item.is_dir()),
        key=lambda item: item.name,
        reverse=True,
    )
    for stale in generations[2:]:
        shutil.rmtree(stale, ignore_errors=True)


def load_market_cache(cache_dir: str | Path) -> dict[str, pd.DataFrame] | None:
    close_path, amount_path, raw_path = cache_paths(_active_cache_dir(cache_dir))
    if not close_path.exists() or not amount_path.exists():
        return None
    close = pd.read_parquet(close_path)
    amount = pd.read_parquet(amount_path)
    close_raw = pd.read_parquet(raw_path) if raw_path.exists() else close.copy()
    close.index = pd.to_datetime(close.index)
    amount.index = pd.to_datetime(amount.index)
    close_raw.index = pd.to_datetime(close_raw.index)
    dates = close.index.union(amount.index).union(close_raw.index).sort_values()
    columns = close.columns.union(amount.columns).union(close_raw.columns).sort_values()
    return {
        "close": close.reindex(index=dates, columns=columns).astype(np.float32),
        "amount": amount.reindex(index=dates, columns=columns).astype(np.float32),
        "close_raw": close_raw.reindex(index=dates, columns=columns).astype(np.float32),
    }


def bootstrap_from_full_panels(
    full_panels: dict[str, pd.DataFrame],
    cache_dir: str | Path,
    rolling_days: int = ROLLING_DAYS,
) -> dict[str, pd.DataFrame]:
    """从研究面板生成小体积生产种子。"""
    close = full_panels["close"].iloc[-rolling_days:].copy()
    amount = full_panels["amount"].reindex_like(close).copy()
    close_raw = full_panels.get("close_raw", close).reindex_like(close).copy()
    save_market_cache(
        cache_dir, close, amount, close_raw=close_raw, rolling_days=rolling_days
    )
    return {
        "close": close.astype(np.float32),
        "amount": amount.astype(np.float32),
        "close_raw": close_raw.astype(np.float32),
    }


def merge_market_rows(
    cached: dict[str, pd.DataFrame] | None,
    close_rows: pd.DataFrame,
    amount_rows: pd.DataFrame,
    raw_rows: pd.DataFrame | None = None,
    rolling_days: int = ROLLING_DAYS,
) -> dict[str, pd.DataFrame]:
    """合并最近若干日修订数据；重复日期以新抓取结果为准。"""
    if cached is None:
        old_close = pd.DataFrame()
        old_amount = pd.DataFrame()
        old_raw = pd.DataFrame()
    else:
        old_close = cached["close"]
        old_amount = cached["amount"]
        old_raw = cached.get("close_raw", cached["close"])

    raw_rows = close_rows if raw_rows is None else raw_rows

    columns = (
        old_close.columns.union(close_rows.columns).union(amount_rows.columns)
        .union(old_raw.columns).union(raw_rows.columns).sort_values()
    )
    old_close = old_close.reindex(columns=columns)
    old_amount = old_amount.reindex(columns=columns)
    old_raw = old_raw.reindex(columns=columns)
    close_rows = close_rows.reindex(columns=columns)
    amount_rows = amount_rows.reindex(columns=columns)
    raw_rows = raw_rows.reindex(columns=columns)

    def overlay(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        dates = old.index.union(new.index).sort_values()
        base = old.reindex(index=dates, columns=columns).copy()
        base.update(new.reindex(index=dates, columns=columns))
        return base

    close = overlay(old_close, close_rows)
    amount = overlay(old_amount, amount_rows)
    close_raw = overlay(old_raw, raw_rows)
    dates = close.index.union(amount.index).union(close_raw.index).sort_values()[-rolling_days:]
    return {
        "close": close.reindex(dates).astype(np.float32),
        "amount": amount.reindex(dates).astype(np.float32),
        "close_raw": close_raw.reindex(dates).astype(np.float32),
    }


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


def production_scores(
    panels: dict[str, pd.DataFrame],
    mature_codes: set[str] | None = None,
) -> pd.DataFrame:
    """只计算线上策略使用的三个因子，口径与全量研究实现完全一致。"""
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
    ret = factors.daily_return(close)
    selected = {
        "liqsize20": factors.liquidity_size(amount, 20),
        "rev5": factors.rev(close, 5),
        "ivol60": factors.idio_vol(ret, 60),
    }
    return strategy.composite(selected, FACTOR_WEIGHTS, mask)


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
    frequency: int = 10,
) -> list[pd.Timestamp]:
    """沿用上一调仓日锚点，避免滚动窗口截短后调仓相位漂移。"""
    last_rb = pd.Timestamp(last_rebalance_date)
    through = pd.Timestamp(through_date)
    later = trading_dates[(trading_dates > last_rb) & (trading_dates <= through)]
    return [pd.Timestamp(dt) for i, dt in enumerate(later, start=1) if i % frequency == 0]


def normalise_volume(code: str, volume: pd.Series) -> pd.Series:
    """统一成手；腾讯科创板成交量返回股。"""
    return volume / (100.0 if panel._is_share_unit(code) else 1.0)
