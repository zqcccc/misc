---
title: TRHRP 策略详解（Tail Risk Hedged Rotation Portfolio）
date: '2026-07-07T14:00:00.000Z'
description: '一套跨多市场、按波动率+动量识别市场状态(Regime)来切换股/金/债仓位的尾部风险对冲型轮动组合，全文拆解每个英文专业名词。'
---

# TRHRP 策略详解（Tail Risk Hedged Rotation Portfolio）

> TRHRP = **T**ail **R**isk **H**edged **R**otation **P**ortfolio（尾部风险对冲型轮动组合）。
> 它是一个**跨多个市场、按"市场状态"切换股票仓位**的资产配置策略——不挑个股、不择时买卖单只股票，而是决定"现在该把多少比例放在股票里、多少放黄金、多少放现金/短债"。

![TRHRP 端到端数据流](/trhrp-pipeline.png)

---

## 一、TRHRP 到底是个什么策略

它同时做三件事：

1. **多市场（Multi-market）**：同时盯 6 个市场——沪深300、中证500、恒生指数、恒生科技、SPY（美股大盘）、QQQ（美股科技）。
2. **状态识别（Regime）**：用波动率 + 动量，把每个市场分成三档——进攻（risk_on）、中性（moderate）、防御（risk_off）。
3. **轮换配置（Rotation + Hedge）**：三档对应不同的股/金/债配比，并叠加一层"均值回归"微调。

代码里它跑在 `monitor/daemon_trhrp.py`，每 60 分钟算一次快照，把结果写进 `state.json`，由 `monitor.py status` 展示。和 `ba` 项目里的同源脚本口径一致，但 monitor 这边是独立维护的。

---

## 二、数据从哪来（download_ohlc）

对每个 market，去 **yfinance**（Yahoo Finance 的 Python 数据接口库）拉 **OHLC**（Open/High/Low/Close，开/高/低/收）日线，时间从 2010 年到今天。

- **ticker**：传给 yfinance 的代码，如 `510300.SS`、`^HSI`、`SPY`。
- **proxy**：有些指数没直接 ETF，用代理标的（如恒生科技用 `3033.HK`）。纯说明字段。
- **cache（本地缓存）**：拉下来的 CSV 存到 `caches/TRHRP/yf_cache/`，12 小时内不重复拉（避免撞 yfinance 限频）。
- **retry / backoff（重试 + 退避）**：yfinance 偶尔限频返回空，代码会重试 3 次、每次退避 3 秒；全失败时**回退到本地旧缓存**而不是让该市场变 `null`。
- **rate-limit（限频）**：Yahoo 对短时间连续请求会限流，所以品种之间还故意 sleep 1.5 秒。

---

## 三、核心：信号怎么算（build_signal_frame）

对收盘价序列算出 5 个量（窗口单位都是"交易日"）：

| 信号 | 计算 | 中文 |
|---|---|---|
| **mom**（Momentum 动量） | 近 21 天累计涨跌幅 `close.pct_change(21)` | 约 1 个月收益率，衡量"涨没涨" |
| **vol**（Realized Volatility 已实现波动率） | 日收益滚动 21 天标准差 × √252 | 年化波动率，衡量"颠不颠" |
| **vol_p60** | vol 在 252 天窗口内的**第 60 百分位** | "相对过去一年，现在波动率算高还是低"的分水岭 |
| **vol_med**（Median 中位数） | vol 在 126 天窗口内的中位数 | 半年波动中枢 |
| **z-score** | log(价格) 的 252 天滚动 z-score | 价格相对自身长期均值偏离几个标准差（σ）|

几个关键点：

- **annualized（年化）**：日波动 × √252（一年约 252 个交易日），把"日波动"放大成"年波动"才好比较。
- **rolling window（滚动窗口）**：不是看全部历史一个值，而是每天往回看 N 天算一个值，形成一条时间序列。
- **percentile（百分位 p60）**：把过去 252 天的 vol 从小到大排，取第 60% 位置的值——高于它就说明"现在比历史上 60% 的时间都更动荡"。
- **log price（对数价格） + mean reversion（均值回归）**：用 `log(价)` 算 z-score，衡量价格是否"涨过头/跌过头"，假设长期会回归均值。

---

## 四、三档 Regime 怎么判定（决策树）

用两个输入 `vol` 和 `mom`：

- **risk_off（防御）🔴**：满足任一即触发
  - `vol > 30%`（**crash_trigger 崩盘触发线**）——波动爆表，无条件防御；
  - 或 `vol > vol_p60 且 mom < 0`——波动率高于历史 60% 分位、且价格在跌（典型的"下跌且放大"恐慌态）。
- **risk_on（进攻）🟢**：`vol ≤ vol_med 且 mom > 0 且 未触发崩盘`——波动收敛在中枢以下、价格在涨，放心进攻。
- **moderate（中性）🟡**：以上都不满足的"其他情况"——比如波动不高但也没低到中枢下，或涨了但波动还偏大。

注意 `changed`（状态切换）：daemon 会比较"上一有效交易日"和"最新交易日"的 regime，不同就标记为 changed，并触发通知。

![Regime 判定决策树](/trhrp-decision-tree.png)

---

