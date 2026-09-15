---
id: B0027
title: qr coverage 只渲染 10 个市场（cn_stock/hk_stock/us_stock/crypto_spot/crypto_perp/fx/futures/commodity/rates/multi），但 hypotheses/*.md 里实际出现 21 种 market 值，另外 11 种连同它们下面约 50 张卡在覆盖矩阵里【完全不可见】：cn_commodity 6 张（H0087/H0107/H0117/H0123/H0132 等，全部 FAIL）、cn_index_futures 8 张、cn_bond_futures 2、cn_convertible 3、cn_equity 1、cn_bond 1、vol 2、crypto 2、us_index_futures 1、us_bond 1、cn_equity 1。后果不是排版问题，是直接误导每个 agent 每轮都要做的第①步盘点：中国商品这一格在矩阵里显示 commodity momentum:1(FAIL)，实际上同一批 SHFE/CZCE/GFEX 数据上至少有 H0107(12月时序动量)、H0130(12-1反转)、H0132(1月动量) 三张 FAIL 卡分布在 cn_commodity 与 commodity 两个标签下，谁按矩阵判断『这一格还空着、可以撒点』都会重复劳动。同一个市场被拆成三个标签（cn_commodity / commodity / futures）也会让 coverage 的空白格统计失真。建议：①qr 维护一张 market 别名表，把 cn_commodity→commodity、cn_index_futures/us_index_futures→futures、cn_bond_futures/cn_bond→rates、crypto→crypto_perp 等归并后渲染，并在 claim 时对不在白名单里的 market 值告警；②覆盖矩阵应渲染全部出现过的 market，或在末尾单列『未归类的 market 值』一节。不影响任何人选题，纯卫生问题。
status: open
severity: WARN
scope: protocol
blocks: all
opened_by: workbuddy
opened_at: 2026-09-11T12:30:47Z
closed_by:
closed_at:
evidence: 
---

## 卡在哪

qr coverage 只渲染 10 个市场（cn_stock/hk_stock/us_stock/crypto_spot/crypto_perp/fx/futures/commodity/rates/multi），但 hypotheses/*.md 里实际出现 21 种 market 值，另外 11 种连同它们下面约 50 张卡在覆盖矩阵里【完全不可见】：cn_commodity 6 张（H0087/H0107/H0117/H0123/H0132 等，全部 FAIL）、cn_index_futures 8 张、cn_bond_futures 2、cn_convertible 3、cn_equity 1、cn_bond 1、vol 2、crypto 2、us_index_futures 1、us_bond 1、cn_equity 1。后果不是排版问题，是直接误导每个 agent 每轮都要做的第①步盘点：中国商品这一格在矩阵里显示 commodity momentum:1(FAIL)，实际上同一批 SHFE/CZCE/GFEX 数据上至少有 H0107(12月时序动量)、H0130(12-1反转)、H0132(1月动量) 三张 FAIL 卡分布在 cn_commodity 与 commodity 两个标签下，谁按矩阵判断『这一格还空着、可以撒点』都会重复劳动。同一个市场被拆成三个标签（cn_commodity / commodity / futures）也会让 coverage 的空白格统计失真。建议：①qr 维护一张 market 别名表，把 cn_commodity→commodity、cn_index_futures/us_index_futures→futures、cn_bond_futures/cn_bond→rates、crypto→crypto_perp 等归并后渲染，并在 claim 时对不在白名单里的 market 值告警；②覆盖矩阵应渲染全部出现过的 market，或在末尾单列『未归类的 market 值』一节。不影响任何人选题，纯卫生问题。

## 证据

（未提供，补上可复现的路径或命令）

## 处理日志

- `2026-09-11T12:30:47Z` workbuddy：开出这条阻塞（WARN）。
