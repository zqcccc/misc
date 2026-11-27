"""复权重建：事件解不出时必须显式标无效排除，绝不悄悄退回 raw 收益。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aq import adjust


def _affine_pair(n_pre: int = 60, n_post: int = 40, seed: int = 3, noise: float = 0.0):
    """构造 10送10（raw 除权减半、hfq 仿射斜率翻倍）的 (hfq, raw, 事件日)。

    noise > 0 时给除权后段注入报价噪声，仿射残差超限 → 事件解不出。
    """
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=n_pre + n_post)
    raw_pre = 10.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n_pre)))
    raw_post = 5.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n_post)))
    raw = pd.Series(np.concatenate([raw_pre, raw_post]), index=idx)
    hfq = pd.Series(
        np.concatenate([raw_pre, 2.0 * raw_post + rng.normal(0.0, noise, n_post)]),
        index=idx,
    )
    return hfq, raw, idx[n_pre]


def test_resolved_event_recovers_split_ratio():
    hfq, raw, event_day = _affine_pair()

    resolved, unresolved = adjust.classify_events(hfq, raw)

    assert unresolved == []
    assert set(resolved) == {event_day}
    shares, cash = resolved[event_day]
    assert shares == pytest.approx(2.0, abs=1e-9)
    assert abs(cash) < 1e-9


def test_adjusted_levels_reconstructs_total_return_across_event():
    hfq, raw, event_day = _affine_pair()
    level, unresolved = adjust.adjusted_levels(hfq, raw)

    assert unresolved == []
    prev = level.index[level.index.get_loc(event_day) - 1]
    shares, cash = 2.0, 0.0
    expected = (shares * raw.loc[event_day] + cash) / raw.loc[prev] - 1.0
    # 事件日总收益按 (s·raw + C)/raw_prev − 1 还原，而不是 raw 价格的 −50%
    assert level.pct_change().loc[event_day] == pytest.approx(expected, abs=1e-9)


def test_recent_event_with_short_tail_is_unresolved():
    """除权发生在序列末尾、后段窗口不足（< FIT_MIN）：事件解不出，必须显式上报。"""
    hfq, raw, _ = _affine_pair()
    idx_short = pd.bdate_range("2024-01-02", periods=63)
    raw_short = pd.Series(
        np.concatenate([raw.iloc[:60].to_numpy(), raw.iloc[60:63].to_numpy()]),
        index=idx_short,
    )
    hfq_short = pd.Series(
        np.concatenate([hfq.iloc[:60].to_numpy(), 2.0 * raw_short.iloc[60:].to_numpy()]),
        index=idx_short,
    )

    level, unresolved = adjust.adjusted_levels(hfq_short, raw_short)

    assert unresolved == [idx_short[60]]

    adj = adjust.build_scoring_panels(None, raw_short.to_frame("a"), close_hfq=hfq_short.to_frame("a"))
    assert adj.source == "affine_reconstruct"
    assert adj.unresolved_events["a"][0] == idx_short[60]
    pos = adj.factor_valid.index.get_loc(idx_short[60])
    assert not bool(adj.factor_valid.iloc[pos, 0])


def test_unconfirmed_event_masks_factor_window_only():
    """解不出的公司行动：事件日起 invalid_bars 根 K 线内因子无效，窗口外恢复。"""
    hfq, raw, _ = _affine_pair(noise=0.004)
    open_raw = (raw * 1.01).to_frame("a")

    adj = adjust.build_scoring_panels(
        None, raw.to_frame("a"), close_hfq=hfq.to_frame("a"),
        open_raw=open_raw, invalid_bars=20,
    )

    assert adj.source == "affine_reconstruct"
    assert len(adj.unresolved_events["a"]) >= 1
    flags = adj.factor_valid["a"].to_numpy()
    bad_positions = [i for i, ok in enumerate(flags) if not ok]
    first, last = bad_positions[0], bad_positions[-1]
    # 每个未确认事件从当日起连续失效；最后一个窗口结束后全部恢复
    assert bad_positions == list(range(first, last + 1))
    assert bool(flags[first - 1])
    assert flags[last + 1:].all()
    assert len(bad_positions) <= 20 * len(adj.unresolved_events["a"])
    # open 与 close 共用同一复权因子，口径一致
    assert np.allclose(adj.open["a"], open_raw["a"] * (adj.close["a"] / raw), equal_nan=True)


def test_adjusted_open_scales_by_adjustment_factor_and_guards_zero():
    idx = pd.bdate_range("2024-01-02", periods=4)
    close_adj = pd.DataFrame({"a": [10.0, 11.0, 12.0, 13.0]}, index=idx)
    close_raw = pd.DataFrame({"a": [5.0, 5.5, 6.0, 6.5]}, index=idx)
    open_raw = pd.DataFrame({"a": [5.1, 5.6, 6.1, 6.6]}, index=idx)

    open_adj = adjust.adjusted_open(open_raw, close_raw, close_adj)

    assert np.allclose(open_adj["a"], open_raw["a"] * (close_adj["a"] / close_raw["a"]))
    # 不复权收盘为 0：因子不可信，开盘价置 NaN，不冒充可用
    zero_raw = close_raw.copy()
    zero_raw.iloc[2] = 0.0
    guarded = adjust.adjusted_open(open_raw, zero_raw, close_adj)
    assert pd.isna(guarded.iloc[2, 0])
    assert guarded.iloc[0, 0] == pytest.approx(open_raw.iloc[0, 0] * 2.0)


def test_verified_path_passes_through_and_scales_open():
    idx = pd.bdate_range("2024-01-02", periods=10)
    close_verified = pd.DataFrame({"a": np.linspace(10.0, 11.0, 10)}, index=idx)
    close_raw = pd.DataFrame({"a": np.linspace(5.0, 5.5, 10)}, index=idx)
    open_raw = pd.DataFrame({"a": np.linspace(5.1, 5.6, 10)}, index=idx)

    adj = adjust.build_scoring_panels(close_verified, close_raw, open_raw=open_raw)

    assert adj.source == "verified_rebuild"
    assert adj.unresolved_events == {}
    assert bool(adj.factor_valid.all().all())
    assert np.allclose(adj.close["a"], close_verified["a"])
    assert np.allclose(adj.open["a"], open_raw["a"] * (close_verified["a"] / close_raw["a"]))


def test_affine_path_without_open_data_returns_empty_open():
    """没有 open_raw 时 open 面板为空，让调用方显式降级，不伪造开盘价。"""
    hfq, raw, _ = _affine_pair()

    adj = adjust.build_scoring_panels(None, raw.to_frame("a"), close_hfq=hfq.to_frame("a"))

    assert adj.open.empty


def test_build_scoring_panels_requires_input():
    with pytest.raises(ValueError, match="close_verified"):
        adjust.build_scoring_panels(None, pd.DataFrame())
