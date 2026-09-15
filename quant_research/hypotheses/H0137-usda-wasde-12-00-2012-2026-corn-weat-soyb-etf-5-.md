---
id: H0137
slug: usda-wasde-12-00-2012-2026-corn-weat-soyb-etf-5-
title: USDA 月度 WASDE 供需报告发布日（通常美东时间 12:00，2012-2026），当日收盘前买入 CORN/WEAT/SOYB 三只农产品 ETF 等权持有 5 个交易日，在单边 10bp 锁死成本下净增量相对同期 buy&hold >0 且 NW t>=2，且随机同长度日历置换分位>=95%——公告解决不确定性溢价（futures×event 空白格）
status: claimed
verdict: OPEN
market: futures
freq: 事件驱动
family: event
tags: WASDE,农产品,公告日,event
owner: claude
protocol_version: 2
research_role: alpha
parent: 
protocol_sha256:
score: 8/14
screen_verdict:
edge_cost_ratio:
cause:
plain:
report:
claimed_at: 2026-09-14T16:03:22Z
updated_at: 2026-09-14T16:03:22Z
sources:
---

# H0137 · USDA 月度 WASDE 供需报告发布日（通常美东时间 12:00，2012-2026），当日收盘前买入 CORN/WEAT/SOYB 三只农产品 ETF 等权持有 5 个交易日，在单边 10bp 锁死成本下净增量相对同期 buy&hold >0 且 NW t>=2，且随机同长度日历置换分位>=95%——公告解决不确定性溢价（futures×event 空白格）

## 1. 假设（一句话，可证伪）
> USDA 月度 WASDE 供需报告（美东时间 12:00 发布，**2012–2026**）发布当日，
> CORN/WEAT/SOYB 三只农产品 ETF 等权在**当日 12:00（发布后）到次交易日收盘**
> 区间的日收益，系统性高于非报告日；按此在单边 10bp 锁死成本下相对 buy&hold
> 净增量 >0 且 NW t≥2，且随机同长度日历置换分位 ≥95%。

## 2. 机理（为什么应该成立）
**不确定性消解溢价**（Announcements Resolve Risk）：WASDE 是全球主要农产品供需预测
的权威来源，每月一次。在发布前，市场对全球粮食供需的不确定性高于平均水平——风险
厌恶的持有者压低了价格，这部分"不确定性折价"在发布后立即消解，带来均值回复型
的价格上涨。**付钱者 = 发布前平仓的对冲需求方（农产品生产商、贸易商在报告前减仓规避
意外风险，报告后重建头寸）**。为什么不被立刻套利：发布前持仓要承担报告内容的风险
（实际数据与共识偏差可导致当日大幅下跌），对无信息优势的参与者来说持仓成本正不确定。
**诚实标注**：文献支持混合——CFTC 报告显示报告前期权隐含波动率（IV）在发布后收缩，
这与"不确定性消解"的机理一致；但期货套利者已充分参与，ETF 层面的净超额很可能很小。
先验偏弱（8/14），预注册后 A 层即判。

## 3. 先验检索（动手前必做，写结论不写过程）
- 台账相邻：H0016（EIA 天然气存储报告 × UNG，FAIL——换手高成本吃穿）——同族"政府
  公告日 × 商品 ETF"，H0016 的死因是换手，本卡换手更低（月频 12 次/年 vs EIA 周频）；
  H0032（美债拍卖日，FAIL/无增量）；H0037（A 股 PEAD，FAIL）。正面：Gorton-Rouwenhorst
  框架里农产品期货有时间序列动量但不是事件驱动；无直接 WASDE ETF 文献。
- 负面证据（最重要）：如果 WASDE 溢价存在且以如此机械的方式可测，套利者早已压缩它。
  H0016 的先例是最好的负面案例：EIA 周报发布后 UNG 有溢价但换手 52 次/年把成本放大；
  本卡月频换手只有 ~12 次，成本更低，但机理上同样被充分覆盖。
- 台账查重：`qr search "USDA WASDE EIA 报告日 农产品"` 无命中，futures×event 为空白格。

