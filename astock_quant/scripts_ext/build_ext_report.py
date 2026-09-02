"""汇总表：把 ext_summary / ext_verdicts / ext_ablation 拼成一张可读的表。

用法：python3 scripts_ext/build_ext_report.py > reports/platform_audit_table.md
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aq import config  # noqa: E402

V = os.path.join(config.BASE_DIR, "verified")


def g(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def fmt(x, n=2, pct=False):
    if x is None:
        return "—"
    try:
        return f"{x * 100:.{n}f}" if pct else f"{x:.{n}f}"
    except Exception:
        return str(x)


def main():
    summ = json.load(open(os.path.join(V, "ext_summary.json")))
    ver = json.load(open(os.path.join(V, "ext_verdicts.json")))
    rows = summ["策略"]

    print("| 策略 | 家族 | 原文声称年化 | 干净口径年化 | 天梯期年化 | 对等权超额 | "
          "净 alpha | NW t | DSR(全局36试验) | DSR(自身) | 置换分位 | 逐年剔除最低t | "
          "换手x | 成本%/年 | blocked | 裁决 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        v = ver.get(r["key"], {})
        ab, dsr = g(v, "alpha_beta", default={}), g(v, "deflated_sharpe", default={})
        dss = g(v, "deflated_sharpe_self_only", default={})
        rp, jk = g(v, "random_portfolio", default={}), g(v, "year_jackknife", default={})
        alpha = ab.get("ann_alpha")
        t = ab.get("alpha_t")
        ok_alpha = alpha is not None and alpha > 0
        ok_t = t is not None and t >= 2
        ok_dsr = (dsr.get("DSR") or 0) >= 0.90
        ok_perm = (rp.get("percentile_vs_random") or 0) >= 0.95
        ok_blk = r["blocked_frac"] <= 0.05
        if not ok_blk:
            verdict = "作废(blocked>5%)"
        elif not ok_alpha:
            verdict = "作废(alpha≤0)"
        elif not ok_perm:
            verdict = "作废(置换<95%)"
        elif ok_t and ok_dsr:
            verdict = "通过"
        else:
            verdict = "不显著"
        claimed = r["claimed"].split("；")[0].split("（")[0][:56]
        print(f"| {r['title']} | {r['family']} | {claimed} | {r['年化%']}% | "
              f"{r.get('天梯期年化%', '—')}% | {r['对全池等权超额%']}% | "
              f"{fmt(alpha, 2, True)}% | {fmt(t)} | {dsr.get('DSR', '—')} | "
              f"{dss.get('DSR', '未搜参→不适用')} | {rp.get('percentile_vs_random', '—')} | "
              f"{jk.get('最低t', '—')} | {r['年化换手(倍)']} | {r['成本拖累%/年']} | "
              f"{r['blocked_frac']} | **{verdict}** |")

    print("\n### 消融变体（不是原文策略，用于拆解超额来源）\n")
    print("| 变体 | 干净口径年化 | 对等权超额 | 净 alpha | NW t | DSR(全局) | DSR(自身) | 置换分位 | 逐年剔除最低t |")
    print("|---|---|---|---|---|---|---|---|---|")
    for k in ("s02_no_blackout", "s02_wide", "s03_blackout", "s03_wide"):
        v = ver.get(k)
        if not v:
            continue
        ab, dsr = g(v, "alpha_beta", default={}), g(v, "deflated_sharpe", default={})
        dss = g(v, "deflated_sharpe_self_only", default={})
        rp, jk = g(v, "random_portfolio", default={}), g(v, "year_jackknife", default={})
        pf = g(v, "performance", default={})
        print(f"| {k} | {fmt(pf.get('ann_return'), 2, True)}% | — | "
              f"{fmt(ab.get('ann_alpha'), 2, True)}% | {fmt(ab.get('alpha_t'))} | "
              f"{dsr.get('DSR')} | {dss.get('DSR', '—')} | "
              f"{rp.get('percentile_vs_random')} | {jk.get('最低t')} |")

    print("\n### 基准（同一区间 2019-01-02 ~ 2026-09-01）\n")
    print("| 名称 | 年化% | 夏普 | 最大回撤% |")
    print("|---|---|---|---|")
    for b in summ["基准"]:
        print(f"| {b['名称']} | {b['年化收益']} | {b['夏普(rf=0)']} | {b['最大回撤']} |")


if __name__ == "__main__":
    main()
