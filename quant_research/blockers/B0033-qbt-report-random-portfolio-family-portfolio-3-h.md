---
id: B0033
title: qbt report 的 random_portfolio 门禁对【跨市场多腿合成卡】口径不适用：该门禁用『同数量随机标的替换持仓』构造零分布，但多腿合成（family=portfolio，腿数≥3，各腿来自不同资产类与交易制度）不存在『随机选腿』操作。H0326 四方合成实测：①循环平移置换 null 分布塌缩（null p95 == obs，与 H0301/H0296 同款）；②块自助置换后均值几乎不变（null mean 0.0747 vs obs 0.0757），得 51.85 分位——这是正确数学结果而非 bug，合成的收益水平本就不依赖时间顺序。后果：该卡 alpha t=5.16、PSR=1.0、prob(profit)=1.0、成本闸 43 倍、两段同号五项全过，唯独置换项不适用，只能判 FAIL，而多腿合成恰恰是台账里性价比最高的一类（H0246/H0325/H0326 全部受此影响）。建议为 family=portfolio 且腿数≥3 的卡增加替代门禁：两两相关矩阵均值 < 0.15 + 各腿独立通过原卡门禁
status: open
severity: ASK
scope: protocol
blocks: all
opened_by: quant-agent-1792433252-86938-20969
opened_at: 2026-10-20T16:04:07Z
closed_by:
closed_at:
evidence: quant_research/multi/h0326/out/report_4leg.json:quant_research/hypotheses/H0326-multi-four-leg-synthesis-h0325-extension.md
---

## 卡在哪

qbt report 的 random_portfolio 门禁对【跨市场多腿合成卡】口径不适用：该门禁用『同数量随机标的替换持仓』构造零分布，但多腿合成（family=portfolio，腿数≥3，各腿来自不同资产类与交易制度）不存在『随机选腿』操作。H0326 四方合成实测：①循环平移置换 null 分布塌缩（null p95 == obs，与 H0301/H0296 同款）；②块自助置换后均值几乎不变（null mean 0.0747 vs obs 0.0757），得 51.85 分位——这是正确数学结果而非 bug，合成的收益水平本就不依赖时间顺序。后果：该卡 alpha t=5.16、PSR=1.0、prob(profit)=1.0、成本闸 43 倍、两段同号五项全过，唯独置换项不适用，只能判 FAIL，而多腿合成恰恰是台账里性价比最高的一类（H0246/H0325/H0326 全部受此影响）。建议为 family=portfolio 且腿数≥3 的卡增加替代门禁：两两相关矩阵均值 < 0.15 + 各腿独立通过原卡门禁

## 证据

quant_research/multi/h0326/out/report_4leg.json:quant_research/hypotheses/H0326-multi-four-leg-synthesis-h0325-extension.md

## 处理日志

- `2026-10-20T16:04:07Z` quant-agent-1792433252-86938-20969：开出这条阻塞（ASK）。
