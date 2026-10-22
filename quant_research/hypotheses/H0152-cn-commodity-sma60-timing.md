---
id: H0152
slug: cn-commodity-sma60-timing
title: 在中国商品期货（SHFE/CZCE/DCE/GFEX 59品种逐张合约官方日线，2016-2025共96期）上，品种自身60交易日时序均线择时（同合约内累计价格指数>SMA60持多、<=SMA60空仓），在单边3.0bp锁死成本下，月频调仓资金曲线相对『恒定持有该策略平均敞口的静态对照』净年化增量>0且NW t>=2，且两子段同号——中国商品期货单品种时序均线择时检验（commodity×timing空白格）
status: done
verdict: FAIL
market: commodity
freq: d1
family: timing
tags: 
owner: quant-agent-1792433252-86938-20969
protocol_version: 7
research_role: alpha
parent: 
protocol_sha256: cb5ede2cb8610cb2
score:
screen_verdict: GO
edge_cost_ratio: 18.241
cause: 强度不足
plain: 中国商品期货按品种自身六十日均线择时，扣掉一直持有同样平均仓位后每年只剩不到一个百分点的好处，统计上分不出真假，也不如满仓持有整个商品池
report:
claimed_at: 2026-10-19T19:03:14Z
updated_at: 2026-10-19T19:15:17Z
sources:
summary: 中国商品期货按品种自身六十日均线择时，扣掉一直持有同样平均仓位后每年只剩不到一个百分点的好处，统计上分不出真假，也不如满仓持有整个商品池
---

# H0152 · 在中国商品期货（SHFE/CZCE/DCE/GFEX 59品种逐张合约官方日线，2016-2025共96期）上，品种自身60交易日时序均线择时（同合约内累计价格指数>SMA60持多、<=SMA60空仓），在单边3.0bp锁死成本下，月频调仓资金曲线相对『恒定持有该策略平均敞口的静态对照』净年化增量>0且NW t>=2，且两子段同号——中国商品期货单品种时序均线择时检验（commodity×timing空白格）

## 1. 假设（一句话，可证伪）
> 在中国商品期货（SHFE/CZCE/DCE/GFEX 59品种逐张合约官方日线，2016-2025共96期）上，品种自身60交易日时序均线择时（同合约内累计价格指数>SMA60持多、<=SMA60空仓），在单边3.0bp锁死成本下，月频调仓资金曲线相对『恒定持有该策略平均敞口的静态对照』净年化增量>0且NW t>=2，且两子段同号——中国商品期货单品种时序均线择时检验（commodity×timing空白格）。

## 2. 机理（为什么应该成立）
趋势跟踪与库存周期假说：大宗商品受供给刚性与库存周期驱动，价格趋势具有较强持续性（MOP 2012 时序动量）。当品种价格上穿自身中期均线（反映持仓成本与趋势锚点），表明供需缺口正在扩大；跌破均线则反映供给过剩。均线规则可在熊市段自动降低暴露以规避亏损。

## 3. 先验检索（动手前必做，写结论不写过程）
- 经典文献：Moskowitz, Ooi & Pedersen (2012 JFE) 证明商品期货时序趋势跟踪的长期有效性；Brock, Lakonishok & LeBaron (1992) 报告移动均线在美股指数上的择时价值。
- 负面证据：台账 H0107（中国商品 TSMOM，FAIL 信号无增量）已证实 12-1 尺度时序动量在国内商品失效；H0144（标普期货 200 日均线，FAIL）证实均线择时收益来自降低暴露而非挑对时机。本卡检验更短 60 日尺度、且以同合约内复权指数构造均线（避免换月跳空污染）。
- 台账相邻卡：H0107、H0130、H0132、H0145、H0147。填补 commodity×timing 空白格。

## 4. 数据需求
- 中国商品期货交易所（SHFE/CZCE/DCE/GFEX）逐张合约官方日线，主力合约月频面板 `cn_commodity/data/mon/*.parquet`，59 个品种，2594 交易日（2016-01-04 ~ 2026-09-04）。
- 收益口径：同一合约内日收益，换月绝不跨合约拼接价差跳变（H0057 坑）；均线用同合约内累计价格指数构造。
- 宇宙过滤：20 日均主力合约成交额 >= 1 亿元人民币，含已停止交易品种。

