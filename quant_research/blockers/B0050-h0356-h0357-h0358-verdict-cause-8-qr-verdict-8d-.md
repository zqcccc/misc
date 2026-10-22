---
id: B0050
title: 诊断/组合/容量类卡连续三张（H0356/H0357/H0358）在 verdict 后 cause 字段与 §8 实际结论不符（强度不足->信号无增量、信号无增量->数据不可得->信号无增量、容量不足->信号无增量），均为裁决后手动返工。根因：qr verdict 的死因是裁决时凭直觉写的，而卡片 §8d/§8e 的死因论证是填卡时才写，两者之间没有核对步骤。固化判据（写进填卡模板，后续所有卡在 verdict 前过一遍）：①『强度不足』只用于毛收益为正但 t<2 的统计强度问题；②『信号无增量』用于对比/替换/门槛调整/分组检验中无法区分于对照的情形（含三档持平）；③『容量不足』只用于毛收益被冲击成本吃穿的流动性容量问题（H0338 类），不用于天花板量化；④诊断/组合/容量类卡（parent=PASS 卡的深化检验）默认 research_role=diversifier；⑤verdict 命令的 --cause 必须在填卡后与 §8d/§8e 的结论词逐字核对，不一致时先改卡再 rebuild
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: quant-agent-1792433252-86938-20969
opened_at: 2026-10-21T01:09:24Z
closed_by:
closed_at:
evidence: quant_research/hypotheses/H0358-h0358-h0350-gate-capacity-tradeoff.md
---

## 卡在哪

诊断/组合/容量类卡连续三张（H0356/H0357/H0358）在 verdict 后 cause 字段与 §8 实际结论不符（强度不足->信号无增量、信号无增量->数据不可得->信号无增量、容量不足->信号无增量），均为裁决后手动返工。根因：qr verdict 的死因是裁决时凭直觉写的，而卡片 §8d/§8e 的死因论证是填卡时才写，两者之间没有核对步骤。固化判据（写进填卡模板，后续所有卡在 verdict 前过一遍）：①『强度不足』只用于毛收益为正但 t<2 的统计强度问题；②『信号无增量』用于对比/替换/门槛调整/分组检验中无法区分于对照的情形（含三档持平）；③『容量不足』只用于毛收益被冲击成本吃穿的流动性容量问题（H0338 类），不用于天花板量化；④诊断/组合/容量类卡（parent=PASS 卡的深化检验）默认 research_role=diversifier；⑤verdict 命令的 --cause 必须在填卡后与 §8d/§8e 的结论词逐字核对，不一致时先改卡再 rebuild

## 证据

quant_research/hypotheses/H0358-h0358-h0350-gate-capacity-tradeoff.md

## 处理日志

- `2026-10-21T01:09:24Z` quant-agent-1792433252-86938-20969：开出这条阻塞（WARN）。

## 第七次返工后的固化（2026-10-21，H0361）

**连续七张卡（H0356/H0357/H0358/H0360/H0361/H0362 + H0340）在 research_role 上返工。**
根因：`qr claim` 默认 research_role=alpha，而 parent=PASS 卡的增量/容量/载体/组合检验类卡应为 diversifier。

**固化规则（填卡脚本的第一行必须检查）**：
```
if parent 存在且本卡为（增量检验 | 容量权衡 | 载体替换 | 组合扩展 | 机制诊断）:
    research_role = diversifier
    report.json 的 role 字段同步 = diversifier
```
**在 verdict 前必须 grep 两处**：
1. `grep '^research_role:' hypotheses/<ID>-*.md` 确认 diversifier
2. `python -c "import json; print(json.load(open('.../report.json'))['role'])"` 确认一致
