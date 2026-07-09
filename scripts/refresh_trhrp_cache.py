#!/usr/bin/env python3
"""TRHRP 回测行情缓存刷新 —— 让看板"一直更新"。

每次运行只把各标的 yf_cache CSV 向后追加最新行情(append, 不去重覆盖历史),
与 trhrp_backtest_live.py 读取的缓存格式(局部货币原生 Close)保持一致。

设计:
  - 普通标的: 读 monitor/caches/TRHRP/yf_cache/<safe(ticker)>.csv, 用 yfinance 拉取
    [last_date-10d, today] 并追加。
  - 海力士(000660.KS): 特殊 USD 折算, 写入 000660.KS.usd.csv(与 fetch_hynix.py 同口径)。
  - 全程 try/except 且对 yfinance 缺失 / 网络失败做降级: 单个标的失败只跳过并警告,
    不影响其余标的, 也不阻断后续的回测重算(老缓存仍有效)。

用法:
  python3 scripts/refresh_trhrp_cache.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# 路径可经环境变量覆盖, 默认沿用本机布局(本地运行行为不变).
# 容器部署时由 docker/trhrp-data 设置 TRHRP_ROOT / TRHRP_CFG / TRHRP_YF_CACHE / TRHRP_DEF_CACHE.
MON_ROOT = Path(os.environ.get("TRHRP_ROOT", "/Users/gongzhao/code/misc"))
CFG_PATH = Path(os.environ.get("TRHRP_CFG", MON_ROOT / "monitor/strategies_trhrp.json"))
YF_CACHE = Path(os.environ.get("TRHRP_YF_CACHE", MON_ROOT / "monitor/caches/TRHRP/yf_cache"))
DEF_CACHE = Path(os.environ.get("TRHRP_DEF_CACHE", MON_ROOT / "scripts/_trhrp_def_cache"))

# 回测脚本里对海力士的特殊处理(与 trhrp_backtest_live.py 保持一致)
HYNIX = {
    "label": "海力士",
    "ticker": "000660.KS",
    "eq_path": YF_CACHE / "000660.KS.usd.csv",
    "usd": True,
}


def safe_name(t: str) -> str:
    return t.replace("^", "IDX_").replace("=", "_").replace("/", "_").replace(":", "_")


def _dl(ticker: str, start: str) -> pd.DataFrame:
    """下载单标的 OHLCV, 返回单级列 [Open,High,Low,Close,Volume] 的 DataFrame。"""
    import yfinance as yf  # 局部导入, 缺失时抛出可被捕获

    raw = yf.download(
        ticker,
        start=start,
        auto_adjust=False,
        progress=False,
        threads=False,
        actions=False,
    )
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        # 列形如 (field, ticker) -> 取该 ticker 的子帧
        raw = raw.xs(ticker, axis=1, level=1)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    return raw[keep].dropna(subset=["Close"])


def _fx_series(start: str, idx: pd.DatetimeIndex) -> pd.Series:
    import yfinance as yf

    fx = yf.download(
        "KRW=X",
        start=start,
        auto_adjust=False,
        progress=False,
        threads=False,
        actions=False,
    )
    if fx is None or len(fx) == 0:
        raise RuntimeError("KRW=X 下载为空")
    if isinstance(fx.columns, pd.MultiIndex):
        close = fx.xs("KRW=X", axis=1, level=1)["Close"]
    else:
        close = fx["Close"]
    return close.reindex(idx).ffill()


def refresh_one(ticker: str, path: Path, usd: bool = False) -> str:
    if not path.exists():
        return f"SKIP {ticker}: 基础缓存缺失 {path.name}"

    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
    last = df.index.max()
    start = (last - timedelta(days=10)).strftime("%Y-%m-%d")
    new = _dl(ticker, start)
    if len(new) == 0:
        return f"NOOP {ticker}: 无新数据"

    if usd:
        fxc = _fx_series(start, new.index)
        if fxc.isna().all():
            return f"SKIP {ticker}: FX 不可用, 无法折算 USD"
        out = new.copy()
        for c in ["Open", "High", "Low", "Close"]:
            if c in out.columns:
                out[c] = out[c] / fxc
    else:
        out = new

    out = out.loc[out.index > last]
    if len(out) == 0:
        return f"NOOP {ticker}: 已是最新 (last={last.date()})"

    combined = pd.concat([df, out])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined.to_csv(path)
    return f"OK {ticker}: +{len(out)} 行 ({(out.index.min()).date()} ~ {(out.index.max()).date()})"


def refresh_def_leg(ticker: str, path: Path) -> str:
    """刷新防御腿(GLD / SHY): 直接下载全历史覆盖写入; 失败则沿用已有缓存."""
    try:
        df = _dl(ticker, "2000-01-01")
        if len(df) == 0:
            return f"SKIP {ticker}: 下载为空"
        df = df.sort_index()
        df.to_csv(path)
        return f"OK {ticker}: 防御腿 {len(df)} 行 -> {path.name}"
    except Exception as e:
        if path.exists():
            return f"KEEP {ticker}: 下载失败, 沿用已有缓存 ({e})"
        return f"ERR {ticker}: 下载失败且无缓存 ({e})"


def main() -> None:
    try:
        import yfinance  # noqa: F401
    except Exception as e:
        print(f"[refresh] yfinance 不可用, 跳过刷新: {e}")
        sys.exit(0)

    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    markets = cfg.get("markets", [])
    print(f"[refresh] 配置标的数: {len(markets)} + 海力士(特殊)")

    results = []
    for m in markets:
        ticker = m["ticker"]
        path = YF_CACHE / (safe_name(ticker) + ".csv")
        try:
            results.append(refresh_one(ticker, path, usd=False))
        except Exception as e:
            results.append(f"ERR {ticker}: {e}")

    # 海力士特殊 USD 折算
    try:
        results.append(refresh_one(HYNIX["ticker"], HYNIX["eq_path"], usd=True))
    except Exception as e:
        results.append(f"ERR {HYNIX['ticker']}: {e}")

    # 防御腿 GLD / SHY(回测的避险资产, 需随行情更新)
    for t in ["GLD", "SHY"]:
        try:
            results.append(refresh_def_leg(t, DEF_CACHE / (t + ".csv")))
        except Exception as e:
            results.append(f"ERR {t}: {e}")

    print("\n".join(results))
    print(f"[refresh] 完成 @ {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
