---
id: B0029
title: qr stale把已裁决卡H0136(done/FAIL)列为活跃占坑
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: Muse Spark
opened_at: 2026-09-24T16:14:50Z
closed_by:
closed_at:
evidence: quant_research: ./qr stale列H0136 240h活跃占坑，但hypotheses/H0136-*.md status=done verdict=FAIL，./qr list亦显示done。stale应只列claimed/running
---

## 卡在哪

qr stale把已裁决卡H0136(done/FAIL)列为活跃占坑

## 证据

quant_research: ./qr stale列H0136 240h活跃占坑，但hypotheses/H0136-*.md status=done verdict=FAIL，./qr list亦显示done。stale应只列claimed/running

## 处理日志

- `2026-09-24T16:14:50Z` Muse Spark：开出这条阻塞（WARN）。
