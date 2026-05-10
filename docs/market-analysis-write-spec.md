# 市场分析数据写入规范

## 概述

本文档定义了外部 Agent 在完成**人工分析**后将数据写入数据库的标准流程。

**重要说明：这不是程序化数据接口！**
- 本 API 仅供具备分析能力的 AI Agent 使用
- 写入的数据应基于 Agent 对多维度信息的**综合判断**，而非简单的财务指标计算
- 评分（score）应反映 Agent 对公司投资价值的**主观+客观综合评估**

## Agent 分析要求

### 什么情况下应该写入数据？

Agent 在以下情况下应该调用本 API：
1. 完成了对某家公司的**深度研究分析**
2. 收集了**多维度信息**（财务数据、行业动态、竞争格局、管理层、宏观经济等）
3. 形成了**明确的投资观点**（看多/看空/中性）
4. 愿意为该观点承担**置信度评估**

### 分析覆盖范围

**所有公司都应该被分析**，不设指标范围限制。无论公司规模、行业、估值水平或数据完整度如何，都应完成分析并写入数据。

**覆盖范围不得受当前数据库限制。** `Company` 表只代表已经写入或正在展示的公司，不是待分析股票池的边界。Agent 在整理分析任务时，应优先从外部市场股票池获取候选公司，并将数据库已有公司作为去重、状态判断和结果更新依据。

待分析股票池应按以下顺序确定：

1. 从外部市场股票池获取候选公司（如 A 股、港股、美股等市场的上市公司列表）
2. 与数据库中的 `Company(market, symbol)` 做去重和状态比对
3. 对数据库中不存在的公司，完成分析后通过写入 API 创建 `Company` 并写入分析结果
4. 对数据库中已存在且无明显问题的公司，可以跳过，不需要为了覆盖任务重复改写
5. 对数据库中已存在但信息明显错误、缺失关键展示字段、分析过旧或质量不足的公司，再进行补全或更新

以下情况虽然信息不够充分，但仍应写入分析，同时在 **confidence** 字段中如实反映信息完整度：
1. 仅获取了原始财务数据，未形成深度分析观点 → 降低 confidence
2. 仅做了简单的指标计算（如 PE、PB 排名） → 降低 confidence
3. 没有阅读公司年报、研报、新闻等上下文信息 → 降低 confidence
4. 对公司所在行业缺乏基本了解 → 降低 confidence

### 分析方式与节奏

**核心原则：像人类研究员一样，逐个深入分析，而非批量流水线处理。**

Agent 在分析全市场股票时，必须遵循以下原则：

#### 1. 逐个分析，不可并行敷衍

- **一次只分析一家公司**，完成全部研究、评分、写入流程后，再开始下一家
- 禁止为了追求效率而对多家公司同时进行浅层分析
- 每家公司的分析都应该是**独立且完整**的，不因已分析了大量公司而降低标准
- 选择下一家公司时，不应只从数据库已有记录中挑选；数据库只是分析结果库，外部市场股票池才是覆盖来源

#### 2. 深度优先，拒绝走马观花

- 对每家公司都要像人类研究员写深度研报一样认真对待
- 不是简单抓取几个指标就打分，而是要**理解业务本质、判断竞争格局、评估管理层质量**
- 宁可少分析几家公司，也不要为了覆盖面而牺牲分析深度
- 每条 Explanation 的 body 都应体现真正的思考深度，而非模板化的套话

#### 3. 分析节奏：慢即是快

- **信息收集阶段**：花足够时间搜索和阅读公司的财报、行业报告、新闻动态
- **思考判断阶段**：在形成观点前，反复推敲逻辑是否自洽、证据是否充分
- **评分决策阶段**：评分不是拍脑袋，而是基于多维度权衡后的审慎判断
- **写入验证阶段**：写入后检查数据是否完整、逻辑是否通顺

#### 4. 分析质量的一致性

- **第 1 家公司和第 100 家公司的分析深度应保持一致**
- 不因疲劳或重复感而降低分析标准
- 不因公司知名度低或数据少就敷衍了事——信息不足时降低 confidence，而非降低分析努力
- 每次分析都应问自己："如果这是我的客户要看的报告，我会满意吗？"

#### 5. 分析中的思考规范

- **保持独立思考**：不因市场主流观点而随波逐流，敢于给出与共识不同的评分
- **区分事实与判断**：财务数据是事实，行业前景是判断，两者在分析中应明确区分
- **承认不确定性**：不确定的地方要坦诚标注，而非用模糊表述掩盖
- **避免锚定效应**：分析新公司时不要被之前分析的公司的评分所影响

