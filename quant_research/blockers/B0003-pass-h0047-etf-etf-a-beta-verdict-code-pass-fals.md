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

- `2026-09-05T06:05:00Z` claude：**已按新建的执行角色门禁跑过一遍**（`qbt.py carrier`，协议 v4）。
  产物 `cn_index_futures/out/h0047_carrier_verdict.json`，结论 **FAIL**，但死在缺件不是死在经济性。

  **经济性门禁全过**：净年化差 6.21%（NW t=6.76）、暴露调整后 5.43%（NW t=8.60）、
  逐年 10/10 为正、最大回撤比 ETF **浅** 2.31 个百分点、R²=0.977。

  **新发现，复核必看**：`beta=1.1349`、波动比 1.1483 —— **同暴露不成立**。
  期货腿相对 ETF 腿多拿了约 13.5% 的敞口，所以 6.21% 里有约 0.8 个百分点是多担风险换来的，
  真正属于载体的是暴露调整后的 **5.43%**。之前那份 `h0047_verdict.json` 走的是 alpha 路径
  （`role="alpha"`，拿 ETF 当基准），把这 13.5% 的超额暴露算进了 alpha，读数偏乐观。
  为什么会多拿敞口需要查清楚——设计上是「名义敞口相同」，实测不是。

  **还缺两件才能 PASS**（就是 B0003 开头列的那三件里的两件，现在变成了机器门禁）：
  1. `--carrier-stressed`：压力成本档下的日收益序列。`h0047.json` 里已有成本×2 的合并结果
     （净年化差 5.85%、NW t=6.58），但没有落成序列，门禁读不到。
  2. `--carrier-risk` 六项里的四项未申报：最小资金、追保时先动谁、换月盘口深度证据、监管尾部。
     数值项（保证金比例 0.14、历史最大回撤÷保证金 3.42）已从 `h0047.json` 取到。

  也就是说：**这个候选没有被推翻，是还没跑完。** 补齐上面两件再跑一次 `qbt.py carrier`，
  过了才能 `qr verdict H0047 PASS --report ...`。本条阻塞保持 open，等人决定要不要继续投入。
