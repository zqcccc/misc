"""strategies_ext/ 里平台策略的未来函数机器验证。

与 tests/test_no_lookahead.py 同一套手段，覆盖到新增的因子与打分函数：
  1. 截断不变性：数据在 D 日截断后重算，D 日及之前的打分必须逐点相同；
  2. 未来扰动不变性：把 D 日之后的数据换成随机数，历史打分必须不变
     （抓「全样本标准化」这类隐蔽泄漏）；
  3. 整条净值曲线的截断不变性（比打分更强，把信号构造与引擎也一起管住）；
  4. 源码级 AST 静态检查：不允许负向 shift 与 bfill。
"""
import ast
import importlib
import inspect

import numpy as np
import pandas as pd
import pytest

from aq import backtest, strategy, universe
from strategies_ext import common, factors_ext

MODULES = [
    "s01_guorn_smallcap_m1", "s02_jq_gjt_smallcap", "s03_jq_micro_smallest",
    "s04_haitong_rev22", "s05_haitong_rev22_intraday", "s06_cj_volweighted_rev",
    "s07_rev5_highvolume", "s08_lowvol_anomaly", "s08b_lowvol_raw",
    "s09_volsurge_lowamp", "s10_alpha001", "s11_alpha003", "s12_alpha022",
    "s13_cross_stock_reversal", "s14_dual_ma",
]


def _same(a: pd.DataFrame, b: pd.DataFrame, label: str):
    a, b = a.align(b, join="inner")
    assert a.shape[0] > 0, f"{label}: 对齐后无数据"
    both_nan = a.isna() & b.isna()
    close = np.isclose(a.values.astype(float), b.values.astype(float),
                       rtol=1e-9, atol=1e-11, equal_nan=False)
    bad = ~(close | both_nan.values)
    assert not bad.any(), f"{label}: {bad.sum()} 个取值在截断/扰动后变化 —— 存在未来函数"


def _truncate(panels, cut):
    return {k: v.loc[:cut].copy() for k, v in panels.items()}


def _perturb_future(panels, cut, rng):
    out = {}
    for k, v in panels.items():
        v = v.copy()
        future = v.index > cut
        v.loc[future] = v.loc[future].values * rng.uniform(0.2, 5.0, size=(future.sum(), v.shape[1]))
        out[k] = v
    return out


def _mask(panels):
    return universe.investable(panels, min_listed=60, min_amount=0.0,
                               liquidity_top_pct=1.0, exclude_st=False)


def _score(mod, panels, rb_dates=None):
    mask = _mask(panels)
    if hasattr(mod, "mask_filter"):
        mask = mod.mask_filter(panels, mask)
    if "rb_dates" in inspect.signature(mod.score).parameters:
        rb = panels["close"].index[::20] if rb_dates is None else rb_dates
        return mod.score(panels, mask, rb_dates=rb)
    return mod.score(panels, mask)


@pytest.mark.parametrize("name", MODULES)
def test_ext_score_truncation_invariant(name, random_panels):
    mod = importlib.import_module(f"strategies_ext.{name}")
    cut = random_panels["close"].index[300]
    full = _score(mod, random_panels)
    trunc = _score(mod, _truncate(random_panels, cut))
    _same(full.loc[:cut], trunc.loc[:cut], f"{name} 打分")


@pytest.mark.parametrize("name", MODULES)
def test_ext_score_future_perturbation_invariant(name, random_panels, rng):
    mod = importlib.import_module(f"strategies_ext.{name}")
    cut = random_panels["close"].index[300]
    full = _score(mod, random_panels)
    pert = _score(mod, _perturb_future(random_panels, cut, rng))
    _same(full.loc[:cut], pert.loc[:cut], f"{name} 打分(未来扰动)")


def _pipeline(mod, panels, cut_len=None):
    """挂上平台策略的 score，跑完整条净值曲线。"""
    meta = mod.META
    mask = _mask(panels)
    if hasattr(mod, "mask_filter"):
        mask = mod.mask_filter(panels, mask)
    dates = panels["close"].index
    start = dates[130]
    rb = strategy.rebalance_dates(dates, max(meta["freq"], 5), start=start)
    sc = _score(mod, panels, rb_dates=rb)
    if hasattr(mod, "build_signals"):
        sig = mod.build_signals(panels, mask, sc, dates[dates >= start])
    else:
        sig = common.top_n(sc, rb, min(meta["top_n"] or 10, 10), meta["buffer_mult"])
    sig = common.apply_blackout(sig, meta["blackout"], dates)
    return backtest.run(panels, sig, start=start)


@pytest.mark.parametrize("name", MODULES)
def test_ext_backtest_truncation_invariant(name, random_panels):
    """整条净值曲线的截断不变性 —— 比打分不变性强，把信号构造与引擎一起管住。

    比较到「截断日的前一天」为止：截断日当天有一个**引擎固有的边界效应**，
    不是未来函数。引擎用「最后一根有效 K 线之后即视为退市并按最后价清算」
    来识别退市，而数据截断日当天正在停牌的持仓，在截断视角下看起来就是
    「此后再无 K 线」= 退市，于是被清算；全量数据里它后面还有 K 线，不会被清算。
    这只影响截断日那一根，实盘不会发生（实盘的「今天」之后本来就没有数据，
    引擎也不会在今天就判定退市 —— 判定发生在下一根 K 线缺失时）。
    实测差异确实只出现在截断日当天，且当天持仓里确有停牌股。
    """
    mod = importlib.import_module(f"strategies_ext.{name}")
    dates = random_panels["close"].index
    cut, safe = dates[330], dates[329]
    full = _pipeline(mod, random_panels)
    trunc = _pipeline(mod, _truncate(random_panels, cut))
    a, b = full.equity.loc[:safe], trunc.equity.loc[:safe]
    assert len(b) > 50
    pd.testing.assert_series_equal(a.loc[b.index], b, check_exact=False, rtol=1e-10)


def test_ext_no_negative_shift_in_source():
    mods = [factors_ext, common] + [importlib.import_module(f"strategies_ext.{m}") for m in MODULES]
    for mod in mods:
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr = node.func.attr
            assert attr not in ("bfill", "backfill"), f"{mod.__name__} 用了 {attr}()"
            if attr == "shift":
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    neg = (isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub)) or \
                          (isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float))
                           and arg.value < 0)
                    assert not neg, f"{mod.__name__} 里出现了负向 shift（未来函数）"


def test_oracle_score_is_caught(random_panels):
    """反向验证：造一个偷看次日收益的打分，上面的截断检验必须报警。"""
    close = random_panels["close"]
    cut = close.index[300]
    cheat = close.shift(-1) / close - 1.0
    cheat_trunc = close.loc[:cut].shift(-1) / close.loc[:cut] - 1.0
    with pytest.raises(AssertionError):
        _same(cheat.loc[:cut], cheat_trunc.loc[:cut], "作弊打分")