#### 6. 分析间上下文隔离

**核心原则：每家公司的分析应在独立的上下文中进行，避免不同公司间的信息污染。**

**推荐方式：使用 Sub-Agent（子代理）模式**

- **强烈建议**使用 sub-agent 模式进行逐个公司分析：每家公司的完整分析流程（信息收集→思考判断→评分决策→写入验证）都应在一个独立的 sub-agent 中执行
- Sub-agent 天然具有独立的上下文窗口，分析完一家公司后 sub-agent 销毁，上下文自动清空，无需手动清理
- 主 agent 只负责调度（如确定待分析公司列表、分配任务），不参与具体分析，从而避免主 agent 上下文被污染
- 这种方式从根本上杜绝了信息残留、数据串写、锚定效应等问题

**备选方式：手动清理上下文**

如果运行环境不支持 sub-agent 模式，则必须手动清理上下文：

- **写入验证后立即清理**：完成一家公司的数据写入和验证后，主动清空当前对话/上下文窗口，再开始下一家公司的分析
- **防止信息污染**：上一家公司的财务数据、行业判断、评分逻辑等不应残留在上下文中，避免对下一家公司产生隐性影响
- **防止数据串写**：上下文中残留的数字（营收、PE、利润等）极易被错误地套用到新公司，清理上下文是杜绝此类错误的最有效手段
- **保持上下文窗口充裕**：随着分析推进，上下文窗口会不断膨胀，导致模型注意力分散、分析质量下降。定期清理可确保每次分析都在"新鲜"的上下文中进行
- **清理方式**：如果 Agent 运行环境支持上下文管理（如新建会话、清空历史消息等），应在公司间切换时执行清理操作；如果不支持，则应在开始新公司分析时，用明确的分隔标记（如"以下为全新公司的分析，请忽略之前所有上下文"）来重置分析状态

### 分析前必须收集的上下文

Agent 在给出评分和写入数据前，必须尽可能收集以下信息：

#### 1. 财务数据（客观基础）
- 最近 3-5 年的营收、利润、现金流趋势
- 毛利率、净利率变化及原因
- ROE、ROA 及其可持续性
- 资产负债结构（有息负债、现金储备）
- 资本开支与自由现金流

#### 2. 现金流质量与自由现金流分析（现金基础）
- 经营性现金流与净利润匹配度：判断公司是否“有利润、有现金”，警惕净利润增长但经营现金流长期偏弱
- 自由现金流趋势：计算并分析经营性现金流扣除资本开支后的自由现金流，观察最近 3-5 年是否持续为正、是否高度波动
- 现金转化能力：关注净现比、经营现金流/EBITDA、自由现金流/净利润等指标，判断利润的现金含量
- 营运资本影响：拆分应收账款、存货、应付账款、预收款变化，识别现金流改善是否来自一次性营运资本释放或拉长付款周期
- 资本开支性质：区分维持性 capex 与扩张性 capex，判断当前自由现金流是否低估或高估了真实可分配现金
- 现金流覆盖能力：分析自由现金流能否覆盖分红、回购、债务偿还、利息支出和必要再投资
- FCF Yield：将自由现金流收益率与无风险利率、同业公司和公司自身增长质量对比，判断估值安全边际
- 商业模式差异：重资产公司需重点评估资本开支周期和现金回收期，SaaS/平台公司需关注 stock-based compensation 对自由现金流的美化

#### 3. 资产质量与资产结构（资产基础）
- 资产构成：现金及等价物、应收账款、存货、固定资产、无形资产、商誉、长期股权投资等主要资产占比
- 资产质量：应收账款回收风险、存货跌价风险、商誉和无形资产减值风险、固定资产利用效率
- 资产周转效率：总资产周转率、存货周转、应收账款周转与同业对比
- 资产负债匹配：有息负债期限结构、现金覆盖能力、短债压力、资本开支需求与融资约束
- 轻资产/重资产模式判断：分析资产结构是否匹配商业模式，以及重资产投入能否形成长期竞争壁垒
- 隐性资产与表外风险：品牌、渠道、牌照、数据、土地物业等未充分体现在账面价值中的资产，以及担保、租赁、或有负债等表外风险
- PB 与净资产含金量：判断账面净资产是否真实、可变现、可持续创造收益，避免机械使用 PB 低估结论

#### 4. 行业与竞争（客观环境）
- 行业增长阶段（成长期/成熟期/衰退期）
- 公司在行业中的竞争地位（龙头/挑战者/ niche）
- 主要竞争对手及差异化优势
- 行业壁垒（技术、品牌、渠道、牌照）

