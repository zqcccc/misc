---
id: B0016
title: qr search 的查重闸只索引卡片标题与 plain 字段，索引不到『某张卡在 §5 里预登记、在 §7 里算了但没写进标题』的补充切分。实测：2026-09-06 我占坑 H0069（做多股指期货日内段），跑过 qr search 无命中，写完 §1-§5 后才发现 H0043 的 §7 表格行 D 已经把这个口径算完了（−6.99%/年，t=−1.00，CAPM alpha −7.15% t=−2.66）。代价是一次白占坑加约二十分钟。这类『被算过但没被命名』的口径在本台账里不罕见——H0043 的 trials 账本就明写了 7 个变体，其中只有 1 个进了标题。建议 qr search 额外全文检索 hypotheses/*.md 的 §5 尝试账本与 §7 表格，或要求裁决时把已算过的补充切分登记成可检索的 sub-result
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: claude-opus-5
opened_at: 2026-09-06T01:06:27Z
closed_by:
closed_at:
evidence: quant_research/hypotheses/H0043-*.md §5④ 与 §7 行 D；quant_research/hypotheses/H0069-cn-index-futures-intraday-segment.md（已释放）
---

## 卡在哪

qr search 的查重闸只索引卡片标题与 plain 字段，索引不到『某张卡在 §5 里预登记、在 §7 里算了但没写进标题』的补充切分。实测：2026-09-06 我占坑 H0069（做多股指期货日内段），跑过 qr search 无命中，写完 §1-§5 后才发现 H0043 的 §7 表格行 D 已经把这个口径算完了（−6.99%/年，t=−1.00，CAPM alpha −7.15% t=−2.66）。代价是一次白占坑加约二十分钟。这类『被算过但没被命名』的口径在本台账里不罕见——H0043 的 trials 账本就明写了 7 个变体，其中只有 1 个进了标题。建议 qr search 额外全文检索 hypotheses/*.md 的 §5 尝试账本与 §7 表格，或要求裁决时把已算过的补充切分登记成可检索的 sub-result

## 证据

quant_research/hypotheses/H0043-*.md §5④ 与 §7 行 D；quant_research/hypotheses/H0069-cn-index-futures-intraday-segment.md（已释放）

## 处理日志

- `2026-09-06T01:06:27Z` claude-opus-5：开出这条阻塞（WARN）。
