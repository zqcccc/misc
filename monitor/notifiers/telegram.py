"""Telegram Bot 通知 — 读取 monitor/telegram_config.json 统一配置."""
import os
import json
import urllib.parse
import urllib.request

_CONFIG_PATH = os.environ.get(
    "MONITOR_TELEGRAM_CONFIG",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "telegram_config.json"),
)
_CACHED = None
_CACHED_MTIME = 0


def _load():
    global _CACHED, _CACHED_MTIME
    if not os.path.exists(_CONFIG_PATH):
        return None
    try:
        mtime = os.path.getmtime(_CONFIG_PATH)
        if _CACHED is None or mtime != _CACHED_MTIME:
            with open(_CONFIG_PATH) as f:
                cfg = json.load(f)
            _CACHED = cfg if (cfg.get("bot_token") and cfg.get("chat_id")) else None
            _CACHED_MTIME = mtime
        return _CACHED
    except Exception as e:
        print(f"[notifier:telegram] load config err: {e}", flush=True)
        return None


def config_path():
    return _CONFIG_PATH


def is_configured():
    return _load() is not None


def notify(title, message, important=True, **_kw):
    cfg = _load()
    if not cfg:
        return False
    try:
        text = f"{'🔔 ' if important else ''}{title}\n{message}"
        url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": cfg["chat_id"], "text": text}).encode()
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"[notifier:telegram] err: {e}", flush=True)
        return False
