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
ACTIONS_LOG_KEEP_TAIL = 500  # actions.log 保留最近 N 条动作, 避免无限膨胀


def _log(line, log_file, also_print=True):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out = f"[{ts}] {line}"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(out + "\n")
    if also_print:
        print(out, flush=True)


def actions_log_path(cache_dir):
    return os.path.join(cache_dir, "actions.log")


def _read_actions_log(path):
    """读 actions.log JSONL, 返回 list[dict]. 文件不存在或损坏行跳过."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _drop_kind_suffix(kind):
    """'开仓(推断)' -> '开仓', '反手'/'止盈' 原样返回."""
    if kind is None:
        return "?"
    return kind.split("(", 1)[0].strip() or "?"


def _rewrite_actions_log(path, actions):
    """原子重写 actions.log (覆盖写), 用于启动回放重建."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for a in actions:
            f.write(json.dumps(a, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp, path)


def _append_action(path, action):
    """追加一行到 actions.log; 若超过 ACTIONS_LOG_KEEP_TAIL 则裁剪保留尾部."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(action, ensure_ascii=False, default=str) + "\n")
    try:
        st = os.stat(path)
        if st.st_size > 512 * 1024:
            lines = _read_actions_log(path)
            keep = lines[-ACTIONS_LOG_KEEP_TAIL:]
            _rewrite_actions_log(path, keep)
    except Exception:
        pass


def _last_action_from_log(path):
    """读 actions.log 最后一行, 返回 dict 或 None. status 用这个展示真实上一次操作."""
    actions = _read_actions_log(path)
    return actions[-1] if actions else None


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
        side = (cfg.get("tp_side") or "both")
        log(f"      止盈: {cfg['tp_type']} 比例{float(cfg['part_ratio'])*100:.0f}% 冷却{int(cfg.get('cool_bars',20))}根 side={side}")
    else:
        log(f"      止盈: 未启用")
    log(f"数据源: {cfg['data_source']}  日志: {log_file}")
    tg_ok = notifiers.telegram.is_configured()
    wx_ok = notifiers.wechat_work.is_configured()
    mc_ok = notifiers.macos.is_configured()
    fs_ok = notifiers.feishu.is_configured()
    log(f"通知: macOS={'on' if mc_ok else '-'}, "
        f"Telegram={'on' if tg_ok else '未配'}, "
        f"企业微信={'on' if wx_ok else '未配 (写 monitor/wechat_webhook.json 后生效)'}, "
        f"飞书={'on' if fs_ok else '未配 (写 monitor/feishu_webhook.json 后生效)'}")
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
    # actions.log (真实动作历史): daemon 启动时回放 K 线重建历史轨迹 (替代推断语义).
    # 之后每次真实发生 反手/止盈/开仓 都追加一行. status 始终读最后一行 = 真实上一次操作.
    actions_log = actions_log_path(cache_dir)
    replayed = strategy.replay_actions(df_closed, cfg, max_actions=ACTIONS_LOG_KEEP_TAIL)
    if replayed:
        _rewrite_actions_log(actions_log, replayed)
        log(f"已回放 {len(replayed)} 条历史动作, 写入 {actions_log}")
        last_action = _last_action_from_log(actions_log)
        # 真实动作存在时也回填到 state.json 的 last_action 字段, 保持向下兼容.
        if last_action:
            la = dict(last_action)
            la.pop("idx", None)
            la["kind"] = _drop_kind_suffix(la.get("kind"))
            cur_state["last_action"] = la
    elif cur_state["position"] != 0:
        # 回放无动作但确有持仓 (极少数: 回放起点之前的旧仓位): 标注为推断, 仅占位.
        last_action = {
            "kind": "开仓(推断)",
            "price": cur_state["entry_price"],
            "time": cur_state["entry_time"],
            "pos": cur_state["position"],
            "pos_size": cur_state["pos_size"],
            "descr": f"推断已{cur_state['position_str']} @ {cur_state['entry_price']:.4g} (启动时, K 线回放窗口内无完整轨迹)",
        }
        cur_state["last_action"] = last_action
    else:
        last_action = None
        cur_state["last_action"] = None

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

    # 盘中实时探针设置 (cfg.realtime_quote)
    rt_source = (cfg.get("realtime_quote") or "none").lower()
    rt_interval = int(cfg.get("realtime_interval") or 30)
    if rt_source != "none":
        log(f"开始持续监控 (对齐{tf}收盘 + 盘中实时探针 [源={rt_source}, 间隔={rt_interval}s], Ctrl+C 退出)...")
    else:
        log(f"开始持续监控 (对齐{tf}收盘, Ctrl+C 退出)...")
    prev_probe_state = None  # 上一个盘中探针 state
    try:
        while True:
            sleep_s = strategy.next_close_seconds(tf) if rt_source == "none" else min(rt_interval, strategy.next_close_seconds(tf))
            time.sleep(max(sleep_s, 1))

            # === 盘中实时探针: 未到收盘就用实时现价预演一次 ===
            if rt_source != "none" and strategy.next_close_seconds(tf) > 5:
                try:
                    rt = datasources.fetch_realtime(rt_source, cfg["symbol"])
                    probe_price = float(rt["last"])
                    # 用已收根 + 探针价, 跑一遍 live_probe
                    probe_state = strategy.live_probe(df_closed, probe_price, cfg)
                    # 把实时报价信息附加到 state 中
                    probe_state["realtime_quote"] = {
                        "source": rt["source"], "name": rt.get("name", ""),
                        "last": probe_price, "change": rt.get("change", 0),
                        "change_pct": rt.get("change_pct", 0),
                        "time": rt.get("time") or rt.get("datetime", ""),
                    }
                    probe_changes = strategy.probe_change_summary(prev_probe_state, probe_state)
                    if probe_changes:
                        for c in probe_changes:
                            log(f"⚠ {c}")
                        # 盘中预警 = 比正式信号提前通知 (但不更新 last_action 因为还没收盘)
                        # 每个变化只在第一次出现时推一次, 之后 prev_probe 接力避免重复推
                        notifiers.notify_all(
                            f"[{cfg['name']}] 盘中预警",
                            "\n".join(probe_changes) + f"\n\n实时报价 {probe_price} ({rt.get('change_pct',0):+.2f}%), "
                            f"预演结果可能因尾盘波动而变化, 仅供参考. "
                            f"\nK线收盘后会有正式信号确认通知.",
                            important=False,
                        )
                    # 保存 probe 内容到 state.json 给 status 查看参考
                    cur_state_copy = dict(cur_state)
                    cur_state_copy["realtime_probe"] = probe_state["realtime_quote"]
                    cur_state_copy["probe_preview"] = {k: probe_state[k] for k in
                        ("position", "pos_size", "ema", "bull_streak", "bear_streak",
                         "dev_pct", "rsi") if k in probe_state}
                    with open(state_file, "w") as f:
                        json.dump(cur_state_copy, f, ensure_ascii=False, indent=2, default=str)
                    prev_probe_state = probe_state
                except Exception as e:
                    log(f"盘中探针失败 (继续主循环): {e}", also_print=False)
            # === 收盘后正式信号处理 (主路径不变) ===
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
                        # 更新最近一次操作: 真实发生则追加到 actions.log, state.json 里也回填一份.
                        la_kind = "反手" if is_reversal else "止盈"
                        if "新开仓" in changes[-1]:
                            la_kind = "开仓"
                        la_record = {
                            "kind": la_kind,
                            "price": float(cur_state["live_price"]),
                            "time": cur_state["last_closed"],
                            "pos": int(cur_state["position"]),
                            "pos_size": float(cur_state["pos_size"]),
                            "tp_count_this_trade": int(cur_state.get("tp_count_this_trade", 0)),
                            "descr": changes[-1],
                        }
                        try:
                            _append_action(actions_log, la_record)
                        except Exception as e_append:
                            log(f"actions.log 追加失败 (忽略, state.json 仍会更新): {e_append}", also_print=False)
                        cur_state["last_action"] = la_record
                        notifiers.notify_all(
                            f"[{cfg['name']}] 信号变化" if is_reversal else f"[{cfg['name']}] 止盈触发",
                            strategy.notify_message(cur_state, cfg, cb_threshold, changes),
                            important=is_reversal,
                        )
                        bars_since_hb = 0
                        # 正式信号触发后重置 prev_probe (新起点)
                        prev_probe_state = None
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
                    log(f"K线收盘数据未更新 (探针仍在跑), {RETRY_INTERVAL}s后重试...", also_print=False)
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
