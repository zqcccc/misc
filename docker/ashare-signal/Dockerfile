FROM python:3.11-slim

WORKDIR /app

# 安装时区与基础网络库
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 安装 Python 依赖
COPY docker/ashare-signal/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制策略脚本与通知模块
COPY scripts/ashare_quant /app/scripts/ashare_quant
COPY monitor/notifiers /app/monitor/notifiers
COPY monitor/feishu_webhook.json* /app/monitor/

# 预置本地已验证的离线缓存与交付物 (bundle)
COPY deliverables/ashare_strategy_backtest.json /app/bundle_deliverables/ashare_strategy_backtest.json
COPY scripts/ashare_quant/cache /app/bundle_cache

# 入口脚本
COPY docker/ashare-signal/run.sh /app/run.sh
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
