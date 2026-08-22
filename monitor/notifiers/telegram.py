"""Telegram Bot 通知 — 读取 monitor/telegram_config.json 统一配置.
国内直连 api.telegram.org 被墙, 必须走代理. 代理来源优先级:
  telegram_config.json 的 "proxy" 字段 > 环境变量 HTTPS_PROXY/HTTP_PROXY
EMA/TRHRP daemon 进程通常不继承 shell 代理变量, 所以推荐在 json 里显式配 proxy.
"""
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


def _proxy_url():
    """代理优先级: json 的 proxy 字段 > 环境变量 HTTPS_PROXY/HTTP_PROXY."""
    cfg = _load()
    proxy = None
    if cfg:
        proxy = cfg.get("proxy")
    if not proxy:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    return proxy


def notify(title, message, important=True, **_kw):
    cfg = _load()
    if not cfg:
        return False
    try:
        text = f"{'🔔 ' if important else ''}{title}\n{message}"
        url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": cfg["chat_id"], "text": text}).encode()
        req = urllib.request.Request(url, data=data)
        # telegram 国内被墙, 走代理; 无代理则直连(境外/已配系统代理时可用).
        proxy = _proxy_url()
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            )
            resp = opener.open(req, timeout=10)
        else:
            resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"[notifier:telegram] err: {e}", flush=True)
        return False
