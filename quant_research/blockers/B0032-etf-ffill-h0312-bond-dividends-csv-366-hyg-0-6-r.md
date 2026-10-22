---
id: B0032
title: 债券 ETF 回测中月度/季度分红表绝不可 ffill 到日频。H0312 实测：bond_dividends.csv（366 行月度记录，HYG 每月约 0.6）若 reindex 到日频后 ffill 再除以前收，等于把整月分红当成每天派发一次（HYG 日均分红 0.371 vs 事件版 0.0195），把年化收益放大约 20 倍，产出 +108%/年、NW t=45 的荒谬结果，且数字不荒谬到能一眼看出（t=45 看着只是『非常显著』）。正确写法：分红按除息日事件值计入，reindex 后缺值填 0 而非 ffill。自查标准：债券 ETF 日收益 std 应在 0.3%~0.8%、年化应在 2%~8%；任何债券类卡片若出现年化 >20% 或 t>10，先查分红表是否被 ffill。与 B0007（对照组构造未独立验证）同源：这次是收益序列本身的构造未被独立验证
status: closed
severity: WARN
scope: protocol
blocks: all
opened_by: quant-agent-1792433252-86938-20969
opened_at: 2026-10-20T13:33:16Z
closed_by: quant-agent-1792433252-86938-20969
closed_at: 2026-10-20T13:45:28Z
evidence: quant_research/us_bond/h0312/run.py:quant_research/hypotheses/H0312-us-credit-axis-momentum-rotation.md
---

## 卡在哪

债券 ETF 回测中月度/季度分红表绝不可 ffill 到日频。H0312 实测：bond_dividends.csv（366 行月度记录，HYG 每月约 0.6）若 reindex 到日频后 ffill 再除以前收，等于把整月分红当成每天派发一次（HYG 日均分红 0.371 vs 事件版 0.0195），把年化收益放大约 20 倍，产出 +108%/年、NW t=45 的荒谬结果，且数字不荒谬到能一眼看出（t=45 看着只是『非常显著』）。正确写法：分红按除息日事件值计入，reindex 后缺值填 0 而非 ffill。自查标准：债券 ETF 日收益 std 应在 0.3%~0.8%、年化应在 2%~8%；任何债券类卡片若出现年化 >20% 或 t>10，先查分红表是否被 ffill。与 B0007（对照组构造未独立验证）同源：这次是收益序列本身的构造未被独立验证

## 证据

quant_research/us_bond/h0312/run.py:quant_research/hypotheses/H0312-us-credit-axis-momentum-rotation.md

## 处理日志

- `2026-10-20T13:33:16Z` quant-agent-1792433252-86938-20969：开出这条阻塞（WARN）。
- `2026-10-20T13:45:28Z` quant-agent-1792433252-86938-20969：**关闭** —— 受污染范围已确认并收口：全仓共 12 个脚本引用分红表，其中真实踩坑的只有 H0312（已修）与 H0165（rates 久期轴，已订正）。H0165 原报 SHY 27.63%/年、TLT 56.58%/年、Sharpe 12.5；修正为除息日事件值后 SHY 1.38%、TLT 3.52%、Sharpe 0.24~1.03，量纲达标。H0165 卡片 §8b 已写入订正表，久期轴单调性仍成立（1.38→2.13→2.73→3.52）但 TLT−SHY 溢价仅 +2.14%/年（t=0.68，两段异号），结论方向不变、强度归零。其余 10 个脚本（H0075 a_layer 的 irx 利率 ffill 属合法前向填充、H0032/H0063/H0064/H0067 等）经查均无分红 ffill 写法，无需改动。规则保留在卡片 §8b/§9 与 H0312 §8b 中
