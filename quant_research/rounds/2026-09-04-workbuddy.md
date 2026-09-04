# 本轮台账 · 2026-09-04 · workbuddy

## 启动参数
- 预算：1 个假设（推进到裁决）
- 方向 / 市场 / 约束：全开放；优先往零覆盖维度撒点
- 配额例外：`qr coverage` 明示零覆盖市场 = 无，与 claude/doubao/gpt 同日同例外处理，
  改为优先打「零覆盖机理族 ml」+「全台账零覆盖颗粒度 h1」+ 各市场空白格。

## 覆盖盘点结论（qr coverage）
- 零覆盖市场：无（10 个市场均有卡）
- 零覆盖机理族（跨全部市场）：**ml**
- 零覆盖颗粒度（全台账）：**h1、tick**（m1/m15 各 1 张，其余全是 d1/w1/事件驱动）
- 今日其他 agent 已占坑（互斥避开）：claude→H0025 资金费横截面 carry（FAIL）、
  doubao→H0024 A股 size（PARK）、gpt→H0026 发达市场质量（FAIL）

## 候选池（14 个）
配额自查：市场 **10** 个（零覆盖市场 0 个，例外已注明）｜颗粒度 **4** 种（h1/d1/w1/事件驱动）
｜机理族 **8** 个（seasonality/microstructure/carry/flow/event/ml/lowvol/quality）｜
非价量输入 **8** 个（时段日历、月内日历、农事日历、两融余额、公告日、稳定币供给、ETF 流量、汇率时段）
｜第一直觉方向（crypto 时段效应）**2** 个 ✅ 全部达标

