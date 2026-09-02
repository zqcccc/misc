#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3.11
echo "=== 1/4 research (修复分层测试后重跑) ==="; $PY scripts/run_research.py --top-n 50 --freq 10 --buffer 2
echo "=== 2/4 grid (加入低换手配置) ===";        $PY scripts/run_grid.py
echo "=== 3/4 validation ===";                  $PY scripts/run_validation.py --iters 200 --top-n 50 --freq 20
echo "=== 4/4 report ===";                      $PY scripts/build_report.py
echo "=== ALL DONE ==="
