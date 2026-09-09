# 长跑台账 · 2026-09-06 · doubao

## 启动参数
- 长跑模式（PROMPT_LONGRUN.md），无预算上限，一次只推进一张。
- QR_RUN=doubao-1788658144-53845；协议 v7/cb5ede2cb8610cb2。start 退出 0。
- 保护文件不改；实验不提交 git；派生视图只经 qr 生成。
- 已全文读 KNOWLEDGE/GLOSSARY，完成 leads/coverage/scorecard/list/stale/blocker。
- 阻塞盘点：B0015(HALT, data:fx-load_fx) → 本趟避开 load_fx 管线；B0017(ASK, 逐合约期货免费源缺失) → 商品期限结构不可直建，用 ETF−连续期货收益差代理；其余 WARN/ASK 不挡选题。

## 线索优先核查（第 1 档）
- H0003（funding 重回 8%）：Codex 已于本日核查 BTC/ETH 年化名义收费 5.68%/3.60%，未达 8% 重开线 → 不重开。
- H0022/H0035（TEST 段质量 alpha 转正 / 24 个新月份）：时间条件未满足，无法占坑。
- H0032（含特殊回购融资的现券报价）：需付费数据，未取得。
- H0034（新增 10 年未参与选择的月度事件）：条件未满足。
→ 进入第 2/3 档：能解释已有结论的深挖 + coverage 空白格。

## 候选池（10 个；广度：6 市场｜d1/w1/事件 3 颗粒度｜carry/momentum/size/event/reversal/seasonality/flow 7 族｜非价量输入 B,C,F,G,H 5 项｜第一直觉方向仅 A,B）

| # | 市场/颗粒度/族 | 一句话假设 | 机理 | 数据从哪来 | 预计换手 | 来源 |
|---|---|---|---|---|---|---|
| A | commodity/d1/carry | 商品 ETF 横截面展期损耗差：做多「ETF 相对其连续期货过去 252 日跑赢」的（≈贴水/低损耗）、做空跑输的（≈升水/高损耗），月度调仓 | 套保者必须付展期费；期限结构斜率是风险溢价（KMPV 2018 carry） | yfinance 单品种商品 ETF（USO/UNG/GLD/SLV/DBO/UGA/BNO/CORN/WEAT/PPLT/PALL/...）+ 本地 futures/data/ohlc.parquet 22 品种连续期货 | 低（月度） | KMPV 2018；coverage 空白格 |
| B | crypto_spot/d1/carry | 现货-永续基差（非资金费口径）横截面排序做多/做空 | 杠杆需求与套利限制 | binance.vision 现货/永续 klines（本地 crypto_perp/data/ 已有） | 低 | coverage 空白格 |
| C | rates/d1/carry | 纯债券 ETF 池（SHY/IEF/TLT/LQD/HYG/EMB/MBB/TIP/...）按 H0046 口径 carry（分红率−短端）横截面 | 期限溢价/信用溢价 | yfinance | 低 | H0046 同口径扩展 |
| D | us_stock/d1/momentum | 美股行业/板块 ETF 12-1 动量横截面 | 行为偏差 | yfinance | 低 | us_stock×momentum 空白格 |
| E | us_stock/d1/size | 标普 500 内部小市值倾斜（PIT 宇宙） | 规模溢价 | PIT+yfinance | 低 | claude-opus-5 R2 解锁的 PIT 宇宙 |
| F | multi/d1/event | 美 CPI 公布日跨资产（股/债/金）公告日效应 | 公告后漂移 | yfinance+官方日历 | 事件 | 日历事件族 |
| G | cn_stock/d1/reversal | A股周频（5 日）反转横截面 | 流动性提供 | 本地 A 股管线 | 高 | cn_stock×reversal 空白格 |
| H | fx/w1/seasonality | G10 货币月度季节性 | 弱/资金流 | yfinance FX（避开 load_fx） | 低 | fx×seasonality 空白格 |
| I | crypto_perp/d1/flow | 大单/元订单方向流预测（平均单笔成交额代理） | 大单拆分持续流 | 本地逐笔（待验证可得性） | 中 | arXiv 2608.30999 |
| J | hk_stock/d1/momentum | 港股横截面 12-1 动量 | 行为偏差（已在 4 市场死过） | akshare | 低 | hk_stock×momentum 空白格 |

