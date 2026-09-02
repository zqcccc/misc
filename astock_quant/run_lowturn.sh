#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3.11
echo "=== 1/3 walkforward 200/40 ==="; $PY scripts/run_walkforward.py --top-n 200 --freq 40 --buffer 3
echo "=== 2/3 validation 200/40 ===";  $PY scripts/run_validation.py --iters 200 --top-n 200 --freq 40 --buffer 3
echo "=== 3/3 report ===";             $PY scripts/build_report.py
echo "=== ALL DONE ==="
