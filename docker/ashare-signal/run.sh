#!/usr/bin/env bash
# ashare-signal 容器入口:
# 1. 首次启动时从镜像 bundle 播种共享卷 (CSV 缓存 / 回测交付物 / signal_state.json)
# 2. 启动自检: 失败则标记 DEGRADED, 每轮重试直至通过, 绝不静默
# 3. 每个交易日 15:05~15:25 执行 刷新 -> 回测 -> 信号 推送流水线;
#    任一步失败即中止当日流程并进入有限退避重试, 成功前不宣告成功
set -uo pipefail

echo "[ashare-signal] Service starting @ $(date)"

export PYTHONPATH="/app"
export TZ="Asia/Shanghai"

# 读取飞书 Webhook 地址 (从环境变量或配置文件解析)
FEISHU_URL="${MONITOR_FEISHU_WEBHOOK:-}"
if [ -z "$FEISHU_URL" ] && [ -f /app/monitor/feishu_webhook.json ]; then
    FEISHU_URL=$(grep -o '"webhook_url": *"[^"]*"' /app/monitor/feishu_webhook.json | sed 's/"webhook_url": *"//;s/"//' 2>/dev/null) || FEISHU_URL=""
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
            # 上报本身失败必须如实反映, 不许打印"发送成功"
            if curl -fsS --max-time 10 -X POST -H "Content-Type: application/json" -d "$ALERT_JSON" "$FEISHU_URL"; then
                echo "[ashare-signal] Crash alert sent to Feishu."
            else
                echo "[ashare-signal] Crash alert FAILED to reach Feishu (curl exit $?)."
            fi
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
    if ! cp /app/bundle_deliverables/ashare_strategy_backtest.json /app/deliverables/ 2>/dev/null; then
        echo "[ashare-signal] WARN: bundle deliverables seed failed; shared volume deliverable missing."
    fi
fi

