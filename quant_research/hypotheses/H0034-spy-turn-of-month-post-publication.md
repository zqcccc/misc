---
id: H0034
slug: spy-turn-of-month-post-publication
title: SPY 在每月倒数第二个交易日收盘买入并持有月末最后一日及下月前三个交易日，在论文发表后的2009-2026样本中扣除单边3bp后仍比随机四日窗口有正净增量
status: done
verdict: FAIL
market: us_stock
freq: d1
family: seasonality
tags: turn-of-month,calendar,spy
owner: gpt
protocol_version: 2
research_role: alpha
parent: 
protocol_sha256: 49d889c195be79ff
score: 9/14
screen_verdict: GO
edge_cost_ratio: 10.0
cause: 强度不足
plain: 2016至2021年虽然净赚22.7%，但同年月和星期随机挑四天仍有27.4%的方案更好，删掉2020年后相对市场还会转负
report:
claimed_at: 2026-09-04T14:32:43Z
updated_at: 2026-09-04T14:39:46Z
sources: https://www.chesler.us/resources/academia/turn_of_the_month_stock_returns.pdf https://repository.up.ac.za/bitstreams/1d1c2ddd-f5be-45b3-95f0-462abe301799/download 
summary: 2016至2021年虽然净赚22.7%，但同年月和星期随机挑四天仍有27.4%的方案更好，删掉2020年后相对市场还会转负
---

# H0034 · SPY 在每月倒数第二个交易日收盘买入并持有月末最后一日及下月前三个交易日，在论文发表后的2009-2026样本中扣除单边3bp后仍比随机四日窗口有正净增量

## 1. 假设（一句话，可证伪）
> 从每月倒数第二个共同交易日 16:00 ET 收盘买入 SPY，持有月末最后一个交易日及下月前三个
> 交易日的 close-to-close 收益，在单边 3bp 成本后，于论文发表后的独立 TEST 仍有正收益、
> 对全时段 SPY 有正净增量，并超过同年月/同持有期/同换手的随机连续四日窗口 95% 分位。

## 2. 机理（为什么应该成立）
**预定资金流与月末资产负债表约束。** 工资、养老金缴款和定投资金在月初进入，机构则在月末按
目标权重再平衡；若股票在此前相对债券走弱，月末被动调仓会形成买盘。付钱者是必须在固定日期
完成申购或风险预算复位、不能自由择时的机构和个人资金。

但原论文没有在月末成交量或股票基金净流入中找到支持，因此这只是可检验解释，不是已确认事实；
效应也已公开近二十年，最可能的结局是被套利或只剩承担市场 beta 的回报。这正是本轮只给 9/14、
将其作为校准位的原因。

