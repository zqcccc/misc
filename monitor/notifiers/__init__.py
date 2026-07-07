"""
通知适配器统一接口.
每个 adapter 提供 notify(title, message, important=False) -> bool.
加新通道: 新建 <name>.py 实现 notify, 在 REGISTRY 注册.
"""
from . import macos
from . import telegram
from . import wechat_work
from . import feishu

REGISTRY = {
    "macos": macos,
    "telegram": telegram,
    "wechat_work": wechat_work,
    "feishu": feishu,
}


def notify_all(title, message, important=True, channels=None):
    """对 channels (默认全部已启用且配置 OK) 逐一发送, 返回 dict[channel] -> bool.

    注意: 未配置的通道 (如 telegram_config.json 不存在 / wechat_webhook.json 不存在)
    会通过 adapter 内部 is_configured() 优雅跳过, 不抛异常.
    """
    results = {}
    for name, mod in REGISTRY.items():
        if channels and name not in channels:
            continue
        # 未配置的通道直接跳过 (adapter.notify 会再判断, 这里提前是为了不打扰日志)
        if hasattr(mod, "is_configured") and not mod.is_configured():
            results[name] = False
            continue
        try:
            results[name] = bool(mod.notify(title, message, important=important))
        except Exception as e:
            results[name] = False
            print(f"[notifier:{name}] err: {e}", flush=True)
    return results
