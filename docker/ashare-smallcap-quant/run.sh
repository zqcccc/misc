#!/usr/bin/env bash
set -uo pipefail

echo "[ashare-smallcap-quant] A股小微盘轮动量化计算服务启动中 @ $(date)"

export PYTHONPATH="/app:/app/astock_quant"
export TZ="Asia/Shanghai"
export SMALLCAP_DATA_DIR="${SMALLCAP_DATA_DIR:-/data/market}"
export SMALLCAP_STATE_DIR="${SMALLCAP_STATE_DIR:-/data/market/notify}"

mkdir -p /app/deliverables "$SMALLCAP_DATA_DIR" "$SMALLCAP_STATE_DIR"

# 命名卷/共享卷会遮住镜像内同路径文件，因此从独立 bundle 目录做首次引导。
if [ ! -f /app/deliverables/smallcap_strategy.json ]; then
    echo "[ashare-smallcap-quant] 初始化 smallcap_strategy.json seed..."
    cp /app/bundle_deliverables/smallcap_strategy.json /app/deliverables/smallcap_strategy.json
fi

# ARM1 自主增量抓取全市场行情；启动立即补漏，交易日 15:30 后再执行当日更新。
echo "[ashare-smallcap-quant] 启动增量数据与信号守护进程..."
exec python3 /app/astock_quant/scripts/smallcap_live_service.py \
    --daemon \
    --cache-dir "$SMALLCAP_DATA_DIR" \
    --out /app/deliverables/smallcap_strategy.json