| # | 市场/颗粒度/族 | 一句话假设 | 机理 | 数据从哪来 | 预计换手 | 来源 |
|---|---|---|---|---|---|---|
| 1 | crypto_perp/h1/**seasonality** ⬜🟨 | 主流永续池每日 21:00–23:00 UTC 文献先验窗口持有等权多头、其余空仓，成本后净 alpha 对同池 24h B&H>0 | 传统市场参与者的注意力/流动性节律映射进 24/7 市场；窗口完整避开 00/08/16 UTC 资金费结算点 | data.binance.vision 1h 月度 zip（无频率限制），宇宙用本地 864 标的 1d dump 做 PIT 选池 | 高（730 边/年 → taker 3.65%/年） | [Padysak-Vojtko 2022 via paperswithbacktest](https://paperswithbacktest.com/blog/bitcoin-never-sleeps-exploiting-seasonality)；负证据 [Müller 2024 FRL](https://econpapers.repec.org/article/eeefinlet/v_3a64_3ay_3a2024_3ai_3ac_3as1544612324004598.htm)、[综述](https://frontierledger.ai/time-series-forecasting/seasonality-in-crypto-markets-myth-or-modelable-pattern) |
| 2 | us_stock/d1/seasonality ⬜ | SPY 月末→月初 4 日窗口持有、其余空仓，成本后优于 B&H | 发薪/结算周期驱动的机构再平衡流 | yfinance SPY 1993+ | 低（~50 边/年） | 经典 turn-of-month |
| 3 | us_stock/d1/microstructure ⬜ | SPY/QQQ 隔夜（prev close→open）与日内（open→close）收益分离后，隔夜腿单独持有仍有正超额 | 机构执行时点偏好（Lou-Polk-Skouras tug-of-war） | yfinance 日 OHLC | 中（252 边/年） | LPS 2019 |
| 4 | crypto_perp/d1/event ⬜ | 美国 BTC 现货 ETF 单日净流入→次日 BTC 正反应，按流入符号择时 | 被动流量冲击 + 注意力效应 | Farside Investors 流量表抓取 | 低（日频调仓） | 结构摩擦反推；样本 2024+ 偏短 |
| 5 | fx/h1/seasonality ⬜ | G10 货币对在特定 UTC 时段（东京/伦敦开盘）有稳定方向漂移 | 时段流动性分层 + 定盘机制 | yfinance 小时线仅 730 天 ⚠️ | 高 | arXiv 2609.02660 邻域 |
| 6 | rates/w1/carry ⬜ | 2s10s 陡峭化持有 rolldown carry，对恒定久期基准有超额 | 期限溢价 + rolldown | 财政部 CMT（H0008 已建管线） | 低 | H0008 相邻但结构不同 |
| 7 | futures/w1/carry ⬜ | 16-22 品种期限结构 carry 横截面，多贴水空升水 | 套保者展期溢价（Erb-Harvey） | 需自建 back-adjusted 序列（H0013 教训） | 低 | claude 本日候选 #3 未占 |
| 8 | commodity/w1/seasonality ⬜ | 农产品在收割窗口有做空偏向（收割压力） | 存货套保供给冲击 | 单品种 ETF 载体 + 农事日历 | 低 | 结构摩擦反推 |
| 9 | cn_stock/d1/flow ⬜ | 融资余额 20 日增量高的股票跑赢（杠杆资金动量） | 杠杆资金流/情绪自我强化 | akshare 两融（PIT=T+1 披露） | 中 | doubao 本日候选 #5 未占 |
| 10 | cn_stock/事件驱动/event ⬜ | 业绩预告盈利意外分层后的 PEAD | 信息扩散摩擦 | akshare 公告 PIT（难，claude 已判 0 分） | 低 | 经典 PEAD |
| 11 | crypto_spot/d1/flow ⬜ | 稳定币总供给 7 日变化→主流币风险偏好择时 | 稳定币=加密场内"弹药"，供给扩张=入场资金 | DeFiLlama 稳定币历史 API | 低 | 另类数据路线 |
| 12 | multi/d1/ml ⬜🟨 | 跨资产动量+波动特征 expanding 窗逻辑回归改善风险平价 | 状态非线性（ml 零覆盖族） | yfinance 全球 ETF | 中 | gpt 本日候选 #6 邻域 |
| 13 | hk_stock/d1/lowvol ⬜ | 港股 60 日 ivol 最低分位纯多有超额 | 低波异象在港股 | futu/akshare | 中 | hk lowvol 空白格 |
| 14 | crypto_perp/d1/seasonality ⬜ | BTC 周一效应（Velo 2026 近 3 月 +1.5%）可交易 | 周内流动性节律（弱机理） | 本地 1d dump | 中 | [Velo via coindesk 转述](https://www.digitaltoday.co.kr/en/view/53560/)；Müller 2024 判这类效应已死 |

⬜ = 空白的 市场×族 格子（12 个）｜🟨 = 打在零覆盖维度（h1 颗粒度 / ml 族）

## 打分卡（六维各 0~2）

| # | 机理 | 正交 | 数据 | 成本 | 容量 | 速度 | 总分 | 入选? |
|---|---|---|---|---|---|---|---|---|
| **1** crypto 21-23UTC | 2 | 2 | 2 | 1 | 2 | 2 | **11** | ✅ |
| 2 | SPY ToM | 2 | 1 | 2 | 2 | 2 | 2 | 11 | ❌ 并列，见下 |
| 3 | 隔夜/日内 | 2 | 1 | 2 | 2 | 2 | 2 | 11 | ❌ 并列，见下 |
| 4 | ETF flow | 1 | 2 | 2 | 2 | 2 | 2 | 11 | ❌ 并列，样本仅 32 个月功效不足 |
| 5 | fx 时段 | 1 | 2 | 1 | 1 | 2 | 2 | 9 | |
| 6 | 2s10s carry | 2 | 1 | 2 | 2 | 2 | 1 | 10 | |
| 7 | 商品 carry | 2 | 1 | 1 | 2 | 2 | 1 | 9 | |
| 8 | 收割压力 | 1 | 2 | 1 | 2 | 1 | 1 | 8 | |
| 9 | 两融 | 1 | 2 | 1 | 1 | 1 | 1 | 7 | |
| 10 | 业绩预告 | 2 | 2 | 0 | 1 | 2 | 0 | 7 | |
| 11 | 稳定币 | 1 | 2 | 2 | 1 | 1 | 2 | 9 | |
| 12 | multi ml | 0 | 2 | 2 | 1 | 1 | 1 | 7 | |
| 13 | hk 低波 | 1 | 2 | 1 | 1 | 1 | 1 | 7 | |
| 14 | 周一效应 | 0 | 2 | 2 | 1 | 2 | 2 | 9 | |

**入选：#1。** 四个 11 分并列（#1/#2/#3/#4），决胜依据：
① #1 一次打穿**两个**全台账零覆盖维度（h1 颗粒度 × crypto_perp seasonality 族），#2/#3 只填 us_stock 空白族
且 us_stock timing 已死 2 次（H0004/H0005）正交性实为 1；② #4 样本仅 2024+ 32 个月，任何裁决功效都不够，
天然只能出 PARK，浪费本轮预算；③ #1 文献先验有明确窗口参数（21:00–23:00 UTC，不许搜参），
且负面证据同样清晰（Müller 2024：日历收益异象不稳健）——正反先验俱全，无论结果如何都可复用。

## 未入选的，为什么（下一轮的输入）
- #2 SPY turn-of-month：11 分，机理扎实（发薪/结算周期）。下轮可直接做，yfinance 一条数据 2 小时出判定。
- #3 隔夜/日内拆分：11 分，LPS 2019 发表后衰减是主要风险；与 #2 共用数据管线可一起做。
- #4 ETF 流量：等 Farside 样本再攒一年到 40+ 个月再开，否则只能 PARK。
- #6 2s10s carry：H0008 死于"信号无增量"，本候选要先回答"carry 与 CP 因子信息是否正交"再动手。
- #7 商品 carry：必须先自建 back-adjusted 序列（H0013 证 yfinance 连续合约不可用），工程前置 2-4 小时。
- #12 multi ml：机理 0 分（纯数据挖掘），诚实打分就该垫底；ml 族要过 DSR 需要把全部网格计 trials，
  1 个假设的预算撑不起诚实的 ML 检验。
- #14 周一效应：Müller 2024 已系统证伪，不值得花预算。

## 本轮覆盖变化（对着 qr coverage）
- 变色的格子：crypto_perp×seasonality、h1 颗粒度（若跑完）
- 还剩的大片空白：ml 全族、tick 颗粒度、us/cn/fx 的大多数空白族

## 数据源踩坑记录
- data.binance.vision 月度 1h zip：无 key、无频率限制；早期文件无表头、时间戳有 ms/μs 两种单位
  （>1e15 即 μs）——复用 crypto_perp/scripts/fetch_binance.py 的清洗逻辑。
- yfinance 小时线只有近 730 天，做不了长样本时段效应（#5 因此数据 1 分）。
- 永续小时季节性的混杂：00/08/16 UTC 资金费结算点附近的微结构足迹会制造假 8h 季节
  （frontierledger 综述警告）；21-23 UTC 窗口不含结算点，但对比基准（24h B&H）含，
  funding 现金流差异必须单独归因。
