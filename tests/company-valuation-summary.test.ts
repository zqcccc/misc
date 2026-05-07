import * as assert from 'node:assert/strict'
import {
  buildCompanyValuationCard,
  parseJsonArray,
  pickPrimaryExplanation,
} from '../app/api/company-valuation/summary'

assert.deepEqual(parseJsonArray('["AI","小盘股"]'), ['AI', '小盘股'])
assert.deepEqual(parseJsonArray('bad json'), [])
assert.deepEqual(parseJsonArray(null), [])

const explanations = [
  {
    explanationType: 'price',
    title: '股价反映订单恢复',
    body: '市场正在提前反映订单恢复。',
    impactDirection: 'positive',
    isRecurring: true,
    confidence: 70,
  },
  {
    explanationType: 'profit',
    title: '利润包含一次性处置收益',
    body: '本期 EPS 被资产处置收益抬高，不能直接外推为业务增长。',
    impactDirection: 'negative',
    isRecurring: false,
    confidence: 85,
  },
] as const

assert.equal(pickPrimaryExplanation(explanations)?.title, '利润包含一次性处置收益')

const card = buildCompanyValuationCard({
  company: {
    id: 'company_1',
    symbol: '00700.HK',
    market: 'hk',
    name: '腾讯控股',
    currency: 'HKD',
  },
  entry: {
    entryType: 'discovered',
    title: null,
    note: 'AI 近期发现',
  },
  latestValuation: {
    asOfDate: new Date('2026-03-31T00:00:00.000Z'),
    price: 380,
    ttmEps: 18.2,
    ttmPe: 20.88,
    profitLinePrice: 273,
    referenceLinePrice: 546,
    upsideToProfitLine: -28.16,
    upsideToReferenceLine: 43.68,
  },
  latestExploration: {
    summary: '游戏和广告恢复，云业务利润率改善。',
    thesis: '利润质量改善但估值不低。',
    score: 78,
    tags: '["互联网","现金流"]',
  },
  explanations,
})

assert.equal(card.id, 'company_1')
assert.equal(card.symbol, '00700.HK')
assert.equal(card.title, '腾讯控股')
assert.equal(card.primaryExplanation?.title, '利润包含一次性处置收益')
assert.equal(card.profitQuality, '需调整')
assert.deepEqual(card.tags, ['互联网', '现金流'])
assert.equal(card.metrics.ttmPe, 20.88)
