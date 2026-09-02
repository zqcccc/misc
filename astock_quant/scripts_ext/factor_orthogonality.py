"""新因子与已有 17 个量价因子的正交性诊断（回答「最缺什么正交信息源」）。

做法：把每个因子在每个截面上转成百分位秩，逐日算 Spearman 相关，再对时间取均值；
然后对 17+N 的相关矩阵做特征分解，用「解释 95% 方差需要几个主成分」衡量有效自由度。
用法：python3 scripts_ext/factor_orthogonality.py
产物：verified/ext_orthogonality.json
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import config, factors, panel, universe  # noqa: E402
from strategies_ext import factors_ext as fx  # noqa: E402

VERIFIED = os.path.join(config.BASE_DIR, "verified")
SAMPLE_EVERY = 20          # 每 20 个交易日取一个截面，够稳且省时


def rank_panels(fp: dict, mask: pd.DataFrame) -> dict:
    return {k: v.where(mask).rank(axis=1, pct=True) for k, v in fp.items()}


def mean_corr(rp: dict, dates) -> pd.DataFrame:
    names = list(rp)
    acc = np.zeros((len(names), len(names)))
    cnt = 0
    for d in dates:
        m = np.column_stack([rp[n].loc[d].to_numpy() for n in names])
        ok = np.isfinite(m).all(axis=1)
        if ok.sum() < 200:
            continue
        c = np.corrcoef(m[ok].T)
        if np.isfinite(c).all():
            acc += c
            cnt += 1
    return pd.DataFrame(acc / max(cnt, 1), index=names, columns=names)


def eff_dof(corr: pd.DataFrame) -> dict:
    ev = np.sort(np.linalg.eigvalsh(corr.to_numpy()))[::-1]
    ev = np.clip(ev, 0, None)
    frac = np.cumsum(ev) / ev.sum()
    return {"特征值前5": [round(float(x), 2) for x in ev[:5]],
            "解释80%方差所需主成分数": int(np.searchsorted(frac, 0.80) + 1),
            "解释95%方差所需主成分数": int(np.searchsorted(frac, 0.95) + 1),
            "因子数": int(len(ev))}


def main():
    p = panel.load_panels()
    mask = universe.investable(p)
    old = factors.build_all(p)
    close, open_, high = p["close"], p["open"], p["high"]
    volume, amount = p["volume"], p["amount"]
    new = {
        "新:日内反转22": fx.intraday_reversal(open_, close, 22),
        "新:量加权反转21": fx.volume_weighted_reversal(close, volume, 21),
        "新:alpha001": fx.alpha001(close),
        "新:alpha003": fx.alpha003(open_, volume),
        "新:alpha022": fx.alpha022(high, volume, close),
        "新:量能突增": fx.volume_surge(volume, 20),
        "新:振幅4日": -fx.max_amplitude(high, p["low"], 4),
        "新:MA5/MA10": fx.ma(close, 5) / fx.ma(close, 10) - 1.0,
    }
    allf = {**old, **new}
    dates = close.index[(close.index >= "2019-01-02") & (close.index <= "2026-09-01")][::SAMPLE_EVERY]
    rp = rank_panels(allf, mask)
    corr = mean_corr(rp, dates)

    old_names, new_names = list(old), list(new)
    rows = []
    for n in new_names:
        c = corr.loc[n, old_names].abs()
        rows.append({"新因子": n, "与17因子最大|相关|": round(float(c.max()), 3),
                     "最相关的老因子": c.idxmax(),
                     "与17因子平均|相关|": round(float(c.mean()), 3)})
    out = {
        "截面数": len(dates),
        "老17因子有效自由度": eff_dof(corr.loc[old_names, old_names]),
        "加入新因子后有效自由度": eff_dof(corr),
        "新因子正交度": sorted(rows, key=lambda r: r["与17因子最大|相关|"]),
        "老因子两两|相关|中位数": round(float(
            corr.loc[old_names, old_names].abs().where(
                ~np.eye(len(old_names), dtype=bool)).stack().median()), 3),
    }
    json.dump(out, open(os.path.join(VERIFIED, "ext_orthogonality.json"), "w"),
              ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