## 打分卡（七维各 0~2，先打分后选）
| # | 机理 | 付钱者/持续 | 数据/时点 | 成本余量 | 容量 | 组合增量 | 证伪速度 | 总分 | 入选? |
|---|---|---|---|---|---|---|---|---|---|
| A | 2 | 2 | 2 | 1 | 2 | 2 | 2 | **13/14** | ✅ 本轮主卡（commodity×carry 空白格） |
| B | 2 | 1 | 2 | 1 | 1 | 1 | 2 | 10/14 | 备选 |
| C | 2 | 1 | 2 | 1 | 2 | 1 | 2 | 11/14 | 备选 |
| D | 1 | 1 | 2 | 1 | 2 | 1 | 2 | 10/14 | 动量已在 4+ 市场死过 |
| E | 1 | 1 | 1 | 1 | 2 | 1 | 2 | 9/14 | 备选 |
| F | 2 | 1 | 1 | 1 | 2 | 1 | 2 | 10/14 | 备选 |
| G | 2 | 1 | 2 | 0 | 1 | 1 | 1 | 8/14 | A股换手成本重 |
| H | 1 | 0 | 1 | 1 | 2 | 1 | 2 | 8/14 | 机理弱 |
| I | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 4/14 | 数据不可行 |
| J | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 8/14 | 机理已死 4 次 |

选 A。理由：① commodity×carry 是 coverage 空白格；② 机理有 KMPV 2018 学术背书且「套保者必须付展期费」的付钱者路径清晰；③ 数据已验证：yfinance 单品种商品 ETF 19 只可得、本地 22 品种连续期货全历史（2000-2026）；④ 低换手，成本闸容易过；⑤ 与本台账 crypto/股票/A股 现有结论低相关。

## 负面证据（A 候选）
- KMPV 2018（JFE）商品 carry 有横截面预测力，但 Jacobs Levy 讨论：商品与期权市场 carry 预测系数 <1，市场会收回部分 carry（不是全部）。
- Quantica Capital 2021：静态 long-only 商品多头收获不到正 carry，趋势跟随才能吃到——提示展期收益需要多空或择时结构。
- 新浪股吧（非学术）：2000-2025 原油深 Back 期 roll 年化约 5.7%——展期收益真实存在但依赖结构。
- 展期损耗常识：商品指数基金 net-of-fees 长期落后现货 2~5%/年（contango 拖累，油和气最重）——支持「损耗可排序、可吃」。
- 数据限制：yfinance 已到期期货合约无历史（CLF20 等 0 行）→ 无法直建近远月价差，只能用 ETF−连续期货收益差代理展期损耗（混入费用与跟踪误差，A 层需验证代理是否主要反映损耗）。

## 数据源踩坑记录
- yfinance 商品 ETF：USO/UNG/GLD/SLV/DBC/DBO/UGA/UCO/SCO/XLE/PDBC/USCI/BNO/CORN/WEAT/DBA/TAN/PPLT/PALL 可得；JJG/BAL/NIB/JJA/SGG 已退市不可得。
- UCO/SCO 是 ±2x 杠杆 ETF、XLE/TAN 是股票 ETF → 池内排除。
- yfinance 期货逐合约：当前活跃合约（CLZ26.NYM/GCZ26.CMX/SIZ26.CMX）可得；**已到期合约无历史**（CLF20/CLH21/CLZ22/NGU26/GCM20/SIH20 全 0 行或 404）→ 期限结构无法回测，必须用连续合约序列。
- 本地 futures/data/ohlc.parquet：22 品种 yfinance 连续期货 2000-08→2026-09，含 GC/SI/HG/PL/PA/CL/BZ/NG/RB/HO/ZC/ZS/ZM/ZW/CC/KC/CT/SB/OJ/HE/LE 等，与 H0053/H0059 同源。
- USO 与 CL=F 日收益相关仅 0.54、DBO 0.45（远月+期权策略），其余 ETF 0.83-0.92 → ETF−连续期货收益差代理在油类上混入大量跟踪噪音。

## 轮次进度

