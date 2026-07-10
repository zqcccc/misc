#!/usr/bin/env python3
"""
EMA 趋势反手策略 · 统一监控入口
================================
一个脚本管理所有品种的策略监控 daemon.

用法:
  python monitor.py list                                   # 列出所有已配置策略 + 是否在跑
  python monitor.py start ETH,SOL                          # 启动指定品种 (逗号分隔)
  python monitor.py start --all                            # 启动全部
  python monitor.py start ETH --foreground                 # 前台跑 (不开 daemon, 调试用)
  python monitor.py start ETH --dry-run                    # 只跑一轮拉数据 + 推断持仓, 不进入主循环
  python monitor.py stop ETH                              # 停某品种
  python monitor.py stop --all                             # 停全部
  python monitor.py restart ETH                            # 等价于 stop ETH && start ETH
  python monitor.py status                                 # 全品种汇总 ( daemon 状态 + state.json 关键字段)
  python monitor.py logs                                   # 实时跟随所有品种日志 (默认)
  python monitor.py logs ETH                               # 实时跟随 ETH 日志
  python monitor.py logs --no-follow                        # 只打印最近 N 行后退出, 不跟随
  python monitor.py logs ETH --no-follow                    # 只看 ETH 最近 20 行
  python monitor.py show ETH                               # cat state.json
  python monitor.py run ETH --ema 200 --bp 0.005           # 临时覆盖参数前台跑 (调试, 不写 strategies.json)

环境变量:
  MONITOR_PY            python 解释器 (启动 daemon 子进程用, 默认本进程的解释器)
  MONITOR_TELEGRAM_CONFIG   telegram 配置路径 (默认 monitor/telegram_config.json)

设计:
  - 配置唯一来自 monitor/strategies.json
  - 一个品种 = 一个独立 daemon 子进程 (出错互不影响, 状态天然分目录)
  - caches/<name>/{daemon.pid, state.json, monitor.log, stdout.log}
"""
import os
import re
import sys
import json
import time
import signal
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
STRATEGIES_FILE = os.path.join(HERE, "strategies.json")
CACHES_DIR = os.path.join(HERE, "caches")
os.makedirs(CACHES_DIR, exist_ok=True)

DEFAULT_PY = os.environ.get("MONITOR_PY") or sys.executable

# 让 `from monitor import daemon` 在本文件被直接执行时也能解析到 misc/monitor/ 包.
_PARENT = os.path.dirname(HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)


def load_strategies():
    with open(STRATEGIES_FILE) as f:
        return json.load(f)


def find_cfg(name):
    for s in load_strategies()["strategies"]:
        if s["name"] == name:
            return s
    raise SystemExit(f"未知策略 name={name!r}; 用 `monitor.py list` 查看全部")


def _ensure_known_name(name):
    """校验 name 是已知策略; TRHRP 子系统 (独立配置) 跳过 find_cfg, 其余按 EMA 反手校验."""
    if _is_trhrp_name(name):
        return
    find_cfg(name)


def cache_dir_for(name):
    d = os.path.join(CACHES_DIR, name)
    os.makedirs(d, exist_ok=True)
    return d


def pidfile_for(name):
    return os.path.join(cache_dir_for(name), "daemon.pid")


def read_pid(name):
    pf = pidfile_for(name)
    if not os.path.exists(pf):
        return None
    try:
        with open(pf) as f:
            return int(f.read().strip())
    except Exception:
        return None


def is_running(name):
    pid = read_pid(name)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except Exception:
        return False


def clear_pid(name):
    pf = pidfile_for(name)
    if os.path.exists(pf):
        os.remove(pf)


# ============================================================
# commands
# ============================================================
def cmd_list(args):
    data = load_strategies()
    print(f"{'NAME':<10} {'SYMBOL':<22} {'TF':<5} {'EMA':>5} {'CB':>6} {'BP':>7} {'TP':<24} {'SRC':<10} {'RUN':<5}")
    print("-" * 106)
    for s in sorted(data["strategies"], key=lambda x: (x.get("priority", 99), x["name"])):
        cb = (f"f{s['cb_float']:.2f}" if s.get("cb_float") else f"{int(s['confirm_bars'])}i")
        run = "✓" if is_running(s["name"]) else "-"
        if s.get("tp_enabled", True) and s.get("tp_type") not in (None, "none"):
            side = s.get("tp_side", "both")
            tp = f"{s['tp_type']}[{side}]"
        else:
            tp = "none"
        print(f"{s['name']:<10} {s['symbol']:<22} {s.get('timeframe','15m'):<5} {int(s['ema_span']):>5} {cb:>6} "
              f"{float(s['breakout_pct'])*100:>6.2f}% {tp:<24} {s['data_source']:<10} {run:<5}")
    print(f"\n共 {len(data['strategies'])} 个 EMA 策略. 配置文件: {STRATEGIES_FILE}")
    # TRHRP 子系统也一并展示
    cmd_trhrp_list()


def _is_trhrp_name(name):
    """判断给定 name 属于 TRHRP 子系统 (否则认为是 EMA 反手策略)."""
    cfg = _load_trhrp_config()
    return bool(cfg) and cfg.get("name", "TRHRP") == name


def cmd_start(args):
    names = _expand_names(args.names, args.all, default_all=True)
    started = []
    skipped = []
    for name in names:
        if _is_trhrp_name(name):
            daemon_file = "daemon_trhrp.py"
        else:
            find_cfg(name)  # 校验 EMA 反手策略存在
            daemon_file = "daemon.py"
        if is_running(name):
            skipped.append(name)
            print(f"[{name}] already running (pid {read_pid(name)}), skip")
            continue
        cd = cache_dir_for(name)
        stdout_log = os.path.join(cd, "stdout.log")
        cmd = [DEFAULT_PY, "-u", os.path.join(HERE, daemon_file), name]
        if args.foreground:
            print(f"[{name}] foreground start: {' '.join(cmd)}",
                  "(Ctrl+C 退出)" if not args.dry_run else "(dry-run)")
            if args.dry_run:
                cmd = cmd + ["--dry-run"] if False else cmd
                # dry-run 复用前台模式 + 与 daemon 协议: daemon 暂未单独处理, 这里加环境变量提示
                os.environ["MONITOR_DRY_RUN"] = "1"
            os.execvpe(cmd[0], cmd, os.environ)
        else:
            with open(stdout_log, "a") as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
            with open(pidfile_for(name), "w") as f:
                f.write(str(proc.pid))
            print(f"[{name}] started pid={proc.pid}, log {os.path.join(cd, 'monitor.log')}")
            started.append(name)
        time.sleep(0.3)
    if started:
        print(f"\n启动 {len(started)} 个: {', '.join(started)}")
    if skipped:
        print(f"跳过 {len(skipped)} 个 (已在运行): {', '.join(skipped)}")

    # 启动完毕推一条汇总通知 (合并为一条, 不一对一轰炸); 只走 telegram, macos 不弹 (留给信号变化).
    # foreground/exec 模式不会走到这里 (已替换进程); 只在真后台启动后汇总.
    if started and not args.foreground:
        try:
            from monitor import notifiers
            msg = (f"✅ 监控已启动 {len(started)} 个新 daemon"
                   + (f" (+跳过 {len(skipped)} 个已在跑)" if skipped else "")
                   + f": {', '.join(started)}")
            notifiers.notify_all("监控启动汇总", msg, important=False)
        except Exception as e:
            print(f"(汇总通知失败, 忽略: {e})", file=sys.stderr)


