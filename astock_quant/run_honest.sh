#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3.11
echo "=== 样本内选参配置 300只/20日/缓冲3（未偷看样本外）==="
$PY scripts/run_walkforward.py --top-n 300 --freq 20 --buffer 3
$PY scripts/run_validation.py --iters 200 --top-n 300 --freq 20 --buffer 3
$PY scripts/run_jackknife.py
echo "=== ALL DONE ==="
