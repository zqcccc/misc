"""macOS 通知中心 — osascript 弹窗 + 声音. 仅在 macOS 本机工作."""
import subprocess

_AVAILABLE = None


def is_configured():
    """判断当前系统是否 macOS (有 osascript). 缓存结果."""
    global _AVAILABLE
    if _AVAILABLE is None:
        import shutil
        _AVAILABLE = shutil.which("osascript") is not None
    return _AVAILABLE


def config_path():
    return "osascript (macOS 系统通知中心)" if is_configured() else "(非 macOS, 跳过)"


def notify(title, message, important=True, sound=None, **_kw):
    if not is_configured():
        return False
    try:
        t = title.replace('"', '\\"')
        m = message.replace('"', '\\"')
        s = sound or ("Frog" if important else "Glass")
        script = f'display notification "{m}" with title "{t}" sound name "{s}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        return True
    except Exception as e:
        print(f"[notifier:macos] err: {e}", flush=True)
        return False
