---
id: H0155
slug: cn-commodity-size-factor
title: 在中国商品期货（SHFE/CZCE/DCE/GFEX 59品种逐张合约官方日线，2018-2026共97期）上，横截面规模信号（按品种20日均成交额排序，最低1/3小品种做多、最高1/3大品种做空），在单边3.0bp锁死成本下，月频调仓资金曲线净年化>0且NW t>=2，且两子段同号——中国商品期货规模因子检验（commodity×size空白格）
status: done
verdict: FAIL
market: commodity
freq: d1
family: size
tags: 
owner: quant-agent-1792433252-86938-20969
protocol_version: 7
research_role: alpha
parent: 
protocol_sha256: cb5ede2cb8610cb2
score:
screen_verdict: GO
edge_cost_ratio: 30.818
cause: 强度不足
plain: 中国商品期货按成交规模做小品种做多大品种做空，八年多累计超额仅一个多百分点，统计检验分不出真假
report:
claimed_at: 2026-10-19T19:31:15Z
updated_at: 2026-10-19T19:39:33Z
sources:
summary: 中国商品期货按成交规模做小品种做多大品种做空，八年多累计超额仅一个多百分点，统计检验分不出真假
---

# H0155 · 在中国商品期货（SHFE/CZCE/DCE/GFEX 59品种逐张合约官方日线，2018-2026共97期）上，横截面规模信号（按品种20日均成交额排序，最低1/3小品种做多、最高1/3大品种做空），在单边3.0bp锁死成本下，月频调仓资金曲线净年化>0且NW t>=2，且两子段同号——中国商品期货规模因子检验（commodity×size空白格）

## 1. 假设（一句话，可证伪）
> 在中国商品期货（SHFE/CZCE/DCE/GFEX 59品种逐张合约官方日线，2018-2026共97期）上，横截面规模信号（按品种20日均成交额排序，最低1/3小品种做多、最高1/3大品种做空），在单边3.0bp锁死成本下，月频调仓资金曲线净年化>0且NW t>=2，且两子段同号——中国商品期货规模因子检验（commodity×size空白格）。

## 2. 机理（为什么应该成立）
流动性溢价假说（Liquidity Premium，Amihud 2002）：大品种（如螺纹钢、原油、PTA、豆粕）聚集了大量机构对冲资金与量化做市资金，定价高度充分且流动性充裕；小品种（成交额相对偏小的主力合约）受机构覆盖率低、持仓集中度较高影响，市场参与者要求额外的流动性溢价补偿。

## 3. 先验检索（动手前必做，写结论不写过程）
- 经典文献：股票与债券市场中规模与非流动性溢价广泛存在（Banz 1981, Amihud 2002）。
- 负面证据：加密市场台账 H0126（永续小盘币）与 H0146（现货小盘币）证实小币超额完全由单一牛市事件驱动，去尾后增量消失；商品期货领域流动性较小品种容易遭遇仓位容量受限与点差扩大。
- 台账相邻卡：H0087（carry）、H0123（仓单）、H0132（动量）、H0147（低波）、H0154（估值）。填补 commodity×size 空白格。

## 4. 数据需求
- 中国商品期货交易所（SHFE/CZCE/DCE/GFEX）逐张合约官方日线，主力合约月频面板，59 品种，1923 交易日（2018-05-24 ~ 2026-09-04，97 个调仓期）。
- 收益口径：同一合约内日收益，换月绝不跨合约拼接价差跳变。
- 规模代理：品种 20 日均主力合约成交额（turn20），以 1 亿元为活跃门槛。

## 5. 口径锁死（写完不许再改）
- 策略角色：alpha
- 宇宙 / 可投池规则：59 品种活跃主力合约
- 成本：单边 3.0bp，压力档单边 6.0bp
- 调仓频率与持仓数：每 20 交易日决策；成交额最低 1/3 做多、最高 1/3 做空，等权名义美元中性
- 基准：同池等权多头（EW benchmark）
- 目标函数与判读线：毛收益/成本倍数>=2（A层）；相对基准年化净超额>0且NW alpha t>=2；子段同号；置换分位>=95%
- 信息→决策→成交→PnL：T 日收盘计算<=T日 20 日均成交额，T 日收盘后决策，T+1 日起持仓生效至 T+20 日
- 压力成本与容量假设：单边 6.0bp；小品种做多需满足 1 亿元日成交下限
- 尝试账本：单一预注册标准 20 日均成交额三分位多空

