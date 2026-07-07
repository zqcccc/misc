# TRHRP 回测数据 sidecar —— 让 /trhrp-backtest 页面在任意服务器上自动有数据并持续更新.
#
# 它不依赖宿主机有 Python / yfinance: 镜像自带依赖与 seed 数据,
# 启动时把 seed 引导进可写卷(离线也能出首份结果), 之后每天 refresh(拉最新行情) + backtest(重算),
# 把 _all.json 写到共享卷 /data/trhrp_backtest_all, 由 misc 容器只读挂载为 /app/deliverables.
FROM python:3.12-slim

WORKDIR /app

# 编译依赖保险(lxml 等若有源码安装需求)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY scripts/trhrp_lib/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 回测所需的仓库代码(内置 helper + 主脚本 + monitor 策略口径)
COPY scripts/ /app/scripts/
COPY monitor/trhrp_strategy.py /app/monitor/trhrp_strategy.py
COPY monitor/strategies_trhrp.json /app/monitor/strategies_trhrp.json

# 引导用 seed 数据(离线也能跑出首份结果)
COPY scripts/trhrp_lib/seed/ /app/seed/

# 容器内路径: 所有写操作指向可写卷 /data(由 compose 挂载命名卷)
ENV TRHRP_ROOT=/app \
    TRHRP_CFG=/app/monitor/strategies_trhrp.json \
    TRHRP_STRATEGY=/app/monitor \
    TRHRP_OUT=/data/trhrp_backtest_all \
    TRHRP_YF_CACHE=/data/yf_cache \
    TRHRP_DEF_CACHE=/data/def_cache

COPY docker/trhrp-data/run.sh /app/run.sh
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
