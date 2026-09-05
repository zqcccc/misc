#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B0005 修复：重建乘法复权（总收益）日线，取代腾讯的加法复权 hfq。

为什么需要：腾讯 fqkline 返回的是 `hfq = k·raw + c`（加法复权）。加法项进了收益率的
分母，于是 `r_hfq = r_raw × (k·raw/hfq)` —— 日收益被一个每天都在变、小于 1 的系数
系统性压缩（工行年化波动 0.1193，真实值 0.1837）。详见 quant_research/blockers/B0005-*。

怎么修（不需要外部公司行动表，两个本地源互为校验）：
  1. **定位事件**：baostock 的 pctChg 是交易所口径（分母是除权参考价）。凡是它与不复权
     日收益分歧超过阈值的那一天，就是除权除息日。这一步决定召回率。
  2. **定量**：hfq 与 raw 的仿射关系 `hfq = k·raw + c` 中，k、c 只在事件日跳变。
     事件前后各拟合一段，得到股数倍数 m = k_before/k_after 与每股现金 D = Δc/k_after。
     这一步决定精度（实测与交易所折算红利差 0.003~0.005 元，即报价量化极限）。
  3. **重建**：total_return = (raw·m + D)/raw_prev − 1，累乘成复权价，
     并输出逐日乘法因子供 OHLC 一致缩放。
  4. **逐只对账**：重建序列必须与 pctChg 逐日相等，否则这只股票被隔离并写明原因。
     宁可隔离，不要放一只没对上账的进面板。

已知不覆盖：配股（需要建模缴款）、没有 baostock 对照的标的。两者都会被隔离。
产出的是**交易所折算口径**的总收益，不是税后实际到账现金。

用法：
    ../.venv/bin/python scripts/rebuild_adjusted.py            # 全量
    ../.venv/bin/python scripts/rebuild_adjusted.py --limit 200  # 抽样试跑
