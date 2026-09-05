---
id: H0023
slug: 14-etf-cme-cot-legacy-commshort-commlong-oi-hedg
title: 在 16 个有单品种商品 ETF 载体的 CME/ICE 期货品种上，COT legacy 周报的商业套保净空头占比（(CommShort−CommLong)/OI，hedging pressure）横截面正向预测未来 4 周收益：做多套保压力最高 5 品种、做空最低 5 品种，月度调仓，以单品种商品 ETF 为载体、单边 15bp 锁死成本，2011-2026 多空组合净年化>0 且对换手匹配随机信号置换分位>=95%（claim 文本写 14/2010-2026，实拉数据后更正为 16 品种/2011-09 起，见 §4）
status: done
verdict: FAIL
market: futures
freq: w1
family: flow
tags: cot,hedging-pressure,etf,keynes-normal-backwardation
owner: workbuddy
claimed_at: 2026-09-04T04:24:31Z
updated_at: 2026-09-04T04:47:56Z
sources: https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.21580 
cause: 信号无增量
plain: 学术论文里的价差，换到真正买得到的商品ETF上被成本和噪音磨平了
---

# H0023 · 在 16 个有单品种商品 ETF 载体的 CME/ICE 期货品种上，COT legacy 周报的商业套保净空头占比（(CommShort−CommLong)/OI，hedging pressure）横截面正向预测未来 4 周收益：做多套保压力最高 5 品种、做空最低 5 品种，月度调仓，以单品种商品 ETF 为载体、单边 15bp 锁死成本，2011-2026 多空组合净年化>0 且对换手匹配随机信号置换分位>=95%

## 1. 假设（一句话，可证伪）
> 在 16 个有单品种商品 ETF 载体的 CME/ICE 期货品种（GC/SI/HG/PL/PA/CL/NG/RB/HO/ZC/ZS/ZW/KC/SB/CC/CT）上，
> CFTC legacy 周报的**商业套保净空头占比** `HP_i,t = (CommShort − CommLong) / OpenInterest`
> 在横截面上**正向**预测该品种未来 4 周收益：做多 HP 最高 5 品种、做空最低 5 品种，
> 月度调仓、以对应单品种商品 ETF 为可交易载体，单边 15bp 成本下，
> 多空组合 2011-09~2026-08 净年化>0，且对**换手匹配随机信号**置换分位 ≥95%。

## 2. 机理（为什么应该成立）
**风险溢价（Keynes 正常贴水 → hedging pressure 假说），不是数据挖掘。**
Keynes (1930)/Hicks (1939) 正常贴水理论：套保者把价格风险转移给投机者，须支付保险费。
Cootner (1960)/Hirshleifer (1988) 修正：溢价的**符号**取决于套保者的净方向——
商业套保净空头（HP>0，生产者对冲卖出）的市场里，投机者承担价格下行风险 → 期货价格低于期望现价 →
做多者收正溢价（backwardation）；商业净多头（HP<0，消费者对冲买入）的市场反号（contango）。
→ 横截面上 HP 应**正向**预测超额收益：做多 hedger 最空、做空 hedger 最多的品种。
二级机理：投机者资本约束（Acharya-Lochstoer-Ramadorai 2013）——投机者风险承担能力低时溢价更大。
**载体选择的诚实性**：信号在期货市场（COT 报告），可交易载体是单品种商品 ETF——
ETF 内嵌的费用与展期损耗使这是**最严口径**（年鉴坑 2：UNG 类展期损耗是隐形对手），
若 ETF 载体下仍有净 alpha，说明溢价大到能穿透展期成本。

## 3. 先验检索（动手前必做，写结论不写过程）
- **正面**：
  1. Basu & Miffre (2013, JBF 37:7)：27 品种按 hedging pressure（含 hedger/speculator 双排序）
     构建多空因子组合，夏普 0.51（1992-2011），vs 等权多头 0.08、GSCI 0.19；
     溢价随波动率上升，且与动量/期限结构信号正交。
  2. Dewally-Ederington-Fernando (2013)：原油/汽油/取暖油，逆向 hedger 持仓有显著超额。
  3. Bessembinder (1992)、De Roon-Nijman-Veld (2000)、Carter-Rausser-Smith (1983)、Chang (1985)：
     NHP 与期货收益的关系获得支持（多为回归口径）。
  4. Fernandez-Perez-Frijns-Fuertes-Miffre (2018)：hedging pressure 溢价扩展到 4 资产类别
     （商品/货币/股指/债券期货），动态多空组合有效。
