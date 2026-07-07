"""
TRHRP 多市场 regime 策略 daemon.

与 EMA 反手策略完全不同的另一套范式 (在 monitor 端独立子系统, 共用通知/落盘框架但不共享配置):
  - "持仓" 不是单一方向 1/-1/0, 而是 N 个市场 (默认 6 个: 沪深300/中证500/恒生指数/恒生科技/SPY/QQQ)
    每个市场一种 regime (risk_on/moderate/risk_off), 进而决定股/GLD/SGOV 配比,
    再叠加 z-score 偏离规则调整 equity 比例. "当前仓位水平"就是这个表格.
  - 信号是日度 T 日收盘生成, T+1 生效. 不做盘中预演.
  - daemon 按 check_interval_minutes 周期性拉一次完整快照, 与上次快照对比:
      任一市场 nextRegime 变化即写 actions.log + 发通知 + 落盘 state.json.
  - 配置唯一来源: monitor/strategies_trhrp.json (与 EMA 反手 strategies.json 完全独立).
  - 策略口径实现: monitor/trhrp_strategy.py (与 ba 项目同源但独立维护).

被 monitor.py 作为子进程拉起, 入口 run(name).
复用:
  - caches/<name>/{state.json, actions.log, monitor.log, stdout.log, daemon.pid}
  - notifiers 通知框架 (macOS/telegram/企业微信)
  - daemon.py 里的 actions.log 读写工具 (_log/_append_action/_last_action_from_log)
"""
import os
import sys
import time
import json
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from monitor import notifiers, trhrp_strategy
from monitor.daemon import _log, _append_action

REGIME_LABEL = {"risk_on": "RISK_ON", "moderate": "MODERATE", "risk_off": "RISK_OFF"}


def _cache_dir(name):
    d = os.path.join(_HERE, "caches", name)
    os.makedirs(d, exist_ok=True)
    return d


def _load_trhrp_cfg():
    """从 monitor/strategies_trhrp.json 加载 TRHRP 配置 (单 daemon, 一个 name)."""
    p = os.path.join(_HERE, "strategies_trhrp.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"找不到 TRHRP 配置: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _state_file_path(cache_dir):
    return os.path.join(cache_dir, "state.json")


def _actions_log_path(cache_dir):
    return os.path.join(cache_dir, "actions.log")


def _yf_cache_dir(cache_dir):
    """yfinance 拉下来的 OHLC 缓存目录 (12h 内复用, 避免重复打 yfinance 限频)."""
    d = os.path.join(cache_dir, "yf_cache")
    os.makedirs(d, exist_ok=True)
    return Path(d)


def _write_state(state_file, payload):
    tmp = state_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, state_file)


def _build_state_from_snapshot(snap, cfg):
    """从 trhrp_strategy.build_snapshot() 返回结构裁剪成 daemon state.json 字段."""
    markets = []
    for m in snap.get("markets") or []:
        markets.append({
            "marketGroup": m.get("marketGroup"),
            "label": m.get("label"),
            "ticker": m.get("ticker"),
            "proxy": m.get("proxy"),
            "signalDate": m.get("signalDate"),
            "price": m.get("price"),
            "volPct": m.get("volPct"),
            "volP60Pct": m.get("volP60Pct"),
            "medianVolPct": m.get("medianVolPct"),
            "momPct": m.get("momPct"),
            "crashTriggerVolPct": m.get("crashTriggerVolPct"),
            "crashMode": m.get("crashMode"),
            "crashZscore": m.get("crashZscore"),
            "priceZScore252": m.get("priceZScore252"),
            "currentRegime": m.get("currentRegime"),
            "nextRegime": m.get("nextRegime"),
            "currentEmoji": m.get("currentEmoji"),
            "nextEmoji": m.get("nextEmoji"),
            "currentRegimeReason": m.get("currentRegimeReason"),
            "currentRegimeNextTrigger": m.get("currentRegimeNextTrigger"),
            "nextRegimeReason": m.get("nextRegimeReason"),
            "nextRegimeNextTrigger": m.get("nextRegimeNextTrigger"),
            "changed": bool(m.get("changed")),
            "overlayRuleLabel": m.get("overlayRuleLabel"),
            "overlayAction": m.get("overlayAction"),
            "overlayEquityDeltaPct": m.get("overlayEquityDeltaPct"),
            "overlayRecommendationText": m.get("overlayRecommendationText"),
            "allocationText": m.get("allocationText"),
            "overlayAdjustedAllocationText": m.get("overlayAdjustedAllocationText") or m.get("allocationText"),
        })
    return {
        "fetchedAt": snap.get("fetchedAt"),
        "asOfDate": snap.get("asOfDate"),
        "riskOnCount": snap.get("riskOnCount", 0),
        "moderateCount": snap.get("moderateCount", 0),
        "riskOffCount": snap.get("riskOffCount", 0),
        "changedMarkets": snap.get("changedMarkets", 0),
        "telegramEnabled": bool(snap.get("telegramEnabled")),
        "stale": bool(snap.get("stale")),
        "error": snap.get("error"),
        "warnings": snap.get("warnings") or [],
        "markets": markets,
        "message": snap.get("message"),
    }


