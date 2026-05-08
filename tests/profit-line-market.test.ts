import * as assert from 'node:assert/strict'
import {
  buildQuarterPoints,
  latestDailyPrice,
  normalizeMarketSymbol,
  pickEastmoneyEpsRows,
} from '../app/api/profit-line/market-data'

assert.deepEqual(normalizeMarketSymbol('600519'), {
  market: 'cn',
  symbol: '600519',
  eastmoneyCode: '600519.SH',
  priceSecid: '1.600519',
  currency: 'CNY',
})

assert.deepEqual(normalizeMarketSymbol('000001'), {
  market: 'cn',
  symbol: '000001',
  eastmoneyCode: '000001.SZ',
  priceSecid: '0.000001',
  currency: 'CNY',
})

assert.deepEqual(normalizeMarketSymbol('00700'), {
  market: 'hk',
  symbol: '00700',
  eastmoneyCode: '00700',
  priceSecid: '116.00700',
  currency: 'HKD',
})

assert.deepEqual(normalizeMarketSymbol('AAPL'), {
  market: 'us',
  symbol: 'AAPL',
})

const quarterlyRows = pickEastmoneyEpsRows(
  [
    { REPORT_DATE: '2024-03-31 00:00:00', EPSJB: 1 },
    { REPORT_DATE: '2024-06-30 00:00:00', EPSJB: 2 },
    { REPORT_DATE: '2024-09-30 00:00:00', EPSJB: 3 },
    { REPORT_DATE: '2024-12-31 00:00:00', EPSJB: 4 },
    { REPORT_DATE: '2025-03-31 00:00:00', EPSJB: 5 },
  ],
  'EPSJB',
)

assert.equal(quarterlyRows.length, 5)
assert.equal(quarterlyRows[0].date, '2024-03-31')
assert.equal(quarterlyRows[0].eps, 1)

const points = buildQuarterPoints(
  quarterlyRows,
  [
    { date: '2024-03-29', close: 10 },
    { date: '2024-06-28', close: 20 },
    { date: '2024-09-30', close: 30 },
    { date: '2024-12-31', close: 40 },
    { date: '2025-03-31', close: 50 },
  ],
)

assert.equal(points[2].ttmEps, null)
assert.equal(points[3].ttmEps, 10)
assert.equal(points[4].ttmEps, 14)
assert.equal(points[4].ttmPe, 3.57)

assert.deepEqual(
  latestDailyPrice([
    { date: '2025-03-31', close: 50 },
    { date: '2026-05-06', close: 61.234 },
    { date: '2026-05-02', close: 59 },
  ]),
  { date: '2026-05-06', price: 61.23 },
)