## 6. 实现位置
- `cn_commodity/h0155/run.py`：主回测与 1000 次块置换
- `cn_commodity/h0155/probe_size.py`：探查脚本
- 产物：`cn_commodity/h0155/out/{qbt_strategy.csv, qbt_bench.csv, trades.csv, trials.csv, permutation.json, execution_manifest.json, h0155_main.json, report.json}`
- 跑法：`python3 .agents/skills/quant-backtest-protocol/scripts/qbt.py report --returns cn_commodity/h0155/out/qbt_strategy.csv --bench cn_commodity/h0155/out/qbt_bench.csv --trades cn_commodity/h0155/out/trades.csv --trials cn_commodity/h0155/out/trials.csv --trials-field score --single-spec --permutation-result cn_commodity/h0155/out/permutation.json --execution-manifest cn_commodity/h0155/out/execution_manifest.json --data-manifest cn_commodity/h0155/data_manifest.json --market commodity --periods-per-year 252 --min-alpha-t 2 --min-random-percentile 0.95 --out cn_commodity/h0155/out/report.json`

## 7. 验收结果（quant-backtest-protocol 研究漏斗）
| 层 | 问题 | 结果 | 判定 |
|---|---|---|---|
| A 快速证伪 | 毛超额 vs 摩擦成本 | 毛年化 +1.96%，摩擦 0.06%/年，倍数 30.818 | GO (通过成本门禁) |
| B 数据因果 | PIT 与同合约复权 | 成交额与收益均用<=T日同合约内数据，无前视 | 通过 |
| B 成交时序 | information≤decision≤execution | T 收盘决策、T+1 日起生效，时间对齐 | 通过 |
| B 可交易性 | 换手与摩擦 | 年化换手仅 2.12 次单边，持仓极其稳定 | 通过 |
| C 归因 | 净 alpha 与 NW t | 年化 alpha +1.70%，Newey-West alpha t = **1.23**（p=0.219） | 失败 (未达 t>=2 门槛) |
| C 路径检验 | 分块自助 prob(profit) | prob(profit) = **0.8336**，P5 = 0.9310 出现亏损重采样路径 | 失败 (未达 95% 门槛) |
| C 置换检验 | 1000次同构块置换 | 观测值 +1.23%/年，分位 0.959（p=0.041） | 通过 |
| C 子段检验 | 前半段 vs 后半段 | 前半段 +1.23%/年 (t=0.52)，后半段 +1.23%/年 (t=0.77) | 失败 (两子段统计均不显著) |

## 8. 裁决
`FAIL`（死因：强度不足）
严格报告 `cn_commodity/h0155/out/report.json` 判定 FAIL，两项核心门禁未通过：Newey-West alpha t 仅 1.23（要求>=2.0）、分块自助盈利概率仅 83.36%（要求>=95%），小品种多空年化超额仅一个多百分点，统计检验值未能达到显著门槛。

## 9. 留给后人的一句话
中国商品期货按成交规模做小品种做多、大品种做空虽然换手极低且点估计为正，但八年多累计超额仅一个多百分点，统计上分不出真假，无法支撑独立可交易策略。

## 探索日志
- `2026-10-19T19:31:41Z` quant-agent-1792433252-86938-20969：**成本闸 GO** —— 毛收益是成本的 30.8 倍，值得往下做（毛/成本 = 30.818）
- `2026-10-19T19:39:33Z` quant-agent-1792433252-86938-20969：**裁决 FAIL** —— 中国商品期货按成交规模做小品种做多大品种做空，八年多累计超额仅一个多百分点，统计检验分不出真假