def _regime_summary(state):
    return (f"🟢{state.get('riskOnCount',0)} 🟡{state.get('moderateCount',0)} 🔴{state.get('riskOffCount',0)}"
            f" (变化 {state.get('changedMarkets',0)})")


def _market_line(m):
    """每个市场仓位水平单行签."""
    cur_r = REGIME_LABEL.get(m.get("currentRegime"), "?")
    nxt_r = REGIME_LABEL.get(m.get("nextRegime"), "?")
    bal = m.get("allocationText") or "-"
    adj = m.get("overlayAdjustedAllocationText") or bal
    z = m.get("priceZScore252")
    z_str = f"{z:+.2f}σ" if isinstance(z, (int, float)) else "-"
    overlay_text = m.get("overlayRecommendationText") or "-"
    return f"{m.get('label','?')} [今日 {cur_r} -> 次日 {nxt_r}] | 基础 {bal} | 叠加 {adj} | z={z_str} | {overlay_text}"


def _compare_regime_changes(prev_state, cur_state):
    """对比 prev/cur 两份 daemon state, 返回 nextRegime 真实变化的 list[dict]."""
    if not prev_state or not prev_state.get("markets"):
        return []
    prev_map = {m.get("label"): m for m in prev_state.get("markets") or []}
    out = []
    for cur_m in cur_state.get("markets") or []:
        label = cur_m.get("label")
        prev_m = prev_map.get(label)
        if not prev_m:
            continue
        if prev_m.get("nextRegime") != cur_m.get("nextRegime"):
            out.append({
                "label": label,
                "marketGroup": cur_m.get("marketGroup"),
                "prevRegime": prev_m.get("nextRegime"),
                "curRegime": cur_m.get("nextRegime"),
                "prevAlloc": prev_m.get("allocationText"),
                "curAlloc": cur_m.get("allocationText"),
                "overlayAction": cur_m.get("overlayAction"),
                "overlayDeltaPct": cur_m.get("overlayEquityDeltaPct") or 0.0,
            })
    return out


def _action_record_from_change(chg):
    """把一条 regime_change 打包成 actions.log 一条 JSON 行."""
    descr = (f"{chg['label']} {REGIME_LABEL.get(chg['prevRegime'],'?')} -> "
             f"{REGIME_LABEL.get(chg['curRegime'],'?')}  仓位 "
             f"{chg['prevAlloc'] or '-'} -> {chg['curAlloc'] or '-'}")
    return {
        "kind": "regime_change",
        "label": chg.get("label"),
        "marketGroup": chg.get("marketGroup"),
        "prevRegime": chg.get("prevRegime"),
        "curRegime": chg.get("curRegime"),
        "prevAlloc": chg.get("prevAlloc"),
        "curAlloc": chg.get("curAlloc"),
        "overlayAction": chg.get("overlayAction"),
        "overlayDeltaPct": chg.get("overlayDeltaPct"),
        "descr": descr,
    }


