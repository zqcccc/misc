#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3.11
echo "=== 1/6 rebuild panel (修科创板成交量单位) ==="; $PY scripts/build_panel.py
echo "=== 2/6 research ===";     $PY scripts/run_research.py --top-n 50 --freq 10 --buffer 2
echo "=== 3/6 grid ===";         $PY scripts/run_grid.py
echo "=== 4/6 walkforward ===";  $PY scripts/run_walkforward.py --top-n 200 --freq 40 --buffer 3
echo "=== 5/6 validation ===";   $PY scripts/run_validation.py --iters 200 --top-n 200 --freq 40 --buffer 3
echo "=== 6/6 jackknife+report ==="; $PY scripts/run_jackknife.py; $PY scripts/build_report.py
echo "=== ALL DONE ==="
