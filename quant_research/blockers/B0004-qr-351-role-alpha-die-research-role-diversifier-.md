---
id: B0004
title: 协议缺陷：qr 第 351 行硬编码 [ "$role" = "alpha" ] || die，导致 research_role 为 diversifier/hedge/execution 的卡片在现有 qbt v2 下永远无法落 PASS——不是判死，是根本没有验收路径。H0047 严格报告已 verdict_code=PASS、falsification_failures=[] 仍被拒。需要补一份 execution/hedge/diversifier 角色的专用验收报告（执行角色的判读线应是：同暴露下的净成本差、追加保证金压力、最小资金门槛、载体特有的尾部，而不是 alpha 显著性）
status: open
severity: HALT
scope: protocol
opened_by: claude
opened_at: 2026-09-05T04:16:06Z
closed_by:
closed_at:
evidence: quant_research/qr:351；复现：cd quant_research && ./qr verdict H0047 PASS --report ../cn_index_futures/out/h0047_verdict.json "..."
---

## 卡在哪

协议缺陷：qr 第 351 行硬编码 [ "$role" = "alpha" ] || die，导致 research_role 为 diversifier/hedge/execution 的卡片在现有 qbt v2 下永远无法落 PASS——不是判死，是根本没有验收路径。H0047 严格报告已 verdict_code=PASS、falsification_failures=[] 仍被拒。需要补一份 execution/hedge/diversifier 角色的专用验收报告（执行角色的判读线应是：同暴露下的净成本差、追加保证金压力、最小资金门槛、载体特有的尾部，而不是 alpha 显著性）

## 证据

quant_research/qr:351；复现：cd quant_research && ./qr verdict H0047 PASS --report ../cn_index_futures/out/h0047_verdict.json "..."

## 处理日志

- `2026-09-05T04:16:06Z` claude：开出这条阻塞（HALT）。
