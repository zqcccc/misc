#!/usr/bin/env python3
"""从本地完整研究面板生成 ARM1 使用的滚动生产种子。"""
from __future__ import annotations

import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AQ_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, AQ_ROOT)

from aq import live_smallcap, panel  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, help="生产缓存输出目录")
    parser.add_argument("--days", type=int, default=live_smallcap.ROLLING_DAYS)
    args = parser.parse_args()

    print("[bootstrap] 加载完整研究面板...", flush=True)
    full = panel.load_panels(fields=["close", "amount", "close_raw"])
    cache = live_smallcap.bootstrap_from_full_panels(
        full, args.out_dir, rolling_days=args.days
    )
    print(
        f"[bootstrap] 完成: {len(cache['close'])} 天 × "
        f"{len(cache['close'].columns)} 只股票 -> {args.out_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