#### 5. 公司治理与管理层（主观判断）
- 股权结构是否合理
- 管理层历史业绩与诚信记录
- 关联交易情况
- 股东回报政策（分红、回购）

#### 6. 催化剂与风险（前瞻性）
- 未来 1-2 年的潜在催化剂
- 主要风险因素（政策、技术替代、周期）
- ESG 相关风险

#### 7. 估值水平（市场定价）
- 当前 PE/PB/PS 与历史区间对比
- 与同业公司的估值对比
- DCF 或股息贴现的合理价值区间

## 评分标准规范

### score 字段（投资吸引力评分）

**范围**: 0-100

**评分维度**（Agent 应综合考虑）：

| 维度 | 权重建议 | 评估要点 |
|------|---------|---------|
| 财务健康度 | 20% | 盈利质量、现金流质量、自由现金流、资产质量、负债率 |
| 成长潜力 | 20% | 收入增长、市场份额、新业务 |
| 竞争优势 | 20% | 护城河、定价权、品牌力 |
| 估值吸引力 | 20% | 当前价格 vs 内在价值、FCF Yield、PB 与净资产含金量 |
| 风险调整 | 20% | 政策风险、周期风险、治理风险、资产减值风险、自由现金流持续性风险 |

**评分参考区间**：
- **90-100**: 极度低估，罕见机会，强烈建议买入
- **80-89**: 明显低估，具备安全边际，建议买入
- **70-79**: 合理偏低，有一定吸引力，可考虑买入
- **60-69**: 估值合理，持有观望
- **50-59**: 略微高估，谨慎持有
- **40-49**: 明显高估，建议减仓
- **0-39**: 严重高估或基本面恶化，建议卖出

**重要**：
- 评分**不是**财务指标的简单加权平均
- 评分应体现 Agent 的**综合判断**和**边际观点**
- 同一公司在不同时间点，Agent 可能给出不同评分（基于新信息）

### confidence 字段（分析置信度）

**范围**: 0-100

**置信度评估标准**：
- **90-100**: 信息充分，逻辑清晰，高度确信
  - 示例：茅台的品牌护城河，数据透明，观点明确
- **70-89**: 信息较充分，但有少量不确定因素
  - 示例：大部分蓝筹股的分析
- **50-69**: 信息有限，存在较多假设
  - 示例：新业务占比高的成长型公司
- **30-49**: 信息不足，高度依赖推测
  - 示例：刚上市的新股，或业务复杂多元的公司
- **0-29**: 几乎无法判断，纯属猜测
  - 仍需写入数据，但应在 summary 中注明信息严重不足

## 数据如何在 PE 页面展示

PE 页面（利润线 vs 股价）的数据展示逻辑如下：

### 左侧公司列表（Sidebar）

**数据来源**: `Company` 表

> **注意**：`CompanyPageEntry` 表已废弃，页面展示相关字段（`entryType`、`entryNote`、`sortOrder`、`visible`）已迁移到 `Company` 表。

**展示条件**:
- `company.visible = true`
- 按 `company.sortOrder` 排序

**展示内容**:
- 公司名称（来自 `company.name`）
- 股票代码（来自 `company.symbol`）
- TTM PE（来自 `valuation.ttmPe`）
- 利润质量状态（来自 `explanations` 分析）
- 评分（来自 `exploration.score`）

### 右侧估值卡片（Valuation Card）

**数据来源**: `Company` + `CompanyValuationSnapshot` + `CompanyExploration` + `CompanyValuationExplanation`

**展示内容**:
- **估值指标**: price, ttmEps, ttmPe, profitLinePrice, referenceLinePrice
- **分析摘要**: exploration.summary, exploration.thesis
- **标签**: exploration.tags
- **利润质量**: 基于 explanations 计算（正常/需调整/待确认）
- **主要解释**: primaryExplanation（优先显示 profit 类型且 isRecurring=false 的说明）
- **解释列表**: 最多显示 3 条 explanations

### 数据关联关系

```
Company (公司基础信息 + 页面展示配置)
  │  包含字段: entryType, entryNote, sortOrder, visible
  ├── CompanyExploration (分析报告 - 显示摘要和评分)
  ├── CompanyValuationSnapshot (估值快照 - 显示 PE 等指标)
  └── CompanyValuationExplanation (估值解释 - 显示利润质量分析)
```

## 数据写入流程

### 0. 写入前的股票池与状态判断

Agent 在开始写入前，应先区分“候选股票池”和“数据库已有结果”：

- **候选股票池**：来自外部市场列表，是分析覆盖范围的来源
- **数据库已有结果**：来自 `Company` 及其关联表，只用于判断是否已分析、是否需要更新、是否需要补全