def _notify_changes(cfg, chgs, cur_state):
    if not chgs:
        return
    name = cfg["name"]
    cur_map = {m.get("label"): m for m in (cur_state.get("markets") or [])}
    as_of = cur_state.get("asOfDate") or "-"
    lines = [f"TRHRP 档位切换 ({len(chgs)} 个市场) | 信号日 {as_of}, T+1 生效"]
    # 每条变化明确显示: 上次预测档位 -> 本次预测档位, 以及仓位变化, 信号日期, 推理
    for c in chgs:
        m = cur_map.get(c.get("label"))
        prev_r = REGIME_LABEL.get(c.get("prevRegime"), "?")
        cur_r = REGIME_LABEL.get(c.get("curRegime"), "?")
        prev_alloc = c.get("prevAlloc") or "-"
        cur_alloc = c.get("curAlloc") or "-"
        sig_date = (m or {}).get("signalDate") or as_of
        z = (m or {}).get("priceZScore252")
        z_str = f"{z:+.2f}σ" if isinstance(z, (int, float)) else "-"
        overlay_text = (m or {}).get("overlayRecommendationText") or "-"
        lines.append(
            f"{c['label']}: {prev_r} → {cur_r} | 仓位 {prev_alloc} → {cur_alloc} "
            f"| z={z_str} | {overlay_text} ⚠️"
        )
        lines.append(f"  信号日 {sig_date} (T+1 生效, 次日开盘调仓)")
        if m:
            # 在通知里带上 "为什么这次会被判定为新档位" 的解释
            reason = m.get("nextRegimeReason")
            if reason:
                lines.append(f"  ↳ 判定依据: {reason}")
            nt = m.get("nextRegimeNextTrigger")
            if nt and nt != "-":
                lines.append(f"  ↳ 维持/下一步: {nt}")
    lines.append("")
    lines.append(f"当前持仓分布: {_regime_summary(cur_state)}")
    notifiers.notify_all(f"[{name}] 档位切换", "\n".join(lines), important=True)


def _bootstrap_log(prev_state, cur_state, log_func):
    """daemon 启动时把 "上次 state.json -> 当前" 之间 regime 变化一次性记录到 actions.log, 不发通知."""
    chgs = _compare_regime_changes(prev_state, cur_state)
    if chgs:
        log_func(f"启动时检测到与上次 state.json 间有 {len(chgs)} 条 regime 变化 (仅记录 actions.log, 不通知)")
        for c in chgs:
            log_func(f"  ↪ {c['label']} {REGIME_LABEL.get(c['prevRegime'],'?')} -> {REGIME_LABEL.get(c['curRegime'],'?')}")


def _fetch_snapshot(cfg, yf_cache):
    """调 monitor 端 TRHRP 策略, 拉一次完整快照 (含数据拉取 + 指标 + overlay). 失败 raise."""
    return trhrp_strategy.build_snapshot(cfg, yf_cache)


def _fake_error_state(err_text):
    return {
        "fetchedAt": None, "asOfDate": None, "markets": [],
        "riskOnCount": 0, "moderateCount": 0, "riskOffCount": 0, "changedMarkets": 0,
        "telegramEnabled": False, "stale": True, "error": err_text, "warnings": [], "message": "",
    }


