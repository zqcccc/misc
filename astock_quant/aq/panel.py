"""把逐只股票的 CSV 拼成宽表面板（date × code），并落盘为 parquet。

面板里的每个字段都是"当日收盘后可知"的量：开高低收（后复权）、成交量、
估算成交额、不复权收盘价。任何前视处理（如 ffill 未来价格）都不允许出现在
这一层 —— 停牌日保持 NaN，由回测引擎按"停牌不可交易、持仓不变"处理。
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from . import config, datasource as ds

FIELDS = ["open", "high", "low", "close", "volume", "amount", "close_raw"]

# 连续交易（前一日未停牌）时 A 股单日涨跌幅不可能超过 20%+，超过这个阈值
# 只可能是数据源的复权因子出错或退市整理期的脏数据
BAD_TICK_THRESHOLD = 0.25


def _is_share_unit(code: str) -> bool:
    """成交量按「股」返回的板块（科创板）。其余板块是「手」= 100 股。"""
    return code[2:].startswith(("688", "689"))


def clean_bad_ticks(panels: dict[str, pd.DataFrame],
                    threshold: float = BAD_TICK_THRESHOLD) -> tuple[dict[str, pd.DataFrame], int]:
    """剔除脏数据：前后两日都有 K 线却出现 |涨跌幅| > threshold 的记录。

    A 股有涨跌停制度，连续交易时不可能出现这种跳变（停牌复牌的跳空不在此列，
    因为前一日没有 K 线）。这类点几乎都是数据源的复权因子出错或退市整理期的
    脏数据，一根就能把等权组合的净值打穿。

    处理方式：从出错那一天起把该股票整段置为缺失（等同于"数据到此为止"），
    引擎会按最后一个有效价清算。判定只用到当日及前一日的数据，不含未来信息。
    """
    close = panels["close"]
    has_bar = close.notna()
    ret = close / close.shift(1) - 1.0
    bad = (ret.abs() > threshold) & has_bar & has_bar.shift(1).fillna(False)
    if not bad.any().any():
        return panels, 0
    dead_from = bad.cummax()          # 出错之后一律视为无效
    n_bad = int(bad.sum().sum())
    return {k: v.mask(dead_from) for k, v in panels.items()}, n_bad


def _panel_path(field: str) -> str:
    return os.path.join(config.PANEL_DIR, f"{field}.parquet")


def build_panel(codes: list[str] | None = None, verbose: bool = True) -> dict[str, pd.DataFrame]:
    meta = pd.read_csv(os.path.join(config.DATA_DIR, "meta.csv"))
    meta = meta.drop_duplicates(subset="code")
    if codes is None:
        codes = [c for c in meta["code"].tolist() if ds.is_tradable_board(c)]

    series: dict[str, dict[str, pd.Series]] = {f: {} for f in FIELDS}
    for i, code in enumerate(codes):
        hfq = ds.load_local(code, "hfq")
        if hfq is None or hfq.empty:
            continue
        hfq = hfq.drop_duplicates(subset="date").set_index("date")
        raw = ds.load_local(code, "raw")
        if raw is not None and not raw.empty:
            raw = raw.drop_duplicates(subset="date").set_index("date")
            close_raw = raw["close"].reindex(hfq.index)
        else:
            close_raw = pd.Series(np.nan, index=hfq.index)
        # 成交额估算：成交量(手) * 100 * 不复权收盘价。腾讯接口不给成交额，
        # 用收盘价近似当日均价，量级上足够做流动性过滤与 Amihud 因子。
        # 坑：科创板(688/689)返回的成交量单位是「股」不是「手」，实测中位数成交额
        # 比其他板块高 100 倍。这里统一折算成「手」，否则科创板会被当成流动性
        # 极好的超大盘股，永远通过流动性过滤，liqsize20 / amihud20 也整体错位。
        volume = hfq["volume"] / (100.0 if _is_share_unit(code) else 1.0)
        amount = volume * 100.0 * close_raw
        for f in ["open", "high", "low", "close"]:
            series[f][code] = hfq[f]
        series["volume"][code] = volume
        series["amount"][code] = amount
        series["close_raw"][code] = close_raw
        if verbose and (i + 1) % 500 == 0:
            print(f"  拼接 {i + 1}/{len(codes)}", flush=True)

    panels = {}
    for f in FIELDS:
        df = pd.DataFrame(series[f])
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().astype(np.float32)
        panels[f] = df
    return panels


def save_panels(panels: dict[str, pd.DataFrame]) -> None:
    for f, df in panels.items():
        out = df.copy()
        out.index.name = "date"
        out.to_parquet(_panel_path(f))


def load_panels(fields: list[str] | None = None) -> dict[str, pd.DataFrame]:
    fields = fields or FIELDS
    panels = {}
    for f in fields:
        df = pd.read_parquet(_panel_path(f))
        df.index = pd.to_datetime(df.index)
        panels[f] = df
    return panels


def load_index(code: str) -> pd.DataFrame:
    df = ds.download(code, "hfq")  # 指数无复权，hfq 与原始一致
    df = df.drop_duplicates(subset="date").copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def trading_calendar() -> pd.DatetimeIndex:
    """交易日历：用上证综指的交易日，避免用个股并集（个股停牌/复牌会漏日）。"""
    return load_index(config.CALENDAR_INDEX).index