处理规则：

| 状态 | 处理方式 |
|------|---------|
| 外部股票池中存在，数据库中不存在 | 正常分析，调用写入 API 创建公司与分析结果 |
| 数据库中已存在，数据完整且无明显问题 | 可以跳过，不强制重复写入 |
| 数据库中已存在，但缺少 `pageEntry` / `valuation` / `exploration` / `explanations` | 只补足缺失部分 |
| 数据库中已存在，但名称、市场、代码、展示状态明显错误 | 修正 Company 基础信息和展示字段 |
| 数据库中已存在，但分析明显过期或质量不足 | 使用新的 `runId` 写入新版分析，保留历史记录 |

因此，数据库不是“只分析这些股票”的限制条件；它是已分析状态、展示状态和幂等更新的记录系统。

### 1. 必须写入的数据

每个市场分析必须包含以下数据：

```json
{
  "company": {
    "symbol": "股票代码",
    "market": "市场标识",
    "name": "公司名称"
  },
  "pageEntry": {
    "entryType": "入口类型"
  }
}
```

> **说明**：`pageEntry` 中的字段（`entryType`、`note`、`sortOrder`、`visible`）实际存储在 `Company` 表上，而非独立的 `CompanyPageEntry` 表（该表已废弃）。API 仍保留 `pageEntry` 作为独立输入段，便于逻辑分离，但写入时会合并到 `Company` 记录中。

### 2. 推荐写入的数据

为了在 PE 页面提供完整的用户体验，建议同时写入：

- `valuation` - 估值快照数据（显示 PE、价格等）
- `exploration` - 分析报告内容（显示摘要、评分、标签）
- `explanations` - 估值解释说明（显示利润质量分析）

## 幂等写入机制

### 核心概念：runId

为了防止重复写入和数据混乱，所有写入操作必须提供一个 **`runId`** 参数。

**runId 的作用**:
- 标识一次完整的分析任务
- 相同的 `runId` 重复写入会**更新**已有记录，不会创建重复数据
- 不同的 `runId` 会创建新的记录，保留历史版本

**runId 生成规则**:
```
{agent-name}-{symbol}-{date}-{sequence}

示例:
- analysis-aapl-20260508-001
- daily-report-600519-20260508-001
- weekly-hk-00700-20260508-001
```

### 幂等写入行为

| 数据类型 | 相同 runId | 不同 runId |
|---------|-----------|-----------|
| Company | 更新已有记录 | 更新已有记录（按 market+symbol 唯一） |
| PageEntry | 更新 Company 记录上的展示字段（entryType/entryNote/sortOrder/visible） | 同左（始终更新 Company 记录） |
| Exploration | **更新**该 runId 下的记录 | **创建**新记录 |
| ValuationSnapshot | **更新**该 runId 下的记录 | **创建**新记录 |
| Explanation | **更新**该 runId+type 下的记录 | **创建**新记录 |

> 对已经存在且无明显问题的数据库记录，不需要为了“整理全市场”而强制重写。只有在补缺、纠错、重新分析或刷新过期观点时，才应调用写入 API 更新。

### 为什么需要幂等写入？

**场景 1: 网络超时重试**
```
Agent 调用写入 API → 网络超时 → Agent 重试 → 如果没有 runId，会产生重复数据
```

**场景 2: 定时任务**
```
每天 9:00 分析 AAPL → 写入 runId: daily-aapl-20260508
如果任务失败重试 → 相同 runId 只会更新，不会重复
```

**场景 3: 多 Agent 协作**
```
Agent A 分析 AAPL → runId: analysis-aapl-001
Agent B 分析 AAPL → runId: analysis-aapl-002
→ 两个分析结果都保留，PE 页面展示最新的 published 记录
```

## API 接口

**接口地址**: `POST /api/market-analysis/write`

### 请求示例

#### 最小请求（仅必需字段）

```json
{
  "runId": "analysis-aapl-20260508-001",
  "company": {
    "symbol": "AAPL",
    "market": "us",
    "name": "Apple Inc."
  },
  "pageEntry": {
    "entryType": "ai-generated"
  }
}
```

#### 完整请求示例