"""
import argparse
import glob
import json
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HFQ = os.path.join(ROOT, "data", "kline_hfq")
RAW = os.path.join(ROOT, "data", "kline_raw")
BSD = os.path.join(ROOT, "data_bs", "daily")
OUT_DIR = os.path.join(ROOT, "data", "kline_adj")
ACTIONS = os.path.join(ROOT, "data", "corporate_actions.csv")
REPORT = os.path.join(ROOT, "data", "rebuild_report.json")

EVENT_TOL = 3e-4      # r_raw 与交易所 pctChg 的分歧阈值：超过即判为除权日
FIT_WIN = 20          # 事件前后各取多少个交易日拟合仿射关系
FIT_MIN = 6           # 拟合最少需要几个点
FIT_MIN_TAIL = 3      # 序列末尾的事件允许更短的后段（仿射只有两个未知数）
RESID_TOL = 0.004     # 仿射拟合残差容差（约 4 倍报价跳动的一半）
RECON_TOL = 1e-5      # 对账容差：重建收益与 pctChg 的逐日偏差
RECON_MAX_BAD = 0.002 # 允许对不上的天数占比上限
EVENT_TOL_TR = 2e-3   # 事件日总收益的对账残差上限（s 取错会到百分数量级）


def bs_path(code):
    return os.path.join(BSD, f"{code[:2]}_{code[2:]}.csv")


def load(code):
    ph, pr = os.path.join(HFQ, f"{code}.csv"), os.path.join(RAW, f"{code}.csv")
    if not (os.path.exists(ph) and os.path.exists(pr)):
        return None
    h = pd.read_csv(ph).set_index("date").sort_index()
    r = pd.read_csv(pr).set_index("date").sort_index()
    if "close" not in h or "close" not in r:
        return None
    df = pd.DataFrame({"h": h["close"], "r": r["close"]}).dropna()
    for c in ("open", "high", "low"):
        if c in r:
            df[c] = r[c]
    b = None
    if os.path.exists(bs_path(code)):
        bs = pd.read_csv(bs_path(code))
        bs["date"] = bs["date"].astype(str)
        b = pd.to_numeric(bs.set_index("date").sort_index()["pctChg"], errors="coerce") / 100.0
    return df, b


def affine_at(df, i, win=FIT_WIN):
    """在下标 i 处求事件前后两段的 (k, c)。返回 (m, D) 或 None。

    序列末尾的事件后面没有 FIT_MIN 天，但仿射只有两个未知数，3 个点就能定且留一点余量；
    定出来的金额还要过「与交易所口径互比」那道独立校验，所以放宽尾段是安全的。
    """
    lo, hi = max(0, i - win), min(len(df), i + win)
    before, after = df.iloc[lo:i], df.iloc[i:hi]
    tail_min = FIT_MIN if hi < len(df) else FIT_MIN_TAIL
    if len(before) < FIT_MIN or len(after) < tail_min:
        return None
    out = []
    for seg in (before, after):
        k, c = np.polyfit(seg.r.to_numpy(), seg.h.to_numpy(), 1)
        if np.max(np.abs(k * seg.r.to_numpy() + c - seg.h.to_numpy())) > RESID_TOL:
            return None
        out.append((float(k), float(c)))
    (k0, c0), (k1, c1) = out
    if abs(k1) < 1e-12:
        return None
    return k0 / k1, (c1 - c0) / k1


def detect(df, b):
    """事件日只由交易所口径定位；没有 bs 对照时才退回仿射分段。

    腾讯与 baostock 偶有单日收盘价分歧（如 2016-01-04 熔断日），表现为当天分歧 −x、
    次日 +x 的等量反向对。这种是数据分歧不是除权，必须剔掉，否则会被当成一次假分红。
    """
    if b is None:
        H, R = df.h.to_numpy(), df.r.to_numpy()
        days, i = [], 0
        while i < len(df):
            end = min(i + FIT_WIN, len(df))
            if end - i < FIT_MIN:
                break
            k, c = np.polyfit(R[i:end], H[i:end], 1)
            t = end
            while t < len(df) and abs(k * R[t] + c - H[t]) <= RESID_TOL:
                t += 1
            if t < len(df):
                days.append(df.index[t])
            i = t
        return days, []

    rr = df.r.pct_change()
    z = pd.concat([rr.rename("r"), b.rename("b")], axis=1).dropna()
    dv = z.r - z.b
    cand = list(z.index[dv.abs() > EVENT_TOL])
    idx = list(z.index)
    pos = {d: i for i, d in enumerate(idx)}
    events, glitches = [], set()
    for d in cand:
        i = pos[d]
        # 某一天的收盘价两边对不上，会让【当天】和【次日】的日收益一起偏，且等量反向。
        # 所以这一对的两天都不是除权日，两天都要剔掉——只看单侧会漏掉反向的那一半。
        nxt = dv.iloc[i + 1] if i + 1 < len(idx) else 0.0
        prv = dv.iloc[i - 1] if i - 1 >= 0 else 0.0
        cur = dv.iloc[i]
        if abs(nxt + cur) < 0.2 * abs(cur) or abs(prv + cur) < 0.2 * abs(cur):
            glitches.add(d)
            if i + 1 < len(idx) and abs(nxt + cur) < 0.2 * abs(cur):
                glitches.add(idx[i + 1])
        else:
            events.append(d)
    glitches = sorted(glitches)
    return [e for e in events if e not in set(glitches)], glitches


# A 股送转比例是「每 10 股送/转 N 股」，N 可以带半股（10转4.5 常见），所以网格取 0.05
RATIO_GRID = [1.0 + n / 20.0 for n in range(0, 61)]


def solve_event(prev, cur, pct, affine):
    """解一次公司行动的 (股数倍数 s, 每股现金 C)。

    **股数倍数只能来自仿射。** 交易所关系式 ref = (前收 − C)/s 里 s 与 C 是同一条直线上
    的两个未知数：任何 (s, C) 组合都同样满足它，拿它去「检验」s 是恒等式。实测残差对
    s=1.0/1.5/2.0/2.1/3.0 一律是 1e-17，选出来的值由浮点噪音决定 —— 格力 2015-07-03
    因此被选成 s=2.10，而真值是 10转10 派30元 的 s=2.00、每股 2.99 元。

    正确做法：s 取仿射解并吸附到合法送转网格；C 取交易所关系式（给定 s 后精确）；
    再拿仿射自己算出的金额做**独立交叉校验** —— 这一步才是真的检查。
    仿射的每股现金按事件后的股数计，换算成事件前股数要乘 s。
    """
    if affine is None:
        return None, "仿射解不出（事件前后样本不足或残差过大）"
    m, d_new = affine
    if abs(m) < 1e-12:
        return None, "仿射斜率为零"
    s_raw = 1.0 / m
    ref = cur / (1 + pct)
    if ref <= 0:
        return None, "除权参考价非正"

    # 独立校验必须用【未吸附】的 s_raw：仿射的两段拟合同时给出 k 的跳变（→s）和 c 的
    # 跳变（→每新股现金），把它们各自代进交易所关系式应当一致。用吸附后的 s 做这个
    # 比较是错的 —— ∂C/∂s = −参考价（量级 10~25），吸附那 1~2% 的误差会被放大成
    # 0.1~0.3 元，看起来像「两种口径对不上」，实际只是吸附误差。
    if abs((prev - s_raw * ref) - s_raw * d_new) > max(0.03, 0.05 * abs(prev - s_raw * ref)):
        return None, (f"仿射与交易所口径不自洽：{round(prev - s_raw * ref, 4)} "
                      f"vs {round(s_raw * d_new, 4)}")

    s = min(RATIO_GRID, key=lambda g: abs(g - s_raw))
    if abs(s - s_raw) > 0.02 * max(1.0, s_raw):
        return None, f"股数倍数 {round(s_raw, 4)} 不在合法送转网格上（疑似缩股/复杂事件）"
    C_exch = prev - s * ref
    # 配股：股东要掏钱，现金流为负。模型表达得了，但「参没参与」是投资者的选择，
    # 总收益取决于这个选择，不能替它决定 —— 单独标注并隔离，不混进普通分红。
    if C_exch < -0.02:
        return None, f"疑似配股（解出负现金流 {round(C_exch, 4)}，股数倍数 {s}）"
    return (s, max(C_exch, 0.0)), ""


def exchange_cash(df, b, day, s):
    """交易所关系式解每股现金（按事件前的股数计）：

        除权参考价 ref = (前收 − C) / s，而 ref 又等于 当日收 / (1 + pctChg)
        ⇒ C = 前收 − s · ref

    校验：格力 2015-07-03（10转10派30元）前收 58.49、ref 27.75、s=2
          ⇒ C = 58.49 − 55.5 = 2.99 ≈ 3.00 元/股。
    """
    i = list(df.index).index(day)
    if i == 0 or day not in b.index:
        return None
    prev = float(df.r.iloc[i - 1])
    pct = float(b.loc[day])
    if not np.isfinite(pct) or abs(1 + pct) < 1e-9:
        return None
    ref = float(df.r.iloc[i]) / (1 + pct)
    return prev - s * ref


def rebuild(code):
    got = load(code)
    if got is None:
        return None, {"code": code, "status": "skip", "reason": "缺 hfq 或 raw 缓存"}
    df, b = got
    if len(df) < 60:
        return None, {"code": code, "status": "skip", "reason": f"样本太短 n={len(df)}"}
    if b is None:
        return None, {"code": code, "status": "quarantine", "n": int(len(df)),
                      "reason": "没有 baostock 对照，无法定位事件也无法对账"}

    ev_days, glitches = detect(df, b)
    pos = {d: i for i, d in enumerate(df.index)}
    events, unsolved, no_affine = {}, [], []
    for day in ev_days:
        i = pos[day]
        if i == 0 or day not in b.index:
            continue
        pct = float(b.loc[day])
        if not np.isfinite(pct) or abs(1 + pct) < 1e-9:
            continue
        md = affine_at(df, i)
        if md is None:
            no_affine.append(str(day))
        got, why = solve_event(float(df.r.iloc[i - 1]), float(df.r.iloc[i]), pct, md)
        if got is None:
            unsolved.append((str(day), why))
            continue
        events[day] = got

    m = pd.Series(1.0, index=df.index)
    d = pd.Series(0.0, index=df.index)
    for day, (ss, cc) in events.items():
        m[day], d[day] = ss, cc
    tr = (df.r * m + d) / df.r.shift(1) - 1

    rec = {"code": code, "n": int(len(df)), "events": len(events),
           "glitch_days": len(glitches), "no_affine": len(no_affine),
           "unsolved": unsolved[:5]}

    z = pd.concat([tr.rename("t"), b.rename("b")], axis=1).dropna()
    ex = set(events) | set(glitches)
    zn = z[~z.index.isin(ex)]
    if len(zn) < 60:
        rec.update(status="quarantine", reason=f"可对账的非事件日太少 n={len(zn)}")
        return None, rec
    bad = int(((zn.t - zn.b).abs() > RECON_TOL).sum())
    rec.update(recon_n=int(len(zn)), recon_bad=bad,
               recon_bad_frac=round(bad / len(zn), 6),
               recon_median=float((zn.t - zn.b).abs().median()))
    if unsolved:
        rec.update(status="quarantine",
                   reason=f"{len(unsolved)} 个事件日解不出（疑似配股/缩股）")
        return None, rec
    if bad / len(zn) > RECON_MAX_BAD:
        rec.update(status="quarantine",
                   reason=f"非事件日对账不通过：{bad}/{len(zn)} 天偏差>{RECON_TOL}")
        return None, rec
    if len(glitches) > 0.005 * len(df):
        rec.update(status="quarantine",
                   reason=f"与 baostock 的单日价格分歧过多：{len(glitches)} 天")
        return None, rec

    adj_close = df.r.iloc[0] * (1 + tr.fillna(0)).cumprod()
    factor = adj_close / df.r
    out = pd.DataFrame({"close": adj_close, "factor": factor, "ret": tr})
    for c in ("open", "high", "low"):
        if c in df:
            out[c] = df[c] * factor
    rec.update(status="ok", reason="")
    rec["_events"] = {str(k): [round(v[0], 6), round(v[1], 6)] for k, v in events.items()}
    return out, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 只（抽样试跑）")
    ap.add_argument("--codes", nargs="*", help="只跑指定代码")
    a = ap.parse_args()

    codes = a.codes or [os.path.basename(f)[:-4] for f in sorted(glob.glob(f"{HFQ}/*.csv"))]
    if a.limit:
        codes = codes[:: max(1, len(codes) // a.limit)][: a.limit]
    os.makedirs(OUT_DIR, exist_ok=True)

    recs, rows = [], []
    for n, code in enumerate(codes, 1):
        out, rec = rebuild(code)
        if out is not None:
            out.to_csv(os.path.join(OUT_DIR, f"{code}.csv"))
            for day, (mm, dd) in rec.pop("_events", {}).items():
                rows.append({"code": code, "date": day,
                             "share_multiple": mm, "cash_per_share_pre_split": dd})
        rec.pop("_events", None)
        recs.append(rec)
        if n % 500 == 0:
            print(f"  ...{n}/{len(codes)}", flush=True)
    pd.DataFrame(rows).to_csv(ACTIONS, index=False)

    df_rec = pd.DataFrame(recs)
    summary = {
        "total": len(recs),
        "ok": int((df_rec.status == "ok").sum()),
        "quarantine": int((df_rec.status == "quarantine").sum()),
        "skip": int((df_rec.status == "skip").sum()),
        "events_total": len(rows),
        "recon_median_of_ok": float(df_rec[df_rec.status == "ok"]["recon_median"].median())
        if (df_rec.status == "ok").any() else None,
        "quarantine_reasons": df_rec[df_rec.status == "quarantine"]["reason"]
        .str.replace(r"\d+", "N", regex=True).value_counts().to_dict(),
    }
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "per_code": recs}, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\n复权序列 → {OUT_DIR}/\n公司行动表 → {ACTIONS}（{len(rows)} 条）\n对账报告 → {REPORT}")


if __name__ == "__main__":
    main()
