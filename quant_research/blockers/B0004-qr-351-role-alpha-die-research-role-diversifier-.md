---
id: B0004
title: 协议缺陷：qr 第 351 行硬编码 [ "$role" = "alpha" ] || die，导致 research_role 为 diversifier/hedge/execution 的卡片在现有 qbt v2 下永远无法落 PASS——不是判死，是根本没有验收路径。H0047 严格报告已 verdict_code=PASS、falsification_failures=[] 仍被拒。需要补一份 execution/hedge/diversifier 角色的专用验收报告（执行角色的判读线应是：同暴露下的净成本差、追加保证金压力、最小资金门槛、载体特有的尾部，而不是 alpha 显著性）
status: closed
severity: HALT
scope: protocol
blocks: all
opened_by: claude
opened_at: 2026-09-05T04:16:06Z
closed_by: gongzhao-73738
closed_at: 2026-09-05T05:20:48Z
evidence: PROTOCOL_LOG.md v4 = 75a867c1e95745a3；SKILL.md『载体替换』段
---

## 卡在哪

协议缺陷：qr 第 351 行硬编码 [ "$role" = "alpha" ] || die，导致 research_role 为 diversifier/hedge/execution 的卡片在现有 qbt v2 下永远无法落 PASS——不是判死，是根本没有验收路径。H0047 严格报告已 verdict_code=PASS、falsification_failures=[] 仍被拒。需要补一份 execution/hedge/diversifier 角色的专用验收报告（执行角色的判读线应是：同暴露下的净成本差、追加保证金压力、最小资金门槛、载体特有的尾部，而不是 alpha 显著性）

## 证据

quant_research/qr:351；复现：cd quant_research && ./qr verdict H0047 PASS --report ../cn_index_futures/out/h0047_verdict.json "..."

## 处理日志

- `2026-09-05T04:16:06Z` claude：开出这条阻塞（HALT）。
- `2026-09-05T05:20:48Z` gongzhao-73738：**关闭** —— 已开出执行角色的验收路径：新增 qbt.py carrier（同暴露 beta 容差 + 暴露调整后差额双门禁 + 压力成本档 + 跨期一致 + 回撤不更深 + 载体风险逐项申报），qr 的 PASS 校验按角色分支。协议登记为 v4（影响 none，历史裁决不受影响）。diversifier/hedge 仍无路径，现在会给出明确报错而不是被当成 alpha 拒绝（证据：PROTOCOL_LOG.md v4 = 75a867c1e95745a3；SKILL.md『载体替换』段）
