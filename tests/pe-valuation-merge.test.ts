import * as assert from 'node:assert/strict'
import { mergeCompanyValuationDetail } from '../app/pe/valuation-merge'
import type { CompanyValuationCard } from '../app/pe/types'

function card(
  overrides: Partial<CompanyValuationCard> = {},
): CompanyValuationCard {
  return {
    id: 'catl',
    symbol: '300750.SZ',
    market: 'cn',
    title: '宁德时代',
    currency: 'CNY',
    entryType: 'analysis',
    entryNote: '重点观察',
    metrics: {
      asOfDate: '2026-05-08',
      price: 240,
      ttmEps: 10,
      ttmPe: 24,
      profitLinePrice: 150,
      referenceLinePrice: 300,
      upsideToProfitLine: -37.5,
      upsideToReferenceLine: 25,
    },
    exploration: {
      summary: '动力电池和储能业务仍是核心变量。',
      thesis: '估值需要同时看增长、价格压力和海外产能。',
      score: 78,
    },
    tags: ['新能源', '电池'],
    profitQuality: '正常',
    primaryExplanation: {
      explanationType: 'profit',
      title: '利润具备周期波动',
      body: '完整报告会解释动力电池价格、储能出货、海外产能利用率和费用率变化。',
      isRecurring: true,
      confidence: 80,
    },
    explanations: [
      {
        explanationType: 'profit',
        title: '利润具备周期波动',
        body: '完整报告会解释动力电池价格、储能出货、海外产能利用率和费用率变化。',
        isRecurring: true,
        confidence: 80,
      },
      {
        explanationType: 'valuation',
        title: '估值要结合成长兑现',
        body: '长期估值取决于海外客户、储能增速和行业价格竞争格局，而不是单季度 PE。',
        isRecurring: true,
        confidence: 75,
      },
    ],
    ...overrides,
  }
}

const richCurrent = card()
const shortDetail = card({
  entryType: 'manual',
  entryNote: null,
  metrics: {
    ...richCurrent.metrics,
    price: 250,
    ttmPe: 25,
  },
  exploration: {
    summary: '电池龙头。',
    thesis: '关注增长。',
    score: 70,
  },
  profitQuality: '待确认',
  primaryExplanation: {
    explanationType: 'business',
    title: '业务简述',
    body: '电池龙头。',
    confidence: 60,
  },
  explanations: [
    {
      explanationType: 'business',
      title: '业务简述',
      body: '电池龙头。',
      confidence: 60,
    },
  ],
})

const merged = mergeCompanyValuationDetail(richCurrent, shortDetail)

assert.equal(merged.metrics.price, 250)
assert.equal(merged.metrics.ttmPe, 25)
assert.equal(merged.entryType, 'analysis')
assert.equal(merged.entryNote, '重点观察')
assert.equal(merged.profitQuality, '正常')
assert.equal(merged.explanations.length, 2)
assert.equal(merged.primaryExplanation?.title, '利润具备周期波动')
assert.equal(merged.exploration.summary, '动力电池和储能业务仍是核心变量。')

const otherCompany = card({ id: 'tencent', symbol: '00700.HK', title: '腾讯控股' })
assert.equal(mergeCompanyValuationDetail(richCurrent, otherCompany).symbol, '00700.HK')
