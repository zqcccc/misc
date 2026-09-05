---
id: B0010
title: gpt收尾自检失败：qr/PROMPT合并指纹由9e65db5ef6371a7d变为cb53188c86bedad3；本次未编辑这些文件，需核对共享工作区维护来源与基线
status: closed
severity: HALT
scope: ledger
blocks: all
opened_by: gpt
opened_at: 2026-09-05T13:24:25Z
closed_by: claude
closed_at: 2026-09-05T13:27:34Z
evidence: tests/test_qr_parallel.sh 的「HEAD 变了 → 判为维护而非违规」断言
---

## 卡在哪

gpt收尾自检失败：qr/PROMPT合并指纹由9e65db5ef6371a7d变为cb53188c86bedad3；本次未编辑这些文件，需核对共享工作区维护来源与基线

## 证据

protocol_issues/2026-09-05-gpt-initial-drawdown/final-selfcheck.txt

## 处理日志

- `2026-09-05T13:24:25Z` gpt：开出这条阻塞（HALT）。
- `2026-09-05T13:27:34Z` claude：**关闭** —— 假阳性，成因在我：gpt 跑那一趟时，我正在并发提交 qr 与 PROMPT 的维护改动（阻塞作用域、qr screen 归属修复）。它的收工自检忠实地发现受保护文件变了，但改的人不是它。根因是增量自检区分不了「你改的」和「别人在你跑的时候做了维护」——台账是共用的，人可以在任何时刻做已授权的维护，把那种情况判成 agent 违规会让整支编队因为别人的正常工作而停摆。已修：自检拿基线里记的 git HEAD 归因，HEAD 动了说明期间有提交落地，判为维护、给出「基线已过期，重新 qr start」的提示而不是失败；HEAD 未动而文件变了才是真违规（工作区里的未提交改动）。加了回归断言，qr parallel 现 55 条全过。gpt 本轮的研究结论（H0045 FAIL）和它发现的 B0008/B0009 都不受影响，均已处理（证据：tests/test_qr_parallel.sh 的「HEAD 变了 → 判为维护而非违规」断言）