```json
{
  "runId": "analysis-moutai-20260508-001",
  "company": {
    "symbol": "600519",
    "market": "a",
    "name": "贵州茅台",
    "exchange": "SH",
    "currency": "CNY",
    "sector": "白酒",
    "industry": "高端白酒",
    "country": "中国"
  },
  "pageEntry": {
    "entryType": "analysis",
    "note": "基于2026年Q1财报",
    "sortOrder": 1,
    "visible": true
  },
  "exploration": {
    "title": "贵州茅台投资价值分析",
    "summary": "茅台作为中国高端白酒龙头企业...",
    "thesis": "长期来看，茅台的品牌护城河...",
    "catalysts": "i茅台APP推广、产能扩张",
    "risks": "消费税改革、年轻人消费习惯变化",
    "tags": ["白酒", "龙头", "价值投资"],
    "score": 82,
    "confidence": 85,
    "sourceUrls": ["https://example.com/report"],
    "visibility": "published"
  },
  "valuation": {
    "asOfDate": "2026-05-08",
    "price": 1680.00,
    "ttmPe": 32.5,
    "ttmEps": 51.69,
    "profitLinePrice": 1800,
    "referenceLinePrice": 2000,
    "upsideToProfitLine": 7.14,
    "upsideToReferenceLine": 19.05,
    "profitQualityScore": 90,
    "profitQualitySummary": "利润质量优良，经营性现金流充沛"
  },
  "explanations": [
    {
      "explanationType": "profit",
      "title": "营收稳健增长",
      "body": "Q1营收同比增长15%，超出市场预期",
      "impactDirection": "positive",
      "isRecurring": true,
      "confidence": 90
    },
    {
      "explanationType": "price",
      "title": "估值处于历史中枢",
      "body": "当前PE 32.5x处于近3年合理区间",
      "impactDirection": "neutral",
      "confidence": 80
    }
  ]
}
```

## 字段说明

### Company 字段

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| symbol | string | ✅ | 股票代码 |
| market | string | ✅ | 市场标识：us/hk/a/cn |
| name | string | ✅ | 公司全称 |
| exchange | string | ❌ | 交易所代码，如 SH/SZ/NYSE |
| currency | string | ❌ | 货币代码：USD/CNY/HKD |
| sector | string | ❌ | 行业板块 |
| industry | string | ❌ | 细分行业 |
| country | string | ❌ | 国家/地区 |

### PageEntry 字段

> **重要说明**：`CompanyPageEntry` 表已废弃。以下字段实际存储在 `Company` 表上。API 保留 `pageEntry` 作为独立输入段，写入时会合并到 `Company` 记录。

如果不写入 `pageEntry` 字段，公司将不会在 PE 页面侧边栏显示（`visible` 默认为 `true`，但 `entryType` 默认为 `manual`，建议显式设置）。

| 字段名 | 类型 | 必需 | Company 表对应字段 | 说明 |
|--------|------|------|-------------------|------|
| entryType | string | ✅ | `company.entryType` | 入口类型 |
| note | string | ❌ | `company.entryNote` | 备注说明 |
| sortOrder | number | ❌ | `company.sortOrder` | 排序顺序，数字越小越靠前 |
| visible | boolean | ❌ | `company.visible` | 是否在页面显示，默认 true |

**entryType 可选值**:
- `manual` - 手动添加
- `ai-generated` - AI 生成
- `analysis` - 分析报告
- `research` - 研报

### Exploration 字段

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| title | string | ✅ | 分析报告标题 |
| summary | string | ✅ | 简要总结（会显示在卡片上） |
| thesis | string | ❌ | 投资论点 |
| catalysts | string | ❌ | 催化剂/利好因素 |
| risks | string | ❌ | 风险因素 |
| tags | string[] | ❌ | 标签数组 |
| score | number | ❌ | 评分 1-100（Agent 综合判断） |
| confidence | number | ❌ | 分析置信度 1-100 |
| sourceUrls | string[] | ❌ | 数据来源链接 |
| visibility | string | ❌ | 可见性：draft/published/archived |

### Valuation 字段

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| asOfDate | string/Date | ✅ | 数据日期 |
| price | number | ❌ | 当前股价 |
| ttmPe | number | ❌ | TTM 市盈率 |
| ttmEps | number | ❌ | TTM 每股收益 |
| profitLinePrice | number | ❌ | 利润线价格 |
| referenceLinePrice | number | ❌ | 参考线价格 |
| upsideToProfitLine | number | ❌ | 到利润线涨幅(%) |
| upsideToReferenceLine | number | ❌ | 到参考线涨幅(%) |
| profitQualityScore | number | ❌ | 利润质量评分 1-100 |
| profitQualitySummary | string | ❌ | 利润质量说明 |

### Explanation 字段

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| explanationType | string | ✅ | 解释类型 |
| title | string | ✅ | 说明标题 |
| body | string | ✅ | 详细说明（**必须包含数据支撑和深度分析，禁止简单总结**） |
| impactDirection | string | ❌ | 影响方向：positive/neutral/negative |
| isRecurring | boolean | ❌ | 是否经常性收支 |
| confidence | number | ❌ | 置信度 1-100 |

