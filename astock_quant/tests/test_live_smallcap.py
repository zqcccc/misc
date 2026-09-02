"""生产增量信号必须与研究全量口径一致。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aq import factors, live_smallcap, strategy, universe


def test_production_scores_match_full_factor_pipeline(random_panels):
    mask = universe.investable(
        random_panels,
        min_listed=250,
        exclude_st=True,
        liquidity_top_pct=1.0,
    )
    all_factors = factors.build_all(random_panels)
    expected = strategy.composite(
        {name: all_factors[name] for name in live_smallcap.FACTOR_WEIGHTS},
        live_smallcap.FACTOR_WEIGHTS,
        mask,
    )
    actual = live_smallcap.production_scores(random_panels)
    pd.testing.assert_series_equal(
        actual.iloc[-1], expected.iloc[-1], check_names=False, atol=1e-12, rtol=0
    )


def test_rolling_window_keeps_latest_signal_identical(random_panels):
    full = live_smallcap.production_scores(random_panels)
    rolling = {
        "close": random_panels["close"].iloc[-320:],
        "amount": random_panels["amount"].iloc[-320:],
    }
    incremental = live_smallcap.production_scores(rolling)
    pd.testing.assert_series_equal(
        incremental.iloc[-1], full.iloc[-1], check_names=False, atol=1e-12, rtol=0
    )


def test_mature_code_survives_rolling_listed_day_reset(random_panels):
    rolling = {
        "close": random_panels["close"].iloc[-200:].copy(),
        "amount": random_panels["amount"].iloc[-200:].copy(),
    }
    without_state = live_smallcap.production_scores(rolling)
    with_state = live_smallcap.production_scores(
        rolling, mature_codes=set(rolling["close"].columns)
    )
    assert without_state.iloc[-1].notna().sum() == 0
    assert with_state.iloc[-1].notna().sum() > 0


def test_buffered_select_matches_stateful_strategy():
    dates = pd.bdate_range("2026-01-01", periods=2)
    codes = [f"sh600{i:03d}" for i in range(20)]
    first = pd.Series(np.arange(20.0), index=codes)
    second = first.copy()
    second.iloc[-1] = -10.0
    second.iloc[5] = 30.0
    scores = pd.DataFrame([first, second], index=dates)
    expected = strategy.top_n_signals_buffered(
        scores, dates, top_n=5, buffer_mult=2.0
    ).iloc[-1].dropna().index.tolist()
    held = strategy.top_n_signals_buffered(
        scores.iloc[:1], dates[:1], top_n=5, buffer_mult=2.0
    ).iloc[-1].dropna().index.tolist()
    actual = live_smallcap.buffered_select(second, held, 5, buffer_mult=2.0)
    assert set(actual) == set(expected)


def test_merge_overwrites_recent_corrections():
    dates = pd.bdate_range("2026-01-01", periods=3)
    old = {
        "close": pd.DataFrame({"a": [1.0, 2.0]}, index=dates[:2]),
        "amount": pd.DataFrame({"a": [10.0, 20.0]}, index=dates[:2]),
        "close_raw": pd.DataFrame({"a": [1.0, 2.0]}, index=dates[:2]),
    }
    new_close = pd.DataFrame({"a": [2.2, 3.0]}, index=dates[1:])
    new_amount = pd.DataFrame({"a": [22.0, 30.0]}, index=dates[1:])
    merged = live_smallcap.merge_market_rows(old, new_close, new_amount, new_close)
    assert merged["close"].at[dates[1], "a"] == pytest.approx(2.2)
    assert merged["close"].at[dates[2], "a"] == pytest.approx(3.0)


def test_coverage_gate_rejects_partial_cross_section():
    dates = pd.bdate_range("2026-01-01", periods=2)
    codes = [f"c{i}" for i in range(100)]
    old_close = pd.DataFrame(1.0, index=dates[:1], columns=codes)
    current = pd.DataFrame(np.nan, index=dates[1:], columns=codes)
    current.iloc[:, :80] = 1.0
    cached = {"close": old_close, "amount": old_close.copy()}
    merged = {
        "close": pd.concat([old_close, current]),
        "amount": pd.concat([old_close, current]),
    }
    with pytest.raises(ValueError, match="覆盖不足"):
        live_smallcap.validate_latest_cross_section(
            cached, merged, dates[-1], min_coverage=0.95
        )


def test_atomic_json_never_publishes_nan(tmp_path):
    target = tmp_path / "signal.json"
    live_smallcap.atomic_write_json(target, {"status": "old"})
    with pytest.raises(ValueError):
        live_smallcap.atomic_write_json(target, {"score": float("nan")})
    assert target.read_text(encoding="utf-8").strip().endswith('"old"\n}')