def cmd_stop(args):
    names = _expand_names(args.names, args.all, default_all=True)
    stopped = []
    for name in names:
        if not is_running(name):
            clear_pid(name)
            print(f"[{name}] not running")
            continue
        pid = read_pid(name)
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not is_running(name):
                    break
                time.sleep(0.2)
            if is_running(name):
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.3)
            stopped.append(name)
            print(f"[{name}] stopped (was pid {pid})")
        except ProcessLookupError:
            pass
        finally:
            clear_pid(name)
    if stopped:
        print(f"\n已停止 {len(stopped)} 个: {', '.join(stopped)}")


def cmd_restart(args):
    cmd_stop(args)
    print()
    time.sleep(1)
    # cmd_start 依赖 args.foreground / args.dry_run, restart 子命令默认不支持这些
    args.foreground = False
    args.dry_run = False
    cmd_start(args)


def _fmt_price(p):
    """价格可读化: 10万以上去 0, 1万以上保留 1 位小数, 否则保留 4 位有效数字; 不再用科学计数法."""
    if p is None or p == 0:
        return "-"
    try:
        x = float(p)
    except Exception:
        return "?"
    if x >= 100000:
        return f"{x:,.0f}"
    if x >= 10000:
        return f"{x:,.1f}"
    if x >= 100:
        return f"{x:,.2f}"
    return f"{x:.4g}"


def _read_last_action_from_log(name):
    """从 monitor/caches/<name>/actions.log 最后一行读真实上一次动作. 没有 log 则返回 None.

    这是 LAST_ACTION 展示的真实单一来源: daemon 自身启动时已回放写满, 之后每次动作都追加.
    """
    p = os.path.join(cache_dir_for(name), "actions.log")
    if not os.path.exists(p):
        return None
    try:
        last = None
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except Exception:
                    continue
        return last
    except Exception:
        return None


def _fmt_action_from_log(name, st_fallback):
    """优先从 actions.log 读, 否则回退 state.json 的 last_action. 返回 (短摘要, 详细).

    TRHRP 等子系统若用自己的 actions.log schema 也由这里识别 kind 字段加分支.
    """
    la = _read_last_action_from_log(name)
    if not la:
        la = st_fallback.get("last_action") if st_fallback else None
    if not la:
        return ("-", "-")
    kind = la.get("kind", "?")
    if kind == "regime_change":
        # TRHRP 子系统的限速 schema: label + prevRegime/curRegime
        # 注意: 当某市场数据拉取失败时 prevRegime/curRegime 可能是 JSON null,
        # 此时 .get(...) 返回 None 而非默认值, 不能对其做 [:] 切片.
        # 必须用 (v or '?') 兜底, 否则会抛 'NoneType' object is not subscriptable.
        prev = la.get("prevRegime") or "?"
        cur = la.get("curRegime") or "?"
        short = (f"{la.get('label','?')} {prev[:4].upper()}→{cur[:4].upper()}")
        descr = la.get("descr") or short
        return (short, descr)
    price = _fmt_price(la.get("price"))
    time = (la.get("time") or "")[11:16] or "?"
    short = f"{kind} {price} {time}"
    descr = la.get("descr") or short
    return (short, descr)


def _fmt_action(st):
    """[deprecated, 仅用于向后兼容] 从 state.json 的 last_action 变短行.

    新代码用 _fmt_action_from_log(name, st).
    """
    la = st.get("last_action")
    if not la:
        return ("-", "-")
    kind = la.get("kind", "?")
    price = _fmt_price(la.get("price"))
    time = (la.get("time") or "")[11:16] or "?"
    short = f"{kind} {price} {time}"
    descr = la.get("descr") or short
    return (short, descr)