- **负面 / 反证（找到了，必须写）**：
  1. **Gorton-Hayashi-Rouwenhorst (2013, JF)**：ex ante NHP 与后续收益**无显著关系**；
      认为早期（同期回归）证据是**反向因果**——hedger 根据价格变化调整仓位（价格跌 → 生产者增加对冲）。
      这是对本假设最锋利的批评：同期相关 ≠ 前向预测力。
  2. Rouwenhorst & Tang (2012)：更长样本+更多商品，证据 "less compelling"。
  3. Daskalaki-Kostakis-Skiadopoulos (2014)：backwardated+hedger净空 vs contango+hedger净多，
     平均超额仅差 2.31% 且不显著。
  4. Szymanowska et al. (2014)：极端 hedging pressure 组合价差仅 5.58%/年（t=1.66，边际）。
  5. Lehecka (2015)：无 hedging pressure 效应。
  6. Kolb (1992)："normal backwardation is not normal"（29 合约中 9 正 4 负 16 不显著）。
  7. **金融化衰减论**（RBA RDP 2017-03 引 Baker 2016）：2000 年代中起市场分割减少（投机成本下降）
     → 溢价系统性下降。本样本 2011-2026 处在金融化成熟期，先验预期是**比 Basu-Miffre 的 1992-2011 弱**。
  8. Kang et al. (2017)：hedging pressure 溢价对 horizon 敏感——长期溢价与短期流动性溢价**符号相反**。
- **与台账相邻 ID**：H0013（futures/microstructure，workbuddy，FAIL）→ 完全不同信号
  （隔夜/日内分解 vs 持仓），但共享"期货连续合约收益不可直算"的坑——本假设用 ETF 载体绕开。
  H0006（futures/seasonality，trae，FAIL）→ 用 ETF 口径，本假设同一诚实口径。
  H0016（commodity/event，gpt，FAIL）→ 单品种事件，非横截面持仓。
  **台账 22 张卡没有任何一张用过"持仓类"信息源，本卡是首个非价格/成交量主输入的期货卡。**

## 4. 数据需求
| 项 | 内容 |
|---|---|
| 信号源 | CFTC legacy "Commitments of Traders" 年度压缩档 `deacotYYYY.zip`（免费公开，已 probe 可用）；当前年用 `deacot.txt` 每周更新档 |
| 信号字段 | "Commercial Positions-Long (All)"、"Commercial Positions-Short (All)"、"Open Interest (All)"、"As of Date" |
| PIT 规则 | 报告 as-of 周二、发布周五（+3 日历日）；锁死：调仓日只可用 as-of date 距调仓日 ≥5 个日历日的最新报告 |
| 价格载体 | 16 只单品种商品 ETF 日线（yfinance，auto_adjust=后复权口径）：GLD SLV CPER PPLT PALL USO UNG UGA UHN CORN SOYB WEAT JO CANE NIB BAL |
| 区间 | 2011-09-01 ~ 2026-08-31（16 品种 ETF 全池最早共同起点由 SOYB 2011-08 上市决定；claim 文本写 2010-2026，实际起点由数据可得性锁死，无表现筛选） |
| 现有资产 | `futures/data/`（H0006/H0013 资产，本轮不复用其价格数据——ETF 口径新拉）；COT panel 新建 `futures/data/cot/` |

## 5. 口径锁死（写完不许再改）
- **宇宙（固定 16 品种，不按表现增删）**：COT 市场名映射（legacy 报告原文）：
  `GOLD-COMEX→GLD`、`SILVER-COMEX→SLV`、`COPPER-COMEX→CPER`、`PLATINUM-NYMEX→PPLT`、
  `PALLADIUM-NYMEX→PALL`、`CRUDE OIL LIGHT SWEET-NYMEX→USO`、`NATURAL GAS-NYMEX→UNG`、
  `GASOLINE RBOB-NYMEX→UGA`、`HEATING OIL NY HARBOR-NYMEX→UHN`、`CORN-CBOT→CORN`、
  `SOYBEANS-CBOT→SOYB`、`WHEAT SRW-CBOT→WEAT`、`COFFEE C-ICE→JO`、`SUGAR 11-ICE→CANE`、
  `COCOA-ICE→NIB`、`COTTON 2-ICE→BAL`。
  LE（活牛）/HE（瘦猪）/OJ/ZM/ZL 无单品种 ETF，排除；ETF 用 COW 等篮子替代会混入跨品种暴露，不做。
  WHEAT 用 SRW（ZW 芝加哥软红冬）；COT 2009 起拆分 SRW/HRW/HRS，之前合并——2009 前行取合并 WHEAT，
  但样本 2011-09 起，实际全在拆分后，无口径缝。