## 3. 先验检索（动手前必做，写结论不写过程）
- **原始正面证据**：[McConnell & Xu, *Equity Returns at the Turn of the Month*](https://www.chesler.us/resources/academia/turn_of_the_month_stock_returns.pdf)
  用 1926-2005 CRSP 数据，将经典窗口锁为月末最后交易日到下月第 3 个交易日（−1,+3），并报告
  美国市场的平均回报几乎都集中在这四日；效应也不只由小盘、低价股或 1 月驱动。
- **机理的负证据来自原文**：论文没有发现该窗口 NYSE 成交量更高，也没有发现股票共同基金净流入
  同步增加，因此“发工资/定投买盘”并未被其数据证实。
- **直接失效证据**：[Plastun et al., *Rise and Fall of Calendar Anomalies over a Century*](https://repository.up.ac.za/bitstreams/1d1c2ddd-f5be-45b3-95f0-462abe301799/download)
  报告美国 turn-of-the-month 效应自约 1997 年后消失。这个反结论先于本卡，不能等回测差了才补。
- 先验搜索未发现 Quantocracy/Alpha Architect/GitHub 上能提供独立、逐日可复现的发表后 SPY 实盘
  账本；不把缺少复现当正面证据。与 H0014 同为美股日历事件，但 H0014 是 FOMC 公告风险，
  本卡完全由月序号决定；与台账无重复命中。

## 4. 数据需求
- Yahoo Finance `SPY` 日线 2008-12-01 至 2026-09-03，`auto_adjust=False`，使用 `Adj Close`
  （含分红、拆股调整）与 `Volume`；固定单一上市 ETF，无历史成分幸存者偏差。
- 交易日完全从 SPY 有效价格索引生成，不用自然日猜节假日；每月倒数第二个交易日收盘入场，下月
  第三个交易日收盘离场。若月初不足 3 个有效交易日（仅数据截尾可能发生），该事件作废。
- TRAIN/VALID 只下载到 2021-12-31 的物理开发文件；规格与代码冻结后，TEST 2022-01-01 至
  2026-09-03 只揭盲一次。数据清单保存查询、抓取时间、SHA256、时区与复权口径。

## 5. 口径锁死（写完不许再改）
- **策略角色**：alpha；不是“少持仓降低波动”的 hedge。
- **宇宙 / 可投池**：SPY 单资产；2009 年起，月月参加，不按季度、涨跌或波动率择月。
- **信号 / 持仓**：月末倒数第二个交易日收盘后目标仓位 1；之后四个完整交易日持有（当月最后
  一日 + 下月前三日），第 4 日收盘退出；其余现金收益固定记 0，不事后加入 T-bill。
- **成本**：单边 3bp，0↔1 每次变化均扣；压力 6bp。月度 24 次单边换手。
- **基准 / 归因**：现金 0；全窗口 SPY buy-and-hold 日收益回归；随机日历在每个年月内放置一个
  连续四交易日窗口，保持月份数、持有天数和换手，且整组日历匹配实际入场星期分布。
- **切分**：TRAIN 2009-01~2015-12；VALID 2016-01~2021-12；TEST 2022-01~2026-09-03
  一次揭盲。测试窗口不得从开发段开始持仓。
- **判读线**：A 层毛/成本≥2、压力≥1；PASS 需 TEST 净收益>0、对 SPY 年化净 alpha>0 且
  NW t≥2、DSR≥0.90、10 日块 prob(profit)≥95%、随机日历分位≥95%、逐年剔除方向不翻；
  VALID 失败即不揭 TEST。
- **信息→决策→成交→PnL**：交易所日历在月初已知 → 倒数第二日 15:59:59 决策 → 16:00
  收盘加 3bp 成交 → 下一交易日 close-to-close 才开始 PnL → 第四个持有日 16:00 退出。
- **容量**：SPY 极高流动性；按 100 万美元名义报告入场日成交额占比，缺 Volume 不得默认无限。
- **尝试账本**：5 个规格：主 `classic_h4`；`h3`、`h5` 持有平台；`first3_only`（月末收盘入，
  只含月初三日）；`classic_h4_short` 方向反事实。只允许主规格裁决，全部计入 DSR。

## 6. 实现位置
- 数据物理切分：`quant_research/us_stock/turn_of_month_h0034/prepare_data.py`；开发文件固定止于
  2021-12-31，TEST 写到 `/tmp/quant_research_h0034_test_gpt_20260904/` 并设为只读。
- 锁定实现：`quant_research/us_stock/turn_of_month_h0034/research.py`；开发运行：
  `python3 quant_research/us_stock/turn_of_month_h0034/research.py dev`。只有显式 `reveal --test-dir`
  才能读 TEST，本轮没有运行。
- 产物：`quant_research/us_stock/turn_of_month_h0034/out/` 下的 `research_dev.json`、
  `qbt_valid_report.json`、5 规格 trials、5,000 次匹配置换、日收益/成交与两个 manifest。

## 7. 验收结果（quant-backtest-protocol 研究漏斗）
| 层 | 问题 | 结果 | 判定 |
|---|---|---|---|
| A 快速证伪 | 付钱者 / 信号后毛边际 / 成本倍数 / 简单对照 | 原论文毛边际信封 7.2%/年；24 单边换手×3bp，毛/成本 10、压力 5 | GO |
| B 数据因果 | max\|full−truncated\|、PIT 宇宙 | SPY 固定单资产；信号只用预知交易日历，不读价格；DEV 与 TEST 物理隔离，报告 `test_revealed=false` | 通过 |
| B 成交时序 | information≤decision≤execution≤pnl_start | 倒数第二日 16:00 成交，月末最后一日才开始收益；manifest 校验通过 | 通过 |
| B 可交易性 | 换手、成本、压力成本、blocked_frac、容量 | VALID 71 轮、142 单边换手；3bp 净 CAGR 3.47%，6bp 压力 2.74%；100 万美元占入场成交额中位 0.0059%、最差 0.0136% | 通过 |
| C 归因 | 净 alpha、HAC/NW t、β、风险因子 | VALID 相对全期 SPY 年化净 alpha 0.74%，NW t **0.25**、β 0.165 | **强度失败** |
| C 搜索调整 | DSR（全部 trials）或单规格 PSR | 5 个预注册规格全部入账；DSR **0.2998** | 失败 |
| C 路径 | OOS 日收益分块自助 prob(profit)、P5 | 10 日块 5,000 次：prob(profit)=**91.06%**，P5 终值 **0.9444** | 失败 |
| C 置换 | 匹配换手/在市比例/风险的随机分位 | 每个入场年月、星期、4 日持有及换手匹配；5,000 次仅在 **72.64%** 分位 | 失败 |
| C 稳定 | walk-forward、逐年剔除、全起点、参数平台 | TRAIN t≈−0.02；VALID 剔除 2020 后增量转 −2.42%；h3 为负增量，h5 t=1.15 仍不到线 | 失败 |
| 组合价值 | 加入现有组合后的增量 / 对冲或执行角色指标 | 作为 alpha 未达到最小证据线，且仅约 19% 时间持有 SPY；不送组合评估 | 不评估 |

## 8. 裁决
`PASS` 严格报告通过，仅代表进入组合评估与 paper trading ｜ `FAIL` 已证伪 ｜ `PARK` 有信息但证据/可交易性/组合价值不足

**FAIL（强度不足）。** 2016-2021 的 71 个月净赚 22.7%，但同年月、同星期、同样持有四天的
随机窗口有 27.4% 做得更好；按年度删一次，删掉 2020 后相对市场的增量立即转负。测试集保持封存。

## 9. 留给后人的一句话
月末四日窗口在 2009-2021 仍有正的绝对收益，但证据不足以区分“固定日历效应”和普通四日运气；
不要拿经典 1926-2005 全样本或把持有期延到表现更好的 5 日，替事前四日规则翻案。
**复活条件：** 新增至少 10 年未参与选择的月度事件，且滚动匹配置换分位≥95%、净增量 t≥2。

## 探索日志
- `2026-09-04T14:33:48Z` gongzhao-44269：**成本闸 GO** —— 毛收益是成本的 10.0 倍，值得往下做（毛/成本 = 10.0）
- `2026-09-04T14:39:46Z` gongzhao-54503：**裁决 FAIL** —— 2016至2021年虽然净赚22.7%，但同年月和星期随机挑四天仍有27.4%的方案更好，删掉2020年后相对市场还会转负