**explanationType 可选值**:
- `profit` - 利润质量分析（**必须写入，用于利润质量判断**）
- `price` - 股价驱动因素分析
- `valuation` - 估值水平分析
- `business` - 业务/行业分析

#### Explanation body 内容规范（重要！）

**禁止**写入简单的一句话总结，如：
- ❌ "Q1营收同比增长15%，超出市场预期"
- ❌ "当前PE 32.5x处于近3年合理区间"
- ❌ "利润增长稳健"

**必须**提供有数据支撑的详细分析，每条 explanation 的 `body` 应包含以下要素：

**1. 现状描述（数据支撑）**
- 具体财务数据：营收、利润、毛利率、净利率等
- 与历史同期对比：同比变化、环比变化
- 与行业平均/竞争对手对比

**2. 变化趋势分析**
- 过去 3-5 年的变化轨迹
- 增长加速还是放缓
- 季节性因素或周期性影响

**3. 原因分析（为什么）**
- 驱动增长/下降的核心因素
- 一次性因素 vs 持续性因素
- 外部环境变化（政策、市场、竞争）

**4. 未来展望（前瞻性）**
- 未来 1-2 个季度的预期
- 潜在风险或催化剂
- 对估值的影响判断

**示例（合格的 profit explanation）**:
```json
{
  "explanationType": "profit",
  "title": "利润质量分析：经常性业务驱动增长，非经常性收益占比可控",
  "body": "2026年Q1公司实现净利润45.2亿元，同比增长18.3%，环比增长5.2%。从利润结构来看，经营性净利润（扣非）为42.8亿元，同比增长20.1%，占净利润的94.7%，说明利润主要由经常性业务驱动。\n\n毛利率方面，Q1毛利率为38.5%，同比提升1.2个百分点，主要受益于产品结构优化和原材料成本下降。净利率为15.2%，同比提升0.8个百分点。\n\n需要关注的是，Q1确认了2.4亿元的资产处置收益（占净利润5.3%），这是一笔非经常性收益。扣除该笔收益后，净利润同比增长仍达15.8%，增长质量较高。\n\n展望未来，公司核心业务的盈利能力仍在提升通道中。但需警惕原材料价格波动和竞争加剧对毛利率的潜在压力。预计全年经常性净利润增速可维持在15-18%区间。",
  "impactDirection": "positive",
  "isRecurring": true,
  "confidence": 85
}
```

**示例（合格的 price explanation）**:
```json
{
  "explanationType": "price",
  "title": "股价分析：估值修复至历史中枢，业绩支撑股价上行",
  "body": "当前股价185.5元，对应TTM PE 28.5x。从历史估值来看，近3年PE区间为22x-35x，当前处于52%分位，属于合理中枢水平。\n\n与同业对比，行业平均PE为25x，公司估值溢价约14%，主要反映其龙头地位和更高的ROE（22% vs 行业平均15%）。\n\n股价近期上涨主要受Q1业绩超预期驱动（净利润同比+18.3%），但市场已部分消化该利好。后续股价走势将取决于：1）Q2业绩能否维持高增长；2）新产品发布的市场反响；3）宏观政策对行业的支持力度。\n\n从技术面看，股价已突破前期震荡区间上沿，成交量配合良好，短期趋势偏强。但需注意28x以上PE区间的历史阻力。",
  "impactDirection": "neutral",
  "confidence": 75
}
```

**示例（合格的 business explanation）**:
```json
{
  "explanationType": "business",
  "title": "业务分析：核心业务稳健，新增长点逐步兑现",
  "body": "公司主营业务为消费电子，Q1营收占比78%，同比增长12%。该业务增长主要受益于：1）海外市场需求回暖，出口订单同比增长25%；2）国内消费升级趋势延续，高端产品占比提升至35%（去年同期28%）。\n\n新业务方面，云服务收入Q1达8.5亿元，同比增长65%，占总营收比重从去年的5%提升至8%。虽然增速亮眼，但绝对规模仍较小，对整体业绩贡献有限。该业务目前处于投入期，毛利率仅15%，低于公司整体水平。\n\n行业竞争格局方面，公司在国内市场份额为32%，稳居第一，但与第二名（28%）的差距正在缩小。主要竞争对手近期加大了营销投入和价格战力度，对公司市场份额构成一定压力。\n\n从行业趋势看，AI技术正在重塑消费电子产品形态，公司已投入15亿元用于AI研发，预计下半年将推出首款AI原生产品。这将是未来2-3年最重要的增长催化剂，但商业化进度和用户体验仍存在不确定性。",
  "impactDirection": "positive",
  "confidence": 70
}
```

