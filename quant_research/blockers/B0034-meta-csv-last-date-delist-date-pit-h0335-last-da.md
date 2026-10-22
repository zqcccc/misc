---
id: B0034
title: 用【数据集末日期】（meta.csv 的 last_date / delist_date）构造 PIT 信号，一律视为【未来函数】，不是「事后信息的乐观上限」。H0335 实例：用 last_date 提前 250 交易日剔除退市股，等于提前知道每只股票的确切退市日，策略因此无条件避开退市股；卡片首版把它写成「事后信息，已是乐观上限」，性质被说轻了——后者暗示「说明一下就能用」，而未来函数是直接作废口径。正确表述：+0.07%/年 是完美预知下的上界，真实可实现口径只会更低甚至为负，故该维度在任何口径下都不可用。本阻断点与 B0031（事件子序列 ×252 年化）、B0032（债券 ETF 月度分红 ffill 到日频）并列，三条同属『口径把结论放大或伪造』系列
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: quant-agent-1792433252-86938-20969
opened_at: 2026-10-20T17:15:02Z
closed_by:
closed_at:
evidence: quant_research/hypotheses/H0335-cn-stock-delisting-risk-avoidance.md:quant_research/hypotheses/H0335-cn-stock-delisting-risk-avoidance.md:120
---

## 卡在哪

用【数据集末日期】（meta.csv 的 last_date / delist_date）构造 PIT 信号，一律视为【未来函数】，不是「事后信息的乐观上限」。H0335 实例：用 last_date 提前 250 交易日剔除退市股，等于提前知道每只股票的确切退市日，策略因此无条件避开退市股；卡片首版把它写成「事后信息，已是乐观上限」，性质被说轻了——后者暗示「说明一下就能用」，而未来函数是直接作废口径。正确表述：+0.07%/年 是完美预知下的上界，真实可实现口径只会更低甚至为负，故该维度在任何口径下都不可用。本阻断点与 B0031（事件子序列 ×252 年化）、B0032（债券 ETF 月度分红 ffill 到日频）并列，三条同属『口径把结论放大或伪造』系列

## 证据

quant_research/hypotheses/H0335-cn-stock-delisting-risk-avoidance.md:quant_research/hypotheses/H0335-cn-stock-delisting-risk-avoidance.md:120

## 处理日志

- `2026-10-20T17:15:02Z` quant-agent-1792433252-86938-20969：开出这条阻塞（WARN）。