def run(name):
    cfg = _load_trhrp_cfg()
    if cfg.get("name") != name:
        raise ValueError(f"strategies_trhrp.json name={cfg.get('name')!r} 与命令行参数 {name!r} 不匹配")

    cache_dir = _cache_dir(name)
    state_file = _state_file_path(cache_dir)
    log_file = os.path.join(cache_dir, "monitor.log")
    actions_log = _actions_log_path(cache_dir)
    yf_cache = _yf_cache_dir(cache_dir)

    def log(line, also_print=True):
        _log(line, log_file, also_print=also_print)

    log("=" * 56)
    log(f"[{cfg['name']}] TRHRP 多市场 regime 监控启动 (monitor 端独立实现)")
    log(f"市场 UNIVERSE: {len(cfg.get('markets') or [])} 个 — "
        f"{', '.join(m.get('label','?') for m in (cfg.get('markets') or []))}")
    log(f"检查间隔: {int(cfg.get('check_interval_minutes', 60))} 分钟")
    log(f"状态文件: {state_file}")
    log(f"动作历史: {actions_log}")
    log(f"YFinance 缓存: {yf_cache}")
    tg_ok = notifiers.telegram.is_configured()
    wx_ok = notifiers.wechat_work.is_configured()
    mc_ok = notifiers.macos.is_configured()
    fs_ok = notifiers.feishu.is_configured()
    log(f"通知: macOS={'on' if mc_ok else '-'}, Telegram={'on' if tg_ok else '未配'}, 企业微信={'on' if wx_ok else '未配'}, 飞书={'on' if fs_ok else '未配'}")
    log("=" * 56)

    # 读取上一次 state.json 作对比基准
    prev_state = None
    if os.path.exists(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                prev_state = json.load(f)
            log(f"读取上次 state.json: fetched={prev_state.get('fetchedAt')}, "
                f"asOf={prev_state.get('asOfDate')}, regime={_regime_summary(prev_state)}")
        except Exception as e:
            log(f"读 state.json 失败 (当作首次运行): {e}")
            prev_state = None

    # 首次拉快照
    try:
        snap = _fetch_snapshot(cfg, yf_cache)
    except Exception as e:
        log(f"首次拉快照失败: {e}")
        traceback.print_exc()
        snap = _fake_error_state(str(e))
    cur_state = _build_state_from_snapshot(snap, cfg)
    _write_state(state_file, cur_state)
    log(f"首次快照完成: fetched={cur_state.get('fetchedAt')}, asOf={cur_state.get('asOfDate')}, "
        f"regime={_regime_summary(cur_state)}, error={cur_state.get('error') or '-'}")
    if not cur_state.get("error"):
        for m in cur_state.get("markets") or []:
            log(f"  {_market_line(m)}")

    # 启动时与 prev_state 比较 regime 变化, 只记录 actions.log, 不通知 (避免重启轰炸)
    if prev_state and not cur_state.get("error"):
        _bootstrap_log(prev_state, cur_state, log)

    if os.environ.get("MONITOR_DRY_RUN") == "1":
        log("DRY-RUN: 已完成首轮快照, 退出主循环.")
        return

    interval_s = max(int(cfg.get("check_interval_minutes", 60)) * 60, 300)
    log(f"开始周期监控 (每 {interval_s // 60} 分钟拉一次, Ctrl+C 退出)...")

    try:
        while True:
            time.sleep(interval_s)
            try:
                snap = _fetch_snapshot(cfg, yf_cache)
            except Exception as e:
                log(f"拉快照失败: {e}")
                traceback.print_exc()
                continue
            new_state = _build_state_from_snapshot(snap, cfg)
            chgs = _compare_regime_changes(cur_state, new_state)
            # 写 actions.log (每条 regime 变化一行)
            for chg in chgs:
                la = _action_record_from_change(chg)
                try:
                    _append_action(actions_log, la)
                except Exception as e_app:
                    log(f"actions.log 追加失败 (忽略): {e_app}", also_print=False)
            _write_state(state_file, new_state)
            log(f"快照刷新: fetched={new_state.get('fetchedAt')}, asOf={new_state.get('asOfDate')}, "
                f"regime={_regime_summary(new_state)}")
            for chg in chgs:
                log(f"🚨 {chg['label']} {REGIME_LABEL.get(chg['prevRegime'],'?')} -> "
                    f"{REGIME_LABEL.get(chg['curRegime'],'?')}  {chg['prevAlloc'] or '-'} -> {chg['curAlloc'] or '-'}")
            # 通知
            try:
                if cfg.get("notify_on_change", True):
                    _notify_changes(cfg, chgs, new_state)
            except Exception as e_notify:
                log(f"通知发送失败 (忽略): {e_notify}", also_print=False)
            cur_state = new_state
    except KeyboardInterrupt:
        log("监控已停止。")
        print(f"\n[{cfg['name']}] 监控已停止。状态: {state_file}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="strategies_trhrp.json 里的 name (默认 TRHRP)")
    args = ap.parse_args()
    run(args.name)
