#!/usr/bin/env python3
"""ARM1 生产服务：全市场日线增量更新 -> 最新截面信号 -> JSON/通知。"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
PROJECT_ROOT = os.path.dirname(AQ_ROOT)
sys.path.insert(0, CURRENT_DIR)
sys.path.insert(0, AQ_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from aq import datasource as ds  # noqa: E402
from aq import live_smallcap as live  # noqa: E402
from aq import panel  # noqa: E402
from smallcap_service import (  # noqa: E402
    fetch_live_snapshots,
    notify_rebalance_if_needed,
    send_alert,
)


def _bars_frame(bars: list) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=ds.COLUMNS)
    frame = pd.DataFrame([row[:6] for row in bars], columns=ds.COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ds.COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.drop_duplicates("date").sort_values("date").set_index("date")


def expected_trading_date(end: str | None = None) -> pd.Timestamp:
    end = end or datetime.now().strftime("%Y-%m-%d")
    bars, _ = ds.fetch_chunk("sh000001", end=end, count=10, fq="hfq")
    frame = _bars_frame(bars)
    if frame.empty:
        raise RuntimeError("无法从上证指数行情确认最新交易日")
    return pd.Timestamp(frame.index[-1])


def load_codes(meta_path: str | Path, universe_path: str | Path) -> list[str]:
    codes: set[str] = set()
    meta = pd.read_csv(meta_path)
    codes.update(str(code) for code in meta["code"].dropna())
    path = Path(universe_path)
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            codes.update(saved.get("codes", []))
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 忽略损坏的 universe.json: {exc}", flush=True)
    return sorted(code for code in codes if ds.is_tradable_board(code))


def refresh_universe_if_due(cache_dir: str | Path, max_age_days: int = 30) -> None:
    """每月批量扫描当前有效代码；新股满250日之前发现即可，不必每日扫描。"""
    target = Path(cache_dir) / "universe.json"
    if target.exists():
        try:
            saved = json.loads(target.read_text(encoding="utf-8"))
            checked = datetime.fromisoformat(saved["checked_at"])
            if datetime.now() - checked < timedelta(days=max_age_days):
                return
        except Exception:  # noqa: BLE001
            pass

    active: dict[str, str] = {}
    candidates = ds.candidate_codes()
    print(f"[smallcap-live] 月度扫描新上市代码: {len(candidates)} 个代码空间", flush=True)
    for start in range(0, len(candidates), 50):
        chunk = candidates[start : start + 50]
        url = "http://qt.gtimg.cn/q=" + ",".join(chunk)
        try:
            req = urllib.request.Request(url, headers=ds.UA)
            with urllib.request.urlopen(req, timeout=10) as response:
                text = response.read().decode("gbk", errors="ignore")
            for line in text.split(";"):
                if '="' not in line:
                    continue
                variable, payload = line.split('="', 1)
                code = variable.rsplit("_", 1)[-1].strip()
                parts = payload.rstrip('"\r\n ').split("~")
                if code in chunk and len(parts) > 3 and parts[1] and parts[2]:
                    active[code] = parts[1].replace(" ", "")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 代码扫描批次 {start // 50 + 1} 失败: {exc}", flush=True)

    # 防止网络半失败把代码表缩成残缺集合；旧 meta 仍是永久兜底。
    if len(active) < 4000:
        print(f"[WARN] 月度代码扫描仅得到 {len(active)} 只，拒绝更新 universe.json", flush=True)
        return
    live.atomic_write_json(
        target,
        {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "codes": sorted(active),
            "names": active,
        },
    )
    print(f"[smallcap-live] 月度代码扫描完成: {len(active)} 只当前有效股票", flush=True)


def _stage_path(stage_dir: Path, code: str) -> Path:
    return stage_dir / f"{code}.json"


def _fetch_code(code: str, end: str, count: int, stage_dir: Path) -> dict:
    target = _stage_path(stage_dir, code)
    if target.exists():
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            target.unlink(missing_ok=True)

    hfq_bars, name = ds.fetch_chunk(code, end=end, count=count, fq="hfq")
    raw_bars, raw_name = ds.fetch_chunk(code, end=end, count=count, fq="")
    hfq = _bars_frame(hfq_bars)
    raw = _bars_frame(raw_bars)
    common = hfq.index.intersection(raw.index).sort_values()
    if len(common) == 0:
        raise RuntimeError(f"{code} 没有可合并的后复权/原始日线")

    volume = live.normalise_volume(code, raw.loc[common, "volume"])
    rows = []
    for date in common:
        raw_close = float(raw.at[date, "close"])
        rows.append({
            "date": str(date.date()),
            "close": float(hfq.at[date, "close"]),
            "close_raw": raw_close,
            "amount": float(volume.at[date] * 100.0 * raw_close),
        })
    result = {"code": code, "name": name or raw_name or "", "rows": rows}
    live.atomic_write_json(target, result)
    return result


def fetch_market_rows(
    codes: list[str],
    expected: pd.Timestamp,
    cache_dir: str | Path,
    bootstrap: bool,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str], Path]:
    # 周一多回补一些交易日，自动修复上周可能迟到的历史修订。
    count = live.ROLLING_DAYS if bootstrap else (20 if expected.weekday() == 0 else 8)
    stage_dir = Path(cache_dir) / "staging" / str(expected.date())
    stage_dir.mkdir(parents=True, exist_ok=True)

    close_series: dict[str, pd.Series] = {}
    raw_series: dict[str, pd.Series] = {}
    amount_series: dict[str, pd.Series] = {}
    names: dict[str, str] = {}
    failed: list[tuple[str, str]] = []
    print(
        f"[smallcap-live] 拉取 {len(codes)} 只股票最近 {count} 根日线，"
        f"workers={workers}，已完成文件会断点复用",
        flush=True,
    )

    done = 0
    # 限制同时存活的 Future 数量；首次 400 日灌种时，不能让 5000 份 JSON
    # 结果都挂在 Future 上直到循环结束，否则 ARM1 会出现不必要的内存峰值。
    batch_size = max(100, workers * 20)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for start in range(0, len(codes), batch_size):
            batch = codes[start : start + batch_size]
            futures = {
                executor.submit(_fetch_code, code, str(expected.date()), count, stage_dir): code
                for code in batch
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    result = future.result()
                    frame = pd.DataFrame(result["rows"])
                    frame["date"] = pd.to_datetime(frame["date"])
                    frame = frame.set_index("date").sort_index()
                    close_series[code] = frame["close"]
                    raw_series[code] = frame["close_raw"]
                    amount_series[code] = frame["amount"]
                    names[code] = result.get("name", "")
                except Exception as exc:  # noqa: BLE001
                    failed.append((code, str(exc)))
                done += 1
            print(
                f"[smallcap-live] 抓取进度 {done}/{len(codes)}，失败 {len(failed)}",
                flush=True,
            )

    if failed:
        preview = "; ".join(f"{code}: {err}" for code, err in failed[:10])
        print(f"[WARN] {len(failed)} 只抓取失败（截取前10）: {preview}", flush=True)

    close_rows = pd.DataFrame(close_series).sort_index()
    raw_rows = pd.DataFrame(raw_series).sort_index()
    amount_rows = pd.DataFrame(amount_series).sort_index()
    return close_rows, amount_rows, raw_rows, names, stage_dir


def _initial_state(deliverable: dict, panels: dict[str, pd.DataFrame]) -> dict:
    last_processed = deliverable.get("latest_trading_date") or str(panels["close"].index[-1].date())
    last_rebalance = deliverable.get("latest_rebalance_date") or last_processed
    dates = panels["close"].index
    if pd.Timestamp(last_processed) < dates[0]:
        raise RuntimeError(
            f"seed 信号日 {last_processed} 早于滚动缓存起点 {dates[0].date()}，"
            "无法恢复调仓相位，请重新生成生产种子"
        )
    between = dates[(dates > pd.Timestamp(last_rebalance)) & (dates <= pd.Timestamp(last_processed))]
    return {
        "last_processed_date": last_processed,
        "last_rebalance_date": last_rebalance,
        "trading_days_since_rebalance": int(len(between) % 10),
        "holdings_by_n": {
            str(n): [
                item["code"]
                for item in deliverable.get("configs", {}).get(str(n), {}).get("current_holdings", [])
            ]
            for n in live.CONFIG_SIZES
        },
        "last_success_wall_date": None,
        "last_success_market_date": last_processed,
    }


def load_state(path: str | Path, deliverable: dict, panels: dict[str, pd.DataFrame]) -> dict:
    target = Path(path)
    if target.exists():
        try:
            state = json.loads(target.read_text(encoding="utf-8"))
            if state.get("last_processed_date") and state.get("holdings_by_n"):
                if pd.Timestamp(state["last_processed_date"]) < panels["close"].index[0]:
                    raise RuntimeError("持久化状态已落在滚动缓存之外，请重新灌种")
                return state
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 状态文件损坏，按交付物重建: {exc}", flush=True)
    return _initial_state(deliverable, panels)


def _record_rebalance(
    deliverable: dict,
    n: int,
    date: pd.Timestamp,
    old: list[str],
    new: list[str],
    names: dict[str, str],
) -> None:
    cfg = deliverable["configs"][str(n)]
    old_set, new_set = set(old), set(new)
    bought = sorted(new_set - old_set)
    sold = sorted(old_set - new_set)
    entry = {
        "rebalance_date": str(date.date()),
        "holdings_count": len(new),
        "bought": [{"code": code, "name": names.get(code, code)} for code in bought],
        "sold": [{"code": code, "name": names.get(code, code)} for code in sold],
        "turnover_pct": round(len(bought) / len(new) * 100, 1) if new else 0.0,
    }
    history = [entry]
    history.extend(
        item for item in cfg.get("rebalance_history", [])
        if item.get("rebalance_date") != entry["rebalance_date"]
    )
    cfg["rebalance_history"] = history[:6]


def _portfolio_value(cfg: dict, init_cash: float = 10_000_000.0) -> float:
    curve = cfg.get("equity_curve", [])
    if curve:
        try:
            return init_cash * float(curve[-1]["strategy_nav"])
        except (KeyError, TypeError, ValueError):
            pass
    current = sum(float(item.get("market_val", 0.0)) for item in cfg.get("current_holdings", []))
    return current or init_cash


def _cap_distribution(holdings: list[dict]) -> dict:
    caps = [float(item["float_cap_billion"]) for item in holdings if item.get("float_cap_billion", 0) > 0]
    return {
        "under_20b": sum(cap < 20.0 for cap in caps),
        "between_20_30b": sum(20.0 <= cap < 30.0 for cap in caps),
        "between_30_50b": sum(30.0 <= cap < 50.0 for cap in caps),
        "above_50b": sum(cap >= 50.0 for cap in caps),
        "median_cap": round(float(np.median(caps)), 2) if caps else 0.0,
        "min_cap": round(float(min(caps)), 2) if caps else 0.0,
        "max_cap": round(float(max(caps)), 2) if caps else 0.0,
    }


def update_deliverable(
    deliverable: dict,
    panels: dict[str, pd.DataFrame],
    state: dict,
    names: dict[str, str],
    validation: dict,
    mature_codes: set[str] | None = None,
) -> tuple[dict, dict, bool]:
    scores = live.production_scores(panels, mature_codes=mature_codes)
    latest = pd.Timestamp(panels["close"].index[-1])
    last_processed = pd.Timestamp(state["last_processed_date"])
    new_dates = scores.index[(scores.index > last_processed) & (scores.index <= latest)]
    rebalanced = False

    for date in new_dates:
        state["trading_days_since_rebalance"] = int(
            state.get("trading_days_since_rebalance", 0)
        ) + 1
        if state["trading_days_since_rebalance"] < 10:
            state["last_processed_date"] = str(date.date())
            continue

        for n in live.CONFIG_SIZES:
            key = str(n)
            old = list(state["holdings_by_n"].get(key, []))
            new = live.buffered_select(scores.loc[date], old, n, buffer_mult=2.0)
            if len(new) != n:
                raise RuntimeError(f"{date.date()} N={n} 只有 {len(new)} 只有效候选，拒绝发布")
            _record_rebalance(deliverable, n, pd.Timestamp(date), old, new, names)
            state["holdings_by_n"][key] = new
        state["trading_days_since_rebalance"] = 0
        state["last_rebalance_date"] = str(pd.Timestamp(date).date())
        state["last_processed_date"] = str(pd.Timestamp(date).date())
        rebalanced = True

    if len(new_dates):
        state["last_processed_date"] = str(pd.Timestamp(new_dates[-1]).date())

    all_codes = sorted({
        code
        for held in state["holdings_by_n"].values()
        for code in held
    })
    snapshots = fetch_live_snapshots(all_codes)
    raw_latest = panels.get("close_raw", panels["close"]).loc[latest]
    score_latest = scores.loc[latest]

    for n in live.CONFIG_SIZES:
        key = str(n)
        cfg = deliverable["configs"][key]
        old_by_code = {item["code"]: item for item in cfg.get("current_holdings", [])}
        total_value = _portfolio_value(cfg)
        holdings = []
        for code in state["holdings_by_n"].get(key, []):
            old = old_by_code.get(code, {})
            snap = snapshots.get(code, {})
            fallback_px = raw_latest.get(code, np.nan)
            price = float(snap.get("price") or (fallback_px if pd.notna(fallback_px) else old.get("price", 0.0)))
            if not math.isfinite(price):
                price = float(old.get("price", 0.0) or 0.0)
            score_value = float(score_latest.get(code, math.nan))
            factor_score = (
                round(score_value, 4)
                if math.isfinite(score_value)
                else float(old.get("factor_score", 0.0) or 0.0)
            )
            target_value = total_value / n
            shares = int(target_value / (price * 100)) * 100 if price > 0 else 0
            holdings.append({
                "code": code,
                "display_code": code[2:],
                "name": snap.get("name") or names.get(code) or old.get("name", code),
                "target_weight": round(100.0 / n, 2),
                "price": round(price, 2),
                "change_pct": round(float(snap.get("change_pct", old.get("change_pct", 0.0))), 2),
                "float_cap_billion": float(snap.get("float_cap_billion", old.get("float_cap_billion", 0.0))),
                "total_cap_billion": float(snap.get("total_cap_billion", old.get("total_cap_billion", 0.0))),
                "shares": shares,
                "market_val": round(shares * price, 2),
                "factor_score": factor_score,
            })
        cfg["current_holdings"] = sorted(
            holdings,
            key=lambda item: item["float_cap_billion"] if item["float_cap_billion"] > 0 else 9999,
        )
        cfg["cap_distribution"] = _cap_distribution(cfg["current_holdings"])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    deliverable["update_time"] = now
    deliverable["latest_trading_date"] = str(latest.date())
    deliverable["latest_rebalance_date"] = state["last_rebalance_date"]
    deliverable["runtime"] = {
        "mode": "incremental",
        "status": "healthy",
        "data_source": "tencent_fqkline",
        "cache_rows": int(len(panels["close"])),
        "cache_stocks": int(len(panels["close"].columns)),
        "validation": validation,
        "updated_at": now,
    }
    return deliverable, state, rebalanced


def run_once(args: argparse.Namespace) -> dict:
    out_path = Path(args.out)
    if not out_path.exists():
        raise FileNotFoundError(f"缺少 seed 交付物: {out_path}")
    deliverable = json.loads(out_path.read_text(encoding="utf-8"))
    expected = expected_trading_date(args.end)
    cached = live.load_market_cache(args.cache_dir)
    refresh_universe_if_due(args.cache_dir)
    codes = load_codes(args.meta, Path(args.cache_dir) / "universe.json")
    print(
        f"[smallcap-live] 目标交易日 {expected.date()}，缓存="
        f"{cached['close'].index[-1].date() if cached is not None else '空'}，股票={len(codes)}",
        flush=True,
    )

    close_rows, amount_rows, raw_rows, fetched_names, stage_dir = fetch_market_rows(
        codes=codes,
        expected=expected,
        cache_dir=args.cache_dir,
        bootstrap=cached is None,
        workers=args.workers,
    )
    merged = live.merge_market_rows(cached, close_rows, amount_rows, raw_rows)
    cleaned, bad_ticks = panel.clean_bad_ticks(merged)
    validation = live.validate_latest_cross_section(
        cached, cleaned, expected, min_coverage=args.min_coverage
    )
    validation["bad_ticks_masked"] = int(bad_ticks)
    live.save_market_cache(
        args.cache_dir,
        cleaned["close"],
        cleaned["amount"],
        cleaned["close_raw"],
    )

    meta = pd.read_csv(args.meta).drop_duplicates("code")
    names = meta.set_index("code")["name"].fillna("").astype(str).to_dict()
    names.update({code: name for code, name in fetched_names.items() if name})
    bars = (
        pd.to_numeric(meta["bars"], errors="coerce")
        if "bars" in meta.columns
        else pd.Series(0, index=meta.index)
    )
    mature_codes = set(meta.loc[bars >= 250, "code"].astype(str))
    state_path = Path(args.cache_dir) / "state.json"
    state = load_state(state_path, deliverable, cleaned)
    os.environ.setdefault("SMALLCAP_STATE_DIR", str(Path(args.cache_dir) / "notify"))
    deliverable, state, rebalanced = update_deliverable(
        deliverable, cleaned, state, names, validation, mature_codes=mature_codes
    )
    state["last_success_wall_date"] = datetime.now().strftime("%Y-%m-%d")
    state["last_success_market_date"] = str(expected.date())
    live.atomic_write_json(out_path, deliverable)
    live.atomic_write_json(state_path, state)
    shutil.rmtree(stage_dir, ignore_errors=True)

    if rebalanced:
        notify_rebalance_if_needed(deliverable)
    print(
        f"[smallcap-live] 发布成功: signal={deliverable['latest_trading_date']} "
        f"rebalance={deliverable['latest_rebalance_date']} coverage={validation['coverage']:.1%}",
        flush=True,
    )
    return deliverable


def mark_runtime_failure(out_path: str | Path, error: Exception) -> None:
    """保留上一份有效信号，只把运行状态标成降级。"""
    target = Path(out_path)
    if not target.exists():
        return
    try:
        deliverable = json.loads(target.read_text(encoding="utf-8"))
        runtime = dict(deliverable.get("runtime", {}))
        runtime.update({
            "mode": "incremental",
            "status": "degraded",
            "last_error": str(error),
            "failed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        deliverable["runtime"] = runtime
        live.atomic_write_json(target, deliverable)
    except Exception as mark_error:  # noqa: BLE001
        print(f"[WARN] 写入降级状态失败: {mark_error}", file=sys.stderr, flush=True)


def run_daemon(args: argparse.Namespace) -> None:
    fail_count = 0
    startup_pending = True
    while True:
        now = datetime.now()
        state_path = Path(args.cache_dir) / "state.json"
        last_market_date = None
        if state_path.exists():
            try:
                saved_state = json.loads(state_path.read_text(encoding="utf-8"))
                last_market_date = saved_state.get("last_success_market_date") or saved_state.get(
                    "last_processed_date"
                )
            except Exception:  # noqa: BLE001
                pass
        after_close = now.weekday() < 5 and (
            now.hour > 15 or (now.hour == 15 and now.minute >= 30)
        )
        market_advanced = False
        if after_close:
            try:
                latest_market = expected_trading_date()
                market_advanced = last_market_date is None or latest_market > pd.Timestamp(
                    last_market_date
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] 轮询最新交易日失败: {exc}", flush=True)
        scheduled = after_close and market_advanced
        if startup_pending or scheduled:
            try:
                run_once(args)
                fail_count = 0
            except Exception as exc:  # noqa: BLE001
                fail_count += 1
                mark_runtime_failure(args.out, exc)
                message = (
                    f"A股小微盘增量管线失败（连续 {fail_count} 次）\n"
                    f"错误: {exc}\n{traceback.format_exc()}"
                )
                print(f"[ERROR] {message}", file=sys.stderr, flush=True)
                if fail_count <= 3:
                    send_alert("🚨【A股小微盘增量数据管线失败】", message, important=True)
            startup_pending = False
        time.sleep(300 if fail_count == 0 else 900)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ARM1 A股小微盘增量信号生产服务")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="执行一次后退出")
    mode.add_argument("--daemon", action="store_true", help="启动每日守护")
    parser.add_argument("--cache-dir", default=os.getenv("SMALLCAP_DATA_DIR", "/data/market"))
    parser.add_argument("--out", default="/app/deliverables/smallcap_strategy.json")
    parser.add_argument("--meta", default=os.path.join(AQ_ROOT, "data", "meta.csv"))
    parser.add_argument("--workers", type=int, default=int(os.getenv("SMALLCAP_FETCH_WORKERS", "12")))
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=float(os.getenv("SMALLCAP_MIN_COVERAGE", "0.95")),
    )
    parser.add_argument("--end", help="测试用：行情请求截止日期 YYYY-MM-DD")
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    if cli_args.daemon:
        run_daemon(cli_args)
    else:
        run_once(cli_args)
