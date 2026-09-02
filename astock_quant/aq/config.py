"""全局配置：路径、回测区间、交易成本与市场规则。

所有"市场规则"参数都带生效日期，回测里按当日实际规则取值，避免用今天的规则去
套历史（这本身就是一种未来函数）。
"""
from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
KLINE_HFQ_DIR = os.path.join(DATA_DIR, "kline_hfq")
KLINE_RAW_DIR = os.path.join(DATA_DIR, "kline_raw")
PANEL_DIR = os.path.join(DATA_DIR, "panel")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

for _d in (DATA_DIR, KLINE_HFQ_DIR, KLINE_RAW_DIR, PANEL_DIR, REPORT_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------- 数据区间
DATA_START = "2015-01-01"
DATA_END = "2026-09-02"

# 回测区间：前 1 年数据只用于计算因子的回看窗口（120 日动量等），不产生交易
BACKTEST_START = "2016-01-04"
BACKTEST_END = "2026-09-01"

# 样本内 / 样本外切分：所有参数只允许在样本内确定
IS_END = "2020-12-31"      # in-sample 结束
OOS_START = "2021-01-04"   # out-of-sample 开始

# ---------------------------------------------------------------- 指数
BENCH_INDEX = "sh000300"   # 沪深300，作为"不选股就买指数"的对照
INDEXES = ["sh000300", "sh000905", "sh000985", "sh000001", "sz399006"]
CALENDAR_INDEX = "sh000001"  # 上证综指，用作交易日历

# ---------------------------------------------------------------- 交易成本
COMMISSION_RATE = 0.00025      # 佣金，双边，万 2.5
MIN_COMMISSION = 0.0           # 组合层面按比例计费，忽略 5 元最低
TRANSFER_FEE_RATE = 0.00001    # 过户费，双边，十万分之一
SLIPPAGE_RATE = 0.0010         # 冲击成本 / 滑点，双边，单边 10bp

# 印花税：卖出单边收取，2008-09-19 起 0.1%，2023-08-28 减半至 0.05%
STAMP_DUTY_SCHEDULE = [
    ("1900-01-01", 0.0010),
    ("2023-08-28", 0.0005),
]

# ---------------------------------------------------------------- 市场规则
# 涨跌停幅度：主板 10%，创业板/科创板注册制后 20%，ST 5%（无 PIT 的 ST 名单，
# 统一按对应板块处理，并用"当日涨幅是否贴近上限"来判定，见 rules.py）
LIMIT_MAIN = 0.10
LIMIT_STAR = 0.20               # 科创板 688/689，自开板起就是 20%
LIMIT_CHINEXT = 0.20            # 创业板 300/301，2020-08-24 注册制改革后 20%
CHINEXT_20PCT_DATE = "2020-08-24"
LIMIT_TOLERANCE = 0.002         # 判定"贴上限"的容差

# ---------------------------------------------------------------- 股票池
MIN_LISTED_DAYS = 250           # 上市满 1 年才可选（次新股规则、炒作噪声）
MIN_HISTORY_DAYS = 130          # 因子回看所需的最少历史
LIQUIDITY_TOP_PCT = 0.80        # 按过去 20 日均成交额，剔除最不活跃的 20%
MIN_AMOUNT_YUAN = 2e7           # 过去 20 日均成交额下限：2000 万
EXCLUDE_PREFIX = ("8", "9", "4", "2")  # 北交所 / B 股
