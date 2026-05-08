# 市场分析数据写入规范

## 概述

本文档定义了外部 Agent 在完成市场分析后将数据写入数据库的标准流程。所有通过 Agent 分析产生的数据必须按照此规范写入，以确保数据能够正确地在 PE 页面展示。

## 数据写入流程

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

### 2. 推荐写入的数据

为了在 PE 页面提供完整的用户体验，建议同时写入：

- `valuation` - 估值快照数据
- `exploration` - 分析报告内容
- `explanations` - 估值解释说明

## API 接口

**接口地址**: `POST /api/market-analysis/write`

### 请求示例

#### 最小请求（仅必需字段）

```json
{
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
    "title": "贵州茅台分析",
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

PageEntry 是将公司添加到 PE 页面的关键！如果不写入此字段，分析结果将不会在页面上显示。

| 字段名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| entryType | string | ✅ | 入口类型 |
| title | string | ❌ | 显示标题 |
| note | string | ❌ | 备注说明 |
| sortOrder | number | ❌ | 排序顺序，数字越小越靠前 |
| visible | boolean | ❌ | 是否在页面显示，默认 true |

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
| score | number | ❌ | 评分 1-100 |
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
| body | string | ✅ | 详细说明 |
| impactDirection | string | ❌ | 影响方向：positive/neutral/negative |
| isRecurring | boolean | ❌ | 是否经常性收支 |
| confidence | number | ❌ | 置信度 1-100 |

**explanationType 可选值**:
- `price` - 股价相关
- `profit` - 利润相关
- `valuation` - 估值相关
- `business` - 业务相关

## 写入优先级

外部 Agent 在分析市场数据后，应该按照以下优先级写入数据：

### P0 - 必须写入

```json
{
  "company": { ... },
  "pageEntry": { ... }
}
```

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

## 常见问题

### Q: 分析后只写了 ShareInfo 没有写 Company 会怎样？

A: 数据不会在 PE 页面展示。ShareInfo 是旧的股票信息表，Company + PageEntry 才是 PE 页面展示数据的来源。

### Q: 如何更新已有的分析？

A: 重复调用相同 symbol + market 的写入会更新 Company 信息，但 Exploration、Valuation、Explanation 都是新增记录。如需更新，需额外逻辑。

### Q: 如何删除错误的写入？

A: 目前 API 不支持删除操作，需要通过数据库直接操作或扩展 API。

### Q: visibility 字段的作用？

A: `published` 状态的分析会显示在页面上，`draft` 仅存储不展示，`archived` 为归档状态。

## 代码调用示例

### TypeScript/JavaScript

```typescript
const response = await fetch('/api/market-analysis/write', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    company: {
      symbol: 'AAPL',
      market: 'us',
      name: 'Apple Inc.',
      sector: 'Technology',
    },
    pageEntry: {
      entryType: 'ai-generated',
      title: 'Apple 分析',
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
```

### Python

```python
import requests
import json

data = {
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
