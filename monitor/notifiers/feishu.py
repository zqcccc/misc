"""
飞书自定义群机器人 通知 — 国内备用推送通道 (不需翻墙, 与企业微信互补).
配置统一从 monitor/feishu_webhook.json 或环境变量读取:
  {
    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/<token>",
    "secret": "可选, 群机器人安全设置的签名校验密钥(推荐开启)"
  }
或环境变量 MONITOR_FEISHU_WEBHOOK / MONITOR_FEISHU_SECRET.
(MONITOR_FEISHU_WEBHOOK 通常指向配置文件路径; 若直接设为 http(s):// 地址也会当作 webhook 使用)

获取 webhook + secret:
  飞书群 -> 设置 -> 群机器人 -> 添加机器人(自定义) -> 复制 webhook 地址;
  安全设置选 "签名校验" 拿到 secret.

限制: 飞书 text 消息 content 最长 1500 字符(非字节), 超出服务端报错(非静默截断).
这里按字符数自动分片, 每片 <= 1500, 多片顺序发送.
频率限制: 同一机器人每分钟 100 条, 监控信号一天几次远低于此.
"""
import os
import json
import time
import base64
import hmac
import hashlib
import urllib.request

_CONFIG_PATH = os.environ.get(
    "MONITOR_FEISHU_WEBHOOK",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "feishu_webhook.json"),
)
_SECRET_ENV = os.environ.get("MONITOR_FEISHU_SECRET")

_MAX_CHARS = 1500  # 飞书 text 消息 content 上限(字符, 非字节)

# open.feishu.cn 是国内域名, 必须直连. EMA daemon 进程可能继承了 HTTP(S)_PROXY
# (启动 monitor.py start 时 shell 里开着代理), 走代理会对国内地址超时.
# TRHRP daemon 没继承代理所以正常 —— 两者差异就在这里. 强制不走代理.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _load():
    webhook = None
    secret = _SECRET_ENV
    if os.path.isfile(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            webhook = cfg.get("webhook_url")
            if secret is None:
                secret = cfg.get("secret")
        except Exception as e:
            print(f"[notifier:feishu] load config err: {e}", flush=True)
    # 兼容: MONITOR_FEISHU_WEBHOOK 直接设为 http(s) 地址时当作 webhook 本身
    env_wh = os.environ.get("MONITOR_FEISHU_WEBHOOK")
    if webhook is None and env_wh and env_wh.startswith("http"):
        webhook = env_wh
    return (webhook, secret) if webhook else (None, secret)


def config_path():
    return _CONFIG_PATH or "(未配置)"


def is_configured():
    wh, _ = _load()
    return wh is not None


def _sign(secret, timestamp):
    """飞书签名: HMAC-SHA256(timestamp + '\\n' + secret) -> base64."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _split_chars(text, limit=_MAX_CHARS):
    if not text:
        return [""]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def notify(title, message, important=True, **_kw):
    """
    向飞书群机器人发送 text 消息 (纯文本, 飞书 text 不支持 markdown 渲染).
    长度保护: 单条 text content 上限 1500 字符, 超出自动分片成多条.
    """
    webhook, secret = _load()
    if not webhook:
        return False
    try:
        prefix = "🚨 " if important else "🔔 "
        full = f"{prefix}【{title}】\n\n{message}"
        parts = _split_chars(full)
        ok = True
        for i, part in enumerate(parts, 1):
            content = part
            if len(parts) > 1:
                content = f"{part}\n\n(第 {i}/{len(parts)} 段)"
            payload = {"msg_type": "text", "content": {"text": content}}
            if secret:
                ts = str(int(time.time()))
                payload["timestamp"] = ts
                payload["sign"] = _sign(secret, ts)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                webhook, data=data, headers={"Content-Type": "application/json"}
            )
            resp = _NO_PROXY_OPENER.open(req, timeout=10)
            if resp.status != 200:
                print(f"[notifier:feishu] http {resp.status}", flush=True)
                ok = False
                continue
            # 飞书返回 {"code":0,"msg":"success"} 成功; 失败如 {"code":19021,...}
            body = resp.read().decode("utf-8", errors="replace")
            try:
                rj = json.loads(body)
                if rj.get("code", -1) != 0:
                    print(f"[notifier:feishu] api err: {rj}", flush=True)
                    ok = False
            except Exception:
                pass
        return ok
    except Exception as e:
        print(f"[notifier:feishu] err: {e}", flush=True)
        return False
