---
id: B0019
title: PROMPT_LONGRUN.md 写『接管僵尸占坑必须 compare-and-swap：qr takeover <ID> --expect <原坑主的 run token>』，但 qr:1040 实际比对的是 owner_of()（agent 名字），不是 owner_run_of()（run token）。实测：H0082 坑主 run=claude-opus-5-1788654663-41092，--expect 该 token 被拒（『坑主是 claude-opus-5，不是你以为的 ...-41092』），--expect claude-opus-5 通过。后果正好是 PROMPT_LONGRUN 自己警告过的那个失效模式：同名并发被明确宣布为正常，而按名字做 compare-and-swap 时两个都叫 claude-opus-5 的 agent 会【同时】通过 --expect 检查、同时接管同一个坑，CAS 退化成无保护；run token 字段本身已经存在且已被写进 locks/<ID>/owner，只是 takeover 没用它。修法是一行：把 qr:1040 的 own 改成 owner_run_of，并让报错同时打印两者。不挡任何人：需要 --expect 的场景只在僵尸接管，且当前无同名并发实例
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: claude-opus-5
opened_at: 2026-09-06T12:09:41Z
closed_by:
closed_at:
evidence: quant_research/locks/H0082/owner
---

## 卡在哪

PROMPT_LONGRUN.md 写『接管僵尸占坑必须 compare-and-swap：qr takeover <ID> --expect <原坑主的 run token>』，但 qr:1040 实际比对的是 owner_of()（agent 名字），不是 owner_run_of()（run token）。实测：H0082 坑主 run=claude-opus-5-1788654663-41092，--expect 该 token 被拒（『坑主是 claude-opus-5，不是你以为的 ...-41092』），--expect claude-opus-5 通过。后果正好是 PROMPT_LONGRUN 自己警告过的那个失效模式：同名并发被明确宣布为正常，而按名字做 compare-and-swap 时两个都叫 claude-opus-5 的 agent 会【同时】通过 --expect 检查、同时接管同一个坑，CAS 退化成无保护；run token 字段本身已经存在且已被写进 locks/<ID>/owner，只是 takeover 没用它。修法是一行：把 qr:1040 的 own 改成 owner_run_of，并让报错同时打印两者。不挡任何人：需要 --expect 的场景只在僵尸接管，且当前无同名并发实例

## 证据

quant_research/locks/H0082/owner

## 处理日志

- `2026-09-06T12:09:41Z` claude-opus-5：开出这条阻塞（WARN）。
