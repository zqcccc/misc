"""
单品种 daemon 主循环.
被 monitor.py 作为子进程拉起. 入口 run(cfg_path, cli_overrides).
对齐 K 线收盘轮询 -> 计算指标/持仓 -> 信号变化时通知 -> state.json 落盘 -> 心跳日志.
"""
import os
import sys
import time
import json
import traceback

# 把 misc/ 加在 path 最前面, 让 `import monitor` 解析到 misc/monitor/ 包 (而非同名模块 monitor.py).
_HERE = os.path.dirname(os.path.abspath(__file__))        # monitor/
_PARENT = os.path.dirname(_HERE)                          # misc/
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from monitor import datasources, notifiers, strategy

HEARTBEAT_EVERY_N_BARS = 5
RETRY_INTERVAL = 10
EXCHANGE_TIMEOUT = 30


def _log(line, log_file, also_print=True):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out = f"[{ts}] {line}"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(out + "\n")
    if also_print:
        print(out, flush=True)


def _load_cfg(name):
    path = os.path.join(_HERE, "strategies.json")
    with open(path) as f:
        data = json.load(f)
    for s in data["strategies"]:
        if s["name"] == name:
            return s
    raise ValueError(f"strategy not found: {name}")


def _cache_dir(name):
    d = os.path.join(_HERE, "caches", name)
    os.makedirs(d, exist_ok=True)
    return d