## 五、仓位怎么配（regime_weights + overlay）

**基础配比表**（regime_weights，股/金/债三者加起来 = 100%）：

| Regime | 股票 Equity | 黄金 GLD | 短债 SGOV |
|---|---|---|---|
| risk_on | 80% | 10% | 10% |
| moderate | 50% | 25% | 25% |
| risk_off | 20% | 20% | 60% |

逻辑很直观：**越防御，股票越少、现金（短债）越多**。

**叠加层 overlay（均值回归微调）**：在基础配比之上，用 252 天 z-score 做"极端偏离就反向操作"：

- **A股/港股组（A/H）**：z ≤ −3.4 → 抄底加仓（股票 +20pp，即 20 个百分点），z ≥ 3.0 → 高位减仓（−20pp）；
- **美股组**：阈值更窄，z ≤ −2.0 加 +10pp，z ≥ 2.0 减 −10pp。

`delta` 就是触发时股票仓位变动的**幅度（pp = percentage point 百分点）**，SGOV 反向变动保持总和不变。`buy_threshold / sell_threshold` 是触发加减仓的 z-score 边界。

> GLD = SPDR Gold Shares（全球最大黄金 ETF，跟踪金价）；SGOV = iShares 0-3 Month Treasury Bond ETF（超短久期美债，近似现金/货基，几乎零波动）。

---

## 六、输出与通知

- **snapshot（快照）**：一次对所有市场算完的结果集合，写进 `state.json`。
- **asOfDate（数据截至日）**：信号基于哪天的收盘。口径是 **T 日收盘算信号、T+1 生效**（次日才按新配比调仓）。
- **stale（过期）**：只要某市场走了"缓存回退"，就标 stale，提示数据可能不新鲜。
- **notify_on_change**：任一市场 regime 变化就发 **Telegram** 通知（monitor 端本身不连 TG，由 notifiers 框架统一发）。

---

## 七、英文专业名词全拆解（对照表）

**策略本体**

- **TRHRP** = Tail Risk Hedged Rotation Portfolio
- **Tail Risk（尾部风险）**：市场极端暴跌的小概率大亏损风险
- **Hedged（对冲）**：用黄金/短债抵消股票下跌风险
- **Rotation（轮动）**：在不同资产/状态间切换仓位，而非死扛
- **Portfolio（投资组合）**：这里指"股+金+债"的资产配置整体
- **Regime（状态/机制）**：市场当前所处的宏观"体质"（攻/中/防）
- **Multi-market（多市场）**：同时覆盖多个市场
- **Universe（标的宇宙）**：策略监控的全部标的集合
- **Signal（信号）**：算出来的判定值（mom/vol/z-score）
- **Snapshot（快照）**：某一时刻全市场状态的完整切面

**数据/计算**

- **OHLC** = Open/High/Low/Close（开/高/低/收）
- **yfinance**：Yahoo Finance 的 Python 数据接口库
- **Ticker（代码）**：如 SPY、510300.SS
- **Proxy（代理）**：用 ETF 代理某个指数
- **Cache（缓存）**：本地存的历史数据，避免重复下载
- **Retry（重试）/ Backoff（退避）**：失败后隔段时间再试
- **Rate-limit（限频）**：数据源限制单位时间请求数
- **Momentum / mom（动量）**：一段时间涨跌幅，衡量趋势
- **Realized Volatility / vol（已实现波动率）**：用历史收益标准差衡量的真实波动
- **Window（窗口）**：计算时往回看的天数
- **Rolling（滚动）**：每天重算、形成时间序列
- **Percentile / p60（百分位）**：排序后第 60% 位置的值
- **Median（中位数）**：排序后正中间的值
- **Annualized（年化）**：×√252 把日度放大到年度
- **Z-score（标准分数）**：偏离均值几个标准差（σ）
- **Mean Reversion（均值回归）**：假设价格长期会回到均值
- **Log price（对数价格）**：取对数后的价格，使涨跌可加
- **Auto-adjust（自动复权）**：自动处理拆股/分红对价格的影响
- **Crash trigger（崩盘触发）**：波动超 30% 的硬防御线

**配置/交易**

- **Equity（权益/股票）**
- **GLD**：黄金 ETF
- **SGOV**：超短债 ETF（类现金）
- **Allocation（资产配置/配比）**
- **Regime_weights（状态权重）**：每档对应的股/金/债比例
- **Overlay（叠加层）**：在基础配比上再微调的一层规则
- **Threshold（阈值）**：触发条件的值
- **Buy/Sell threshold（买/卖阈值）**：加减仓的 z-score 边界
- **Delta（增量）**：触发时仓位变动量
- **Percentage point / pp（百分点）**：绝对百分点，区别于百分比变化
- **MarketGroup（市场分组）**：决定走哪条 overlay 规则（A股/港股/美股）

**状态/流程**

- **risk_on（进攻）/ risk_off（防御）/ moderate（中性）**
- **Changed（切换）**：regime 相比上一日发生变化
- **AsOfDate（截至日）**：信号基于的日期
- **Stale（过期）**：数据可能不新鲜（走了缓存回退）
- **T+1**：T 日信号次日生效
- **Sigma（σ）**：标准差符号，z-score 的单位
