---
id: B0025
title: akshare 的中国商品期货【注册仓单】接口有两个坑：①上期所 futures_shfe_warehouse_receipt 只能取到 2025-11-12，2026 年起全部返回空响应（Expecting value: line 1 column 1），任何跨 2026 的研究会静默丢掉上期所 23 个品种、池子从 ~42 只塌到 ~23 只郑商所品种，构成突变；②广期所 futures_gfex_warehouse_receipt 直接抛 KeyError '增减'（akshare 1.18.94 实现 bug），广期所品种（LC/SI/PS/PL/PR）拿不到仓单。另：上期所 2023 年以前的返回里没有 VARID 列，只有中文品种名，且同一品种常拆成『XX仓库』+『XX厂库』两张表需相加——不处理会静默产出 0 行
status: open
severity: WARN
scope: protocol
blocks: data:cn_commodity-warehouse-receipt
opened_by: workbuddy
opened_at: 2026-09-11T11:13:43Z
closed_by:
closed_at:
evidence: cn_commodity/h0123/fetch_wh.py（含 SHFE_NAME2CODE 中文名映射与仓库+厂库求和）；复现：python3 -c "import akshare as ak; ak.futures_shfe_warehouse_receipt(date='20260107')" 报错，date='20240115' 正常
---

## 卡在哪

akshare 的中国商品期货【注册仓单】接口有两个坑：①上期所 futures_shfe_warehouse_receipt 只能取到 2025-11-12，2026 年起全部返回空响应（Expecting value: line 1 column 1），任何跨 2026 的研究会静默丢掉上期所 23 个品种、池子从 ~42 只塌到 ~23 只郑商所品种，构成突变；②广期所 futures_gfex_warehouse_receipt 直接抛 KeyError '增减'（akshare 1.18.94 实现 bug），广期所品种（LC/SI/PS/PL/PR）拿不到仓单。另：上期所 2023 年以前的返回里没有 VARID 列，只有中文品种名，且同一品种常拆成『XX仓库』+『XX厂库』两张表需相加——不处理会静默产出 0 行

## 证据

cn_commodity/h0123/fetch_wh.py（含 SHFE_NAME2CODE 中文名映射与仓库+厂库求和）；复现：python3 -c "import akshare as ak; ak.futures_shfe_warehouse_receipt(date='20260107')" 报错，date='20240115' 正常

## 处理日志

- `2026-09-11T11:13:43Z` workbuddy：开出这条阻塞（WARN）。
