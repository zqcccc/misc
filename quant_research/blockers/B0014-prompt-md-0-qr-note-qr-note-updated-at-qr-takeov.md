---
id: B0014
title: PROMPT.md 阶段0 ④ 要求『接管僵尸占坑前先 qr note 留痕』，但 qr note 会把卡片的 updated_at 刷新到当下，僵尸计时随即归零，于是 qr takeover 立刻报『才 0h 没动，没到僵尸线』——照文档做就一定接管不了，只能退回 --force，而 --force 本意是给『确认对方真的死了』的例外用的。实测：H0062 停更 14h，qr stale 列出它；我按文档先 note 一条，再 takeover 就被拒。建议 qr note 对非坑主的留痕不刷新 updated_at（或 takeover 用 last_owner_update 而非 updated_at 计时）
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: claude-opus-5
opened_at: 2026-09-06T00:33:07Z
closed_by:
closed_at:
evidence: quant_research/locks/H0062/owner + hypotheses/H0062-short-liquidation-fingerprint.md 探索日志末条
---

## 卡在哪

PROMPT.md 阶段0 ④ 要求『接管僵尸占坑前先 qr note 留痕』，但 qr note 会把卡片的 updated_at 刷新到当下，僵尸计时随即归零，于是 qr takeover 立刻报『才 0h 没动，没到僵尸线』——照文档做就一定接管不了，只能退回 --force，而 --force 本意是给『确认对方真的死了』的例外用的。实测：H0062 停更 14h，qr stale 列出它；我按文档先 note 一条，再 takeover 就被拒。建议 qr note 对非坑主的留痕不刷新 updated_at（或 takeover 用 last_owner_update 而非 updated_at 计时）

## 证据

quant_research/locks/H0062/owner + hypotheses/H0062-short-liquidation-fingerprint.md 探索日志末条

## 处理日志

- `2026-09-06T00:33:07Z` claude-opus-5：开出这条阻塞（WARN）。
