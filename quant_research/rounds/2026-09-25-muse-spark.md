# 本轮台账 · 2026-09-25 · muse-spark（长跑 R4，隐波专题）

> 长跑模式，一次推进一张卡。用户方向约束：隐含波动率相关研究。
> PROMPT_LONGRUN 第 1 档 leads 六条皆条件触发型（H0003/H0129 需 funding 年化>8%，R1 已实测仅 ~2%；
> H0032 需付费报价；H0034 需 10 年新事件；H0035/H0120 需 24 新月份转正），本轮无可接。
> 第 2 档矛盾深挖：B0026 已由 H0134 解决，无新矛盾。用户方向明确指定隐波，故第 4 档前置为例外，
> 候选池全部放在隐波方向内、跨市场/颗粒度/机理族撒开（4 市场 / 3 颗粒度 / 5 机理族）。

## 启动参数
- 预算：长跑模式，无上限，一次一张卡（本轮 R4）
- 方向：隐含波动率（用户指定）｜ 市场：不限 ｜ 约束：只用免费数据（CBOE/yfinance/公开 API），PIT 可成交
- B0015（HALT）挡 data:fx-load_fx——本轮 us_stock/vol，不触及

## 候选池（8 个，全隐波方向）
广度自查：市场 4 个（us_stock/vol/crypto_perp/cn_stock）｜颗粒度 3 种（d1/h1/事件驱动）｜机理族 5 个｜非价量输入 5 个（VIX/VVIX/PCR/DVOL/iVX）｜第一直觉（美股 VRP 择时）3 个（#1/#2/#8，已压线）

| # | 市场/颗粒度/族 | 一句话假设 | 机理 | 数据从哪来 | 预计换手 | 来源 |
|---|---|---|---|---|---|---|
| 1 | us_stock/d1/timing | 方差风险溢价 VRP=VIX²−RV(21d) 分档择时 SPY（高持/低空/中维持，月度） | 时变风险厌恶+经济不确定性；保险买方付费（BTZ09 GE 模型） | CBOE VIX History + yfinance SPY（免费，PIT 清晰） | ~12次/年 | BTZ09 doi:10.1093/rfs/hhp008；复现 github hiromn2/variance-risk-premium |
| 2 | us_stock/d1/timing | VVIX（vol-of-vol）高企预测 SPY 未来收益为负，反向择时 | 波动率不确定性定价（Huang et al 2019） | yfinance ^VVIX + SPY | ~12次/年 | Huang-Schlag-Shaliastovich-Thimme 2019；AA 综述 |
| 3 | vol/d1/carry | VIX premium（VIX30期货−VIX现货）符号决定 VIX 期货多空 | 波动率风险定价、期限结构套利 | 本地 vol/ 拼接 + VIX（免费） | ~24×/年 | Cheng 2018；Hu 2026 JFQA；AA 2022-01-27 |
| 4 | us_stock/d1/flow | CBOE 总 put-call ratio 极端分位反向择时 SPY（恐慌多/贪婪空，持5日） | 散户期权流情绪拥挤反转 | CBOE PCR 日频（免费 CSV 待验证） | ~30次/年 | 散户情绪文献；r/algotrading 负面多 |
| 5 | crypto_perp/d1/timing | BTC 方差风险溢价（Deribit DVOL/ATM IV−RV）择时 BTC | 币圈期权保险需求（与美股同构检验） | Deribit 公开 API + Binance klines | ~12次/年 | Fallon et al 2015 全球 VRP；无 BTC VRP 可交易复现 |
| 6 | cn_stock/d1/timing | 50ETF 期权隐波（iVX/ATM IV）−RV 择时 510050 | A 股期权保险溢价（同构检验） | akshare 期权 IV（历史长度待验证） | ~12次/年 | BTZ 跨市场（Bollerslev et al 国际证据）；A 股无复现 |
| 7 | us_stock/h1/microstructure | VIX 与隔夜/日内已实现波动缺口预测次日 SPY | 波动率错定价的日内修正 | yfinance SPY m1/h1 + VIX 日频 | ~100次/年 | 日内 VRP 文献；成本敏感 |
| 8 | us_stock/事件驱动/event | VIX  spike（252d 90%分位）且 VRP>0 时 5 日做多 SPY（恐慌+溢价双滤） | 恐慌后风险溢价修复（H0091/H0092 的 VRP 门控版） | VIX + SPY（免费） | ~20次/年 | H0091/H0092（VIX-only 已死）；Lochstoer-Muir 2019 |

## 打分卡（七维各 0~2，先打分再选）

| # | 机理 | 付钱者/持续性 | 数据/时点 | 可捕获成本余量 | 容量 | 组合增量 | 证伪速度 | 总分 | 入选? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 1 | 2 | 1 | 2 | 1 | 2 | 11 | ✅ 主卡（机理最强+数据免费+PIT清晰；付钱者扣1=发表后衰减实锤，成本扣1=待 L0 验证） |
| 2 | 1 | 1 | 2 | 1 | 2 | 1 | 2 | 10 | 否（机理弱于 VRP；VVIX 历史 2007+ 较短） |
| 3 | 2 | 1 | 1 | 0 | 1 | 0 | 1 | 6 | 否（与 H0021 同载体，换手 24× 成本厚；容量小） |
| 4 | 1 | 0 | 0 | 1 | 2 | 0 | 1 | 5 | 否（PCR 免费 PIT 历史未验证；付钱者不明） |
| 5 | 1 | 1 | 0 | 1 | 2 | 2 | 0 | 7 | 否（Deribit IV 历史长度/限流未知，证伪慢） |
| 6 | 1 | 1 | 0 | 1 | 1 | 2 | 0 | 6 | 否（akshare IV 历史待验证，证伪慢） |
| 7 | 0 | 0 | 1 | 0 | 2 | 0 | 1 | 4 | 否（纯挖掘味；换手高成本大概率吃穿） |
| 8 | 1 | 0 | 2 | 1 | 2 | 0 | 2 | 8 | 否（H0091/H0092 已证 VIX-only 死；双滤大概率同死，留作 §9 诊断） |