def run(name, overrides=None):
    cfg = _load_cfg(name)
    if overrides:
        cfg = dict(cfg)
        cfg.update(overrides)

    cache_dir = _cache_dir(name)
    state_file = os.path.join(cache_dir, "state.json")
    log_file = os.path.join(cache_dir, "monitor.log")

    def log(line, also_print=True):
        _log(line, log_file, also_print=also_print)

    log("=" * 56)
    log(f"[{cfg['name']}] {cfg['symbol']} EMA反手监控启动 (tf={cfg.get('timeframe','15m')})")
    cb_float = float(cfg.get("cb_float", 0) or 0)
    if cb_float > 0:
        log(f"参数: EMA{cfg['ema_span']} + cb连续={cb_float:.2f} (阈值{cb_float*0.95:.2f}) + {float(cfg['breakout_pct'])*100}%")
    else:
        log(f"参数: EMA{cfg['ema_span']} + cb={int(cfg['confirm_bars'])}根整数 + {float(cfg['breakout_pct'])*100}%")
    if cfg.get("tp_enabled", True) and cfg.get("tp_type") not in (None, "none"):
        log(f"      止盈: {cfg['tp_type']} 比例{float(cfg['part_ratio'])*100:.0f}% 冷却{int(cfg.get('cool_bars',20))}根")
    else:
        log(f"      止盈: 未启用")
    log(f"数据源: {cfg['data_source']}  日志: {log_file}")
    tg_ok = notifiers.telegram.is_configured()
    wx_ok = notifiers.wechat_work.is_configured()
    mc_ok = notifiers.macos.is_configured()
    log(f"通知: macOS={'on' if mc_ok else '-'}, "
        f"Telegram={'on' if tg_ok else '未配'}, "
        f"企业微信={'on' if wx_ok else '未配 (写 monitor/wechat_webhook.json 后生效)'}")
    log("=" * 56)

    tf = cfg.get("timeframe", "15m")
    ema_span = int(cfg["ema_span"])
    history_bars = int(cfg.get("history_bars", max(1500, ema_span * 3 + 200)))
    warmup_target = ema_span * 3 + 200

    # 首次拉取
    df = None
    while df is None:
        try:
            df = datasources.fetch_recent(
                cfg["data_source"], cfg["symbol"], tf, history_bars, warmup_target=warmup_target,
            )
            df, cb_threshold = strategy.compute_indicators(df, cfg)
            break
        except Exception as e:
            log(f"首次拉取失败: {e}, 5秒后重试...")
            traceback.print_exc()
            time.sleep(5)

    tf_min = strategy.tf_minutes(tf)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    is_closed = (now - df.iloc[-1]["timestamp"]).total_seconds() >= tf_min * 60
    df_closed = df if is_closed else df.iloc[:-1].reset_index(drop=True)
    live_price = df.iloc[-1]["close"]
    pos = strategy.infer_position(df_closed, cfg)
    cur_state = strategy.snapshot(df_closed, pos, live_price, cfg)

    log("首次状态快照:")
    print(strategy.format_snapshot(cur_state, cfg, cb_threshold), flush=True)
    log("")
    # 首次不再发"已启动"通知 — 由 monitor.py 在启动完所有 daemon 后汇总推一条, 避免被 12 条轰炸.
    # last_action: 最近一次"反手/止盈/开仓"动作的描述; daemon 启动时仅知当前持仓, 用推断标注.
    if cur_state["position"] != 0:
        last_action = {
            "kind": "开仓(推断)",
            "price": cur_state["entry_price"],
            "time": cur_state["entry_time"],
            "pos": cur_state["position"],
            "pos_size": cur_state["pos_size"],
            "descr": f"推断已{cur_state['position_str']} @ {cur_state['entry_price']:.4g} (启动时)",
        }
    else:
        last_action = None
    cur_state["last_action"] = last_action

    with open(state_file, "w") as f:
        json.dump(cur_state, f, ensure_ascii=False, indent=2, default=str)
    prev_state = cur_state
    last_closed_time = cur_state["last_closed"]
    bars_since_hb = 0

    # 通过环境变量 MONITOR_NOTIFY_STARTED=<pidfile> 触发: 启动后由 supervisor 等本进程就绪后发一条汇总
    # (本进程在 dry-run 时直接退出, 否则进入主循环)

    if os.environ.get("MONITOR_DRY_RUN") == "1":
        log("DRY-RUN: 已完成首轮快照与状态推断, 退出主循环.")
        return

    log(f"开始持续监控 (对齐{tf}收盘, Ctrl+C 退出)...")
    try:
        while True:
            sleep_s = strategy.next_close_seconds(tf)
            if sleep_s > 0:
                time.sleep(sleep_s)
            try:
                df = datasources.fetch_recent(
                    cfg["data_source"], cfg["symbol"], tf, history_bars, warmup_target=warmup_target,
                )
                df, cb_threshold = strategy.compute_indicators(df, cfg)
                now = datetime.now(timezone.utc)
                is_closed = (now - df.iloc[-1]["timestamp"]).total_seconds() >= tf_min * 60
                df_closed = df if is_closed else df.iloc[:-1].reset_index(drop=True)
                live_price = df.iloc[-1]["close"]

                cur_closed_time = df_closed.iloc[-1]["timestamp"].isoformat()
                if cur_closed_time != last_closed_time:
                    pos = strategy.infer_position(df_closed, cfg)
                    cur_state = strategy.snapshot(df_closed, pos, live_price, cfg)
                    changes = strategy.detect_changes(prev_state, cur_state)
                    if changes:
                        out = strategy.format_snapshot(cur_state, cfg, cb_threshold, changes)
                        print("\n" + out, flush=True)
                        is_reversal = any("反手" in c for c in changes)
                        for c in changes:
                            log(f"🚨 {c}")
                        # 更新最近一次操作
                        la_kind = "反手" if is_reversal else "止盈"
                        if "新开仓" in changes[-1]:
                            la_kind = "开仓"
                        cur_state["last_action"] = {
                            "kind": la_kind,
                            "price": cur_state["live_price"],
                            "time": cur_state["last_closed"],
                            "pos": cur_state["position"],
                            "pos_size": cur_state["pos_size"],
                            "descr": changes[-1],
                        }
                        notifiers.notify_all(
                            f"[{cfg['name']}] 信号变化" if is_reversal else f"[{cfg['name']}] 止盈触发",
                            strategy.notify_message(cur_state, cfg, cb_threshold, changes),
                            important=is_reversal,
                        )
                        bars_since_hb = 0
                    else:
                        bars_since_hb += 1
                        if bars_since_hb >= HEARTBEAT_EVERY_N_BARS:
                            hb = strategy.heartbeat_line(cur_state, cfg, cb_threshold)
                            print(hb, flush=True)
                            log(hb, also_print=False)
                            bars_since_hb = 0
                    with open(state_file, "w") as f:
                        json.dump(cur_state, f, ensure_ascii=False, indent=2, default=str)
                    prev_state = cur_state
                    last_closed_time = cur_closed_time
                else:
                    log(f"K线收盘数据未更新, {RETRY_INTERVAL}s后重试...", also_print=False)
                    time.sleep(RETRY_INTERVAL)
            except Exception as e:
                log(f"轮询出错: {e}, 继续...")
                traceback.print_exc()
                time.sleep(30)
    except KeyboardInterrupt:
        log("监控已停止。")
        print(f"\n[{cfg['name']}] 监控已停止。状态: {state_file}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="strategies.json 里的品种 name (如 ETH, BTC, XAG, SOL...)")
    ap.add_argument("--ema", type=int, default=None)
    ap.add_argument("--cb", type=int, default=None)
    ap.add_argument("--cb-float", type=float, default=None)
    ap.add_argument("--bp", type=float, default=None)
    ap.add_argument("--tf", default=None)
    args = ap.parse_args()
    overrides = {}
    if args.ema is not None: overrides["ema_span"] = args.ema
    if args.cb_float is not None and args.cb_float > 0:
        overrides["cb_float"] = args.cb_float
        overrides["confirm_bars"] = int(args.cb_float)
    elif args.cb is not None:
        overrides["confirm_bars"] = args.cb
        overrides["cb_float"] = 0.0
    if args.bp is not None: overrides["breakout_pct"] = args.bp
    if args.tf is not None: overrides["timeframe"] = args.tf
    run(args.name, overrides=overrides or None)
