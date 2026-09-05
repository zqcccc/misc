# gpt 修复后长跑候选池（2026-09-05）

预算：长跑不限轮数，每次仅一张；基线 d0bf25c7af2c0ee7。此前四轮续接，H0034 已承担前五轮中分校准，本次第一张为累计第五轮；下个五轮重新留校准位。
来源扫描 source_scan.txt：30条，arXiv API 429、Reddit 403，定向论文检索补充。三路：源扫描/coverage/市场强制风险承担。
广度：vol、futures、crypto_perp、us_stock、multi、rates、cn_stock 等7市场；h1/d1/w1/事件4种；carry/microstructure/lowvol/event/flow/timing等6族；非价量输入5个；第一直觉funding方向1个。

| # | 市场/频率/族 | 假设与机理 | 数据 | 年单边换手预估 | 来源 |
|---|---|---|---|---|---|
| A | vol/w1/carry | H0021子题：期货空头配同到期看涨保护，保费在尾部保护后仍值得收 | Cboe VPN/VPD官方日指数、方法；原始OPRA链需另查 | 4.8期货名义+期权费用 | https://cdn.cboe.com/api/global/us_indices/governance/VPN_Methodology.pdf |
| B | futures/h1/microstructure | H0013子题：贵金属亚洲时段漂移，控制换月与期限结构 | GC/SI逐合约小时价及曲线，需主动取 | 504 | https://doi.org/10.1007/s12197-017-9403-0 |
| C | crypto_perp/d1/carry | H0003重启检查：资金费回升让现金替代重新有意义 | Binance免费funding API、现货及永续价差 | 2–10 | https://www.bis.org/publ/work1087.htm |
| D | us_stock/事件/event | H0014：FOMC漂移重新出现 | Fed日历、SPY原价分红 | 16 | https://www.newyorkfed.org/research/staff_reports/sr512.html |
| E | cn_stock/w1/quality | H0022重启条件：新增期质量收益重新转正 | PIT公告后财务、含退市日价 | 24 | H0022原卡先验与前瞻要求 |
| F | rates/事件/event | H0032：国债拍卖后2/10年久期中性回补 | Treasury拍卖、现券报价、特殊回购融资 | 24–48 | https://www.newyorkfed.org/research/staff_reports/sr570.html |
| G | multi/d1/lowvol | H0036：60/40按滞后波动率缩仓，降低危机损失 | SPY/IEF原价分红、现金利率 | 8 | https://www.nber.org/papers/w22208 |
| H | us_stock/d1/microstructure | GLD/GDX隔夜漂移是否仍超过手续费，客户群分离 | Yahoo原价、拆股分红/发行商 | 504 | https://quantocracy.com/recent-quant-links-from-quantocracy-as-of-02152025/ |
| I | us_stock/w1/carry | 核能能源期权卖put的保费是否足够抵成本 | CRSP/OptionMetrics原论文，免费PIT替代未知 | 24 | https://arxiv.org/abs/2609.01183 |
| J | multi/w1/timing | VIX条件动量是否比固定趋势强 | SPY/VXF/EFA/AGG/BIL与VIX | 24 | https://alphaarchitect.com/vix-trend-following-out-of-sample/ |

七维不变、每项0–2，成本余量为先验待检而非回测结果：
| # | 机理强度 | 付钱者与持续性 | 数据与时点 | 可捕获成本余量 | 容量与可实现性 | 组合增量 | 证伪速度 | 总分 |
|---|---|---|---|---|---|---|---|---|
| A |2|2|1|2|1|1|2|11/14|
| B |2|1|1|1|2|1|1|9/14|
| C |2|2|2|1|2|1|2|12/14|
| D |1|1|2|1|2|1|2|10/14|
| E |1|1|1|1|1|1|1|7/14|
| F |2|2|0|1|1|2|1|9/14|
| G |2|2|2|2|2|1|2|13/14|
| H |1|1|2|1|2|1|2|10/14|
| I |1|1|0|0|1|1|1|5/14|
| J |1|1|2|1|2|1|2|10/14|

选择：优先级覆盖纯分数，未满足父卡重启条件的候选不硬开。C免费API核验最近完整90天：BTC 5.68056%、ETH 3.59684%，均未达持续8%，不认领。D/E尚无足够新增事件/月，F特殊回购报价未取到，B逐合约小时历史待查。A为当前可推进的最高分已裁决线索，认领H0044。G高分但位于覆盖空白档，待旧线索筛完；H为中分校准备选。I论文明确before costs/fixed universe且原始源需付费，不为凑广度进入回测。J先验来自复现者，需原论文/PIT核实。

A负面证据：Szado2020官方赞助研究同时报告VPN历史最大回撤53%，说明单月保险不等于长期保本；当前不重算旧样本，锁定2019+检验。2019为该研究主要比较区间2018终点之后，不声称完全晚于2020论文公开。VPN方法自2008已发布，2019+是指数发布后。

## H0044之后选题更新（先于下一张认领）
B（GC/SI逐合约历史）：CME DataMine官方明确需创建账号、下单购买数据；Databento亦需账号，记“需付费/注册，未取到”，本轮不购买，保留原H0013期货线索。不是因缺本地缓存放弃，也不以ETF替换原期货结论。
H（GDX执行窗口）检索取得Quantpedia作者自己用分钟数据做的反证：9:31卖出收益8.58%/年，远低于OHLC开盘的约30%。这是H0013旁支的新可交易载体题，不等同GC/SI亚洲时段，parent仅记录灵感来源。其保守成本能先判，七维1/1/2/1/2/1/2=10/14不变；用作新五轮校准位。完整源：https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/ 。高分G仍在候选池，下一轮在不可推进线索排除后再做。
