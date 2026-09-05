#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qbt.py · 与框架无关的回测证伪工具箱（EP004 方法论的通用实现）
==============================================================
只依赖 numpy + pandas。不绑定 Freqtrade / backtrader / 自研引擎——
所有输入都归一化成两种最小契约：

  1) 日收益序列  daily returns   （策略、基准都用它）
  2) 逐笔成交    trades          （仅作成交诊断；候选验收的蒙卡统一用日收益）

子命令
------
  sharpe      日频资金曲线口径的夏普/索提诺/卡玛/最大回撤（唯一合法口径）
  alphabeta   CAPM 回归：年化 alpha、beta、R²、alpha 的 t/p、beta 拖累 vs alpha 贡献
  dsr         Deflated Sharpe（Bailey & López de Prado）：夏普里有多少是搜出来的运气
  mc          蒙特卡洛分块自助重采样：prob(profit)、P5/P50/P95
  pvalue      分块自助检验 H0: 日均收益 = 0（回答"这个盈/亏是不是统计噪音"）
  randomport  随机组合置换：同样的宇宙/持仓数/换手，随机选股能拿到多少夏普
  report      一次跑完上面全部 + 出裁决 JSON；默认严格验收，--exploratory 可只诊断

输入格式（CSV 或 JSON，列名大小写不敏感，自动识别）
--------------------------------------------------
  日收益 : date + ret|return|daily_return          → 直接用
           date + equity|balance|nav|cum_pnl       → 差分/pct_change
           close_date + profit_abs                 → 按日汇总 / --capital
  成交   : profit_ratio|profit_pct|pnl_pct  或  profit_abs(+ --capital)
  试验   : {"trials":[{"valid_sharpe":..}]} / [{"valid_score":..}] / CSV 单列
  面板   : 宽表 CSV，行=日期，列=各标的日收益

典型用法
--------
  python qbt.py sharpe    --returns oos_equity.csv --market cn_stock
  python qbt.py alphabeta --returns oos_equity.csv --bench csi300.csv --market cn_stock
  python qbt.py dsr       --returns valid_equity.csv --trials hyperopt_results.json
  python qbt.py mc        --trades oos_trades.csv --iters 5000 --block 10
  python qbt.py randomport --panel universe_returns.csv --sharpe 1.93 --n-long 5 --n-short 5
  python qbt.py report    --returns oos_equity.csv --bench bench.csv \
                          --trades oos_trades.csv --trials hyperopt_results.json \
                          --execution-manifest execution_manifest.json \
                          --data-manifest data_manifest.json \
                          --market crypto --out verified/oos_verdict.json

`report` 默认是候选晋级门禁，必要层缺失即 FAIL。早期探索显式加 `--exploratory`；
该输出只能用于诊断，不能用于写 PASS。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import sys
import zipfile

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 市场口径
# periods_per_year: 夏普年化因子；calendar: 补零用的日历
MARKETS = {
    "crypto":   {"ppy": 365, "calendar": "all"},      # 7x24，非交易日补 0
    "crypto_spot": {"ppy": 365, "calendar": "all"},
    "crypto_perp": {"ppy": 365, "calendar": "all"},
    "cn_stock": {"ppy": 252, "calendar": "observed"},  # 只在实际交易日上算
    "hk_stock": {"ppy": 252, "calendar": "observed"},
    "us_stock": {"ppy": 252, "calendar": "observed"},
    "futures":  {"ppy": 252, "calendar": "observed"},
    "commodity": {"ppy": 252, "calendar": "observed"},
    "rates": {"ppy": 252, "calendar": "observed"},
    "vol": {"ppy": 252, "calendar": "observed"},
    "multi": {"ppy": 252, "calendar": "observed"},
    "fx":       {"ppy": 260, "calendar": "observed"},
}
GAMMA = 0.5772156649015329
REPORT_SCHEMA_VERSION = 2


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """二分求正态分位数，精度足够（避免依赖 scipy）。"""
    p = min(max(p, 1e-12), 1 - 1e-12)
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ---------------------------------------------------------------- 输入加载
def _read_any(path: str) -> pd.DataFrame:
    """CSV / JSON / Freqtrade backtest zip / 目录（取最新 zip）→ DataFrame。"""
    if os.path.isdir(path):
        zs = sorted(glob.glob(os.path.join(path, "*.zip")), key=os.path.getmtime)
        if zs:
            path = zs[-1]
        else:
            cs = sorted(glob.glob(os.path.join(path, "*.csv")), key=os.path.getmtime)
            if not cs:
                sys.exit(f"[qbt] 目录里没有 zip/csv: {path}")
            path = cs[-1]

    low = str(path).lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith(".json") and "_config" not in n:
                    obj = json.loads(z.read(n))
                    rows = _find_records(obj)
                    if rows:
                        return pd.DataFrame(rows)
        sys.exit(f"[qbt] zip 里没找到成交记录: {path}")
    if low.endswith(".json") or low.endswith(".jsonl"):
        if low.endswith(".jsonl"):
            rows = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
            return pd.DataFrame(rows)
        obj = json.load(open(path, encoding="utf-8"))
        rows = _find_records(obj)
        if rows is None:
            sys.exit(f"[qbt] JSON 里没找到记录数组: {path}")
        return pd.DataFrame(rows)
    return pd.read_csv(path)


