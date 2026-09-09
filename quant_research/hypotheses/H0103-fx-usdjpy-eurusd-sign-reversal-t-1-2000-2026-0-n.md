---
id: H0103
slug: fx-usdjpy-eurusd-sign-reversal-t-1-2000-2026-0-n
title: 在 fx 上，外汇日频反转：USDJPY/EURUSD 昨收相对前收为负则今日开盘做多、为正则做空（sign-reversal），T+1 开盘平仓，2000-2026 相对静态对照（恒定持有美元多头）日频资金曲线净增量>0 且 NW t>=2，成本(单边2bp)后仍成立。预注册预测 A 层成本闸 STOP：2bp×2×252 交易日=年成本~10%，任何反转毛边际都覆盖不了。
status: done
verdict: FAIL
market: fx
freq: d1
family: reversal
tags: fx,reversal,usdjpy,eurusd,daily
owner: doubao
protocol_version: 2
research_role: alpha
parent: 
protocol_sha256: cb5ede2cb8610cb2
score: 8/14
screen_verdict: STOP
edge_cost_ratio: 0.485
cause: 成本吃穿
plain: --agent doubao
report: /Users/gongzhao/code/misc/fx/h0091/out/screen_h0103.json,/Users/gongzhao/code/misc/fx/h0091/trials_h0103.json
claimed_at: 2026-09-07T09:16:43Z
updated_at: 2026-09-07T09:18:04Z
sources: https://en.wikipedia.org/wiki/Foreign_exchange_market 
summary: --agent doubao
---

# H0103 · 在 fx 上，外汇日频反转：USDJPY/EURUSD 昨收相对前收为负则今日开盘做多、为正则做空（sign-reversal），T+1 开盘平仓，2000-2026 相对静态对照（恒定持有美元多头）日频资金曲线净增量>0 且 NW t>=2，成本(单边2bp)后仍成立。预注册预测 A 层成本闸 STOP：2bp×2×252 交易日=年成本~10%，任何反转毛边际都覆盖不了。

## 1. 假设（一句话，可证伪）

> 在 fx 上，外汇日频反转：USDJPY/EURUSD 昨收相对前收为负 → 今日开盘做多、为正 →
> 做空（sign-reversal），T+1 开盘平仓，2000-2026 相对静态对照（恒定持有）日频资金
> 曲线净增量 >0 且 NW t≥2，成本（单边 2bp）后仍成立。

## 2. 机理（为什么应该成立）

**微观结构（做市商库存/流动性提供）+ 行为（超调）。** 外汇日频收益有轻微负自相关
（1990s-2000s 文献：FX 微笑/日内均值回复），理论上做市商对订单流超调提供反向流动性。
**为什么已死（预注册负面）**：① 日频反转的毛边际历史上仅 ~0.5-1bp/日，而 FX 单边
2bp × 双边 × 252 交易日 = **年成本 ~10%**，成本闸几乎必然 STOP；② 2000s 后高频
算法交易吃掉日频反转（edge 转移到 tick 级）；③ 本台账 H0018（外汇动量 FAIL）已封
fx×momentum，反转是镜像方向，先验同弱。

## 3. 先验检索（动手前必做，写结论不写过程）

- **正面（历史）**：Froot-Thaler (2005) 综述汇率预测——日频反转在 1990s 有弱证据；
  Menkhoff-Taylor 系列在 2000s 前有日内均值回复证据。
- **负面（充分）**：① 成本结构是硬伤（FX 2bp 单边 vs 毛边际 <1bp/日）；② 2000s 后
  反转 edge 系统性衰减（文献一致）；③ 本台账 H0018（fx×momentum FAIL）、H0015
  （fx carry FAIL）、H0096（fx timing FAIL）——**fx 家族在台账内零存活**；④ 日频
  反转若真存在，做市商自己就吃了，轮不到零售。
- **与台账相邻性**：H0018 是外汇**动量**（同标的反方向），本卡是**反转**，格不同；
  fx×reversal 格为空，本卡第一个。查重闸（外汇反转/FX reversal/日元反转）无命中。

## 4. 数据需求

- USDJPY：`fx/h0091/out/raw/JPY_X.csv` 缓存（H0091 拉过）；EURUSD：yfinance 现拉
  （EURUSD=X，auto_adjust=False 裸价，遵守 B0015 自建读取器不清洗）。
- 2000-01 ~ 2026-08 日线。

## 5. 口径锁死（写完不许再改）

- **策略角色**：alpha（日频反转）。
- **宇宙**：USDJPY、EURUSD 两对，各自独立测（不混合）。
- **信号（PIT）**：t-1 收盘 vs t-2 收盘方向 → t 开盘按反方向建仓，t+1 开盘平仓。
- **成本（锁死）**：FX 单边 2bp；每笔双边 4bp；日频 ~252 笔/年 → 年成本 ~10%。
- **基准**：静态对照＝恒定持有（各自多头）。
- **目标函数与判读线**：L1 净增量>0 且 NW t≥2；L2 两子段同号；L3 成本×2 仍正；
  L4 随机日置换 ≥95%。
- **信息→决策→成交→PnL**：t-1 收盘信号 → t 开盘成交 → t+1 开盘平仓。
- **压力成本与容量**：FX 深度巨大；压力档=成本×2。
- **尝试账本**：
  T0 主口径（USDJPY 日频反转）；
  T1 EURUSD 日频反转；
  T2 周频反转（成本降到 ~2%/年，对照）；
  T3 3 日反转（持 3 日）；
  T4 2010+ 子段（高频化后）。
  **A 层先跑 screen 成本闸：毛边际 < 双边成本 → STOP，不写回测。**

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
- `2026-09-07T09:17:51Z` 未署名：**成本闸 STOP** —— 日频反转毛边际约2bp/日、年化约5%，但双边成本4bp/笔、年化成本约10%——毛收益只有成本的0.49倍，2010+毛边际还减半，成本吃穿，不值得写回测（毛/成本 = 0.485）
- `2026-09-07T09:18:02Z` 未署名：A层成本闸STOP即裁决：外汇日频反转信号确实存在(USDJPY毛边际+1.94bp/日、EURUSD+2.20bp/日,2000-2026)——但2010+各减半(0.86/1.06bp)，且双边成本4bp/笔×252交易日=年成本10.1% vs 年化毛边际4.9-5.5%，edge_cost_ratio=0.485，毛收益只有成本的0.49倍。反转edge是真的但永远喂不饱手续费，且高频化后衰减。裁决FAIL/成本吃穿，fx×reversal格封死(未写回测，screen STOP)。 --agent doubao
- `2026-09-07T09:18:04Z` 未署名：**裁决 FAIL** —— --agent doubao