### 第1轮 H0073（commodity×carry，13/14 高分）
FAIL/信号无增量（A 层死）。池子齐全后（2011+）毛年化 −2.9%（全样本 +3.0% 全靠 2008-2010 六只小池），做多高信号组 −0.9%/年，信号排序相关 0.78、年换手 4.7 只/边，退化为近静态「做多 UGA/BNO、做空 UNG/WEAT/USO」。成本闸全样本 GO(12.8×) 但 2011+ STOP(−12.3×)。代码/数据在 verified/H0073/。selfcheck 退出 0。
**留给下一轮的**：yfinance 已到期期货合约无历史 → 商品近远月价差不可回测（再次印证 B0017）；ETF 代理混入跟踪噪音。

### 第2轮 H0075（rates×carry，11/14）
FAIL/信号无增量（A 层死）。15.6 年（2011-2026）毛年化 2.43%、净 2.17%，对同池等权 alpha 1.78%（HAC t=1.17）不显著；三因子（等权/TLT/信用利差）吸收后截距 −0.69%；信号完全静态（信用组与国债组相关 0.973 > 0.85 预注册判死线），HYG/EMB/SJNK 常驻多头、IEI/SHY/GOVT 常驻空头，年换手 0.84 只/边——与 H0046 同构，纯债券池 carry 横截面=静态信用利差赌注。成本闸 GO(57.9×) 但只因换手极低。代码/数据 verified/H0075/。selfcheck 退出 0。
**踩坑**：债券 ETF 回测必须用「价格+分红」总收益口径（纯价格收益把 carry 来源丢掉）；分红索引带时区导致 reindex 全丢。

### 第3轮选题（进行中）
- 网络故障排查：curl/requests/curl_cffi 全 TLS 挂（2026-09-06 ~10:40-11:00），yfinance 间歇可用（SPY 5d 成功但批量挂），仅搜索 API 通。BLS/FRED 不可达 → **CPI 日历事件候选（multi×event）数据不可得，放弃**。FX 通道（=X）不可用 → **fx×seasonality 放弃**。
- 已核查不可做：cn_stock×reversal（H0061 已覆盖 K=10/20/60，K=10 显著为负 t=−2.76，周频被预示）；A 股周频反转、hk momentum、crypto size 均预期低。
- 选定 **us_stock×momentum（SPDR 行业 ETF 相对动量，10/14 中上分校准位）**：us_stock×momentum 空白格；MG1999 经典；负面证据明确（State Street 2021：2008 后行业 12 月动量基本消失、1 月反转增强）→ 预期 FAIL 信号无增量，作为校准位验证打分卡。数据：yfinance 行业 ETF（XLK/XLY/XLP/XLE/XLF/XLU/XLV/XLI/XLB/XLRE/XLC/SPY），下载脚本后台运行中。

### 第3轮 H0083（cn_stock×value，10/14 校准位）
**PARK/不可成交**（今天唯一非 FAIL，且是校准位超预期）。A 股 PB 横截面多空 2015-2026：净 alpha 对同池等权 +10.20%/yr（NW t=2.40）、置换 300 次 0 超过（p=0.000）、2018+ t=1.80、压力档 5.94%、PIT 合规（bps 更新集中 4-5 月年报季）。但拆解：**空头腿（做空高 PB）+14.1%（t=3.43）贡献全部 alpha，多腿（做多低 PB）全样本 −3.21%（t=−0.93）、2018+ 才转正（+5.34% t=2.23）**；A 股融券制度使 ~1554 只小盘高 PB 空头不可执行。信息：高估值泡沫破裂是 A 股长期事实；2018+ 价值/红利回归有真 alpha。数据源 astock_quant/data/panel（close/pb/bps）PIT 质量好，后续可复用。selfcheck 退出 0。
**网络记录**：yfinance 间歇限流（单只可、批量挂、FX =X 全挂）；BLS/FRED/curl/requests/curl_cffi 全部不可达（仅搜索 API 通）→ fx/CPI 日历候选放弃；改用本地 A 股 panel，零网络依赖。

## 覆盖变化
- commodity×carry：空白 → FAIL（H0073，第1轮）。
- rates×carry：空白 → FAIL（H0075，第2轮）。
- cn_stock×value：空白 → PARK（H0083，第3轮）。