def _find_records(obj):
    """在任意嵌套 JSON 里捞出第一个「记录数组」（trades / trials / 顶层 list）。"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("trades", "trials", "records", "data", "epochs"):
            if isinstance(obj.get(key), list):
                return obj[key]
        for v in obj.values():
            if isinstance(v, (dict, list)):
                r = _find_records(v)
                if r:
                    return r
    return None


def _pick(df: pd.DataFrame, names) -> str | None:
    lower = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n in lower:
            return lower[n]
    return None


def load_daily_returns(path: str, capital: float = 10000.0,
                       calendar: str = "all", compound: bool = False) -> pd.Series:
    """归一化成「日收益率序列」（index=UTC 自然日）。

    口径（EP004 唯一合法口径）：以【每日资金曲线】而非【每笔交易】计算。
    同时持仓多笔时交易严重重叠、并不独立，按笔算会随并发数虚高。
    """
    df = _read_any(path)
    dcol = _pick(df, ["date", "datetime", "day", "close_date", "time", "timestamp", "trade_date"])
    if dcol is None:
        sys.exit(f"[qbt] {path} 缺日期列(date/close_date/...)")
    day = pd.to_datetime(df[dcol], utc=True, errors="coerce", format="mixed").dt.floor("D")

    rcol = _pick(df, ["ret", "return", "returns", "daily_return", "pnl_pct", "profit_ratio"])
    ecol = _pick(df, ["equity", "balance", "nav", "cum_pnl", "wallet", "total"])
    pcol = _pick(df, ["profit_abs", "pnl", "profit", "pnl_abs"])

    if rcol is not None:
        s = pd.to_numeric(df[rcol], errors="coerce").fillna(0.0).groupby(day).sum()
        src = "returns"
    elif ecol is not None:
        eq = pd.to_numeric(df[ecol], errors="coerce").groupby(day).last().sort_index()
        s = eq.pct_change().fillna(0.0) if compound else (eq.diff() / float(eq.iloc[0])).fillna(0.0)
        src = "equity"
    elif pcol is not None:
        s = pd.to_numeric(df[pcol], errors="coerce").fillna(0.0).groupby(day).sum() / float(capital)
        src = "profit_abs"
    else:
        sys.exit(f"[qbt] {path} 里没有 ret / equity / profit_abs 列，无法还原日收益")

    s = s.sort_index()
    if calendar == "all" and len(s) > 1:
        # 7x24 市场：没有成交的日子必须补 0，否则高估波动、低估天数
        idx = pd.date_range(s.index.min(), s.index.max(), freq="D", tz="UTC")
        s = s.reindex(idx, fill_value=0.0)
    s.name = src
    return s.astype(float)


def load_trade_returns(path: str, capital: float = 10000.0) -> np.ndarray:
    """逐笔收益率序列（用于 trade-level 分块自助）。"""
    df = _read_any(path)
    rcol = _pick(df, ["profit_ratio", "profit_pct", "pnl_pct", "ret", "return", "pct"])
    if rcol is not None:
        return pd.to_numeric(df[rcol], errors="coerce").dropna().to_numpy(float)
    pcol = _pick(df, ["profit_abs", "pnl", "profit"])
    if pcol is None:
        sys.exit(f"[qbt] {path} 缺 profit_ratio / profit_abs 列")
    return (pd.to_numeric(df[pcol], errors="coerce").dropna().to_numpy(float) / float(capital))


def input_date_bounds(path: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """读取一个输入文件的可见日期范围；没有日期列时返回 None。"""
    df = _read_any(path)
    dcol = _pick(df, ["date", "datetime", "day", "close_date", "time", "timestamp", "trade_date"])
    if dcol is None:
        return None
    d = pd.to_datetime(df[dcol], utc=True, errors="coerce", format="mixed").dropna().dt.floor("D")
    if d.empty:
        return None
    return d.min(), d.max()


def _load_json_object(path: str, label: str) -> dict:
    try:
        obj = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        return {"error": f"{label} 无法读取: {exc}"}
    if not isinstance(obj, dict):
        return {"error": f"{label} 顶层必须是 JSON object"}
    return obj


def validate_execution_manifest(path: str | None) -> dict:
    """验证信息→决策→成交→收益区间契约。

    自由文本无法替代市场微观结构复核，因此 manifest 必须显式确认收益起点不早于成交。
    """
    if not path:
        return {"error": "缺 --execution-manifest"}
    obj = _load_json_object(path, "execution manifest")
    if "error" in obj:
        return obj
    required = ["information_time", "decision_time", "execution_time", "pnl_start", "pnl_end",
                "price_field", "timezone", "pnl_start_not_before_execution", "validated"]
    missing = [k for k in required if k not in obj]
    if missing:
        return {"error": "execution manifest 缺字段: " + ", ".join(missing)}
    if obj.get("pnl_start_not_before_execution") is not True or obj.get("validated") is not True:
        return {"error": "成交时序未确认：必须 validated=true 且 pnl_start_not_before_execution=true"}
    return {k: obj[k] for k in required}


def validate_data_manifest(path: str | None) -> dict:
    """验证可追溯数据清单；不替代对供应商本身的独立抽查。"""
    if not path:
        return {"error": "缺 --data-manifest"}
    obj = _load_json_object(path, "data manifest")
    if "error" in obj:
        return obj
    sources = obj.get("sources")
    if not isinstance(sources, list) or not sources:
        return {"error": "data manifest 需要非空 sources 数组"}
    required = ["provider", "url_or_query", "retrieved_at", "raw_file", "sha256", "rows",
                "start", "end", "timezone", "adjustment"]
    failures = []
    root = os.path.dirname(os.path.abspath(path))
    for i, src in enumerate(sources):
        if not isinstance(src, dict):
            failures.append(f"sources[{i}] 不是 object")
            continue
        miss = [k for k in required if src.get(k) in (None, "")]
        sha = str(src.get("sha256", ""))
        if sha and (len(sha) != 64 or any(c not in "0123456789abcdefABCDEF" for c in sha)):
            failures.append(f"sources[{i}].sha256 不是 64 位十六进制")
        if miss:
            failures.append(f"sources[{i}] 缺字段: {','.join(miss)}")
            continue
        raw = str(src["raw_file"])
        raw_path = raw if os.path.isabs(raw) else os.path.join(root, raw)
        if not os.path.isfile(raw_path):
            failures.append(f"sources[{i}].raw_file 不存在: {raw_path}")
        else:
            h = hashlib.sha256()
            with open(raw_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest().lower() != sha.lower():
                failures.append(f"sources[{i}] SHA256 与 raw_file 不一致")
    if failures:
        return {"error": "；".join(failures)}
    return {"source_count": len(sources), "providers": sorted({str(s["provider"]) for s in sources})}


SCREEN_SCHEMA_VERSION = 2
SCREEN_GO, SCREEN_THIN, SCREEN_STOP = "GO", "THIN", "STOP"


def screen_edge_vs_cost(gross_annual: float, turnover: float, cost_bps: float,
                        funding_annual: float = 0.0, stress: float = 2.0) -> dict:
    """A 层信封估算：毛边际够不够覆盖成本。

    这是漏斗最前面那道闸，用意是在写任何回测代码之前就把「成本吃穿型」想法拦掉。
    turnover = 单边换手次数/年（每次按名义收一次 cost_bps）；funding_annual 是资金费/借券等持有成本。
    """
    if turnover < 0 or cost_bps < 0:
        raise ValueError("换手与成本不能为负")
    trade_cost = turnover * cost_bps / 1e4
    cost_annual = trade_cost + funding_annual
    stress_cost = trade_cost * stress + funding_annual
    ratio = float("inf") if cost_annual == 0 else gross_annual / cost_annual
    stress_ratio = float("inf") if stress_cost == 0 else gross_annual / stress_cost

    if ratio >= 3.0 and stress_ratio >= 1.0:
        verdict, say = SCREEN_GO, "毛收益是成本的 {:.1f} 倍，值得往下做".format(ratio)
    elif ratio >= 2.0:
        verdict, say = SCREEN_THIN, "毛收益只有成本的 {:.1f} 倍，余量很薄，成本估错一点就归零".format(ratio)
    else:
        verdict, say = SCREEN_STOP, "毛收益只有成本的 {:.1f} 倍，交易费就把它吃光了，不值得写回测".format(ratio)
    if ratio == float("inf"):
        verdict, say = SCREEN_GO, "这个口径下没有交易成本，成本关不构成约束"

    return {
        "schema_version": SCREEN_SCHEMA_VERSION,
        "stage": "screen",
        "gross_annual": gross_annual,
        "turnover_per_year": turnover,
        "cost_bps_per_side": cost_bps,
        "funding_annual": funding_annual,
        "trade_cost_annual": trade_cost,
        "cost_annual": cost_annual,
        "edge_cost_ratio": None if ratio == float("inf") else round(ratio, 3),
        "stress_multiple": stress,
        "edge_cost_ratio_stressed": None if stress_ratio == float("inf") else round(stress_ratio, 3),
        "screen_verdict": verdict,
        "说人话": say,
    }


def load_permutation_result(path: str | None) -> dict:
    """读取策略类别专用的置换结果，统一成 percentile_vs_random。"""
    if not path:
        return {"error": "缺匹配策略形态的置换结果（--panel 或 --permutation-result）"}
    obj = _load_json_object(path, "permutation result")
    if "error" in obj:
        return obj
    values = {}
    for key in ("percentile_vs_random", "percentile", "p_value"):
        if key not in obj:
            continue
        value = obj[key]
        if not valid_gate_number(value, probability=True):
            return {"error": f"permutation result {key} 必须是 [0, 1] 内的有限数值"}
        values[key] = 1.0 - float(value) if key == "p_value" else float(value)
    if not values:
        return {"error": "permutation result 缺 percentile_vs_random/percentile/p_value"}
    pct = next(iter(values.values()))
    if any(not math.isclose(pct, v, rel_tol=0, abs_tol=1e-12) for v in values.values()):
        return {"error": "permutation result 多个统计字段互相矛盾"}
    # 保留原始精度，不能把低于门槛的数值四舍五入成通过。
    return {**obj, "percentile_vs_random": pct}


def valid_gate_number(value, probability=False):
    """门禁仅接受有限实数；布尔、字符串和缺失值均不是统计证据。"""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        return False
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return False
    return math.isfinite(number) and (not probability or 0 <= number <= 1)


def validate_gate_statistics(rep):
    """在最终裁决处复核，兼顾内置面板统计与外部置换结果。"""
    checks = [
        ("alpha_beta", "ann_alpha", False),
        ("alpha_beta", "alpha_t", False),
        ("monte_carlo", "prob_profit", True),
        ("random_portfolio", "percentile_vs_random", True),
    ]
    selection = rep.get("selection_adjustment", {})
    checks.append(("selection_adjustment", "DSR" if "DSR" in selection else "PSR", True))
    failures = []
    for section, field, probability in checks:
        value = rep.get(section, {}).get(field)
        if not valid_gate_number(value, probability):
            failures.append(f"{section}.{field} 缺失或不是合法有限统计值")
    return failures


def load_trial_scores(path: str, field: str | None = None) -> np.ndarray:
    """搜索日志里每一轮的【验证集】得分（DSR 用它估搜索规模与离散度）。"""
    df = _read_any(path)
    col = _pick(df, [field] if field else []) or _pick(
        df, ["valid_sharpe", "valid_score", "validation_sharpe", "test_sharpe",
             "score", "sharpe", "value"])
    if col is None:
        if df.shape[1] == 1:
            col = df.columns[0]
        else:
            sys.exit(f"[qbt] {path} 里找不到每轮验证得分列（valid_sharpe/score/...）")
    return pd.to_numeric(df[col], errors="coerce").dropna().to_numpy(float)


# ---------------------------------------------------------------- 指标
def equity_path(r: pd.Series, compound: bool) -> pd.Series:
    return (1.0 + r).cumprod() if compound else (1.0 + r.cumsum())


def perf_stats(r: pd.Series, ppy: int, compound: bool = False) -> dict:
    T = len(r)
    if T < 20:
        return {"error": f"样本太短 T={T}，指标不可信"}
    sd = float(r.std(ddof=1))
    eq = equity_path(r, compound)
    total = float(eq.iloc[-1] - 1.0)
    if compound:
        ann_ret = float((eq.iloc[-1]) ** (ppy / T) - 1.0) if eq.iloc[-1] > 0 else -1.0
    else:
        ann_ret = total * ppy / T
    dd = float((eq / eq.cummax() - 1.0).min())
    downside = r[r < 0]
    dsd = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sharpe = float(r.mean() / sd * math.sqrt(ppy)) if sd > 0 else 0.0
    sortino = float(r.mean() / dsd * math.sqrt(ppy)) if dsd > 0 else float("nan")
    return {
        "T_days": T,
        "start": str(r.index[0].date()), "end": str(r.index[-1].date()),
        "total_return": round(total, 4),
        "ann_return": round(ann_ret, 4),
        "sharpe_daily_wallet": round(sharpe, 3),
        "sortino": round(sortino, 3) if sortino == sortino else None,
        "max_drawdown": round(abs(dd), 4),
        "calmar": round(ann_ret / abs(dd), 3) if dd < -1e-9 else None,
        "ann_vol": round(sd * math.sqrt(ppy), 4),
        "positive_days_pct": round(float((r > 0).mean()), 3),
    }


def _newey_west_cov(x: np.ndarray, resid: np.ndarray, lags: int) -> np.ndarray:
    """OLS 系数的 Newey-West/HAC 协方差矩阵。"""
    n = len(resid)
    bread = np.linalg.pinv(x.T @ x)
    xu = x * resid[:, None]
    meat = xu.T @ xu
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        gamma = xu[lag:].T @ xu[:-lag]
        meat += weight * (gamma + gamma.T)
    return bread @ meat @ bread * (n / max(n - x.shape[1], 1))


def alpha_beta(r: pd.Series, b: pd.Series, ppy: int, rf_annual: float = 0.0,
               nw_lags: int | None = None) -> dict:
    """R_s - Rf = alpha + beta*(R_b - Rf) + eps，逐日盯市回归，HAC 标准误。

    读法：alpha 是选股/择时真正创造的部分，beta*R_b 是"大盘白送/白拿"的部分。
    亏钱但 alpha 为正**且显著** = 策略本身有效，输在净敞口撞上行情方向。
    不显著的正 alpha 说明不了任何事——结论句必须把这一层说出来，不能只看符号。
    """
    j = pd.concat([r.rename("s"), b.rename("b")], axis=1).dropna()
    if len(j) < 30:
        return {"error": f"重叠样本太短 n={len(j)}"}
    rf = rf_annual / ppy
    y = (j["s"] - rf).to_numpy(float)
    x = (j["b"] - rf).to_numpy(float)
    n = len(y)
    var_x = float(np.var(x, ddof=1))
    if var_x < 1e-14:
        return {"error": "基准无波动"}
    design = np.column_stack([np.ones(n), x])
    coef = np.linalg.lstsq(design, y, rcond=None)[0]
    a_d, beta = float(coef[0]), float(coef[1])
    resid = y - design @ coef
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-14 else 0.0
    if nw_lags is None:
        nw_lags = max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))
    nw_lags = min(max(int(nw_lags), 0), n - 2)
    hac = _newey_west_cov(design, resid, nw_lags)
    se_a = math.sqrt(max(float(hac[0, 0]), 0.0))
    t = a_d / se_a if se_a > 1e-14 else 0.0
    p = 2.0 * (1.0 - _norm_cdf(abs(t)))
    tot_s = float(j["s"].sum())
    tot_b = float(j["b"].sum())
    return {
        "n_days": n,
        "beta": round(beta, 3),
        "r_squared": round(r2, 3),
        "ann_alpha": round(a_d * ppy, 4),
        "alpha_t": round(t, 2),
        "alpha_p": round(p, 4),
        "alpha_significant": bool(p < 0.05),
        "alpha_se_method": "Newey-West/HAC",
        "nw_lags": nw_lags,
        "strategy_total": round(tot_s, 4),
        "benchmark_total": round(tot_b, 4),
        "note": "total/drag/contribution 为日收益加总口径（与日频夏普一致），非复利净值涨跌幅",
        "beta_drag": round(beta * tot_b, 4),
        "alpha_contribution": round(tot_s - beta * tot_b, 4),
        "verdict": (
            "正 alpha 且显著：策略本身有效" if a_d > 0 and p < 0.05 else
            f"正 alpha 但不显著（p={round(p, 4)}）：还看不出策略本身有效" if a_d > 0 else
            "负 alpha 且显著：选股/择时本身在亏钱" if p < 0.05 else
            f"负 alpha 但不显著（p={round(p, 4)}）：看不出选股/择时有效或无效"),
    }


def deflated_sharpe(r: pd.Series, trials: np.ndarray, ppy: int) -> dict:
    """DSR：搜了 N 轮、各轮成绩方差 V，纯运气能刷到的最高夏普是多少？实际有没有显著超过它。

    DSR ≥ 0.95 显著 / 0.90~0.95 偏弱 / < 0.90 大概率是搜出来的运气。
    """
    T = len(r)
    sd = float(r.std(ddof=1))
    if T < 30 or sd <= 0:
        return {"error": f"样本太短或无波动 T={T}"}
    N = max(int(len(trials)), 2)
    v = float(np.var(trials, ddof=1)) if len(trials) > 1 else 0.0
    if v <= 0:
        return {"error": "各轮得分方差为 0，无法估计运气基线"}
    sr_d = float(r.mean() / sd)
    g3 = float(pd.Series(r).skew())
    g4 = float(pd.Series(r).kurt()) + 3.0     # pandas 给的是超额峰度
    sr0_d = math.sqrt(v / ppy) * ((1 - GAMMA) * _norm_ppf(1 - 1.0 / N)
                                  + GAMMA * _norm_ppf(1 - 1.0 / (N * math.e)))
    denom = 1.0 - g3 * sr_d + (g4 - 1.0) / 4.0 * sr_d ** 2
    if denom <= 0:
        return {"error": "收益分布过于极端，DSR 分母非正"}
    z = (sr_d - sr0_d) * math.sqrt(T - 1) / math.sqrt(denom)
    dsr = _norm_cdf(z)
    return {
        "n_trials": N,
        "trial_score_var": round(v, 4),
        "observed_sharpe": round(sr_d * math.sqrt(ppy), 3),
        "luck_baseline_sharpe": round(sr0_d * math.sqrt(ppy), 3),
        "T_days": T, "skew": round(g3, 3), "kurtosis": round(g4, 3),
        "DSR": round(float(dsr), 4),
        "verdict": ("显著 (DSR≥0.95)" if dsr >= 0.95 else
                    "偏弱 (0.90≤DSR<0.95)" if dsr >= 0.90 else
                    "不显著 —— 大概率是搜出来的运气"),
    }


def probabilistic_sharpe(r: pd.Series, ppy: int, benchmark_sharpe: float = 0.0) -> dict:
    """单一、事前锁死规格的 PSR；不伪造不存在的多轮 DSR。"""
    T = len(r)
    sd = float(r.std(ddof=1))
    if T < 30 or sd <= 0:
        return {"error": f"样本太短或无波动 T={T}"}
    sr_d = float(r.mean() / sd)
    sr0_d = float(benchmark_sharpe) / math.sqrt(ppy)
    g3 = float(pd.Series(r).skew())
    g4 = float(pd.Series(r).kurt()) + 3.0
    denom = 1.0 - g3 * sr_d + (g4 - 1.0) / 4.0 * sr_d ** 2
    if denom <= 0:
        return {"error": "收益分布过于极端，PSR 分母非正"}
    z = (sr_d - sr0_d) * math.sqrt(T - 1) / math.sqrt(denom)
    psr = _norm_cdf(z)
    return {
        "method": "PSR-single-spec",
        "observed_sharpe": round(sr_d * math.sqrt(ppy), 3),
        "benchmark_sharpe": round(float(benchmark_sharpe), 3),
        "T_days": T,
        "PSR": round(float(psr), 4),
        "warning": "只适用于真正事前锁死的单一规格；同题尝试过的任何变体都必须改用 DSR",
    }


def _block_indices(n: int, block: int, rng) -> np.ndarray:
    idx = []
    while len(idx) < n:
        s = int(rng.integers(0, max(1, n - block + 1)))
        idx.extend(range(s, min(s + block, n)))
    return np.asarray(idx[:n])


def monte_carlo(x: np.ndarray, iters: int, block: int, seed: int,
                compound: bool = True) -> dict:
    """分块自助重采样：保留一定序列相关性，回答"这条曲线有多少是运气"。"""
    n = len(x)
    if n < 20:
        return {"error": f"样本太少 n={n}"}
    rng = np.random.default_rng(seed)
    finals = np.empty(iters)
    for k in range(iters):
        s = x[_block_indices(n, block, rng)]
        finals[k] = float(np.prod(1.0 + s)) if compound else 1.0 + float(np.sum(s))
    return {
        "n": n, "iters": iters, "block": block,
        "original_final": round(float(np.prod(1.0 + x) if compound else 1 + x.sum()), 4),
        "prob_profit": round(float(np.mean(finals > 1.0)), 4),
        "p5": round(float(np.percentile(finals, 5)), 4),
        "p50": round(float(np.percentile(finals, 50)), 4),
        "p95": round(float(np.percentile(finals, 95)), 4),
        "verdict": ("P5 仍盈利 —— 路径稳健" if float(np.percentile(finals, 5)) > 1.0 else
                    "P5 不盈利 —— 至少 5% 的重采样路径亏损"),
    }


def pvalue_zero_mean(r: pd.Series, iters: int, block: int, seed: int) -> dict:
    """H0: 日均收益 = 0。分块自助去均值重采样，双尾 p。

    用来回答"这一年赚/亏得是不是统计显著"，而不是被少数几天带出来的噪音。
    """
    x = r.to_numpy(float)
    n = len(x)
    if n < 30:
        return {"error": f"样本太短 n={n}"}
    obs = float(x.mean())
    c = x - obs
    rng = np.random.default_rng(seed)
    means = np.empty(iters)
    for k in range(iters):
        means[k] = float(c[_block_indices(n, block, rng)].mean())
    p = float((np.abs(means) >= abs(obs)).mean())
    return {
        "observed_daily_mean": round(obs, 6),
        "p_value": round(p, 4),
        "significant": bool(p < 0.05),
        "verdict": ("显著" + ("盈利" if obs > 0 else "亏损")) if p < 0.05 else "与 0 无显著差异（噪音）",
    }


def require_n_short(n_short):
    """随机对照的多空结构必须和真策略一致，否则置换分位没有意义。

    这里不给默认值是刻意的：原来 --n-short 默认 5，纯多策略不写它就会被拿去和
    多空中性的随机组合比（夏普中位≈0），分位被系统性抬高。实测同一个策略
    75.05% → 99.65%，结论正好相反。宁可报错，不要静默给一个错的零假设。
    """
    if n_short is None:
        raise SystemExit(
            "qbt: 必须显式写 --n-short —— 纯多策略写 --n-short 0，多空策略写实际做空只数。\n"
            "随机对照的多空结构要和真策略一致：拿多空中性的随机组合去比纯多策略，"
            "分位会被系统性抬高，跑出来的显著性是假的。")
    return n_short


def random_portfolio(panel: pd.DataFrame, n_long: int, n_short: int, hold: int,
                     iters: int, seed: int, ppy: int, actual_sharpe: float | None) -> dict:
    """随机组合置换：宇宙、持仓数、换手频率都照抄真策略，只把【选股逻辑】换成随机。

    这是最狠也最容易被忽略的一层——它回答：你的因子到底有没有跑赢"闭着眼睛在同一个
    池子里按同样节奏乱选"。跑不赢 = 收益来自宇宙和仓位结构，不是来自你的因子。
    """
    px = panel.dropna(how="all").fillna(0.0)
    dates, syms = px.index, list(px.columns)
    T, M = len(dates), len(syms)
    if T < 30 or M < 3:
        return {"error": f"面板太小 T={T} M={M}"}
    n_long = min(n_long, M)
    n_short = min(n_short, max(M - n_long, 0))
    rng = np.random.default_rng(seed)
    vals = px.to_numpy(float)
    sharpes = np.empty(iters)
    for k in range(iters):
        w = np.zeros((T, M))
        cur = None
        for t in range(T):
            if t % max(hold, 1) == 0 or cur is None:
                perm = rng.permutation(M)
                cur = np.zeros(M)
                if n_long:
                    cur[perm[:n_long]] = 1.0 / n_long
                if n_short:
                    cur[perm[n_long:n_long + n_short]] = -1.0 / n_short
            w[t] = cur
        # 权重滞后一期：t 日的持仓只能由 t-1 收盘定
        pr = np.sum(np.vstack([np.zeros(M), w[:-1]]) * vals, axis=1)
        sd = pr.std(ddof=1)
        sharpes[k] = pr.mean() / sd * math.sqrt(ppy) if sd > 0 else 0.0
    out = {
        "iters": iters, "n_long": n_long, "n_short": n_short, "rebalance_bars": hold,
        "random_sharpe_mean": round(float(sharpes.mean()), 3),
        "random_sharpe_p50": round(float(np.percentile(sharpes, 50)), 3),
        "random_sharpe_p95": round(float(np.percentile(sharpes, 95)), 3),
        "random_sharpe_max": round(float(sharpes.max()), 3),
    }
    if actual_sharpe is not None:
        pct = float((sharpes < actual_sharpe).mean())
        out.update({
            "actual_sharpe": actual_sharpe,
            "percentile_vs_random": round(pct, 4),
            "p_value": round(1.0 - pct, 4),
            "verdict": ("跑赢 95% 随机组合，因子有信息" if pct >= 0.95 else
                        "打不过随机组合 —— 收益来自宇宙/仓位结构，不是你的因子"),
        })
    return out


# ---------------------------------------------------------------- CLI
def _market(a):
    m = MARKETS.get(a.market)
    if m is None:
        sys.exit(f"[qbt] 未知市场 {a.market}，可选: {list(MARKETS)}")
    ppy = a.periods_per_year or m["ppy"]
    return ppy, m["calendar"]


def _emit(obj, out=None):
    txt = json.dumps(obj, ensure_ascii=False, indent=2)
    print(txt)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        open(out, "w", encoding="utf-8").write(txt)
        print(f"\n[qbt] 已写入 {out}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="回测证伪工具箱（EP004 方法论通用实现）")
    ap.add_argument("cmd", choices=["screen", "sharpe", "alphabeta", "dsr", "mc", "pvalue",
                                    "randomport", "report"])
    ap.add_argument("--returns", help="策略日收益/权益曲线/成交文件")
    ap.add_argument("--bench", help="基准日收益/指数收盘价文件")
    ap.add_argument("--trades", help="逐笔成交文件（report 中只作数量/窗口诊断）")
    ap.add_argument("--trials", help="搜索日志（每轮验证得分），dsr 用")
    ap.add_argument("--trials-field", help="指定每轮得分的列名")
    ap.add_argument("--panel", help="宽表面板 CSV：行=日期，列=各标的日收益（randomport 用）")
    ap.add_argument("--permutation-result", help="类别专用置换 JSON；不能用 randomport 时提供")
    ap.add_argument("--execution-manifest", help="信息/决策/成交/PnL 时序契约 JSON")
    ap.add_argument("--data-manifest", help="数据来源、SHA256、时区、复权口径 JSON")
    ap.add_argument("--single-spec", action="store_true", help="确认只有一个事前规格；用 PSR 代替 DSR")
    ap.add_argument("--exploratory", action="store_true", help="探索诊断：缺失验证层不拦截；不得据此写 PASS")
    ap.add_argument("--market", default="crypto", choices=list(MARKETS))
    ap.add_argument("--periods-per-year", type=int, default=None, help="覆盖年化因子")
    ap.add_argument("--capital", type=float, default=10000.0, help="初始资金（profit_abs → 收益率）")
    ap.add_argument("--compound", action="store_true", help="按复利算权益（默认按初始资金加总，与 EP004 一致）")
    ap.add_argument("--rf", type=float, default=0.0, help="年化无风险利率")
    ap.add_argument("--iters", type=int, default=5000)
    ap.add_argument("--block", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-long", type=int, default=5)
    ap.add_argument("--n-short", type=int, default=None,
                    help="随机对照的做空只数。必须显式给：纯多策略写 0，多空策略写实际做空只数")
    ap.add_argument("--hold", type=int, default=1, help="随机组合的再平衡间隔（根/日）")
    ap.add_argument("--sharpe", type=float, default=None, help="真策略夏普（randomport 对比用）")
    ap.add_argument("--min-alpha-t", type=float, default=2.0)
    ap.add_argument("--min-selection-prob", type=float, default=0.90,
                    help="DSR 或单规格 PSR 的最低概率")
    ap.add_argument("--min-profit-prob", type=float, default=0.95,
                    help="分块自助路径赚钱概率；候选验收默认 95%%")
    ap.add_argument("--min-random-percentile", type=float, default=0.95)
    ap.add_argument("--gross-annual", type=float, help="screen: 信号的年化毛收益上限（小数，0.05=5%%）")
    ap.add_argument("--turnover", type=float, help="screen: 单边换手次数/年")
    ap.add_argument("--cost-bps", type=float, help="screen: 单边成本 bp（照市场年鉴锁死）")
    ap.add_argument("--funding-annual", type=float, default=0.0, help="screen: 年化持有成本（资金费/借券/融资）")
    ap.add_argument("--cost-stress", type=float, default=2.0, help="screen: 压力成本倍数，默认 2x")
    ap.add_argument("--out", help="结果 JSON 落盘路径")
    a = ap.parse_args()
    ppy, cal = _market(a)

    def R():
        if not a.returns:
            sys.exit("[qbt] 需要 --returns")
        return load_daily_returns(a.returns, a.capital, cal, a.compound)

    def B():
        if not a.bench:
            return None
        return load_daily_returns(a.bench, a.capital, cal, compound=True)

    if a.cmd == "screen":
        for k in ("gross_annual", "turnover", "cost_bps"):
            if getattr(a, k) is None:
                raise SystemExit(f"screen 需要 --{k.replace('_', '-')}")
        _emit(screen_edge_vs_cost(a.gross_annual, a.turnover, a.cost_bps,
                                  a.funding_annual, a.cost_stress), a.out)
    elif a.cmd == "sharpe":
        _emit(perf_stats(R(), ppy, a.compound), a.out)

    elif a.cmd == "alphabeta":
        b = B()
        if b is None:
            sys.exit("[qbt] alphabeta 需要 --bench")
        _emit(alpha_beta(R(), b, ppy, a.rf), a.out)

    elif a.cmd == "dsr":
        if not a.trials:
            sys.exit("[qbt] dsr 需要 --trials（每一轮的验证得分）")
        _emit(deflated_sharpe(R(), load_trial_scores(a.trials, a.trials_field), ppy), a.out)

    elif a.cmd == "mc":
        x = (load_trade_returns(a.trades, a.capital) if a.trades
             else R().to_numpy(float))
        _emit(monte_carlo(x, a.iters, a.block, a.seed, compound=bool(a.trades)), a.out)

    elif a.cmd == "pvalue":
        _emit(pvalue_zero_mean(R(), a.iters, a.block, a.seed), a.out)

    elif a.cmd == "randomport":
        if not a.panel:
            sys.exit("[qbt] randomport 需要 --panel")
        pn = pd.read_csv(a.panel, index_col=0, parse_dates=True).sort_index()
        _emit(random_portfolio(pn, a.n_long, require_n_short(a.n_short), a.hold, min(a.iters, 2000),
                               a.seed, ppy, a.sharpe), a.out)

    else:  # report
        r = R()
        strict = not a.exploratory
        rep = {"schema_version": REPORT_SCHEMA_VERSION,
               "stage": "candidate" if strict else "exploratory",
               "role": "alpha",
               "market": a.market, "periods_per_year": ppy,
               "performance": perf_stats(r, ppy, a.compound)}
        b = B()
        if b is not None:
            missing_bench = r.index.difference(b.index)
            if len(missing_bench):
                rep["window_consistency"] = {
                    "error": f"基准缺少 {len(missing_bench)} 个策略日期，不能混用窗口"
                }
            else:
                b = b.reindex(r.index)
                rep["window_consistency"] = {
                    "returns_start": str(r.index.min().date()),
                    "returns_end": str(r.index.max().date()),
                    "benchmark_start": str(b.index.min().date()),
                    "benchmark_end": str(b.index.max().date()),
                    "aligned_days": len(r),
                }
                rep["alpha_beta"] = alpha_beta(r, b, ppy, a.rf)
                rep["benchmark"] = perf_stats(b, ppy, compound=True)
        else:
            rep["window_consistency"] = {"error": "缺 --bench"}
        if a.trials:
            rep["selection_adjustment"] = deflated_sharpe(
                r, load_trial_scores(a.trials, a.trials_field), ppy)
            rep["deflated_sharpe"] = rep["selection_adjustment"]  # 兼容旧消费者
        elif a.single_spec:
            rep["selection_adjustment"] = probabilistic_sharpe(r, ppy)
        else:
            rep["selection_adjustment"] = {"error": "缺完整 trials；若真正只有一个事前规格，显式传 --single-spec"}

        # 候选验收统一对日频资金曲线做路径重采样。逐笔 MC 不能和 OOS 日收益拼成同一裁决。
        rep["monte_carlo"] = monte_carlo(r.to_numpy(float), a.iters, a.block, a.seed,
                                          compound=a.compound)
        rep["monte_carlo"]["basis"] = "daily_returns"
        if a.trades:
            bounds = input_date_bounds(a.trades)
            rep["trades_diagnostic"] = {"n": len(load_trade_returns(a.trades, a.capital))}
            if bounds:
                rep["trades_diagnostic"].update({
                    "start": str(bounds[0].date()), "end": str(bounds[1].date()),
                    "outside_returns_window": bool(bounds[0] < r.index.min() or bounds[1] > r.index.max()),
                })
        rep["p_value"] = pvalue_zero_mean(r, a.iters, a.block, a.seed)
        if a.panel:
            pn = pd.read_csv(a.panel, index_col=0, parse_dates=True).sort_index()
            pn.index = pd.to_datetime(pn.index, utc=True, errors="coerce").floor("D")
            pn = pn[~pn.index.isna()]
            missing_panel = r.index.difference(pn.index)
            if len(missing_panel):
                rep["random_portfolio"] = {"error": f"panel 缺少 {len(missing_panel)} 个策略日期"}
            else:
                pn = pn.reindex(r.index)
                rep["random_portfolio"] = random_portfolio(
                    pn, a.n_long, require_n_short(a.n_short), a.hold, min(a.iters, 2000), a.seed, ppy,
                    rep["performance"].get("sharpe_daily_wallet"))
        else:
            rep["random_portfolio"] = load_permutation_result(a.permutation_result)

        rep["execution_check"] = validate_execution_manifest(a.execution_manifest)
        rep["data_provenance"] = validate_data_manifest(a.data_manifest)

        fails = []
        required = {
            "performance": rep.get("performance", {}),
            "window_consistency": rep.get("window_consistency", {}),
            "alpha_beta": rep.get("alpha_beta", {}),
            "selection_adjustment": rep.get("selection_adjustment", {}),
            "monte_carlo": rep.get("monte_carlo", {}),
            "random_portfolio": rep.get("random_portfolio", {}),
            "execution_check": rep.get("execution_check", {}),
            "data_provenance": rep.get("data_provenance", {}),
        }
        if strict:
            for name, result in required.items():
                if not result or result.get("error"):
                    fails.append(f"{name} 缺失或失败：{result.get('error', '无结果')}")
        fails.extend(validate_gate_statistics(rep))
        ab = rep.get("alpha_beta", {})
        if ab.get("ann_alpha", 0) <= 0:
            fails.append("alpha ≤ 0：收益不来自选股/择时")
        if ab.get("alpha_t") is not None and ab["alpha_t"] < a.min_alpha_t:
            fails.append(f"Newey-West alpha t {ab['alpha_t']} < {a.min_alpha_t}")
        sel = rep.get("selection_adjustment", {})
        sel_prob = sel.get("DSR", sel.get("PSR"))
        if sel_prob is not None and sel_prob < a.min_selection_prob:
            fails.append(f"选择偏差调整概率 {sel_prob} < {a.min_selection_prob}")
        mc_ = rep.get("monte_carlo", {})
        if mc_.get("prob_profit") is not None and mc_["prob_profit"] < a.min_profit_prob:
            fails.append(f"prob(profit) {mc_['prob_profit']} < {a.min_profit_prob}")
        rp = rep.get("random_portfolio", {})
        if rp.get("percentile_vs_random") is not None and rp["percentile_vs_random"] < a.min_random_percentile:
            fails.append(f"随机/置换分位 {rp['percentile_vs_random']} < {a.min_random_percentile}")
        td = rep.get("trades_diagnostic", {})
        if td.get("outside_returns_window"):
            fails.append("trades 含策略收益窗口以外的记录，禁止把 FULL 成交和 OOS 业绩拼接")
        # 去重，保证机器输出稳定。
        fails = list(dict.fromkeys(fails))
        rep["falsification_failures"] = fails
        if not strict:
            rep["verdict_code"] = "DIAGNOSTIC"
            rep["verdict"] = "探索诊断完成；不得据此写 PASS"
        elif not fails:
            rep["verdict_code"] = "PASS"
            rep["verdict"] = "候选验收通过 —— 下一步是实时 paper trading，不等于可直接上仓位"
        else:
            rep["verdict_code"] = "FAIL"
            rep["verdict"] = "未通过：" + "；".join(fails)
        _emit(rep, a.out)


if __name__ == "__main__":
    main()