def cmd_status(args):
    data = load_strategies()
    # EMA 反手段: 只支持 --name 模糊过滤 (group/regime/quality 是 TRHRP 概念, 不适用)
    name_kw = (args.name or "").lower() or None
    print(f"{'NAME':<9} {'RUN':<4} {'PID':<6} {'POS':<4} {'SIZE':>4} {'PRICE':<13} {'UNREAL':<8} {'LAST_ACTION':<28} {'LAST_BAR':<17}")
    print("-" * 110)
    running = 0
    shown = 0
    for s in sorted(data["strategies"], key=lambda x: (x.get("priority", 99), x["name"])):
        name = s["name"]
        # --name 同时匹配 name 与 display_name
        if name_kw and name_kw not in name.lower() \
                and name_kw not in str(s.get("display_name", "") or "").lower():
            continue
        shown += 1
        rn = is_running(name)
        if rn:
            running += 1
        pid = str(read_pid(name) or "-")
        state_file = os.path.join(cache_dir_for(name), "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file) as f:
                    st = json.load(f)
                dirmap = {1: "多", -1: "空", 0: "-"}
                pos = dirmap.get(st.get("position"), "?")
                size = f"{float(st.get('pos_size', 0))*100:.0f}%"
                price = _fmt_price(st.get("live_price", 0))
                unreal = f"{float(st.get('unreal_pct', 0))*100:+.2f}%"
                lastbar = (st.get("last_closed", "") or "")[:16].replace("T", " ")
                la_short, _ = _fmt_action_from_log(name, st)
            except Exception as e:
                pos = size = price = unreal = lastbar = la_short = "?"
        else:
            pos = size = price = unreal = lastbar = la_short = "-"
        run_flag = "✓" if rn else "-"
        print(f"{name:<9} {run_flag:<4} {pid:<6} {pos:<4} {size:>4} {price:<13} {unreal:<8} {la_short:<28} {lastbar:<17}")
    if name_kw:
        print(f"\n运行中 {running}/{shown} (筛选自 {len(data['strategies'])} 只, 关键词={args.name})  "
              f"(PID 文件在 monitor/caches/<name>/daemon.pid; LAST_ACTION 真实来自 actions.log JSONL)")
    else:
        print(f"\n运行中 {running}/{len(data['strategies'])}  (PID 文件在 monitor/caches/<name>/daemon.pid; "
              f"LAST_ACTION 真实来自 actions.log JSONL)")

    # === TRHRP 子系统 (独立配置文件 monitor/strategies_trhrp.json) ===
    trhrp_state = _trhrp_status_section(args)
    if trhrp_state is not None:
        print(trhrp_state)


# ============================================================
# TRHRP 子系统 (与 EMA 反手完全独立)
# ============================================================
def _trhrp_config_path():
    return os.path.join(HERE, "strategies_trhrp.json")


def _load_trhrp_config():
    p = _trhrp_config_path()
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


# 段二使用的短档位名映射与颜色, 让标题/触发条件更紧凑.
_TRHRP_SHORT_REGIME = {"RISK_ON": "ON", "MODERATE": "MOD", "RISK_OFF": "OFF"}
_TRHRP_REGIME_COLOR = {
    "RISK_ON": "\033[32m",    # 绿
    "MODERATE": "\033[33m",   # 黄
    "RISK_OFF": "\033[31m",   # 红
}
_RESET = "\033[0m"


def _trhrp_short_regime(r):
    r = (r or "?").upper()
    return _TRHRP_SHORT_REGIME.get(r, r[:4])


def _trhrp_color_regime(r):
    r = (r or "?").upper()
    return _TRHRP_REGIME_COLOR.get(r, "")


def _trhrp_compact_reason(text):
    """压缩 nextRegimeReason 文本: 去掉冗余注释, 保留关键判断."""
    if not text or text == "-":
        return "-"
    t = text
    t = t.replace("不满足 risk_on 的 vol 收敛条件", "未满足 ON")
    t = t.replace("不满足 risk_off 的 mom<0 条件", "未满足 OFF")
    t = t.replace("两档触发条件均未达成", "两档均未触发")
    t = t.replace("波动率相对自身252d历史 z-score > 2.5σ (非绝对 30% 崩盘线)", "z>2.5σ (相对历史)")
    t = t.replace("波动率相对自身252d历史 z-score > 1.5σ (非绝对 30% 崩盘线)", "z>1.5σ (相对历史)")
    t = t.replace("→ 强制 risk_off", "→ 强制 OFF")
    t = t.replace("→ risk_on", "→ ON")
    t = t.replace("→ risk_off", "→ OFF")
    t = t.replace("→ moderate", "→ MOD")
    t = t.replace("risk_on", "ON")
    t = t.replace("risk_off", "OFF")
    t = t.replace("moderate:", "MOD:")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _trhrp_compact_trigger(text):
    """压缩 nextRegimeNextTrigger 文本: 去掉 '当前...' 重复注释与冗余说明."""
    if not text or text == "-":
        return "-"
    t = text
    # 删除括号内 "当前..." 的注释 (例: "(当前 mom +1.77%, vol 24.81%)")
    t = re.sub(r"\(当前[^)]*\)", "", t)
    # 删除整句 "当前 vol 距 p60 还需降 X% ... 或 mom 转正 (当前 ...)" — 一直吃到 '|' 或结尾
    t = re.sub(r"当前 vol 距 p60 还需降[^|]*", "", t)
    # 删除尾巴上的 "当前仍超崩盘触发线"
    t = t.replace("当前仍超崩盘触发线", "")
    # 短语替换 — 注意顺序: 先替换复合短语, 再替换单词
    t = t.replace("切回 risk_on", "→ ON")
    t = t.replace("切到 risk_on", "→ ON")
    t = t.replace("切回 risk_off", "→ OFF")
    t = t.replace("切到 risk_off 任一即可", "→ OFF 任一即可")
    t = t.replace("切到 risk_off", "→ OFF")
    t = t.replace("波动率 z-score", "z")
    t = t.replace("(崩盘线)", "(crash)")
    # vol_med (中位 vol) 整体替换为 "中位", 避免重复; 再单独处理 vol_med N% 的情况
    t = t.replace("vol_med (中位 vol)", "中位")
    t = t.replace("vol_med", "中位")
    t = t.replace("且 mom>0 转正", "且 mom>0")
    t = t.replace("且 vol 不超崩盘线", "")
    t = t.replace("vol 退到 < 30%", "vol<30%")
    t = t.replace("mom转负", "mom<0")
    # 折叠空格
    t = re.sub(r"\s+", " ", t).strip()
    # 去掉行尾多余的 ".;" 残留
    t = re.sub(r"[.;\s]+$", "", t)
    # 清理孤立的 "." 残留 (例: "mom>0 . " — 句号被孤立)
    t = re.sub(r"\s+\.\s*", " ", t)
    # 多个连续空格的分隔符统一为 " | "
    t = re.sub(r"\s*\|\s*", " | ", t)
    return t


def _trhrp_quality_lookup():
    """从 strategies_trhrp.json 构建优质标的集合. 返回 (quality_tickers, quality_labels)."""
    cfg = _load_trhrp_config()
    tickers = set()
    labels = set()
    if cfg:
        for m in cfg.get("markets") or []:
            if m.get("quality"):
                if m.get("ticker"):
                    tickers.add(m["ticker"])
                if m.get("label"):
                    labels.add(m["label"])
    return tickers, labels


def _trhrp_market_matches(m, args, quality_tickers):
    """判断 state.json 中的 market 条目是否匹配 status 过滤参数 (group/regime/name/quality)."""
    if args is None:
        return True
    groups = getattr(args, "group", None)
    if groups:
        if m.get("marketGroup") not in groups:
            return False
    regime = getattr(args, "regime", None)
    if regime:
        # 同时匹配当前档与次日档, 任一命中即保留
        cur = (m.get("currentRegime") or "").lower()
        nxt = (m.get("nextRegime") or "").lower()
        if regime not in (cur, nxt):
            return False
    name_kw = getattr(args, "name", None)
    if name_kw:
        kw = name_kw.lower()
        label = str(m.get("label") or "").lower()
        ticker = str(m.get("ticker") or "").lower()
        if kw not in label and kw not in ticker:
            return False
    if getattr(args, "quality", False):
        if m.get("ticker") not in quality_tickers:
            return False
    return True


def _trhrp_show_in_summary(m):
    """精简模式下判断 market 是否值得显示:
    有变化 (⚠️) / 临近切换 (outlookDist<0.1) / 次日 regime 非 risk_off (risk_on|moderate 值得关注)."""
    if m.get("changed"):
        return True
    od = m.get("outlookDist")
    if isinstance(od, (int, float)) and od < 0.1:
        return True
    nxt = (m.get("nextRegime") or "").upper()
    if nxt in ("RISK_ON", "MODERATE"):
        return True
    return False


def _trhrp_status_section(args=None):
    """构建 TRHRP 子系统 status 段落. 没配置或没数据时返回 None (不打印).

    模式:
    - 精简模式 (默认, 无过滤参数且未 --full): 段一只显示有变化/临近切换/非 risk_off 的标的,
      段三只显示 quality=true 的标的, 末尾附 `共 N 只 (显示 M 只, --full 查看全部)`.
    - 完整模式 (--full 或传了任意过滤参数): 显示全部匹配过滤条件的标的.
    """
    cfg = _load_trhrp_config()
    if not cfg:
        return None
    name = cfg.get("name", "TRHRP")
    cache_dir = cache_dir_for(name)
    state_file = os.path.join(cache_dir, "state.json")
    rn = is_running(name)
    pid = str(read_pid(name) or "-")

    # 过滤上下文: 是否传了过滤参数, 是否完整模式
    has_filter = False
    if args is not None:
        has_filter = bool(getattr(args, "group", None) or getattr(args, "regime", None)
                          or getattr(args, "name", None) or getattr(args, "quality", False))
    full_mode = bool(getattr(args, "full", False)) if args is not None else True
    if has_filter:
        full_mode = True  # 传了过滤参数则自动全量显示匹配结果

    quality_tickers, quality_labels = _trhrp_quality_lookup()
    quality_count = len(quality_tickers)

    lines = []
    lines.append("")
    lines.append("[TRHRP 多市场 regime 策略子系统]")
    lines.append(f"{'NAME':<8} {'RUN':<4} {'PID':<6} {'REGIME':<30} {'CHG':<4} {'ASOF':<11} {'LAST_ACTION':<40} {'FETCHED':<17}")
    lines.append("-" * 122)
    if not os.path.exists(state_file):
        lines.append(f"{name:<8} {'✓' if rn else '-':<4} {pid:<6} {'-':<30} {'-':<4} {'-':<11} {'-':<40} {'-':<17}")
        return "\n".join(lines)
    try:
        with open(state_file) as f:
            st = json.load(f)
    except Exception as e:
        lines.append(f"(TRHRP state.json 读取失败: {e})")
        return "\n".join(lines)

    # 汇总行: regime 分布 + 优质标的数
    regime_summary = (f"🟢{st.get('riskOnCount',0)} 🟡{st.get('moderateCount',0)} "
                      f"🔴{st.get('riskOffCount',0)} 优质{quality_count}只")
    as_of = (st.get("asOfDate") or "-")[:10]
    changed = st.get("changedMarkets", 0)
    fetched = (st.get("fetchedAt") or "")[:16].replace("T", " ")
    la_short, _ = _fmt_action_from_log(name, st)
    run_flag = "✓" if rn else "-"
    lines.append(f"{name:<8} {run_flag:<4} {pid:<6} {regime_summary:<30} {changed:<4} {as_of:<11} {la_short:<40} {fetched:<17}")
    # 名词速查 (一次出现, 供各市场行参照):
    #   REGIME: 风险档 — RISK_ON 偏多仓 / MODERATE 中性 / RISK_OFF 避险
    #   cur→nxt: 当前生效档 → 次日交易档 (T 日信号, T+1 生效); ⚠️=次日档已变化, 待执行
    #   ★=quality 优质标的; vol: 21d realized vol 年化; p60 = 252 日窗口 60 分位;
    #   中位 = 126 日窗口中位; mom = 21d 动量; 崩盘线: 强制 RISK_OFF 的 vol 阈值
    #   z: 252 日 log 价 z-score (均值回归极端偏差)
    #   基础配比: regime → 股票/GLD/SGOV; 叠加后: 经 z-score overlay 调整后配比 (抄底加 / 高位减)
    lines.append("")

    # === 段一·当前仓位水平 ===
    all_markets = st.get("markets") or []
    # 规范化 None → "-"
    norm_markets = [{k: (v if v is not None else "-") for k, v in (raw_m or {}).items()}
                    for raw_m in all_markets]
    # 应用过滤参数 (group/regime/name/quality)
    filtered = [m for m in norm_markets if _trhrp_market_matches(m, args, quality_tickers)]
    total_count = len(norm_markets)
    if full_mode:
        shown = filtered
    else:
        # 精简模式: 只显示有变化/临近切换/非 risk_off 的标的
        shown = [m for m in filtered if _trhrp_show_in_summary(m)]

    lines.append(f"  ── 段一·当前 {total_count} 个市场仓位水平 (显示 {len(shown)} 只) ──")
    lines.append(f"  {'市场':<10} {'分组':<6} {'REGIME':<20} {'基础配比':<24} {'叠加后配比':<26} {'z-score':<10} {'叠加提示'}")
    for m in shown:
        cur_r = (m.get("currentRegime") or "?")[:8].upper()
        nxt_r = (m.get("nextRegime") or "?")[:8].upper()
        regime_cell = f"{cur_r} → {nxt_r}"
        z = m.get("priceZScore252")
        z_str = f"{z:+.2f}σ" if isinstance(z, (int, float)) else "-"
        marker = " ⚠️" if m.get("changed") else ""
        # quality 优质标的在 label 前加 ★ 标记
        qmark = "★" if m.get("ticker") in quality_tickers else ""
        label_disp = f"{qmark}{m.get('label','-')}"
        lines.append(f"  {label_disp:<10} {m.get('marketGroup','-'):<6} {regime_cell:<20} "
                     f"{m.get('allocationText','-'):<24} "
                     f"{m.get('overlayAdjustedAllocationText','-'):<26} {z_str:<10} "
                     f"{m.get('overlayRecommendationText','-')}{marker}")
    # 段二: 同步应用过滤 (用 filtered, 不再用全量 markets)
    _append_trhrp_section_two(lines, st, filtered, full_mode)
    # 段三: 精简模式只显示 quality 标的; 完整模式按过滤参数显示
    _append_trhrp_section_three(lines, args, quality_labels, full_mode)

    # 末尾汇总行
    if not full_mode:
        lines.append("")
        lines.append(f"  共 {total_count} 只 (显示 {len(shown)} 只, --full 查看全部)")
    elif len(shown) < total_count:
        lines.append("")
        lines.append(f"  共 {total_count} 只 (匹配 {len(shown)} 只)")

    if st.get("error"):
        lines.append("")
        lines.append(f"  ⚠️ error: {st.get('error')}")
    if st.get("warnings"):
        lines.append("")
        for w in st.get("warnings") or []:
            lines.append(f"  ⚠️ 缓存回退: {w}")
    return "\n".join(lines)


def _append_trhrp_section_two(lines, st, filtered_markets=None, full_mode=True):
    """段二: 次日档变化与触发条件. 拆成变化组 (展开) + 维持组 (按档分组, 每市场一行).

    filtered_markets: 已经过滤 (group/regime/name/quality) 并规范化的 market 列表;
                      为 None 时回退到 state.json 全量 markets (向后兼容).
    full_mode: 完整模式标志 (目前段二展示逻辑不变, 仅用于将来扩展).
    """
    lines.append("")
    # 段二同步应用过滤: 优先用上层传入的 filtered_markets, 否则回退全量
    if filtered_markets is not None:
        markets = filtered_markets
    else:
        markets = [{k: (v if v is not None else "-") for k, v in (raw_m or {}).items()}
                   for raw_m in (st.get("markets") or [])]
    total = len(st.get("markets") or [])
    changed_markets = []
    stable_markets = []
    for m in markets:
        cur_r = (m.get("currentRegime") or "?").upper()
        nxt_r = (m.get("nextRegime") or "?").upper()
        is_changed = bool(m.get("changed")) or cur_r != nxt_r
        (changed_markets if is_changed else stable_markets).append(m)

    def _f(x, d=1):
        return f"{x:.{d}f}%" if isinstance(x, (int, float)) else "-"

    def _mom(x):
        return (f"{x:+.2f}%" if isinstance(x, (int, float)) else "-")

    def _z(x):
        return (f"{x:+.2f}σ" if isinstance(x, (int, float)) else "-")

    def _disp_label(label, width=14):
        s = str(label) if label != "-" else "-"
        w = sum(2 if ord(c) > 127 else 1 for c in s)
        if w < width:
            return s + " " * (width - w)
        if w > width:
            out = ""
            cur_w = 0
            for c in s:
                cw = 2 if ord(c) > 127 else 1
                if cur_w + cw > width:
                    break
                out += c
                cur_w += cw
            return out + " " * (width - cur_w)
        return s

    lines.append(f"  ── 段二·次日档变化与触发条件 (共 {total} 个市场 · 变化 {len(changed_markets)} · 维持 {len(stable_markets)}) ──")

    if changed_markets:
        lines.append("")
        lines.append(f"  ⚠️ 次日档变化 {len(changed_markets)} 个 — 次日开盘需调仓:")
        for m in changed_markets:
            cur_r = (m.get("currentRegime") or "?").upper()
            nxt_r = (m.get("nextRegime") or "?").upper()
            vol_pct = m.get("volPct")
            p60 = m.get("volP60Pct")
            med = m.get("medianVolPct")
            mom = m.get("momPct")
            z = m.get("priceZScore252")
            label = m.get("label", "-")
            cur_c = _trhrp_color_regime(cur_r)
            nxt_c = _trhrp_color_regime(nxt_r)
            lines.append(
                f"    • {_disp_label(label)} "
                f"{cur_c}{_trhrp_short_regime(cur_r):>3}{_RESET} → {nxt_c}{_trhrp_short_regime(nxt_r):>3}{_RESET}  "
                f"vol {_f(vol_pct):>6} p60 {_f(p60):>6} 中位 {_f(med):>6} "
                f"mom {_mom(mom):>7} z {_z(z):>7}"
            )
            reason = _trhrp_compact_reason(m.get("nextRegimeReason") or "-")
            if reason != "-":
                lines.append(f"        原因: {reason}")
            trig = _trhrp_compact_trigger(m.get("nextRegimeNextTrigger") or "-")
            if trig != "-":
                lines.append(f"        触发: {trig}")

    if stable_markets:
        lines.append("")
        lines.append(f"  ✓ 维持当前档 {len(stable_markets)} 个 (按档位分组):")
        by_regime = {}
        for m in stable_markets:
            cur_r = (m.get("currentRegime") or "?").upper()
            by_regime.setdefault(cur_r, []).append(m)
        for regime in ["RISK_ON", "MODERATE", "RISK_OFF"]:
            if regime not in by_regime:
                continue
            ms = by_regime[regime]
            rc = _trhrp_color_regime(regime)
            lines.append(f"    [{rc}{_trhrp_short_regime(regime)}{_RESET}] {len(ms)} 个:")
            for m in ms:
                vol_pct = m.get("volPct")
                mom = m.get("momPct")
                z = m.get("priceZScore252")
                label = m.get("label", "-")
                trig = _trhrp_compact_trigger(m.get("nextRegimeNextTrigger") or "-")
                lines.append(
                    f"       {_disp_label(label)} "
                    f"vol {_f(vol_pct):>6} mom {_mom(mom):>7} z {_z(z):>7}  "
                    f"{trig}"
                )


# ── 段三: 历史回测最佳策略 (数据源 deliverables/trhrp_backtest_all/_all.json) ──
_TRHRP_BT_PATH = os.path.normpath(os.path.join(HERE, "..", "deliverables", "trhrp_backtest_all", "_all.json"))
# 5 个策略变体 → (显示名, summary cagr 字段, summary mdd 字段)
_TRHRP_VARIANTS = [
    ("strategy",  "主策略",   "strategy_cagr",  "strategy_max_drawdown"),
    ("benchmark", "买入持有", "benchmark_cagr", "benchmark_max_drawdown"),
    ("timing",    "股现择时", "timing_cagr",    "timing_max_drawdown"),
    ("extreme",   "极值仓位", "extreme_cagr",   "extreme_max_drawdown"),
    ("ronly",     "ON满仓",   "ronly_cagr",     "ronly_max_drawdown"),
]
_trhrp_bt_cache = None  # {label: {variant, name, cagr, mdd, calmar, strat_calmar}}


def _load_trhrp_backtest():
    """懒加载 _all.json, 返回 {label: best_info}. 文件缺失/解析失败返回 None."""
    global _trhrp_bt_cache
    if _trhrp_bt_cache is not None:
        return _trhrp_bt_cache
    if not os.path.exists(_TRHRP_BT_PATH):
        _trhrp_bt_cache = {}
        return _trhrp_bt_cache
    try:
        with open(_TRHRP_BT_PATH) as f:
            data = json.load(f)
    except Exception:
        _trhrp_bt_cache = {}
        return _trhrp_bt_cache
    out = {}
    for r in data.get("results", []):
        meta = r.get("meta") or {}
        label = meta.get("label")
        if not label:
            continue
        s = r.get("summary") or {}
        best = None
        strat_calmar = None
        for key, disp, cagr_k, mdd_k in _TRHRP_VARIANTS:
            cagr = s.get(cagr_k)
            mdd = s.get(mdd_k)
            if not isinstance(cagr, (int, float)) or not isinstance(mdd, (int, float)):
                continue
            if mdd >= 0:
                # mdd==0 除零, 跳过; mdd>0 数据异常也跳过
                continue
            calmar = cagr / abs(mdd)
            if key == "strategy":
                strat_calmar = calmar
            if best is None or calmar > best["calmar"]:
                best = {"variant": key, "name": disp, "cagr": cagr, "mdd": mdd, "calmar": calmar}
        if best is not None:
            best["strat_calmar"] = strat_calmar
            out[label] = best
    _trhrp_bt_cache = out
    return out


def _append_trhrp_section_three(lines, args=None, quality_labels=None, full_mode=True):
    """段三: 各标的历史回测最佳策略 (按 Calmar=CAGR/|MDD| 评选, 突出最佳≠主策略的标的).

    精简模式 (full_mode=False): 只显示 quality=true 的标的.
    完整模式 (full_mode=True): 显示全部, 但应用 --name / --quality 过滤.
    """
    bt = _load_trhrp_backtest()
    if not bt:
        return
    quality_labels = quality_labels or set()
    name_kw = (getattr(args, "name", None) or "").lower() or None
    quality_filter = bool(getattr(args, "quality", False))

    def _label_ok(label):
        if not full_mode:
            # 精简模式: 只显示 quality=true 标的
            if label not in quality_labels:
                return False
        else:
            if quality_filter and label not in quality_labels:
                return False
            if name_kw and name_kw not in str(label).lower():
                return False
        return True

    filtered_bt = {label: info for label, info in bt.items() if _label_ok(label)}
    if not filtered_bt:
        return
    total = len(filtered_bt)
    non_strat = [(label, info) for label, info in filtered_bt.items() if info["variant"] != "strategy"]
    is_strat_count = total - len(non_strat)

    lines.append("")
    scope = "优质标的" if not full_mode and quality_labels else "标的"
    lines.append(f"  ── 段三·历史回测最佳策略 (Calmar = CAGR/|MDD| · 共 {total} 个{scope} · 最佳非主策略 {len(non_strat)} 个) ──")

    def _disp_label(label, width=14):
        s = str(label)
        w = sum(2 if ord(c) > 127 else 1 for c in s)
        if w < width:
            return s + " " * (width - w)
        if w > width:
            out = ""
            cur_w = 0
            for c in s:
                cw = 2 if ord(c) > 127 else 1
                if cur_w + cw > width:
                    break
                out += c
                cur_w += cw
            return out + " " * (width - cur_w)
        return s

    def _pct(x, sign=False):
        if not isinstance(x, (int, float)):
            return "-"
        return (f"{x*100:+.1f}%" if sign else f"{x*100:.1f}%")

    if non_strat:
        lines.append("")
        lines.append(f"  💡 最佳策略非主策略的标的 (改用该变体风险收益比更高):")
        lines.append(f"     {'市场':<14} {'最佳策略':<8} {'CAGR':>7} {'MDD':>7} {'Calmar':>7} {'主Calmar':>12} {'差值':>7}")
        # 按 Calmar 差值 (best - strategy) 降序, 差值越大越值得切换
        non_strat.sort(key=lambda kv: (kv[1]["calmar"] - (kv[1]["strat_calmar"] or 0)), reverse=True)
        for label, info in non_strat:
            diff = info["calmar"] - (info["strat_calmar"] or 0)
            lines.append(
                f"     {_disp_label(label)} {info['name']:<8} "
                f"{_pct(info['cagr']):>7} {_pct(info['mdd']):>7} {info['calmar']:>7.2f} "
                f"{(info['strat_calmar'] or 0):>12.2f} {diff:>+7.2f}"
            )

    if is_strat_count:
        lines.append("")
        lines.append(f"  ✓ 最佳策略即主策略的标的 {is_strat_count} 个 (主策略已是该标的风险收益比最优变体)")



def cmd_trhrp_list(name="TRHRP"):
    """打印 TRHRP 子系统配置的市场 (markets UNIVERSE). 用于 monitor list 子命令展示."""
    cfg = _load_trhrp_config()
    if not cfg:
        return
    markets = cfg.get("markets") or []
    if not markets:
        return
    rn = is_running(name)
    pid = read_pid(name)
    print()
    print("[TRHRP 子系统品种清单]  (单一 daemon 进程, 覆盖下方全部市场)")
    print(f"  守护进程: {'✓ 运行中' if rn else '✗ 未运行'}   pid={pid or '-'}   "
          f"启动: python monitor/monitor.py start {name}   |   停止: python monitor/monitor.py stop {name}")
    print(f"{'#':<3} {'GROUP':<8} {'LABEL':<14} {'TICKER':<14} {'PROXY':<12}")
    print("-" * 60)
    for i, m in enumerate(markets, 1):
        print(f"{i:<3} {m.get('marketGroup','-'):<8} {m.get('label','-'):<14} "
              f"{m.get('ticker','-'):<14} {m.get('proxy','-'):<12}")
    print(f"\n共 {len(markets)} 个市场. 配置文件: {_trhrp_config_path()}")
    print(f"检查间隔: {cfg.get('check_interval_minutes', 60)} 分钟")


def cmd_logs(args):
    names = _expand_names(args.names, args.all, default_all=True)
    if args.follow:
        targets = []
        for name in names:
            _ensure_known_name(name)
            lf = os.path.join(cache_dir_for(name), "monitor.log")
            if not os.path.exists(lf):
                print(f"[{name}] 无日志: {lf}, 跳过", file=sys.stderr)
                continue
            targets.append((name, lf))
        if not targets:
            print("无可跟随的日志", file=sys.stderr)
            return
        if len(targets) == 1:
            _follow_single(targets[0][0], targets[0][1], args.n or 20)
        else:
            _tail_multi(targets, args.n or 20)
        return
    if len(names) == 1:
        name = names[0]
        _ensure_known_name(name)
        log_file = os.path.join(cache_dir_for(name), "monitor.log")
        if not os.path.exists(log_file):
            print(f"无日志文件: {log_file}")
            return
        n = args.n or 20
        with open(log_file) as f:
            lines = f.readlines()
        for line in lines[-n:]:
            print(line, end="")
        return
    # 多品种: 逐个打印, 带品种名分隔
    n = args.n or 20
    for name in names:
        _ensure_known_name(name)
        log_file = os.path.join(cache_dir_for(name), "monitor.log")
        print(f"\n===== [{name}] =====")
        if not os.path.exists(log_file):
            print(f"  (无日志: {log_file})")
            continue
        with open(log_file) as f:
            lines = f.readlines()
        for line in lines[-n:]:
            print(line, end="")


def cmd_show(args):
    name = args.name
    find_cfg(name)
    state_file = os.path.join(cache_dir_for(name), "state.json")
    if not os.path.exists(state_file):
        print(f"无 state 文件: {state_file}")
        return
    with open(state_file) as f:
        print(f.read())


def cmd_notify(args):
    """手动发一条通知到所有已配置通道, 用于验证配置. 不开 daemon."""
    from monitor import notifiers
    print("通知通道状态:")
    for name, mod in notifiers.REGISTRY.items():
        cfg = hasattr(mod, "is_configured") and mod.is_configured()
        path = hasattr(mod, "config_path") and mod.config_path()
        print(f"  - {name}: {'✓ 已配置' if cfg else '✗ 未配置'}  ({path})")
    print(f"\n发送: title={args.title!r} message={args.message!r}")
    results = notifiers.notify_all(args.title, args.message, important=args.important)
    print("\n结果:", results)


def cmd_tail(args):
    """聚合多个品种的 monitor.log, 实时尾随. Ctrl+C 只停聚合查看 (不影响 daemon)."""
    names = _expand_names(args.names, args.all, default_all=True)
    # 不存在日志文件的品种先告知
    targets = []
    for n in names:
        _ensure_known_name(n)
        lf = os.path.join(cache_dir_for(n), "monitor.log")
        if not os.path.exists(lf):
            print(f"[{n}] 无日志: {lf}, 跳过", file=sys.stderr)
            continue
        targets.append((n, lf))
    if not targets:
        print("无可跟随的日志", file=sys.stderr)
        return
    _tail_multi(targets, args.n or 20)


# ---------- tail -f 实现 ----------
def _read_tail(path, n):
    """读最后 n 行, 不足则全读."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    return lines[-n:] if n > 0 else lines


def _follow_single(name, log_file, init_n):
    """单品种 tail -f."""
    # 先打印历史 n 行 (含时间戳)
    for line in _read_tail(log_file, init_n):
        sys.stdout.write(line)
    sys.stdout.flush()
    pos = os.path.getsize(log_file) if os.path.exists(log_file) else 0
    print(f"\n=== [{name}] 跟随中, Ctrl+C 退出 ===\n", flush=True)
    try:
        while True:
            try:
                size = os.path.getsize(log_file)
            except FileNotFoundError:
                time.sleep(1)
                continue
            if size > pos:
                with open(log_file) as f:
                    f.seek(pos)
                    chunk = f.read()
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    pos = size
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n=== 已停止跟随 [{name}] ===")


def _strip_ts(line):
    """去掉日志行前的 [YYYY-MM-DD HH:MM:SS UTC] 时间戳, 避免聚合时重复."""
    if line.startswith("[") and " UTC] " in line:
        return line.split(" UTC] ", 1)[1]
    return line


def _strip_name_prefix(line, name):
    """若日志行本身已带 [NAME] 前缀 (daemon 日志格式), 去掉它, 避免聚合后重复."""
    tag = f"[{name}] "
    if line.startswith(tag):
        return line[len(tag):]
    return line


# ANSI 颜色: 头部用色块区分品种, 主体走终端默认色.
_NAME_COLORS = [
    "\033[36m",  # 青色
    "\033[35m",  # 紫色
    "\033[33m",  # 黄色
    "\033[32m",  # 绿色
    "\033[34m",  # 蓝色
    "\033[31m",  # 红色
    "\033[92m",  # 亮绿
    "\033[93m",  # 亮黄
    "\033[94m",  # 亮蓝
    "\033[95m",  # 亮紫
    "\033[96m",  # 亮青
    "\033[91m",  # 亮红
]
_DIM = "\033[2m"


def _color_for(name):
    """按 hash 给品种分配稳定颜色, 同一品种每次都是同一色."""
    h = sum(ord(c) for c in name)
    return _NAME_COLORS[h % len(_NAME_COLORS)]


def _format_agg_line(name, line):
    """聚合输出: 用颜色化 [NAME] 前缀 + 余下内容; 去掉重复 [NAME]."""
    body = _strip_ts(line)
    body = _strip_name_prefix(body, name)
    return f"{_color_for(name)}[{name}]{_RESET} {body}"


def _tail_multi(targets, init_n):
    """多品种聚合 tail -f. 每行用颜色化 [NAME] 前缀区分来源品种."""
    states = {}
    for name, path in targets:
        for line in _read_tail(path, init_n):
            sys.stdout.write(_format_agg_line(name, line))
        sys.stdout.flush()
        try:
            states[name] = (path, os.path.getsize(path))
        except FileNotFoundError:
            states[name] = (path, 0)
    print(f"\n=== {len(targets)} 个品种 跟随中, 每行以 {_color_for('x')}[NAME]{_RESET} 前缀区分, Ctrl+C 退出 (不影响 daemon) ===\n", flush=True)
    try:
        while True:
            for name, (path, _) in list(states.items()):
                try:
                    size = os.path.getsize(path)
                except FileNotFoundError:
                    continue
                last_pos = states[name][1]
                if size > last_pos:
                    with open(path) as f:
                        f.seek(last_pos)
                        chunk = f.read()
                        for line in chunk.splitlines(keepends=True):
                            sys.stdout.write(_format_agg_line(name, line))
                        sys.stdout.flush()
                    states[name] = (path, size)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n=== 已停止聚合 tail (daemon 继续运行) ===")


def cmd_run(args):
    """前台跑指定品种, 可任意覆盖参数, 不写 strategies.json. 直接 exec daemon.py."""
    if _is_trhrp_name(args.name):
        cmd = [DEFAULT_PY, "-u", os.path.join(HERE, "daemon_trhrp.py"), args.name]
        os.execvpe(cmd[0], cmd, os.environ)
    cmd = [DEFAULT_PY, "-u", os.path.join(HERE, "daemon.py"), args.name]
    if args.ema is not None: cmd += ["--ema", str(args.ema)]
    if args.cb_float is not None and args.cb_float > 0:
        cmd += ["--cb-float", str(args.cb_float)]
    elif args.cb is not None:
        cmd += ["--cb", str(args.cb)]
    if args.bp is not None: cmd += ["--bp", str(args.bp)]
    if args.tf is not None: cmd += ["--tf", args.tf]
    os.execvpe(cmd[0], cmd, os.environ)


def _expand_names(names_csv, all_flag, default_all=False):
    if all_flag or (default_all and not names_csv):
        names = [s["name"] for s in load_strategies()["strategies"]]
        trhrp_cfg = _load_trhrp_config()
        if trhrp_cfg and trhrp_cfg.get("name"):
            tn = trhrp_cfg["name"]
            if tn not in names:
                names.append(tn)
        return names
    if not names_csv:
        raise SystemExit("需要 --all 或显式列出品种 (逗号分隔), 见 --help")
    return [n.strip() for n in names_csv.split(",") if n.strip()]


def main():
    ap = argparse.ArgumentParser(
        prog="monitor.py",
        description="EMA 趋势反手策略 · 统一监控入口 (单一脚本管所有品种)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="列出所有已配置策略 + 是否在跑")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("start", help="启动daemon (无参=全部, 或逗号分隔多个品种, 或 --all)")
    sp.add_argument("names", nargs="?", default=None, help="如 ETH,SOL; 省略=全部 (等价 --all)")
    sp.add_argument("--all", action="store_true", help="启动 strategies.json 中所有品种")
    sp.add_argument("--foreground", action="store_true", help="前台跑 (不开 daemon, 调试用)")
    sp.add_argument("--dry-run", action="store_true", help="只跑首轮拉数据 + 推断持仓即退出, 不进入主循环")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("stop", help="停止 daemon")
    sp.add_argument("names", nargs="?", default=None)
    sp.add_argument("--all", action="store_true")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser("restart", help="重启 daemon")
    sp.add_argument("names", nargs="?", default=None)
    sp.add_argument("--all", action="store_true")
    sp.set_defaults(func=cmd_restart)

    sp = sub.add_parser("status", help="查看所有品种 daemon 状态 + 关键 state 字段")
    sp.add_argument("--group", action="append", default=None, metavar="名称",
                    help="按 marketGroup 过滤 (如 --group A股), 可多次指定")
    sp.add_argument("--regime", choices=["risk_on", "moderate", "risk_off"], default=None,
                    help="只显示当前/次日 regime 匹配的标的")
    sp.add_argument("--name", default=None, metavar="关键词",
                    help="按 label/ticker 模糊搜索 (不区分大小写)")
    sp.add_argument("--quality", action="store_true", help="只显示 quality=true 的优质标的")
    sp.add_argument("--summary", action="store_true", help="精简模式 (默认): 汇总行 + 有变化的标的")
    sp.add_argument("--full", action="store_true", help="完整模式: 显示全部标的 (等价于旧行为)")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("logs", help="查看品种日志; 默认实时跟随所有品种, Ctrl+C 退出")
    sp.add_argument("names", nargs="?", default=None, help="如 ETH 或 ETH,SOL; 省略=全部")
    sp.add_argument("--all", action="store_true", help="查看所有品种")
    sp.add_argument("-n", type=int, default=20, help="启动时先打印最近 N 行历史")
    sp.add_argument("--no-follow", dest="follow", action="store_false", help="不实时跟随, 只打印最近 N 行后退出")
    sp.set_defaults(follow=True)
    sp.set_defaults(func=cmd_logs)

    sp = sub.add_parser("tail", help="聚合多品种 monitor.log 实时尾随 (无参=全部, 仅查看, 不影响 daemon)")
    sp.add_argument("names", nargs="?", default=None, help="如 ETH,SOL; 省略=全部")
    sp.add_argument("--all", action="store_true", help="跟随所有品种")
    sp.add_argument("-n", type=int, default=20, help="启动时先打印最近 N 行历史")
    sp.set_defaults(func=cmd_tail)

    sp = sub.add_parser("show", help="查看 state.json")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("notify", help="手动发一条测试通知, 验证通道配置 (不开 daemon)")
    sp.add_argument("title", help="通知标题 (如 '测试')")
    sp.add_argument("message", nargs="?", default="手动测试消息", help="通知正文")
    sp.add_argument("--quiet", dest="important", action="store_false",
                    help="降级为不重要的样式 (默认 important=True 用醒目提示)")
    sp.set_defaults(func=cmd_notify)

    sp = sub.add_parser("run", help="前台跑指定品种；可临时覆盖参数 (不写 strategies.json)")
    sp.add_argument("name")
    sp.add_argument("--ema", type=int, default=None)
    sp.add_argument("--cb", type=int, default=None)
    sp.add_argument("--cb-float", type=float, default=None)
    sp.add_argument("--bp", type=float, default=None)
    sp.add_argument("--tf", default=None)
    sp.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
