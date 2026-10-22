---
id: B0054
title: 60 日/月频调仓家族的 alpha_t 是【期收益序列的 t 值】（如 42 期 = 42 个 60 日收益点），不是日频序列的 t——这是口径性质而非 bug，但卡片与报告里常被读成『日频显著的 alpha』。核查 qbt.py alpha_beta()（第612-666行）：它直接在传入的 Series 上做 OLS + Newey-West，ppy 只用于年化（ann_alpha = 日/期 alpha × ppy）与 rf 折算（rf = rf_annual/ppy），不做频率转换。因此：①t 值本身不虚高——42 个点就是 42 个点的 t；②但 42 期 vs 2836 天的统计功效差 7 倍，42 期的 alpha_t=5.46 与日频 alpha_t=5.46 的置信度不可比；③ppy 取值需与期频匹配：60 日期收益的真实年化因子是 252/60=4.2 而非 4（差 5%，ann_alpha 会低估约 5%）；④下游 15 张卡（H0220/H0221/H0222/H0223/H0224/H0227/H0231/H0233/H0235/H0237/H0239/H0242/H0243/H0246/H0248/H0249/H0263）都是 42 期左右，引用其 alpha_t 时必须注明『这是 N 期收益序列的 t，非日频 t』。建议 qbt 的 report 输出增加 n_periods 与 periods_per_year 的显式说明，卡片 §7 的 C 归因行也注明序列口径
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: quant-agent-1792433252-86938-20969
opened_at: 2026-10-21T06:07:07Z
closed_by:
closed_at:
evidence: .agents/skills/quant-backtest-protocol/scripts/qbt.py
---

## 卡在哪

60 日/月频调仓家族的 alpha_t 是【期收益序列的 t 值】（如 42 期 = 42 个 60 日收益点），不是日频序列的 t——这是口径性质而非 bug，但卡片与报告里常被读成『日频显著的 alpha』。核查 qbt.py alpha_beta()（第612-666行）：它直接在传入的 Series 上做 OLS + Newey-West，ppy 只用于年化（ann_alpha = 日/期 alpha × ppy）与 rf 折算（rf = rf_annual/ppy），不做频率转换。因此：①t 值本身不虚高——42 个点就是 42 个点的 t；②但 42 期 vs 2836 天的统计功效差 7 倍，42 期的 alpha_t=5.46 与日频 alpha_t=5.46 的置信度不可比；③ppy 取值需与期频匹配：60 日期收益的真实年化因子是 252/60=4.2 而非 4（差 5%，ann_alpha 会低估约 5%）；④下游 15 张卡（H0220/H0221/H0222/H0223/H0224/H0227/H0231/H0233/H0235/H0237/H0239/H0242/H0243/H0246/H0248/H0249/H0263）都是 42 期左右，引用其 alpha_t 时必须注明『这是 N 期收益序列的 t，非日频 t』。建议 qbt 的 report 输出增加 n_periods 与 periods_per_year 的显式说明，卡片 §7 的 C 归因行也注明序列口径

## 证据

.agents/skills/quant-backtest-protocol/scripts/qbt.py

## 处理日志

- `2026-10-21T06:07:07Z` quant-agent-1792433252-86938-20969：开出这条阻塞（WARN）。
