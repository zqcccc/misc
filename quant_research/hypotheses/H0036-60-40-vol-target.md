---
id: H0036
slug: 60-40-vol-target
title: SPY/IEF 60/40组合每月按滞后20日实现波动率缩放到10%目标并限制杠杆0.25至1.5倍，在2020-2026相对未管理60/40提高净夏普至少0.2且最大回撤降低25%
status: abandoned
verdict: OPEN
market: multi
freq: d1
family: lowvol
tags: volatility-targeting,60-40,tail-risk
owner: gpt
protocol_version: 2
research_role: hedge
parent: 
protocol_sha256:
score: 14/14
screen_verdict:
edge_cost_ratio:
cause:
plain:
report:
claimed_at: 2026-09-04T14:47:39Z
updated_at: 2026-09-05T01:54:24Z
sources: https://www.nber.org/papers/w22208 https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X 
---

# H0036 · SPY/IEF 60/40组合每月按滞后20日实现波动率缩放到10%目标并限制杠杆0.25至1.5倍，在2020-2026相对未管理60/40提高净夏普至少0.2且最大回撤降低25%

## 1. 假设（一句话，可证伪）
> 在 <市场/池子> 上，<信号> 对 <未来 N 日收益> 有 <方向> 的横截面/时序预测力，
> 在 <成本假设> 下净超额为正。

## 2. 机理（为什么应该成立）
风险溢价 / 微观结构 / 行为偏差 / 制度约束 —— 说清是哪一条。
**说不出机理、只有数据挖掘的，优先级直接降到最低，并在此写明。**

## 3. 先验检索（动手前必做，写结论不写过程）
- Quantocracy / arXiv / Alpha Architect / r/algotrading / GitHub 各自查到了什么？
- **有没有找到负面证据？** 只找到吹的、找不到骂的 = 检索没做完。
- 与台账里哪些 ID 相邻？为什么不算重复？

## 4. 数据需求
资产类别 / 时间颗粒度 / 起止区间 / 字段；现有资产能否直接支撑，缺的怎么主动取（公开 API）。
**不许因为"本地没现成数据"就砍掉高价值假设，也不许把假设削足适履塞进不匹配的缓存。**

## 5. 口径锁死（写完不许再改）
- 策略角色（alpha / diversifier / hedge / execution）：
- 宇宙 / 可投池规则：
- 成本（单边 bp，含税费滑点）：
- 调仓频率与持仓数：
- 基准（同池等权 + 指数对照）：
- 目标函数与判读线：
- 信息→决策→成交→PnL：
- 压力成本与容量假设：
- 尝试账本（参数/过滤器/区间/失败变体都计入）：

## 6. 实现位置
代码路径、入口函数、跑法（含后台长任务命令）。

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
- 2026-09-05 gpt：续跑检查发现 qbt 的无效置换统计可以绕过严格验收，已按长跑停止条件第 5 条停止。证据见 `protocol_issues/2026-09-05-gpt-nonfinite-permutation/README.md`。本卡只完成选题占坑，尚未完成成本闸、预注册或回测；未对策略下 FAIL/PARK/PASS 裁决。释放占坑，待协议维护经人工处理后再认领，不能将本次中断视为策略无效证据。
- `2026-09-05T01:54:24Z` gpt：放弃占坑 —— 发现验收协议缺陷，按长跑第5条停止；本卡尚未研究，证据见 protocol_issues/2026-09-05-gpt-nonfinite-permutation/README.md
