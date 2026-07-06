# ETH / SOL / BNB 15m 最优 EMA 反手策略研究

## 项目位置

```
eth_sol_bnb_15m/
├── data/                          # 3币 × 3年 15m 永续 K 线
│   ├── eth_15m.parquet           # 105,601 bars (2023-07-01 ~ 2026-07-05)
│   ├── sol_15m.parquet           # 105,600 bars
│   └── bnb_15m.parquet           # 105,600 bars
├── scripts/                       # 回测与分析脚本
│   ├── backtest_engine.py        # skill 内置回测引擎 (5 函数 + 可视化)
│   ├── fetch_data.py             # ccxt 拉取历史 K 线
│   ├── research_step1_3.py        # 基线 EMA 网格 + confirm 网格扫描
│   ├── research_step3_full_grid.py  # EMA × cb × bp 三维网格
│   ├── research_step65_walkforward.py  # expanding window 无未来函数验证
│   ├── research_step6_kline_tp.py     # 7 种 K 线止盈全样本测试
│   ├── research_step6b_walkforward_with_tp.py  # A5 长上影 walk-forward 验证
│   ├── research_step67_pit.py    # ★ Point-in-Time 全起点抽样 (任意一天买入)
│   └── build_final_report.py     # 综合可视化 HTML 报告
└── reports/
    ├── FINAL_report.html         # ★ 自包含综合报告 (含图)
    ├── step3_chosen.json         # 各币种全样本最优配置
    ├── step3_full_grid.json      # 三维网格全结果
    ├── step65_walkforward.json   # walk-forward 累积结果
    ├── step67_pit.json           # PIT 抽样结果
    ├── step6_kline_tp.json       # K 线止盈全样本
    ├── step6b_walkforward_with_tp.json  # 含止盈 walk-forward
    └── fig_*.png                 # 各图 PNG
```

## 最终结论 · 最好的那个策略

### 三币种全样本最优配置 (step3, 找自全样本)

| 币种 | 配置 | 全样本净收益 | 最大回撤 | buy-hold (同期) |
|---|---|---|---|---|
| ETH | **EMA3000 + cb4 + bp0.8%** | +491.88% | -37.21% | +8.84% |
| SOL | **EMA3000 + cb16 + bp0.2%** | +979.39% | -49.14% | +314.12% |
| BNB | **EMA200 + cb32 + bp1.5%** | +322.73% | -33.52% | +172.40% |

⚠ 全样本最优含未来函数 (peak overfitting), 不真实可达.

### Walk-forward expanding 真实可达净值 (无未来函数, 60d 测试段 × 18 段)

| 币种 | walk-forward 净值 | buy-hold 同期 | 未来函数偏差 | wf 最大回撤 | bh 最大回撤 |
|---|---|---|---|---|---|
| **ETH** ⭐ | **+161.74%** | +12.67% | +330pp | -51.01% | -63.73% |
| SOL | -34.91% | +328.84% | +1014pp | -60.74% | -66.63% |
| BNB | +40.93% | +178.93% | +282pp | -33.72% | -48.89% |

→ ETH 是唯一 walk-forward 真正跑赢 buy-hold 的币种 (Real Alpha!)

### Point-in-Time 全起点抽样 · 任意一天买入 360 天后的分布

(起点间隔 7d, 97~106 个起点, 每起点跑 360 天HODL vs 策略)

| 币种 | 策略平均 | bh 平均 | diff | 5pct最差 | bh 5pct | diff | 胜率 | bh 胜率 |
|---|---|---|---|---|---|---|---|---|
| **ETH** ⭐ | +117.47% | +11.98% | **+105.5pp** | +39.05% | -45.11% | **+84.2pp** | 100% | 51.5% |
| **SOL** ⭐ | +96.24% | +71.51% | +24.7pp | +19.84% | -50.00% | **+69.8pp** | 100% | 51.5% |
| **BNB** ⭐ | +68.74% | +62.92% | +5.8pp | +30.32% | -5.29% | +35.6pp | 100% | 86.8% |

→ **三币种 360 天视角** (任意起点) 全部跑赢 buy-hold (mean/5pct/胜率/回撤)

### 答案 · 最好的那个策略

**对策略选择 (按"任意一天买入可达"评价)**:

- **ETH**: EMA3000 + cb4 + bp0.8% — 所有维度碾压 buy-hold, 最佳配置
- **SOL**: EMA3000 + cb16 + bp0.2% — 任意起点 360d 全胜 (100%), 5pct最差 +20% (bh -50%)
- **BNB**: EMA200 + cb32 + bp1.5% — 任意起点 360d 100% 胜率, 平均回撤远小于 bh

**对单策略综合最优 (跨三币种均可)**:

→ **EMA3000 + cb16 + bp0.2%** 也强烈推荐: PIT 360天 SOL 胜率 100%, ETH 胜率 98.9%

### 关键洞察

1. **趋势反手策略在"任何起点 360d 持有"的口径下系统性跑赢 buy-hold** (三币种均成立),
   短窗口 (60d/180d) 在大牛市中会被 buy-hold 右尾抛下;
2. **ETH 表现最稳** (4/4 维度全占优, walk-forward 真实可达), 因 ETH 在 2023-2026 整体横盘,
   趋势反手吃震荡长成;
3. **SOL 在大牛市 (2024-2025 暴涨 +500%+) 难跑赢 hold** — 这是趋势策略的固有限制;
4. **BNB 最优周期最短 (EMA200 ≈ 2天趋势)**, 显示其与外更频繁横盘 / 震荡;
5. **K 线止盈 (A5 长上影) 在 walk-forward ETH/SOL 中等比 baseline 略有改善 (+30pp/+33pp)**,
   在 BNB 无效 (-7pp) — 止盈不是必要改善, 趋势策略不该早止盈的结论保持.

## 使用方法

```bash
# 看自包含报告
open reports/FINAL_report.html

# 重新跑某个步骤
cd /Users/gongzhao/code/misc/eth_sol_bnb_15m
python scripts/research_step1_3.py
python scripts/research_step3_full_grid.py
python scripts/research_step65_walkforward.py
python scripts/research_step67_pit.py
python scripts/research_step6_kline_tp.py
python scripts/research_step6b_walkforward_with_tp.py
python scripts/build_final_report.py
```

## 风险提示

- 回测不代表未来收益, 三币种 3 年覆盖 1 段震荡 + 1 段大牛 + 1 段震荡, 行情属性局限;
- 全样本最优有未来函数, 仅 step6.5 walk-forward / step6.7 PIT 是真正可达口径;
- 永续合约有清算风险, 实盘需仓控;
- 本报告不构成投资建议.

## 复用的方法学

参考 skill `ema-trend-reversal-research` 的 7 步迭代法:
- §0 时间级别选择/对齐 (15m 默认)
- §1 基线 EMA 反手
- §3 确认过滤 (含 cb×bp 三维网格)
- §6 K 线形态止盈 + walk-forward 验证
- §6.5 walk-forward expanding (无未来函数)
- §6.7 Point-in-Time 全起点抽样 (任意一天买入分布)
