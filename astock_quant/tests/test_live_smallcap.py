"""生产增量信号必须与研究全量口径一致。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aq import backtest, factors, live_smallcap, rules, strategy, universe


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


def test_explicit_end_does_not_require_calendar_request():
    service = _import_live_service()
    assert service.expected_trading_date("2026-11-27") == pd.Timestamp("2026-11-27")


def test_merge_allows_float64_updates_into_float32_cache():
    dates = pd.bdate_range("2026-01-01", periods=3)
    old_close = pd.DataFrame({"a": np.array([1.0, 2.0], dtype=np.float32)}, index=dates[:2])
    old = {"close": old_close, "amount": old_close.copy(), "close_raw": old_close.copy()}
    new_close = pd.DataFrame({"a": np.array([2.2, 3.0], dtype=np.float64)}, index=dates[1:])

    merged = live_smallcap.merge_market_rows(old, new_close, new_close, new_close)

    assert merged["close"].at[dates[0], "a"] == pytest.approx(1.0)
    assert merged["close"].at[dates[1], "a"] == pytest.approx(2.2)
    assert merged["close"].at[dates[2], "a"] == pytest.approx(3.0)
    assert merged["close"].dtypes["a"] == np.float32


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


# ---------------------------------------------------------------- 调仓频率 20 日与一次性迁移


def _run_rebalance_clock(state: dict, ticks: int) -> list[int]:
    """沿 update_deliverable 的用法逐日推进调仓时钟，返回每次触发的计数值。"""
    due_days = []
    for _ in range(ticks):
        days, due = live_smallcap.rebalance_tick(
            state["trading_days_since_rebalance"],
            live_smallcap.state_rebalance_frequency(state),
        )
        state["trading_days_since_rebalance"] = days
        if due:
            due_days.append(days)
            live_smallcap.settle_rebalance_state(state)
    return due_days


def test_legacy_state_migrates_at_existing_next_rebalance_day():
    """旧 10 日状态：既有下一调仓日（计数达 10）触发一次迁移，之后按 20 日。"""
    state = {"trading_days_since_rebalance": 8}
    assert (
        live_smallcap.state_rebalance_frequency(state)
        == live_smallcap.LEGACY_REBALANCE_FREQUENCY
    )

    due_days = _run_rebalance_clock(state, 61)

    assert due_days == [10, 20, 20]
    assert state["rebalance_frequency"] == live_smallcap.REBALANCE_FREQUENCY


def test_new_state_runs_on_twenty_day_clock():
    """新状态直接按 20 日节奏，第一次触发就在第 20 个交易日。"""
    state = {
        "rebalance_frequency": live_smallcap.REBALANCE_FREQUENCY,
        "trading_days_since_rebalance": 0,
    }

    assert _run_rebalance_clock(state, 20) == [20]
    assert state["trading_days_since_rebalance"] == 0


def test_state_frequency_field_is_authoritative():
    assert live_smallcap.state_rebalance_frequency({"rebalance_frequency": 20}) == 20
    assert live_smallcap.state_rebalance_frequency({"rebalance_frequency": "20"}) == 20
    assert live_smallcap.state_rebalance_frequency({}) == live_smallcap.LEGACY_REBALANCE_FREQUENCY
    assert (
        live_smallcap.state_rebalance_frequency({"rebalance_frequency": None})
        == live_smallcap.LEGACY_REBALANCE_FREQUENCY
    )


def _import_live_service():
    """导入生产服务模块；smallcap_service 会安装真实告警钩子，导入后立刻还原。"""
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    saved_hook = sys.excepthook
    try:
        import smallcap_live_service as svc  # noqa: PLC0415
    finally:
        sys.excepthook = saved_hook
    return svc


def test_initial_state_directly_uses_twenty_day_phase():
    """新建状态（种子重建）直接按 20 日相位，并写入 rebalance_frequency 字段。"""
    svc = _import_live_service()

    dates = pd.bdate_range("2026-01-01", periods=40)
    panels = {"close": pd.DataFrame({"a": range(40)}, index=dates, dtype=float)}
    deliverable = {
        "latest_trading_date": "2026-01-30",
        "latest_rebalance_date": "2026-01-20",
        "configs": {},
    }

    state = svc._initial_state(deliverable, panels)

    between = dates[
        (dates > pd.Timestamp("2026-01-20")) & (dates <= pd.Timestamp("2026-01-30"))
    ]
    assert state["trading_days_since_rebalance"] == int(len(between) % 20)
    assert state["rebalance_frequency"] == live_smallcap.REBALANCE_FREQUENCY


# ---------------------------------------------------------------- seed 持仓 == 回测末期信号


def test_signal_holdings_match_backtest_end_holdings():
    """seed 持仓必须直接取最后一期缓冲后信号，与回测引擎末期目标持仓同源。"""
    n_days, n_stocks = 120, 12
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    rets = np.random.default_rng(7).normal(0.001, 0.02, size=(n_days, n_stocks))
    close = pd.DataFrame(
        20.0 * np.exp(np.cumsum(rets, axis=0)),
        index=dates,
        columns=[f"sz30{i:04d}" for i in range(n_stocks)],
    )
    open_ = close.shift(1).fillna(close.iloc[0])
    panels = {
        "open": open_,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        # 合成序列没有公司行动，raw 与复权价一致——这是事实口径，不是退回复权价
        "open_raw": open_,
        "high_raw": close * 1.01,
        "low_raw": close * 0.99,
        "volume": pd.DataFrame(1e6, index=dates, columns=close.columns),
        "amount": pd.DataFrame(1e8, index=dates, columns=close.columns),
        "close_raw": close,
    }
    score = pd.DataFrame(
        np.random.default_rng(11).normal(size=(n_days, n_stocks)),
        index=dates,
        columns=close.columns,
    )
    rb_dates = strategy.rebalance_dates(dates, 10, start=dates[30], end=dates[-5])
    sig = strategy.top_n_signals_buffered(score, rb_dates, top_n=3, buffer_mult=2.0)
    res = backtest.run(
        panels, sig, start=dates[0], end=dates[-1],
        init_cash=10_000_000.0, keep_holdings=True,
    )

    seed_codes = live_smallcap.signal_holdings_at(sig)
    backtest_codes = res.holdings[max(res.holdings)].index.tolist()

    assert len(seed_codes) == 3
    assert sorted(seed_codes) == sorted(backtest_codes)


# ---------------------------------------------------------------- open 持久化


def test_market_cache_round_trip_includes_open(tmp_path):
    dates = pd.bdate_range("2026-01-05", periods=5)
    close = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=dates)
    amount = close * 1e6
    close_raw = close / 2.0
    open_panel = close.shift(1).fillna(1.0)
    open_raw = open_panel / 2.0

    live_smallcap.save_market_cache(tmp_path, close, amount, close_raw, open_panel, open_raw)

    loaded = live_smallcap.load_market_cache(tmp_path)
    assert loaded is not None
    for key in ("close", "amount", "close_raw", "open", "open_raw"):
        assert loaded[key] is not None
    pd.testing.assert_frame_equal(loaded["open"], open_panel.astype(np.float32), check_freq=False)
    generation = json.loads((tmp_path / "current.json").read_text(encoding="utf-8"))["generation"]
    generation_dir = tmp_path / "generations" / generation
    assert sorted(item.name for item in generation_dir.iterdir()) == [
        "amount.parquet",
        "close.parquet",
        "close_raw.parquet",
        "open.parquet",
        "open_raw.parquet",
    ]


def test_market_cache_without_open_reports_missing(tmp_path):
    """旧版缓存没有 open：显式返回 None 让调用方降级，绝不拿 close 冒充。"""
    dates = pd.bdate_range("2026-01-05", periods=3)
    close = pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=dates)
    live_smallcap.save_market_cache(tmp_path, close, close * 1e6, close, close, close)
    generation = json.loads((tmp_path / "current.json").read_text(encoding="utf-8"))["generation"]
    generation_dir = tmp_path / "generations" / generation
    (generation_dir / "open.parquet").unlink()
    (generation_dir / "open_raw.parquet").unlink()

    loaded = live_smallcap.load_market_cache(tmp_path)

    assert loaded is not None
    assert loaded["open"] is None
    assert loaded["open_raw"] is None


def test_merge_overlays_open_rows_and_keeps_missing_open_nan():
    dates = pd.bdate_range("2026-01-01", periods=3)
    old = {
        "close": pd.DataFrame({"a": [1.0, 2.0]}, index=dates[:2]),
        "amount": pd.DataFrame({"a": [10.0, 20.0]}, index=dates[:2]),
        "close_raw": pd.DataFrame({"a": [1.0, 2.0]}, index=dates[:2]),
    }
    new_rows = pd.DataFrame({"a": [2.2, 3.0]}, index=dates[1:])
    new_open = pd.DataFrame({"a": [2.0, 2.8]}, index=dates[1:])

    merged = live_smallcap.merge_market_rows(
        old, new_rows, new_rows, new_rows, new_open, new_open
    )

    assert merged["open"].at[dates[1], "a"] == pytest.approx(2.0)
    # 旧日期没有 open：保持 NaN，不伪造
    assert pd.isna(merged["open"].at[dates[0], "a"])


# ---------------------------------------------------------------- 本期收益：降级标记与剔除


def test_current_period_marks_degraded_without_open_panel():
    close, close_raw, _ = _period_panels()

    summary = live_smallcap.current_period_summary(
        close, list(close.columns), close.index[0], close.index[-1], close_raw=close_raw,
    )

    assert summary["entry_basis"] == live_smallcap.ENTRY_BASIS_SIGNAL_CLOSE
    assert summary["entry_basis_degraded"] is True


def test_current_period_open_basis_not_degraded():
    close, close_raw, open_panel = _period_panels()

    summary = live_smallcap.current_period_summary(
        close, list(close.columns), close.index[0], close.index[-1],
        close_raw=close_raw, open_panel=open_panel,
    )

    assert summary["entry_basis"] == live_smallcap.ENTRY_BASIS_T1_OPEN
    assert summary["entry_basis_degraded"] is False


def test_current_period_excludes_codes_crossing_unconfirmed_event():
    """建仓到最新收盘之间跨未确认公司行动的标的：剔除并写明原因，不冒充。"""
    close, close_raw, open_panel = _period_panels()

    summary = live_smallcap.current_period_summary(
        close, list(close.columns), close.index[0], close.index[-1],
        close_raw=close_raw, open_panel=open_panel,
        unresolved_events={"sz300002": pd.DatetimeIndex([close.index[2]])},
    )

    assert summary["codes_excluded"] == {"sz300002": "corporate_action_unconfirmed"}
    assert "sz300002" not in summary["returns_by_code"]
    # 组合收益只由剩余一只构成：13 / 10.5 - 1 = +23.81%
    assert summary["return_pct"] == pytest.approx((13.0 / 10.5 - 1.0) * 100.0, abs=0.01)


def test_current_period_pending_has_no_degraded_marker():
    close, close_raw, _ = _period_panels()

    summary = live_smallcap.current_period_summary(
        close, list(close.columns), close.index[-1], close.index[-1], close_raw=close_raw,
    )

    assert summary["status"] == live_smallcap.PERIOD_STATUS_PENDING
    assert summary["entry_basis_degraded"] is None


# ---------------------------------------------------------------- 复权无效窗口进打分


def test_factor_valid_mask_excludes_code_from_cross_section(random_panels):
    scores, _, _ = live_smallcap.production_score_breakdown(random_panels)
    latest = scores.index[-1]
    valid_scores = scores.loc[latest].dropna()
    assert not valid_scores.empty
    code = valid_scores.index[0]
    valid = pd.DataFrame(True, index=scores.index, columns=scores.columns)
    valid.loc[latest, code] = False

    masked, _, _ = live_smallcap.production_score_breakdown(random_panels, factor_valid=valid)

    assert pd.isna(masked.at[latest, code])
    assert pd.notna(scores.at[latest, code])
    # 只影响被标记的当日截面，前一天不变（equals 把两侧 NaN 视为相等）
    assert masked.iloc[-2].equals(scores.iloc[-2])


def test_tradability_fails_closed_without_raw_price_panels():
    """缺不复权价面板必须 fail-closed（B0005）：fixtures 给全，但校验本身不能被绕过。"""
    dates = pd.bdate_range("2026-01-05", periods=3)
    panels = {
        "open": pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=dates),
        "high": pd.DataFrame({"a": [1.1, 2.1, 3.1]}, index=dates),
        "low": pd.DataFrame({"a": [0.9, 1.9, 2.9]}, index=dates),
        "close": pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=dates),
        "volume": pd.DataFrame({"a": [1e6] * 3}, index=dates),
        "close_raw": pd.DataFrame({"a": [1.0, 2.0, 3.0]}, index=dates),
        # 故意缺 open_raw / high_raw / low_raw
    }

    with pytest.raises(KeyError, match="不复权价面板"):
        rules.tradability(panels, price="open")


# ---------------------------------------------------------------- 增量抓取根数（bars 上限估计）


def _cached_up_to(last_date: str) -> dict:
    index = pd.DatetimeIndex([pd.Timestamp("2026-01-05"), pd.Timestamp(last_date)])
    close = pd.DataFrame({"a": [1.0, 2.0]}, index=index)
    return {"close": close, "amount": close.copy(), "close_raw": close.copy()}


def test_fetch_bars_needed_bootstraps_full_window():
    assert live_smallcap.fetch_bars_needed(None, "2026-11-27") == live_smallcap.ROLLING_DAYS


def test_fetch_bars_needed_covers_long_gap():
    """9-02→11-27 长停更：按工作日跨度放大根数（62 个工作日），不能只抓 8 根留洞。"""
    bars = live_smallcap.fetch_bars_needed(_cached_up_to("2026-09-02"), "2026-11-27")

    assert bars == 62
    assert bars < live_smallcap.ROLLING_DAYS


def test_fetch_bars_needed_caps_at_rolling_window():
    bars = live_smallcap.fetch_bars_needed(_cached_up_to("2024-01-02"), "2026-11-27")

    assert bars == live_smallcap.ROLLING_DAYS


def test_fetch_bars_needed_keeps_monday_and_weekday_minimums():
    monday = live_smallcap.fetch_bars_needed(_cached_up_to("2026-11-20"), "2026-11-23")
    weekday = live_smallcap.fetch_bars_needed(_cached_up_to("2026-11-24"), "2026-11-25")
    same_day = live_smallcap.fetch_bars_needed(_cached_up_to("2026-11-25"), "2026-11-25")

    assert monday == 20
    assert weekday == 8
    assert same_day == 8


# ---------------------------------------------------------------- 交易日历缺口校验


def test_missing_trading_days_flags_gap_inside_window():
    calendar = pd.bdate_range("2026-11-23", "2026-11-27")
    merged = calendar.delete(calendar.get_loc(pd.Timestamp("2026-11-25")))

    missing = live_smallcap.missing_trading_days(merged, calendar, "2026-11-20", "2026-11-27")

    assert missing == [pd.Timestamp("2026-11-25")]


def test_missing_trading_days_ignores_days_before_cache_end():
    """缓存末端当天的历史日期不在校验范围内，只查 (缓存末端, 目标日]。"""
    calendar = pd.bdate_range("2026-11-20", "2026-11-27")
    merged = calendar.delete(calendar.get_loc(pd.Timestamp("2026-11-20")))

    missing = live_smallcap.missing_trading_days(merged, calendar, "2026-11-20", "2026-11-27")

    assert missing == []


def test_assert_trading_calendar_complete_rejects_gap():
    calendar = pd.bdate_range("2026-11-23", "2026-11-27")
    merged = calendar.delete(calendar.get_loc(pd.Timestamp("2026-11-24")))

    with pytest.raises(ValueError, match="行情缺口"):
        live_smallcap.assert_trading_calendar_complete(
            merged, calendar, "2026-11-20", "2026-11-27"
        )


def test_assert_trading_calendar_complete_accepts_full_window():
    calendar = pd.bdate_range("2026-11-23", "2026-11-27")

    live_smallcap.assert_trading_calendar_complete(
        calendar, calendar, "2026-11-20", "2026-11-27"
    )


# ---------------------------------------------------------------- staging 目录按 bars 隔离


def test_fetch_market_rows_staging_path_includes_bars(tmp_path):
    """断点目录必须带 bars，避免长停更重抓时复用当天早先的 8 根残缺文件。"""
    svc = _import_live_service()
    expected = pd.Timestamp("2026-11-27")

    result = svc.fetch_market_rows(
        codes=[], expected=expected, cache_dir=tmp_path, bars=62, workers=1
    )

    assert result["stage_dir"] == tmp_path / "staging" / "2026-11-27-62"
    assert result["stage_dir"].is_dir()
    assert result["close"].empty