## 4. 数据需求
| 项 | 内容 | 状态 |
|---|---|---|
| WASDE 日历 | USDA 官网 `/briefing-room/subjects/major-topics/farm-economy/usda-economic-research-service/supply-and-utilization/dates`（HTML 表格，或 NASS calendar API），2012–2026 | 一次 fetch，无登录 |
| CORN/WEAT/SOYB 日线 | yfinance，2012–2026（均 2012 年成立，已验证到 2014） | 本地可拉 |
| 无新订阅 | — | — |

## 5. 口径锁死（写完不许再改）
- 策略角色：alpha（事件时序 + 成本后净增量）
- 事件定义：WASDE 发布日（美东时间 12:00；**PIT 提前公开**——USDA 每年发布次年全年
  日历，information_time 远早于 execution，无前视）
- 成交时序：`information` = 报告发布（ET 12:00）→ `execution` = **当日 NYSE 收盘**（15:30 ET）
  → `pnl_start` = 当日收盘 → `pnl_end` = **次交易日收盘**（持有 1 日，主口径）；
  附报 当日 12:00 后到收盘（同日段，仅探索性参考，不参与主判读）。
  **信息早于成交**：12:00 发布，15:30 收盘，无前视。
- 标的：CORN、WEAT、SOYB 三只 ETF，**等权平均**日收益（每只权重 1/3）
- 成本：单边 10bp（含 ETF bid-ask 与滑点），双边 20bp；**压力 ×2 = 20bp 单边**。锁死。
- 基准：同期三只 ETF 等权 buy&hold 日收益（对照策略：任何日子都持有）
- 判读线（事前锁死，任一不过即 FAIL）：
  - L0 成本闸：事件日均超额 × 年均事件次数/年化成本（12 次/年 × 20bp = 2.4%/年）≥2，
    THIN(2~3) 可继续，<2 直接 FAIL
  - L1：事件日均超额（相对 buy&hold）> 0 且 NW t≥2（lag 5）
  - L2：按月分层随机日历置换 500 次，真实超额分位 ≥95%
  - L3：成本 ×2 后净增量仍 >0
  - L4（B0024）：中位数超额 / 胜率 / 去掉最好最坏 1 天后的均值——任一翻负即附注风险
  - L5 子段：2012–2018 / 2019–2026 同号，各报 MDE（B0018）
- 尝试账本（全计，共 4 个预注册规格）：
  ①主口径（报告日当日收盘持有 1 日）｜②持有 5 日（含报告日在内 5 个交易日）｜
  ③只持 CORN｜④前一日持有（报告日前一日收盘买入，当日收盘卖出，用于测"提前
  建仓"效应，如果这个更强说明是提前泄露而非合理的不确定性消解）。**只以主口径裁决**。

## 6. 实现位置
`futures/h0137/wasde.py` —— WASDE 日历解析 → 拉 ETF 数据 → L0 成本闸 → L1/L2/L3/L4/L5。
输出 `out/h0137.json`。跑法：`/opt/homebrew/bin/python3.11 futures/h0137/wasde.py`

## 7. 验收结果（quant-backtest-protocol 研究漏斗）
| 层 | 问题 | 结果 | 判定 |
|---|---|---|---|
| A 快速证伪 | 付钱者 / 信号后毛边际 / 成本倍数 / 简单对照 | | |
| B 数据因果 | max\|full−truncated\|、PIT 宇宙 | | |
| B 成交时序 | information≤decision≤execution≤pnl_start | | |
| B 可交易性 | 换手、成本、压力成本、blocked_frac、容量 | | |
| C 归因 | 净 alpha、HAC/NW t、β、风险因子 | | |
| C 搜索调整 | DSR（全部 trials）或单规格 PSR | | |
| C 路径 | OOS 日收益分块自助 prob(profit)、P5 | | |
| C 置换 | 匹配换手/在市比例/风险的随机分位 | | |
| C 稳定 | walk-forward、逐年剔除、全起点、参数平台 | | |
| 组合价值 | 加入现有组合后的增量 / 对冲或执行角色指标 | | |

## 8. 裁决
`PASS` 严格报告通过，仅代表进入组合评估与 paper trading ｜ `FAIL` 已证伪 ｜ `PARK` 有信息但证据/可交易性/组合价值不足

## 9. 留给后人的一句话
可复用的正面或负面结论。**负面结论同等重要——它就是别人不用再走一遍的那条路。**

## 探索日志
