---
id: B0017
title: 连续三个候选卡在同一堵墙：【逐合约期货日线免费源缺失】。① H0047（台账唯一 PASS）的负对照『ES 主力+T-bill 替代 SPY』——yfinance 实测无 ESH24.CME/ESM24.CME/ESZ25.CME（404），只有拼接连续 ES=F，按 H0049 的教训拼接连续不能用来算持仓 PnL；② 商品期货期限结构 carry（commodity 13 格空白）——同样只有连续合约；③ H0047 的第三市场检验『恒指期货+港币现金替代 2800』——akshare 的 futures_foreign_commodity 列表无 HSI，futures_global_hist_em 连接被拒，本机 futu OpenD(11111) 未运行。后果具体且可量化：H0047 是台账唯一 PASS，它的机理主张是『A股独有的深贴水（对冲需求过剩+融券受限）』，而公开证据（de Shaw Imbalance Sheet）说美国方向相反（期货偏贵）——**这个负对照没做，H0047 的机理就只有单市场证据**。同理，整个『结构性载体差/carry』方向在 A 股之外全部打不开。需要人决定是否为 CME/HKEX 逐合约日结算价配预算（或确认已有可用订阅、或授权启动 futu OpenD 并开通期货权限）。不挡任何人的选题
status: closed
severity: ASK
scope: protocol
blocks: all
opened_by: claude-opus-5
opened_at: 2026-09-06T01:08:18Z
closed_by: claude-opus-5
closed_at: 2026-09-06T02:10:28Z
evidence: quant_research/rounds/2026-09-06-claude-opus-5.md 的 R2 候选池 #2/#3/#5 与『未入选的，为什么』一节
---

## 卡在哪

连续三个候选卡在同一堵墙：【逐合约期货日线免费源缺失】。① H0047（台账唯一 PASS）的负对照『ES 主力+T-bill 替代 SPY』——yfinance 实测无 ESH24.CME/ESM24.CME/ESZ25.CME（404），只有拼接连续 ES=F，按 H0049 的教训拼接连续不能用来算持仓 PnL；② 商品期货期限结构 carry（commodity 13 格空白）——同样只有连续合约；③ H0047 的第三市场检验『恒指期货+港币现金替代 2800』——akshare 的 futures_foreign_commodity 列表无 HSI，futures_global_hist_em 连接被拒，本机 futu OpenD(11111) 未运行。后果具体且可量化：H0047 是台账唯一 PASS，它的机理主张是『A股独有的深贴水（对冲需求过剩+融券受限）』，而公开证据（de Shaw Imbalance Sheet）说美国方向相反（期货偏贵）——**这个负对照没做，H0047 的机理就只有单市场证据**。同理，整个『结构性载体差/carry』方向在 A 股之外全部打不开。需要人决定是否为 CME/HKEX 逐合约日结算价配预算（或确认已有可用订阅、或授权启动 futu OpenD 并开通期货权限）。不挡任何人的选题

## 证据

quant_research/rounds/2026-09-06-claude-opus-5.md 的 R2 候选池 #2/#3/#5 与『未入选的，为什么』一节

## 处理日志

- `2026-09-06T01:08:18Z` claude-opus-5：开出这条阻塞（ASK）。
- `2026-09-06T02:10:28Z` claude-opus-5：**关闭** —— 已由 H0078 解决其核心诉求。B0017 开出的理由是『H0047（台账唯一 PASS）主张载体差来自基差符号，但美股 ES 与港股恒指的负对照因逐合约日线无免费源做不了，机理只有单市场证据』。H0078 在第三个市场（币圈永续 vs 现货，数据本地全有、基差符号与 A 股相反）做出了这条负对照：净年化差 -9.33%(NW t=-5.00)、两标的同号、逐年剔除后 t 全在 -3.75~-5.33，且分解对账误差仅 0.008pp（永续与现货价格六年半年化只差 0.14%/0.27%，载体差 100% 由现金流决定）。同一个公式在两个基差符号相反的市场上各自对上账，H0047 的机理不再是单市场证据。**仍然缺的**：美股方向的正面量化（公开研究说美国股指期货融资利差为正、持有期货更贵），以及商品期货期限结构 carry——这两条依然需要 CME 逐合约日结算价，但它们现在是『锦上添花』而不是『机理存疑』，不再需要为此专门决定预算。谁要做，数据缺口原文见本阻塞与 rounds/2026-09-06-claude-opus-5.md 的 R2 候选池 #2/#5。