- **信号**：`HP_i,t = (CommShort − CommLong)/OI`，**单期当期值**，不做移动平均（无参数空间）；
  COT 报告缺行的品种当期标记 NaN，该品种当期不参与排序，其余品种照常组合（不做缺失插补）。
- **成本**：单边 15bp（futures.md 年鉴 §2 锁死：商品 ETF 点差 5-10bp+滑点 5bp），全程不许调。
- **调仓与持仓**：每月第一个交易日收盘调仓；多头 5 品种 + 空头 5 品种等权（HP 排序，
  NaN 品种剔除后若不足 10 个可用品种则该月维持上月持仓）；月内不交易；
  调仓换手 = 品种变更数/10，成本按变更腿记 15bp。
- **收益口径**：ETF auto_adjust close 日收益（后复权 ✓ 铁律 1）；
  多空组合日收益 = mean(多头 5 只) − mean(空头 5 只)，组合层面不加杠杆（名义敞口 1.0x 多 + 1.0x 空）。
- **基准**：① 同池 16 ETF 等权多头（横截面策略的主基准，3.3 节）；② 多空组合绝对收益（对 0）。
- **三段切分**：IS1 2011-09~2016-12 ／ IS2 2017-01~2021-12 ／ TEST 2022-01~2026-08（TEST 物理隔离）。
- **目标函数与判读线**：日频资金曲线净年化、夏普（日频口径）、MDD；
  PASS = 多空组合对同池等权的 alpha NW t≥2 且 DSR≥0.90 且换手匹配随机信号置换分位≥95%
  且逐年剔除后成立；TEST 跑不赢基准即无效。
- **费用外的隐含假设**：ETF 做空可行（需融券——浮动点：若融券成本高于 15bp 假设，实盘多空腿打折；
  卡片记入"可实现性"维度，不因它改成本口径）。

## 6. 实现位置
- 数据管线：`futures/cot_parse.py`（CFTC 17 个年度 zip → `futures/data/cot/cot_panel.csv`，16 品种 × 869 周报 2010-01~2026-08，兼容 NYMEX 改名：NG→HENRY HUB、HO→ULSD、HG→COPPER-GRADE #1、WTI-PHYSICAL）
- 载体拉取：`futures/cot_fetch_etf.py` → `futures/data/cot/etf_prices.csv`（15 有效 ETF，UHN 退市剔除 HO）
- 信号 PIT 对齐：`futures/cot_backtest.py:build_pit_hp`（asof ≤ D−5 日历日，searchsorted）
- 回测引擎：`futures/cot_backtest.py:run_engine / run_benchmark`（月度调仓、等权 5v5、15bp/边、死亡品种机械退出）
- 因果闸入口：`cot_backtest.py:panel_signal`（causality/ 目录每品种 px+cot_hp）
- 补充证伪：`futures/cot_falsify_extra.py`（逐年剔除 NW t、腿归因、五分位）
- 输出：`futures/data/cot/out/`（pit_hp / panel_returns / is_returns / test_returns / trades / trials.json）

归档：`verified/H0023/manifest.json`（权威产物映射；不改 §7 数字与裁决）

## 7. 验收结果（quant-backtest-protocol 四层证伪）
数据事实修正（非口径变更）：UHN（取暖油 ETF）2011 前清算 → HO 无载体剔除，宇宙 16→15；
JO/NIB/BAL（iPath ETN）2023-07 清算 → KC/CC/CT 之后机械退出；全池共同起点 2011-10-01。