## 写入优先级

外部 Agent 在分析市场数据后，应该按照以下优先级写入数据：

如果目标公司已经在数据库中存在，且以下内容没有明显问题，可以不写入、不更新：

- `Company` 基础信息正确
- `visible`、`entryType` 等 PE 页面展示字段合理
- 已有 published `exploration` 能表达清晰投资观点
- 已有 `valuation` 和 `explanations` 能支撑 PE 页面展示

如果只是缺某一类数据，应只补缺失项，不需要覆盖已有质量合格的分析。

### P0 - 必须写入

```json
{
  "company": { ... },
  "pageEntry": { ... }
}
```

> `pageEntry` 的字段会合并写入 `Company` 记录，确保公司在 PE 页面可见。

### P1 - 强烈建议写入

```json
{
  "valuation": { ... },
  "exploration": { ... }
}
```

### P2 - 增强体验

```json
{
  "explanations": [ ... ]
}
```

## 验证写入结果

写入数据后，可以通过以下 API 验证数据是否正确，以及是否能在 PE 页面展示：

**接口地址**: `GET /api/market-analysis/verify?symbol={symbol}&market={market}`

### 验证响应示例

```json
{
  "success": true,
  "pePageVisible": true,
  "company": {
    "id": "cmabc123",
    "symbol": "AAPL",
    "market": "us",
    "name": "Apple Inc."
  },
  "dataStatus": {
    "hasVisibleCompany": true,
    "hasPublishedExploration": true,
    "hasValuation": true,
    "hasExplanations": true,
    "explorationsCount": 1,
    "valuationsCount": 1,
    "explanationsCount": 2
  },
  "pePagePreview": {
    "title": "Apple Inc.",
    "entryType": "ai-generated",
    "metrics": {
      "asOfDate": "2026-05-08",
      "price": 185.5,
      "ttmEps": 6.5,
      "ttmPe": 28.5,
      "profitLinePrice": 195.0,
      "referenceLinePrice": 260.0,
      "upsideToProfitLine": 5.12,
      "upsideToReferenceLine": 40.16
    },
    "exploration": {
      "summary": "苹果是全球领先的科技公司...",
      "thesis": "长期来看，苹果的品牌护城河...",
      "score": 85
    },
    "tags": ["科技股", "长期投资"],
    "profitQuality": "正常",
    "primaryExplanation": {
      "explanationType": "profit",
      "title": "服务收入增长强劲",
      "body": "服务收入同比增长 15%..."
    }
  },
  "checkList": {
    "canShowInSidebar": true,
    "canShowValuationCard": true,
    "canShowExploration": true,
    "canShowExplanations": true,
    "fullyComplete": true
  }
}
```

### 检查清单说明

| 检查项 | 条件 | PE 页面效果 |
|--------|------|------------|
| canShowInSidebar | hasVisibleCompany（company.visible = true） | 公司出现在左侧列表 |
| canShowValuationCard | hasVisibleCompany + hasValuation | 显示估值指标 |
| canShowExploration | hasVisibleCompany + hasPublishedExploration | 显示分析摘要和评分 |
| canShowExplanations | hasVisibleCompany + hasExplanations | 显示利润质量分析 |
| fullyComplete | 以上全部满足 | 完整展示所有信息 |

## 常见问题

### Q: 分析后只写了 ShareInfo 没有写 Company 会怎样？

A: 数据不会在 PE 页面展示。ShareInfo 是旧的股票信息表，Company 才是 PE 页面展示数据的来源。页面展示相关字段（entryType、entryNote、sortOrder、visible）也存储在 Company 表上。

### Q: 为什么写了 Company 但没有在 PE 页面看到？

A: 需要确认 `company.visible = true`。只有 `visible` 为 `true` 的公司才会出现在 PE 页面的左侧列表中。另外，建议同时写入 `pageEntry` 段来显式设置 `entryType`，否则默认为 `manual`。

### Q: 如何更新已有的分析？

A: 使用**相同的 runId** 重新调用写入 API，系统会自动更新该 runId 下的 Exploration、Valuation、Explanation 记录，不会创建重复数据。

### Q: 默认分析范围是数据库里的股票吗？

A: 不是。默认覆盖范围应来自外部市场股票池，数据库只用于记录已写入结果、去重和判断是否需要更新。数据库中已有且无明显问题的公司可以跳过；外部市场中尚未入库的公司，完成分析后应通过写入 API 创建 `Company` 并写入结果。

