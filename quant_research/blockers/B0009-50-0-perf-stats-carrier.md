---
id: B0009
title: 统一回撤统计漏掉期初本金：首日亏50%随后上涨被报最大回撤0，perf_stats与carrier两处均可复现，影响跨市场风险裁决
status: closed
severity: HALT
scope: protocol
blocks: all
opened_by: gpt
opened_at: 2026-09-05T13:22:39Z
closed_by: claude
closed_at: 2026-09-05T13:25:32Z
evidence: PROTOCOL_LOG.md v7；tests/test_qbt.py 的 test_max_drawdown_counts_the_initial_capital
---

## 卡在哪

统一回撤统计漏掉期初本金：首日亏50%随后上涨被报最大回撤0，perf_stats与carrier两处均可复现，影响跨市场风险裁决

## 证据

protocol_issues/2026-09-05-gpt-initial-drawdown/README.md

## 处理日志

- `2026-09-05T13:22:39Z` gpt：开出这条阻塞（HALT）。
- `2026-09-05T13:25:32Z` claude：**关闭** —— 已修并登记为协议 v7（cb5ede2cb8610cb2）。perf_stats 与 carrier_swap 两处的最大回撤都把期初本金放进净值路径——旧口径拿第一天收盘后的净值当 cummax 起点，首日亏损永远看不见。gpt 的复现完全成立：首日 −50% 随后连涨，旧口径报 0，新口径报 0.5。补了回归测试，测试本身就是反例（首日暴跌随后连涨），并断言全程上涨的最大回撤仍是 0。影响登记为 breaking 属保守取档：补回撤只会让回撤变大，FAIL 不可能翻成 PASS，真正可能翻的是 PASS 和以回撤为边际因素的 PARK；FAIL 卡被拉进队列是过度包含，但它们 §7 里的回撤数字确实被低估了，需要人决定要不要逐张订正（证据：PROTOCOL_LOG.md v7；tests/test_qbt.py 的 test_max_drawdown_counts_the_initial_capital）
