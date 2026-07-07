#!/usr/bin/env bash
# TRHRP 数据 sidecar 入口:
#   1) 首次启动若可写卷为空, 用镜像内置 seed 填充(离线也能出首份结果)
#   2) 循环: refresh(拉最新行情, 失败不阻断) -> backtest(重算 _all.json) -> 睡 24h
set -uo pipefail

echo "[trhrp-data] starting @ $(date -u)"

# 引导: 仅当目标缺失时复制 seed(no-clobber), 绝不覆盖运行时已刷新的数据
mkdir -p /data/deliverables /data/yf_cache /data/def_cache
cp -n /app/seed/def/*    /data/def_cache/   2>/dev/null || true
cp -n /app/seed/equity/* /data/yf_cache/    2>/dev/null || true

while true; do
    echo "[trhrp-data] refresh @ $(date -u)"
    python3 /app/scripts/refresh_trhrp_cache.py \
        || echo "[trhrp-data] refresh failed, will retry next cycle"

    echo "[trhrp-data] backtest @ $(date -u)"
    python3 /app/scripts/trhrp_backtest_live.py \
        || echo "[trhrp-data] backtest failed, will retry next cycle"

    echo "[trhrp-data] cycle done, sleeping 24h"
    sleep 86400
done
