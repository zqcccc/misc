#!/usr/bin/env bash
# 量化策略持续探索一键启动脚本
# 默认前台会话运行（Ctrl-C 中断）；RUN_MODE=tmux 时进入后台 tmux 会话。
#
# 使用方法：
#   ./quant_research/loop/start.sh [AGENT_ID]
#   RUN_MODE=tmux ./quant_research/loop/start.sh [AGENT_ID]
#
# 停止：
#   touch quant_research/loop/STOP
#
# tmux 查看：
#   tmux attach -t quant-goal-1 （快捷键 Ctrl-b d 脱离保留）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if [[ -n "${1:-}" && "$1" != -* ]]; then
  AGENT_ID="$1"
  shift
fi
if [[ -z "${AGENT_ID:-}" ]]; then
  AGENT_ID="quant-agent-$(date +%s)-$$-$RANDOM"
fi
export AGENT_ID

STOP_FILE="quant_research/loop/STOP"
if [[ -f "$STOP_FILE" || -f STOP ]]; then
  echo "注意：检测到残留的停止标记（$STOP_FILE 或 STOP）"
  echo "启动后实例会在首轮检查到并直接退出。如需重新开始，请先执行：rm -f $STOP_FILE STOP"
fi
GOAL_FILE="${GOAL_FILE:-quant_research/loop/GOAL_QUANT_RESEARCH.md}"
CONFIG_FILE="${CONFIG_FILE:-quant_research/loop/keepalive.yml}"
RUN_MODE="${RUN_MODE:-fg}"

# —— 后台 tmux 模式 ——
if [[ "$RUN_MODE" == tmux ]]; then
  n=1
  while tmux has-session -t "quant-goal-$n" 2>/dev/null; do
    n=$((n + 1))
  done
  SESSION="quant-goal-$n"

  ENV_FILE="$SCRIPT_DIR/.env-${SESSION}"
  {
    echo "AGENT_ID='${AGENT_ID//\'/\'\\\'\'}'"
    echo "GOAL_FILE='${GOAL_FILE//\'/\'\\\'\'}'"
    echo "CONFIG_FILE='${CONFIG_FILE//\'/\'\\\'\'}'"
  } > "$ENV_FILE"

  tmux new-session -d -s "$SESSION" -c "$REPO_ROOT" -- "$SCRIPT_DIR/run-goal.sh" "$ENV_FILE" "$@"

  echo "AGENT_ID=${AGENT_ID} SESSION=${SESSION}"
  echo "已在 tmux 后台会话 ${SESSION} 启动 omp 量化持续探索循环。"
  echo "  接入终端查看：tmux attach -t ${SESSION}"
  echo "  断开后台保留：快捷键 Ctrl-b d"
  echo "  全局停止循环：touch $STOP_FILE"
  exit 0
fi

# —— 默认：前台运行模式 ——
echo "AGENT_ID=${AGENT_ID}（当前终端前台运行，后台运行请使用 RUN_MODE=tmux）"
GOAL_BODY="$(cat "$GOAL_FILE")"
exec omp --goal "$GOAL_BODY" --config "$CONFIG_FILE" --auto-approve --approval-mode yolo "$@"
