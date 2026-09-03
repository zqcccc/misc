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


def test_tencent_snapshot_uses_change_percent_not_open_price():
    parts = [""] * 50
    parts[1] = "示例股份"
    parts[2] = "600001"
    parts[3] = "10.20"
    parts[4] = "10.00"
    parts[5] = "9.88"
    parts[30] = "20260903150123"
    parts[32] = "2.00"
    parts[44] = "12.34"
    parts[45] = "23.45"

    quote = live_smallcap.parse_tencent_snapshot_parts(parts)

    assert quote["open"] == pytest.approx(9.88)
    assert quote["change_pct"] == pytest.approx(2.0)
    assert quote["change_pct"] != quote["open"]


def test_factor_breakdown_contributions_sum_to_total(random_panels):
    scores, raw, ranked = live_smallcap.production_score_breakdown(random_panels)
    latest = scores.index[-1]
    code = scores.loc[latest].dropna().index[0]
    breakdown = live_smallcap.factor_breakdown_at(raw, ranked, latest, code)

    assert sum(item["contribution"] for item in breakdown["items"]) == pytest.approx(
        scores.at[latest, code], abs=2e-6
    )
    assert breakdown["total_score"] == pytest.approx(scores.at[latest, code], abs=1e-6)


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


def _period_panels() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2026-01-05", periods=4)
    codes = ["sh600001", "sz300002"]
    close = pd.DataFrame(
        [[10.0, 20.0], [11.0, 21.0], [12.0, 22.0], [13.0, 23.0]],
        index=dates,
        columns=codes,
    )
    open_panel = pd.DataFrame(
        [[9.5, 19.5], [10.5, 20.5], [11.5, 21.5], [12.5, 22.5]],
        index=dates,
        columns=codes,
    )
    return close, close.copy(), open_panel


def test_current_period_pending_before_execution_day():
    close, close_raw, open_panel = _period_panels()
    signal_date = close.index[-1]

    summary = live_smallcap.current_period_summary(
        close,
        list(close.columns),
        signal_date,
        close.index[-1],
        close_raw=close_raw,
        open_panel=open_panel,
    )

    assert summary["status"] == live_smallcap.PERIOD_STATUS_PENDING
    assert summary["execution_date"] is None
    assert summary["return_pct"] is None
    assert summary["trading_days_elapsed"] == 0
    assert summary["trading_days_remaining"] == live_smallcap.REBALANCE_FREQUENCY


def test_current_period_uses_next_day_open_as_entry_price():
    close, close_raw, open_panel = _period_panels()
    signal_date = close.index[0]

    summary = live_smallcap.current_period_summary(
        close,
        list(close.columns),
        signal_date,
        close.index[-1],
        close_raw=close_raw,
        open_panel=open_panel,
    )

    assert summary["status"] == live_smallcap.PERIOD_STATUS_RUNNING
    assert summary["execution_date"] == str(close.index[1].date())
    assert summary["entry_basis"] == live_smallcap.ENTRY_BASIS_T1_OPEN
    assert summary["trading_days_elapsed"] == 3
    # 13 / 10.5 - 1 = +23.81%，23 / 20.5 - 1 = +12.20%
    assert summary["returns_by_code"]["sh600001"]["return_pct"] == pytest.approx(23.81)
    assert summary["returns_by_code"]["sh600001"]["entry_price"] == pytest.approx(10.5)
    assert summary["return_pct"] == pytest.approx((23.81 + 12.2) / 2, abs=0.01)


def test_current_period_falls_back_to_signal_close_without_open_panel():
    close, close_raw, _ = _period_panels()
    signal_date = close.index[0]

    summary = live_smallcap.current_period_summary(
        close,
        list(close.columns),
        signal_date,
        close.index[-1],
        close_raw=close_raw,
    )

    assert summary["entry_basis"] == live_smallcap.ENTRY_BASIS_SIGNAL_CLOSE
    # 回退口径以信号日收盘 10.0 为基准：13 / 10 - 1 = +30%
    assert summary["returns_by_code"]["sh600001"]["return_pct"] == pytest.approx(30.0)


def test_current_period_survives_signal_date_outside_rolling_cache():
    """滚动缓存截断后信号日可能不在面板里，守护进程不能因此崩掉。"""
    close, close_raw, _ = _period_panels()

    summary = live_smallcap.current_period_summary(
        close,
        list(close.columns),
        close.index[0] - pd.Timedelta(days=30),
        close.index[-1],
        close_raw=close_raw,
    )

    assert summary["status"] == live_smallcap.PERIOD_STATUS_RUNNING
    assert summary["entry_date"] == str(close.index[0].date())
    assert summary["returns_by_code"]["sh600001"]["return_pct"] == pytest.approx(30.0)
