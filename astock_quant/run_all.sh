#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3.11
echo "=== 1/5 research ==="; $PY scripts/run_research.py --top-n 50 --freq 10 --buffer 2
echo "=== 2/5 grid ===";     $PY scripts/run_grid.py
echo "=== 3/5 walkforward ==="; $PY scripts/run_walkforward.py --top-n 50 --freq 20
echo "=== 4/5 validation ==="; $PY scripts/run_validation.py --iters 200 --top-n 50 --freq 20
echo "=== 5/5 report ===";   $PY scripts/build_report.py
echo "=== ALL DONE ==="
