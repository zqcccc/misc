#!/usr/bin/env bash
set -uo pipefail

echo "[ashare-signal] Service starting @ $(date)"

export PYTHONPATH="/app"
export TZ="Asia/Shanghai"

# 读取飞书 Webhook 地址 (从环境变量或配置文件解析)
FEISHU_URL="${MONITOR_FEISHU_WEBHOOK:-}"
if [ -z "$FEISHU_URL" ] && [ -f /app/monitor/feishu_webhook.json ]; then
    FEISHU_URL=$(grep -o '"webhook_url": *"[^"]*"' /app/monitor/feishu_webhook.json | sed 's/"webhook_url": *"//;s/"//' || true)
fi

# 核心崩溃告警陷阱: 当脚本因错误崩溃退出时，第一时间直连飞书上报！
on_crash_or_exit() {
    EXIT_CODE=$?
    if [ "$EXIT_CODE" -ne 0 ]; then
        echo "[ashare-signal] CRITICAL: Container exiting with error code $EXIT_CODE @ $(date)"
        if [ -n "$FEISHU_URL" ] && [[ "$FEISHU_URL" == http* ]]; then
            ALERT_JSON=$(cat << JSON
{
  "msg_type": "text",
  "content": {
    "text": "🚨【严重警报】A股策略信号监控容器意外崩溃退出！\n• 退出代码: $EXIT_CODE\n• 异常时间: $(date '+%Y-%m-%d %H:%M:%S')\n• 主机环境: Docker (ashare-signal)\n• 说明: 容器已异常终止，Docker 将尝试自动拉起，请登机查看日志！"
  }
}
JSON
)
            curl -s -X POST -H "Content-Type: application/json" -d "$ALERT_JSON" "$FEISHU_URL" || true
            echo "[ashare-signal] Crash alert sent to Feishu."
        fi
    else
        echo "[ashare-signal] Service stopped normally (exit 0)."
    fi
}
trap on_crash_or_exit EXIT

# 1. 引导数据到共享卷 (首发离线安全)
mkdir -p /app/deliverables /app/scripts/ashare_quant/cache
if [ ! -f /app/deliverables/ashare_strategy_backtest.json ]; then
    echo "[ashare-signal] Initializing deliverables from image bundle..."
    cp /app/bundle_deliverables/ashare_strategy_backtest.json /app/deliverables/ 2>/dev/null || true
fi

# 复制初始股票数据缓存 (如果卷为空)
cp -n /app/bundle_cache/*.csv /app/scripts/ashare_quant/cache/ 2>/dev/null || true

# 2. 启动时执行一次信号自检
echo "[ashare-signal] Running startup signal check..."
python3 /app/scripts/ashare_quant/signal_service.py || true

# 3. 常驻循环守护 (每个交易日 15:05 自动执行)
LAST_RUN_DATE=""

while true; do
    CUR_DATE=$(date +%Y-%m-%d)
    CUR_TIME=$(date +%H:%M)
    DAY_OF_WEEK=$(date +%u) # 1~5 为周一至周五

    # 周一到周五，15:05 ~ 15:20 之间且今天未执行过
    if [ "$DAY_OF_WEEK" -le 5 ] && [ "$CUR_TIME" \> "15:04" ] && [ "$CUR_TIME" \< "15:25" ]; then
        if [ "$LAST_RUN_DATE" != "$CUR_DATE" ]; then
            echo "[ashare-signal] Market closed for $CUR_DATE. Starting daily pipeline..."
            
            # A. 刷新最新行情
            echo "-> Refreshing daily market data..."
            python3 /app/scripts/ashare_quant/refresh_all_data.py || echo "Refresh failed, will use cached data"

            # B. 重算最新回测指标并更新到共享卷 (页面实时更新)
            echo "-> Updating backtest deliverables..."
            python3 /app/scripts/ashare_quant/backtest_runner.py || echo "Backtest runner failed"

            # C. 计算信号并推送飞书
            echo "-> Checking strategy signal & notifying Feishu..."
            python3 /app/scripts/ashare_quant/signal_service.py || echo "Signal service failed"

            LAST_RUN_DATE="$CUR_DATE"
            echo "[ashare-signal] Daily pipeline finished successfully @ $(date)"
        fi
    fi

    sleep 30
done
