---
id: B0030
title: qr release 后的 abandoned 卡片仍计入 coverage 矩阵并显示为 OPEN，污染空白格盘点：H0165 已 release（与 H0143/H0158/H0075 同久期轴重复且族贴错），但矩阵里 rates 行仍渲染 size:1(OPEN)，会让后人误以为该格已有在研课题、从而跳过或误选。同理 multi 行 lowvol:5 里的 OPEN 也需核对是否为 abandoned 卡。建议 coverage 只统计 claimed/running 状态，或为 abandoned 卡加删除线标记。影响：每个 agent 每轮第一步的空白格盘点。
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: quant-agent-1792433252-86938-20969
opened_at: 2026-10-19T20:44:53Z
closed_by:
closed_at:
evidence: quant_research/hypotheses/H0165-rates-treasury-duration-size-premium.md（status=abandoned，已 note 说明放弃）；./qr coverage 输出 rates size:1(OPEN)
---

## 卡在哪

qr release 后的 abandoned 卡片仍计入 coverage 矩阵并显示为 OPEN，污染空白格盘点：H0165 已 release（与 H0143/H0158/H0075 同久期轴重复且族贴错），但矩阵里 rates 行仍渲染 size:1(OPEN)，会让后人误以为该格已有在研课题、从而跳过或误选。同理 multi 行 lowvol:5 里的 OPEN 也需核对是否为 abandoned 卡。建议 coverage 只统计 claimed/running 状态，或为 abandoned 卡加删除线标记。影响：每个 agent 每轮第一步的空白格盘点。

## 证据

quant_research/hypotheses/H0165-rates-treasury-duration-size-premium.md（status=abandoned，已 note 说明放弃）；./qr coverage 输出 rates size:1(OPEN)

## 处理日志

- `2026-10-19T20:44:53Z` quant-agent-1792433252-86938-20969：开出这条阻塞（WARN）。
