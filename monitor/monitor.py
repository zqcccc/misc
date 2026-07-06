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
  python monitor.py logs ETH                               # tail -n 20 最近日志
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
    print(f"{'NAME':<10} {'SYMBOL':<22} {'TF':<5} {'EMA':>5} {'CB':>6} {'BP':>7} {'TP':<18} {'SRC':<10} {'RUN':<5}")
    print("-" * 100)
    for s in sorted(data["strategies"], key=lambda x: (x.get("priority", 99), x["name"])):
        cb = (f"f{s['cb_float']:.2f}" if s.get("cb_float") else f"{int(s['confirm_bars'])}i")
        run = "✓" if is_running(s["name"]) else "-"
        tp = s.get("tp_type", "none") if s.get("tp_enabled", True) else "none"
        print(f"{s['name']:<10} {s['symbol']:<22} {s.get('timeframe','15m'):<5} {int(s['ema_span']):>5} {cb:>6} "
              f"{float(s['breakout_pct'])*100:>6.2f}% {tp:<18} {s['data_source']:<10} {run:<5}")
    print(f"\n共 {len(data['strategies'])} 个策略. 配置文件: {STRATEGIES_FILE}")


def cmd_start(args):
    names = _expand_names(args.names, args.all, default_all=True)
    started = []
    skipped = []
    for name in names:
        find_cfg(name)  # 校验存在
        if is_running(name):
            skipped.append(name)
            print(f"[{name}] already running (pid {read_pid(name)}), skip")
            continue
        cd = cache_dir_for(name)
        stdout_log = os.path.join(cd, "stdout.log")
        cmd = [DEFAULT_PY, "-u", os.path.join(HERE, "daemon.py"), name]
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


def _fmt_action(st):
    """从 state.json 的 last_action 提取可读短行. 返回 (短摘要, 详细描述)."""
    la = st.get("last_action")
    if not la:
        return ("-", "-")
    kind = la.get("kind", "?")
    price = _fmt_price(la.get("price"))
    time = (la.get("time") or "")[11:16] or "?"  # HH:MM
    short = f"{kind} {price} {time}"
    descr = la.get("descr") or short
    return (short, descr)


def cmd_status(args):
    data = load_strategies()
    print(f"{'NAME':<9} {'RUN':<4} {'PID':<6} {'POS':<4} {'SIZE':>4} {'PRICE':<13} {'UNREAL':<8} {'LAST_ACTION':<22} {'LAST_BAR':<17}")
    print("-" * 100)
    running = 0
    for s in sorted(data["strategies"], key=lambda x: (x.get("priority", 99), x["name"])):
        name = s["name"]
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
                la_short, _ = _fmt_action(st)
            except Exception as e:
                pos = size = price = unreal = lastbar = la_short = "?"
        else:
            pos = size = price = unreal = lastbar = la_short = "-"
        run_flag = "✓" if rn else "-"
        print(f"{name:<9} {run_flag:<4} {pid:<6} {pos:<4} {size:>4} {price:<13} {unreal:<8} {la_short:<22} {lastbar:<17}")
    print(f"\n运行中 {running}/{len(data['strategies'])}  (PID 文件在 monitor/caches/<name>/daemon.pid)")


def cmd_logs(args):
    name = args.name
    find_cfg(name)
    log_file = os.path.join(cache_dir_for(name), "monitor.log")
    if args.follow:
        _follow_single(name, log_file, args.n or 20)
        return
    if not os.path.exists(log_file):
        print(f"无日志文件: {log_file}")
        return
    n = args.n or 20
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
        find_cfg(n)
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


def _tail_multi(targets, init_n):
    """多品种聚合 tail -f. 每行前缀 [NAME] 区分."""
    states = {}
    for name, path in targets:
        for line in _read_tail(path, init_n):
            sys.stdout.write(f"[{name}] {_strip_ts(line)}")
        sys.stdout.flush()
        try:
            states[name] = (path, os.path.getsize(path))
        except FileNotFoundError:
            states[name] = (path, 0)
    print(f"\n=== {len(targets)} 个品种 跟随中, Ctrl+C 退出 (不影响 daemon) ===\n", flush=True)
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
                            sys.stdout.write(f"[{name}] {_strip_ts(line)}")
                        sys.stdout.flush()
                    states[name] = (path, size)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n=== 已停止聚合 tail (daemon 继续运行) ===")


def cmd_run(args):
    """前台跑指定品种, 可任意覆盖参数, 不写 strategies.json. 直接 exec daemon.py."""
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
        return [s["name"] for s in load_strategies()["strategies"]]
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
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("logs", help="查看品种日志; -f 实时跟随")
    sp.add_argument("name")
    sp.add_argument("-n", type=int, default=20, help="先打印最近 N 行")
    sp.add_argument("-f", "--follow", action="store_true", help="尾随, Ctrl+C 退出")
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
