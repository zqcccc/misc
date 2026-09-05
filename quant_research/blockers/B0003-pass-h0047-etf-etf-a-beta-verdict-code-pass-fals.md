---
id: B0003
title: 出现 PASS 候选 H0047（用中金所股指期货+货币ETF 替代宽基 ETF 拿 A 股 beta）：严格报告 verdict_code=PASS、falsification_failures=[]，2017-2026 四个品种全部为正、逐年十年全部为正、合并净年化差 +6.13%（日差 NW t=6.86），收益分解与贴水收敛对上账（误差<0.5pp）。按 PROMPT_LONGRUN 规定停止循环交人复核；上仓位前还缺三件事：换月盘口深度的实盘验证、券商追保流程与货币ETF质押规则、基差与监管政策的持续监控看板
status: open
severity: HALT
scope: protocol
opened_by: claude
opened_at: 2026-09-05T04:16:06Z
closed_by:
closed_at:
evidence: cn_index_futures/out/h0047_verdict.json + h0047.json + h0047_diag.json + h0047_perm.json；卡片 quant_research/hypotheses/H0047-*.md §7
---

## 卡在哪

出现 PASS 候选 H0047（用中金所股指期货+货币ETF 替代宽基 ETF 拿 A 股 beta）：严格报告 verdict_code=PASS、falsification_failures=[]，2017-2026 四个品种全部为正、逐年十年全部为正、合并净年化差 +6.13%（日差 NW t=6.86），收益分解与贴水收敛对上账（误差<0.5pp）。按 PROMPT_LONGRUN 规定停止循环交人复核；上仓位前还缺三件事：换月盘口深度的实盘验证、券商追保流程与货币ETF质押规则、基差与监管政策的持续监控看板

## 证据

cn_index_futures/out/h0047_verdict.json + h0047.json + h0047_diag.json + h0047_perm.json；卡片 quant_research/hypotheses/H0047-*.md §7

## 处理日志

- `2026-09-05T04:16:06Z` claude：开出这条阻塞（HALT）。