# 复制初始股票数据缓存 (如果卷为空); cp -n 保留卷内已有文件, 只做镜像首次播种
if ! cp -n /app/bundle_cache/*.csv /app/scripts/ashare_quant/cache/ 2>/dev/null; then
    echo "[ashare-signal] WARN: bundle cache seed failed (existing volume cache kept)."
fi

# 恢复去重/持仓状态: 卷内没有 signal_state.json 时才从 bundle 恢复, 卷内文件始终优先
CACHE_DIR=/app/scripts/ashare_quant/cache
STATE_FILE="$CACHE_DIR/signal_state.json"
if [ ! -f "$STATE_FILE" ] && [ -f /app/bundle_cache/signal_state.json ]; then
    echo "[ashare-signal] Restoring signal_state.json from image bundle (first seed)..."
    cp /app/bundle_cache/signal_state.json "$STATE_FILE" || echo "[ashare-signal] WARN: state seed failed."
fi

# 2. 启动时执行一次信号自检; 失败不静默: 标记 DEGRADED, 每轮循环重试直至成功
DEGRADED=0
STARTUP_CHECK_OK=0
echo "[ashare-signal] Running startup signal check..."
if python3 /app/scripts/ashare_quant/signal_service.py; then
    STARTUP_CHECK_OK=1
    echo "[ashare-signal] Startup signal check passed."
else
    DEGRADED=1
    echo "[ashare-signal] DEGRADED: startup signal check FAILED (exit $?), will retry each loop."
fi

# 3. 常驻循环守护 (每个交易日 15:05 自动执行)
# LAST_RUN_DATE 只在整个流水线成功后写入; 失败经由 RETRY_ATTEMPTS/RETRY_NEXT_TS 有限退避重试
LAST_RUN_DATE=""
RETRY_ATTEMPTS=0
RETRY_NEXT_TS=0
STARTUP_FAILS=0
MAX_ATTEMPTS=4

run_pipeline() {
    # A. 刷新最新行情; 失败时不允许继续用旧缓存生成新通知
    echo "-> Refreshing daily market data..."
    if ! python3 /app/scripts/ashare_quant/refresh_all_data.py; then
        echo "[ashare-signal] Refresh FAILED; aborting today's pipeline (stale cache must not feed new notifications)."
        return 1
    fi

    # B. 重算最新回测指标并更新到共享卷 (页面实时更新)
    echo "-> Updating backtest deliverables..."
    if ! python3 /app/scripts/ashare_quant/backtest_runner.py; then
        echo "[ashare-signal] Backtest runner FAILED; aborting today's pipeline."
        return 1
    fi

    # C. 计算信号并推送飞书
    echo "-> Checking strategy signal & notifying Feishu..."
    if ! python3 /app/scripts/ashare_quant/signal_service.py; then
        echo "[ashare-signal] Signal service FAILED; aborting today's pipeline."
        return 1
    fi

    return 0
}

while true; do
    # 自检未通过: 失败步数退避后整体重跑自检 (init 成功即清除 DEGRADED)
    if [ "$STARTUP_CHECK_OK" -ne 1 ]; then
        if python3 /app/scripts/ashare_quant/signal_service.py; then
            STARTUP_CHECK_OK=1
            DEGRADED=0
            echo "[ashare-signal] Startup signal check now passed; leaving DEGRADED state."
        else
            DEGRADED=1
            STARTUP_FAILS=$((STARTUP_FAILS + 1))
            echo "[ashare-signal] Startup check still failing (failure #$STARTUP_FAILS); will retry."
        fi
    fi

    CUR_DATE=$(date +%Y-%m-%d)
    CUR_TIME=$(date +%H:%M)
    DAY_OF_WEEK=$(date +%u) # 1~5 为周一至周五

    # 周一到周五，15:05 ~ 15:20 之间且今天未执行过
    if [ "$DAY_OF_WEEK" -le 5 ] && [ "$CUR_TIME" \> "15:04" ] && [ "$CUR_TIME" \< "15:25" ]; then
        if [ "$LAST_RUN_DATE" != "$CUR_DATE" ] && [ "$(date +%s)" -ge "$RETRY_NEXT_TS" ]; then
            if [ "$DEGRADED" -eq 1 ]; then
                echo "[ashare-signal] Pipeline suppressed: service still DEGRADED from failed startup check."
            elif [ "$RETRY_ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
                echo "[ashare-signal] Daily pipeline gave up after $RETRY_ATTEMPTS attempts on $CUR_DATE; no success signal was emitted. Retrying tomorrow."
                if [ -n "$FEISHU_URL" ] && [[ "$FEISHU_URL" == http* ]]; then
                    GIVEUP_JSON=$(cat << JSON
{
  "msg_type": "text",
  "content": {
    "text": "⚠️【流水线失败】A股信号监控当日流水线重试 $RETRY_ATTEMPTS 次仍失败，今日未产出信号通知（未宣告成功）。\n• 日期: $CUR_DATE\n• 时间: $(date '+%Y-%m-%d %H:%M:%S')\n• 说明: 明日窗口将自动重试，请检查容器日志。"
  }
}
JSON
)
                    if curl -fsS --max-time 10 -X POST -H "Content-Type: application/json" -d "$GIVEUP_JSON" "$FEISHU_URL"; then
                        echo "[ashare-signal] Give-up alert sent to Feishu."
                    else
                        echo "[ashare-signal] Give-up alert FAILED to reach Feishu (curl exit $?)."
                    fi
                fi
                LAST_RUN_DATE="$CUR_DATE"
                RETRY_ATTEMPTS=0
            else
                echo "[ashare-signal] Market closed for $CUR_DATE. Starting daily pipeline..."
                if run_pipeline; then
                    LAST_RUN_DATE="$CUR_DATE"
                    RETRY_ATTEMPTS=0
                    RETRY_NEXT_TS=0
                    echo "[ashare-signal] Daily pipeline finished successfully @ $(date)"
                else
                    RETRY_ATTEMPTS=$((RETRY_ATTEMPTS + 1))
                    # 30s/2m/4m/8m 退避, 覆盖整个 15:05~15:25 窗口; 仍失败则次日重试
                    RETRY_NEXT_TS=$(( $(date +%s) + 30 * (1 << (RETRY_ATTEMPTS - 1)) ))
                    echo "[ashare-signal] Pipeline failed (attempt $RETRY_ATTEMPTS/$MAX_ATTEMPTS); LAST_RUN_DATE NOT set; backoff until $(date -d "@$RETRY_NEXT_TS" '+%H:%M:%S' 2>/dev/null || date -r "$RETRY_NEXT_TS" '+%H:%M:%S')."
                fi
            fi
        fi
    fi

    sleep 30
done