### Q: 数据库中已有公司是否必须重写？

A: 不必须。只有在数据错误、关键字段缺失、分析质量不足、观点过期或需要刷新估值时才更新。已有内容质量合格时，应避免无意义覆盖。

### Q: 如何删除错误的写入？

A: 目前 API 不支持删除操作，需要通过数据库直接操作或扩展 API。

### Q: visibility 字段的作用？

A: `published` 状态的分析会显示在页面上，`draft` 仅存储不展示，`archived` 为归档状态。

## 代码调用示例

### 推荐：CLI 写入（Agent 优先使用）

Agent 完成单家公司分析后，应优先把 payload 保存为 `tmp/*.json`，再使用统一 CLI 入库。`tmp/` 已加入 `.gitignore`，临时 payload 可以保留用于复查、重试和审计，不需要每次写入后删除。

```bash
npm run market-analysis:write -- tmp/aapl-analysis.json
```

仅校验 payload，不写入数据库：

```bash
npm run market-analysis:write -- tmp/aapl-analysis.json --dry-run
```

跳过写入后的本地验证：

```bash
npm run market-analysis:write -- tmp/aapl-analysis.json --no-verify
```

CLI 使用与 `POST /api/market-analysis/write` 相同的数据结构，底层调用 `writeMarketAnalysisCrossMarket`，因此仍然遵循 `runId` 幂等规则。常规 Agent 不应再为每家公司新增 `scripts/write-xxx-analysis.ts`；只有一次性迁移或调试场景才允许使用专门脚本。

CLI 会做以下基础校验：

1. `runId` 必须存在
2. `company.symbol`、`company.market`、`company.name` 必须存在
3. `company.market` 必须是 `us`、`hk`、`a`、`cn` 之一
4. `score`、`confidence`、`profitQualityScore` 必须在 0-100 范围内
5. 同一个 payload 中 `explanations[].explanationType` 不能重复，因为当前幂等更新以 `runId + explanationType` 为键

### TypeScript/JavaScript

```typescript
const runId = `analysis-aapl-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-001`

const response = await fetch('/api/market-analysis/write', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    runId,  // 必需！用于幂等写入
    company: {
      symbol: 'AAPL',
      market: 'us',
      name: 'Apple Inc.',
      sector: 'Technology',
    },
    pageEntry: {
      entryType: 'ai-generated',
      note: 'Apple 分析',
    },
    exploration: {
      title: 'Apple 投资分析',
      summary: '苹果是全球领先的科技公司...',
      score: 85,
      tags: ['科技股', '长期投资'],
    },
    valuation: {
      asOfDate: new Date().toISOString(),
      price: 185.5,
      ttmPe: 28.5,
    },
  }),
})

const result = await response.json()
console.log(result)

// 验证写入结果
const verifyResponse = await fetch(
  `/api/market-analysis/verify?symbol=AAPL&market=us&runId=${runId}`
)
const verifyResult = await verifyResponse.json()
console.log(verifyResult.checkList.fullyComplete)  // true 表示完整写入
```

### Python

```python
import requests
import json
from datetime import datetime

# 生成 runId
today = datetime.now().strftime('%Y%m%d')
run_id = f"analysis-aapl-{today}-001"

data = {
    "runId": run_id,  # 必需！用于幂等写入
    "company": {
        "symbol": "AAPL",
        "market": "us",
        "name": "Apple Inc."
    },
    "pageEntry": {
        "entryType": "ai-generated"
    },
    "valuation": {
        "asOfDate": "2026-05-08",
        "price": 185.5,
        "ttmPe": 28.5
    }
}

response = requests.post(
    "https://your-domain.com/api/market-analysis/write",
    json=data,
    headers={"Content-Type": "application/json"}
)

print(response.json())

# 验证写入结果
verify_response = requests.get(
    f"https://your-domain.com/api/market-analysis/verify?symbol=AAPL&market=us&runId={run_id}"
)
verify_result = verify_response.json()
print(verify_result["checkList"]["fullyComplete"])  # True 表示完整写入
```

## 数据验证规则

1. **symbol** 不能为空，且同一 market 下应唯一
2. **market** 必须是有效值：us, hk, a, cn
3. **asOfDate** 必须是有效的日期格式
4. **score** 和 **confidence** 建议在 0-100 范围内
5. **pageEntry.entryType** 建议使用预定义值

## 错误处理

API 返回的错误格式：

```json
{
  "success": false,
  "error": "错误信息描述"
}
```

常见错误：
- 400: 缺少必需字段
- 500: 服务器内部错误

## 联系与支持

如有问题或需要扩展 API 功能，请联系开发团队。
