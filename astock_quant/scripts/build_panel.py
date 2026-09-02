"""把逐股 CSV 拼成宽表面板并落盘。用法：python3 scripts/build_panel.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aq import config, panel  # noqa: E402


def main():
    print("拼接面板 ...", flush=True)
    panels = panel.build_panel()
    close = panels["close"]
    print(f"  原始：{close.shape[0]} 个交易日 × {close.shape[1]} 只股票")

    # 交易日历对齐：以上证综指交易日为准，剔除个股数据里的脏日期
    cal = panel.trading_calendar()
    cal = cal[(cal >= pd.Timestamp(config.DATA_START)) & (cal <= pd.Timestamp(config.DATA_END))]
    panels = {k: v.reindex(cal) for k, v in panels.items()}

    panels, n_bad = panel.clean_bad_ticks(panels)
    print(f"  清洗脏数据：{n_bad} 处异常跳变（连续交易日涨跌幅 > 25%），"
          f"相关股票自异常日起截断")

    # 剔除样本内永远不可能满足"上市满 250 交易日"的股票（纯粹减少列数，
    # 不涉及未来信息：这些代码在整段样本里都没进过股票池）
    bars = panels["close"].notna().sum()
    keep = bars[bars >= config.MIN_LISTED_DAYS].index
    panels = {k: v[keep].astype(np.float32) for k, v in panels.items()}
    print(f"  对齐后：{panels['close'].shape[0]} 交易日 × {panels['close'].shape[1]} 只股票")

    n_delisted = (panels["close"].apply(lambda s: s.last_valid_index())
                  < pd.Timestamp(config.DATA_END) - pd.Timedelta(days=15)).sum()
    print(f"  其中样本期内退市/长期停牌的：{n_delisted} 只（保留在池中，避免幸存者偏差）")

    panel.save_panels(panels)
    print(f"已保存到 {config.PANEL_DIR}")


if __name__ == "__main__":
    main()
