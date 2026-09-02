#!/usr/bin/env bash
set -uo pipefail

echo "[ashare-smallcap-quant] A股小微盘轮动量化计算服务启动中 @ $(date)"

export PYTHONPATH="/app:/app/astock_quant"
export TZ="Asia/Shanghai"

mkdir -p /app/deliverables

# 启动先运行一次生成
echo "[ashare-smallcap-quant] 正在执行初始交付物生成..."
python3 /app/astock_quant/scripts/smallcap_service.py --once --out /app/deliverables/smallcap_strategy.json || true

# 启动常驻守护循环 (每日 15:10 收盘后自动更新并支持崩溃告警)
echo "[ashare-smallcap-quant] 启动常驻守护进程..."
python3 /app/astock_quant/scripts/smallcap_service.py --daemon --out /app/deliverables/smallcap_strategy.json