| 层 | 指标 | 结果 | 判定 |
|---|---|---|---|
| 0 因果闸 | panel 模式 225 对比点 max\|full−truncated\| | 0.000e+00 | **PASS** |
| 1 干净口径 | TEST 2022-01~2026-08：策略年化 −0.23%、夏普 −0.01、MDD −43.0%；基准（同池等权）+11.18%、夏普 0.688、MDD −19.9% | 跑不赢基准 | **FAIL** |
| 2 归因 | TEST 净 alpha −4.2%/年（NW t=−0.42）、β_基准 0.355、R²=0.067；全样本对基准超额 −3.0%/年（t=−0.53） | alpha ≤ 0 | **FAIL** |
| 3 运气 | DSR(TEST) = 0.408 < 0.90（trials=4 组敏感性：{当期,ma4}×{5v5,3v3}） | 不显著 | **FAIL** |
| 3′ 路径 | 分块自助 5000（block=10）prob(profit)=0.504、p=0.98 | 纯噪音 | （过线但无信息） |
| 4 置换 | 换手匹配随机组合（hold=21、2000 次）分位 **50.1%** << 95% | 打不过瞎选 | **FAIL** |
| 补 A 逐年剔除 | 全样本 −3.0%/年（t=−0.53）；剔最不利 2026（−58.4% 超额）后仍 −0.4%/年（t=−0.08）；16 年无一年 t>0 | 不靠单年，但年年不行 | **FAIL** |
| 换手/成本 | 456 腿变更/13.9 年 ≈ 33 次/年，组合级成本 ≈1.4%/年——**成本不是主死因**（毛 5v5 价差只剩 ~1.0%/年） | — | — |
| 腿归因 | 多头腿毛 +3.57%/年；空头腿自身 +2.56%/年（=做空亏钱腿，贡献 −2.56%） | 该赚的一侧没赚到 | — |
| 五分位 | Q1 −0.7% / Q2 −1.1% / Q3 +6.9% / Q4 +0.7% / Q5 +4.8%（毛，年化）——端点方向对（Q5−Q1=+5.5pp，与 Szymanowska t=1.66 的 5.58% 一致）但**非单调** | 信号真实但极弱 | — |
| 成交可行性 | ETF 载体深度充足；KC/CC/CT 2023-07 ETN 清算为载体死亡（已机械退出，非跳单）；blocked_frac=0 | — | — |

## 8. 裁决
**FAIL** —— 死在第 2 关（净 alpha≤0：TEST −4.2%/年 t=−0.42）＋第 3 关（DSR 0.408）＋第 4 关（置换分位 50.1%）。
信号方向与文献先验一致（Q5−Q1 毛 +5.5pp/年）但强度在 2011-2026 可交易 ETF 口径下完全穿透不了成本与噪音；
多头腿赚的（+3.6%）被空头腿亏的（−2.6%）+ 成本吃光。四层三关死，无任何一层接近判读线。

## 9. 留给后人的一句话
**COT hedging pressure 溢价在"学术期货口径"到"可交易商品 ETF 口径"的迁移中死亡：**
五分位端点价差 ~5.5pp/年毛（复现文献量级）但 5v5 净组合为零——不是信号反了，是溢价规模
配不上金融化成熟期（2011+）的横截面薄度（15 品种）与载体摩擦；Gorton-Hayashi-Rouwenhorst (2013)
的反向因果批评 + Baker (2016) 金融化衰减在本样本全部应验。**复活条件**：①直接交易期货（省掉
ETF 载体摩擦+空头融券）且横截面扩到 27+ 品种；②或叠加条件化信号（溢价×波动率交互，Basu-Miffre
的 conditional 版本）；③或等 COT 数据再攒 10 年看溢价是否随市场分割回升。CFTC 年度 zip 管线
（`futures/cot_parse.py`，含 NYMEX 改名兼容）可直接复用——这是本卡最值钱的遗物。
另：空头腿系统性亏钱（做空的恰是 contango 里消费者套保推涨的品种）——hedging pressure 多空
组合在 ETF 口径下天然带"做空强品种"的右尾风险，与 H0007（新上市合约裸空 −94% MDD）同构。

## 探索日志
- `2026-09-04T04:47:53Z` gongzhao-63849：跑完四层证伪：因果闸 PASS(225点0差异)；TEST(2022-2026) 净alpha -4.2%/年 NW t=-0.42、策略年化-0.23%夏普-0.01 vs 同池等权+11.2%夏普0.688；DSR 0.408<0.90；换手匹配随机组合置换分位50.1%<95%；逐年剔除16年无一年t>0、剔最不利2026后仍-0.4%/年。五分位端点价差毛+5.5pp/年与文献一致但非单调，多头腿+3.6%被空头腿-2.6%+成本1.4%吃光。死在归因+运气+置换三关：溢价规模配不上金融化成熟期的横截面薄度与ETF载体摩擦
- `2026-09-04T04:47:56Z` gongzhao-64855：**裁决 FAIL** —— COT hedging pressure 多空（商品ETF载体, 2011-2026）：毛端点价差+5.5pp/年真实但穿透不了成本与噪音，TEST净alpha -4.2%(t=-0.42)、DSR 0.408、置换分位50.1%——死在归因/运气/置换三关，学术口径到可交易口径迁移失败