## 5. 口径锁死（写完不许再改）
- 策略角色：alpha / timing
- 宇宙 / 可投池规则：59 品种活跃主力合约
- 成本：单边 3.0bp，压力档单边 6.0bp
- 调仓频率与持仓数：每 20 交易日决策；品种价格>SMA60 持多(1.0)，否则空仓(0.0)
- 基准：恒定持有该策略平均敞口（0.5114）的静态对照，兼报同池等权多头
- 目标函数与判读线：毛收益/成本倍数>=2（A层）；相对静态对照年化净超额>0且NW t>=2；块置换分位>=95%；prob(profit)>=95%；子段同号
- 信息→决策→成交→PnL：T 日收盘计算<=T日指数与均线 → T 日收盘后决策 → T+1 日收盘成交生效 → PnL 区间 T+1~T+20
- 压力成本与容量假设：单边 6.0bp 压力档；59 品种主力合约流动性充足
- 尝试账本：15 个真实参数变体（均线窗口 20/40/60/90/120 × 调仓周期 10/20/40），主口径 sma60_rebal20，全部计入 DSR/PSR 运气基线

## 6. 实现位置
- `cn_commodity/h0152/run.py`：主回测与块置换（1000 次，保持翻转次数与在市比例同构）
- `cn_commodity/h0152/variants.py`：15 个参数变体扫描，产出 `out/trials.csv`
- 产物：`cn_commodity/h0152/out/{qbt_strategy.csv, qbt_bench.csv, trades.csv, trials.csv, permutation.json, execution_manifest.json, h0152_main.json}` 与 `cn_commodity/h0152/data_manifest.json`、`out/report.json`
- 跑法：`.venv/bin/python cn_commodity/h0152/variants.py`；`.venv/bin/python cn_commodity/h0152/run.py`；`python3 .agents/skills/quant-backtest-protocol/scripts/qbt.py report --returns cn_commodity/h0152/out/qbt_strategy.csv --bench cn_commodity/h0152/out/qbt_bench.csv --trades cn_commodity/h0152/out/trades.csv --trials cn_commodity/h0152/out/trials.csv --trials-field score --permutation-result cn_commodity/h0152/out/permutation.json --execution-manifest cn_commodity/h0152/out/execution_manifest.json --data-manifest cn_commodity/h0152/data_manifest.json --market commodity --periods-per-year 252 --min-alpha-t 2 --min-random-percentile 0.95 --out cn_commodity/h0152/out/report.json`

## 7. 验收结果（quant-backtest-protocol 研究漏斗）
| 层 | 问题 | 结果 | 判定 |
|---|---|---|---|
| A 快速证伪 | 毛收益/成本倍数 | 毛年化 +2.26%，摩擦 0.12%/年，倍数 18.24 | GO |
| B 数据因果 | PIT 与同合约复权 | 指数与均线均用<=T日数据，换月不跨合约拼接 | 通过 |
| B 成交时序 | information≤decision≤execution | T 收盘决策、T+1 收盘成交，pnl_start 不早于 execution（校验器确认） | 通过 |
| B 可交易性 | 换手与压力成本 | 年化单边换手 1.74 次；压力档 6.0bp 下净增量仍 +0.75%/年 | 通过 |
| C 归因 | 净 alpha 与 NW t | 年化净超额 +0.84%/年，CAPM beta 1.078，NW alpha t = **0.56**（p=0.573） | 失败 |
| C 搜索调整 | DSR（15 个真实变体） | DSR = 0.9202（偏弱区间） | 边缘未达标 |
| C 路径 | 分块自助 prob(profit) | prob(profit) = **0.9098**，P5 = 0.9316 | 失败 |
| C 置换 | 块置换分位（1000 次） | 观测 +0.84%/年，置换均值 -0.19%/年，分位 **0.867** | 失败 |
| C 稳定 | 子段一致性 | 前半段 +2.11%/年，后半段 +0.66%/年（同号但衰减近七成） | 边缘 |
| 组合价值 | 相对同池等权 | 策略净年化 3.16% vs 满仓等权 4.53%，绝对收益更低 | 负向 |

## 8. 裁决
`FAIL`（死因：强度不足）
严格报告 `cn_commodity/h0152/out/report.json` 判定 FAIL，三项硬门禁未通过：Newey-West alpha t 0.56（要求>=2）、分块自助盈利概率 0.9098（要求>=0.95）、保持换手与在市比例同构的块置换分位 0.867（要求>=95%）。

## 9. 留给后人的一句话
中国商品期货上按品种自身 60 日均线择时，扣掉一直持有同样平均仓位后每年只剩不到一个百分点的好处，统计上分不出真假，且明显不如满仓持有整个商品池；本卡把商品横截面之外的单品种时序这一格也填成了负数。

## 探索日志
- `2026-10-19T19:05:51Z` quant-agent-1792433252-86938-20969：**成本闸 GO** —— 毛收益是成本的 18.2 倍，值得往下做（毛/成本 = 18.241）
- `2026-10-19T19:15:17Z` quant-agent-1792433252-86938-20969：**裁决 FAIL** —— 中国商品期货按品种自身六十日均线择时，扣掉一直持有同样平均仓位后每年只剩不到一个百分点的好处，统计上分不出真假，也不如满仓持有整个商品池
