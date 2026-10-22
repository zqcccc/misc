#!/usr/bin/env bash
# tmux 内部运行体：加载环境文件并以 --goal 模式启动 omp
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if [[ -n "${1:-}" && -f "$1" ]]; then
  # shellcheck disable=SC1090
  source "$1"
  shift
fi

GOAL_FILE="${GOAL_FILE:-quant_research/loop/GOAL_QUANT_RESEARCH.md}"
CONFIG_FILE="${CONFIG_FILE:-quant_research/loop/keepalive.yml}"
GOAL_BODY="$(cat "$GOAL_FILE")"

exec omp --goal "$GOAL_BODY" --config "$CONFIG_FILE" --auto-approve --approval-mode yolo "$@"
