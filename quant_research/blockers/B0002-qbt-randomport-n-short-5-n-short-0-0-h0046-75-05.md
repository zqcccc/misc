---
id: B0002
title: qbt randomport 的 --n-short 默认 5：纯多策略若不显式写 --n-short 0，随机对照会变成多空中性组合（夏普中位≈0），置换分位被虚报（H0046 实测 75.05% → 99.65%，结论正好相反）；另 qbt alphabeta 的 verdict 只看 alpha 符号不看显著性，alpha_t=0.70/p=0.48 仍打印「正 alpha：策略本身有效」
status: closed
severity: HALT
scope: protocol
opened_by: claude
opened_at: 2026-09-05T03:55:22Z
closed_by: gongzhao-34905
closed_at: 2026-09-05T05:10:58Z
evidence: PROTOCOL_LOG.md v3 = 02a1d5457de17265
---

## 卡在哪

qbt randomport 的 --n-short 默认 5：纯多策略若不显式写 --n-short 0，随机对照会变成多空中性组合（夏普中位≈0），置换分位被虚报（H0046 实测 75.05% → 99.65%，结论正好相反）；另 qbt alphabeta 的 verdict 只看 alpha 符号不看显著性，alpha_t=0.70/p=0.48 仍打印「正 alpha：策略本身有效」

## 证据

multi_carry/out/perm.json + H0046 §7e；复现：qbt.py randomport --panel multi_carry/out/panel.csv --n-long 3 [--n-short 0] --hold 21

## 处理日志

- `2026-09-05T03:55:22Z` claude：开出这条阻塞（WARN）。

- `2026-09-05T05:10:00Z` claude：**提级 WARN → HALT**。按 `PROMPT_LONGRUN.md` 的判据（会不会让**别人**正在做的研究得出错误结论），
  这是个假阳性发生器：任何纯多策略只要不显式写 `--n-short 0`，置换分位都会被系统性抬高，
  不只是开出者自己这一轮受影响。已核实 `qbt.py:713` 的 `--n-short` 默认值确为 5。

## 受影响范围（只读扫描，2026-09-05）

扫描全工作区的 qbt 报告 JSON（排除依赖、git、构建目录与人工夹具），33 份带 `random_portfolio` 输出，
其中 **20 份 `n_short > 0`**：

| 报告 | n_long/n_short | 分位 |
|---|---|---|
| `verified/H0010/oos_verdict_long_only.json` | 5/5 | 0.9345 |
| `verified/H0010/oos_verdict_long_short.json` | 5/5 | 0.7395 |
| `verified/H0011/oos_verdict_{maker,taker}.json` | 5/1 | 0.0 |
| `quant_research/multi/out/oos_verdict.json` | 5/4 | 1.0 |
| `astock_quant/verified/*.json`（s01~s14、oos，共 14 份） | 5~550 / 5 | 0.02 ~ 1.0 |

**对台账裁决的影响：无。** 分位被抬高只会让策略更容易过门槛，不会把该过的判成不过；
而台账里目前一张 PASS 都没有，受影响的卡（H0010 PARK、H0011 FAIL）都是因为别的原因被判的，
H0010 的 long_only 分位 0.9345 即使被抬高过也仍在 0.95 门槛之下。

**真正需要重看的是 `astock_quant/verified/` 那 14 份**：那批是台账机制之前的 A 股小盘研究，
`s01_guorn_smallcap_m1`（5/5，分位 1.0）、`s02/s03` 系列都是**纯多选股**策略却配了多空随机对照，
分位数字不可信。它们是小盘实盘服务的依据，需要用 `--n-short 0` 重跑一遍再看结论还站不站得住。
本次只做只读扫描，没有重跑、没有改动任何历史结论。

**H0047 未受影响**：它用的是自己手写的置换文件（`cn_index_futures/out/h0047_perm.json`），
不走 `qbt randomport`。
- `2026-09-05T05:10:58Z` gongzhao-34905：**关闭** —— 已按 v3 修复：randomport 的 --n-short 去掉静默默认值，缺省即报错并说明纯多要写 0；alpha_beta 结论句改为带显著性。补 2 条回归测试（13 项全过）。受影响范围已只读扫描并写进本记录：台账裁决无一被影响，需要重跑的是 astock_quant/verified/ 那 14 份台账机制之前的纯多小盘报告（证据：PROTOCOL_LOG.md v3 = 02a1d5457de17265）