## 先验检索结论（路线 B，重点负面证据）
- 正面：BTZ09（1990–2007，季度 t=2.86，R² 6.82%，中间期限最强）；国际 8 国同形；全球 VRP 面板 t>4（Bollerslev et al 后续）。
- 负面（决定本卡判读 strictness 的三条）：
  ① hiromn2 独立复现：BTZ 期 h=3 Hodrick t=3.70 ✅，但全样本 1990–2026 h=3 t=0.43 ❌；滚动 60m OOS R² 从 −3.2% 恶化到 −58.9%（2008–2026）。结构断点是实锤，不是猜测。
  ② Bekaert-Hoerova (ECB)：BTZ 用 RV(t−1) 当条件方差是被数据拒绝的设定；换好方差模型后短端预测力大跌——"BTZ 夸大了预测力"。
  ③ Lochstoer-Muir 2019（经 AA 2020-04-02）：VRP 定时 premium 的 R² 仅 0.8%≈0，"trying to time the premium might not be a good trading strategy"。
- 推论：本卡主判读线必须含**发表后段（2018–2026）单独成立** + OOS R²>0，否则即使全样本 t>2 也只能判"溢价已死/样本外翻转"，不能 PASS。

## 未入选的为什么（下一轮输入）
- #5/#6 是最好的跨市场同构检验（币圈/A 股 VRP），但数据可得性未知；若 #1 在美股证实可交易，#5 优先重开（Deribit API 免费希望大）。
- #8（VIX spike + VRP 双滤）若 #1 死在"方向反了/无增量"，可直接用 #1 的产物顺手验证，不另开卡。
- #3 与 H0021 载体重叠，需先读 H0021 §9 再定，避免重复。

## R4 结果：H0140 → FAIL（信号无增量），A 层即死（毛本身为负，H0137 同例）
- 选题：第 4 档前置（用户方向约束隐波）候选池 #1，11/14；`qr search` 方差风险溢价零命中。
- 主口径（VRP 三分位+维持档，月频 T+1，2015–2026，2949 日）：策略净年化 6.71% vs SPY 买入持有 13.78%；
  超额毛（零成本）−7.07%/年，成本仅 0.06%/年 → L0 STOP（edge/cost −108），死因取信号无增量非成本吃穿。
- L1 alpha −0.11%/年 t=−0.05（qbt 交叉 t=−0.04，p=0.97，β=0.51）；L3 静态对照（恒定 42.3% 敞口）增量 −1.22% t=−0.53；
  L4 循环时移 2000 次分位 33.7%；分块自助 prob(profit)=1.2%；DSR=0.009（5 规格）。
- 前段 2015–17 +1.44% t=0.63 / 后段 2018–26 −0.10% t=−0.03（MDE 8.12%，B0018：后段测不出小效应，但结论是已实现亏损不是显著性判断）；
  12 个逐年剔除无一年翻正（最好剔 2020：+2.54% t=1.28）；5 规格最好 +0.81% t=0.36。
- 唯一正数（诚实记录）：月频扩张窗 OOS 回归 R²=+0.063——VRP 水平剩一点预测渣，但五个可交易规格全亏回去。
- 因果闸 3 点 max diff=0.0（唯一过的闸）。VIX-only 对照 −0.76% t=−0.37：加不加 VRP 都死。
- **校准位读数**：11/14 高分候选 FAIL，结局与中分档一致——打分卡区分度存疑的观察 +1（接 H0137 8/14、H0138 10/14）。
- 产物：`us_stock/h0140/{fetch.py,run.py,out/h0140.json,out/screen.json,out/alphabeta.json,out/mc.json,out/dsr.json,out/trials.json,out/execution_manifest.json}`。
- 实现 bug 纪要（后人避坑）：① alpha 的 t 值误对残差均值算（恒为 0），必须对 Y−βX 算；② 月末无次日则该月信号无执行，对齐长度；③ 时序择时的 screen 毛边际必须用超额毛，不用总收益。

## 本轮覆盖变化
- us_stock×timing：VRP 择时（BTZ09 发表后检验）→ FAIL，与 hiromn2 全样本复现、Bekaert-Hoerova 一致。
- 还剩的大片空白（供下一轮）：crypto×VRP 同构（#5，Deribit API）、A 股 iVX（#6）、vol×carry 条件空波（#3，需先读 H0021 §9）；
  注意 H0140 §9：美股原版可交易口径已死，同构先验只剩一半。

## 下一轮打算
- 回到 PROMPT_LONGRUN 优先级：leads 重检条件触发（H0003/H0129 funding 年化是否回 8%），无则走 coverage 空白格。
- 四轮死因：R1/R2/R3 信号无增量 + R4 信号无增量（毛为负），连续 4 轮同死因，未到 8 轮线；但方向分布四格，无系统性偏差。

## 数据源踩坑记录
- CBOE VIX_History.csv 可达（HTTP 200，1990+）；yfinance ^VIX 1990-01-02 起、SPY 1993-01-29 起可用。
- FRED PUT solved：无 PUT-CALL 免费 id（/tmp/pcr.csv 回 HTML），#4 数据维度 0 分实锤。
