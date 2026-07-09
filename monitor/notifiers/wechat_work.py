"""
企业微信群机器人 通知 — 国内主力推送通道 (不需翻墙).
配置统一从 monitor/wechat_webhook.json 或环境变量 MONITOR_WECHAT_WEBHOOK 读取.

获取 Webhook URL:
  1. 企业微信群里 -> 群设置 -> 群机器人 -> 添加 -> 复制 Webhook 地址
     形如 https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=<KEY>
  2. 写入 monitor/wechat_webhook.json 内容:
     { "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." }

频率限制: 每分钟 20 条到同个群. 监控信号触发一天通常几次, 远低于此阈值.
"""
import os
import json
import urllib.parse
import urllib.request

_CONFIG_PATH = os.environ.get(
    "MONITOR_WECHAT_WEBHOOK",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wechat_webhook.json"),
)
_CONFIG_PATH = _CONFIG_PATH if os.path.isfile(_CONFIG_PATH) else None
_CACHED = None


def _load():
    global _CACHED
    if _CONFIG_PATH is None:
        return None
    if _CACHED is not None:
        return _CACHED
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        url = cfg.get("webhook_url")
        _CACHED = url if url else None
        return _CACHED
    except Exception as e:
        print(f"[notifier:wechat_work] load config err: {e}", flush=True)
        return None


def config_path():
    return _CONFIG_PATH or "(未配置, 请写 monitor/wechat_webhook.json 或设 MONITOR_WECHAT_WEBHOOK)"


def is_configured():
    return _load() is not None


# 企业微信 markdown 消息 content 硬上限 4096 字节, 超长会被服务端静默截断.
# 留 96 字节余量给标题前缀/分片标记, 单段上限 4000 字节.
_MAX_CONTENT_BYTES = 4000

# qyapi.weixin.qq.com 是国内域名, 必须直连. EMA daemon 进程可能继承了 HTTP(S)_PROXY
# (启动 monitor.py start 时 shell 里开着代理), 走代理会对国内地址超时/不稳定.
# TRHRP daemon 没继承代理所以正常 —— 两者差异就在这里. 强制不走代理.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _split_utf8(text, limit=_MAX_CONTENT_BYTES):
    """按 UTF-8 字节数切分文本, 保证每段 <= limit 字节且不在字符中间断开."""
    chunks, cur = [], ""
    for ch in text:
        if len((cur + ch).encode("utf-8")) > limit:
            if cur:
                chunks.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        chunks.append(cur)
    return chunks


def notify(title, message, important=True, **_kw):
    """
    向企业微信群发送 markdown 消息 (更醒目, 重要消息红色框).
    企业微信 webhook 接受 markdown 但不支持文本颜色样式 (只支持简单 markdown 格式);
    important=True 时用更醒目的文本块前缀, 否则用普通 block.

    长度保护: 单条 markdown content 上限 4096 字节, 超出会被服务端静默截断.
    这里按 UTF-8 字节数自动分片成多条发送, 确保长内容完整到达.
    """
    url = _load()
    if not url:
        return False
    try:
        prefix = "🚨 " if important else "🔔 "
        full = f"{prefix}**{title}**\n\n{message}"
        parts = _split_utf8(full)
        ok = True
        for i, part in enumerate(parts, 1):
            suffix = f"\n\n_(第 {i}/{len(parts)} 段)_" if len(parts) > 1 else ""
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": part + suffix},
            }
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            resp = _NO_PROXY_OPENER.open(req, timeout=10)
            if resp.status != 200:
                print(f"[notifier:wechat_work] http {resp.status}", flush=True)
                ok = False
                continue
            # 企业微信返回 json {"errcode":0,"errmsg":"ok"} 成功
            body = resp.read().decode("utf-8", errors="replace")
            try:
                rj = json.loads(body)
                if rj.get("errcode", -1) != 0:
                    ok = False
            except Exception:
                pass
        return ok
    except Exception as e:
        print(f"[notifier:wechat_work] err: {e}", flush=True)
        return False
