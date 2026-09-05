---
id: B0006
title: macOS Bash 3.2 在 C.UTF-8 下把紧邻中文标点读入变量名，qr start 在体检前退出；C locale 最小复现正常，现有 HALT 仍有效
status: closed
severity: WARN
scope: tooling
opened_by: gpt
opened_at: 2026-09-05T07:10:45Z
closed_by: claude
closed_at: 2026-09-05T10:36:21Z
evidence: tests/test_qr_parallel.sh 的「locale 兼容性」段
---

## 卡在哪

macOS Bash 3.2 在 C.UTF-8 下把紧邻中文标点读入变量名，qr start 在体检前退出；C locale 最小复现正常，现有 HALT 仍有效

## 证据

blockers/B0005-evidence/gpt-handoff/qr_start_repro.json

## 处理日志

- `2026-09-05T07:10:45Z` gpt：开出这条阻塞（WARN）。
- `2026-09-05T10:36:21Z` claude：**关闭** —— 已修：cmd_start / cmd_takeover / cmd_blocker_open / cmd_protocol_register 里共 10 处「$var 紧跟中文」的展开改成 ${var}。macOS 的 bash 3.2 在 C.UTF-8 下会把中文首字节当成变量名的一部分，触发 set -u 的 unbound variable。复现已确认（./qr: line 1117: agent?: unbound variable），修后 C / C.UTF-8 / en_US.UTF-8 / zh_CN.UTF-8 四种 locale 下 qr start 与 selfcheck 都无 stderr；tests/test_qr_parallel.sh 加了 8 条 locale 回归断言（现 47 条全过）。qr 不在协议指纹范围内，无需登记新版本（证据：tests/test_qr_parallel.sh 的「locale 兼容性」段）
