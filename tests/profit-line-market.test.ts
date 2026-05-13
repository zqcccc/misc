import * as assert from 'node:assert/strict'
import {
  adjustUsEpsForShareClass,
  buildQuarterPoints,
  buildQuarterlyEpsRows,
  isQuarterDataStale,
  latestDailyPrice,
  normalizeMarketSymbol,
  normalizeYahooDividendEvents,
  pickSecAnnualEpsRows,
  pickSecFilingEpsRows,
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

assert.deepEqual(normalizeMarketSymbol('brk.b'), {
  market: 'us',
  symbol: 'BRK-B',
})

assert.deepEqual(
  adjustUsEpsForShareClass('BRK-B', [
    { date: '2024-03-31', quarter: '2024 Q1', eps: 1500 },
    { date: '2024-06-30', quarter: '2024 Q2', eps: 750, ttmEps: 3000 },
  ]),
  [
    { date: '2024-03-31', quarter: '2024 Q1', eps: 1 },
    { date: '2024-06-30', quarter: '2024 Q2', eps: 0.5, ttmEps: 2 },
  ],
)

assert.deepEqual(
  pickSecAnnualEpsRows({
    facts: {
      'us-gaap': {
        EarningsPerShareDiluted: {
          units: {
            'USD/shares': [
              {
                form: '6-K',
                start: '2024-01-01',
                end: '2024-09-30',
                val: 1.8,
              },
              {
                form: '20-F',
                start: '2023-01-01',
                end: '2023-12-31',
                val: 1.45,
                frame: 'CY2023',
                filed: '2024-04-25',
              },
              {
                form: '20-F',
                start: '2024-01-01',
                end: '2024-12-31',
                val: 2.6,
                frame: 'CY2024',
                filed: '2025-04-28',
              },
            ],
          },
        },
      },
    },
  }),
  [
    { date: '2023-12-31', quarter: '2023 FY', eps: 1.45, ttmEps: 1.45 },
    { date: '2024-12-31', quarter: '2024 FY', eps: 2.6, ttmEps: 2.6 },
  ],
)

assert.deepEqual(
  pickSecAnnualEpsRows({
    facts: {
      'us-gaap': {
        EarningsPerShareDiluted: {
          units: {
            'USD/shares': [
              {
                form: '6-K',
                start: '2025-04-01',
                end: '2025-06-30',
                val: 2.44,
                frame: 'CY2025Q2',
              },
            ],
          },
        },
        EarningsPerShareBasic: {
          units: {
            'USD/shares': [
              {
                form: '20-F',
                start: '2024-01-01',
                end: '2024-12-31',
                val: 8.69,
                frame: 'CY2024',
                filed: '2025-03-27',
              },
              {
                form: '20-F',
                start: '2025-01-01',
                end: '2025-12-31',
                val: 3.35,
                frame: 'CY2025',
                filed: '2026-03-26',
              },
            ],
          },
        },
      },
    },
  }),
  [
    { date: '2024-12-31', quarter: '2024 FY', eps: 8.69, ttmEps: 8.69 },
    { date: '2025-12-31', quarter: '2025 FY', eps: 3.35, ttmEps: 3.35 },
  ],
)

assert.deepEqual(
  pickSecFilingEpsRows(
    `
    <xbrl>
      <context id="a">
        <period><startDate>2026-01-01</startDate><endDate>2026-03-31</endDate></period>
        <segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">brka:EquivalentClassAMember</xbrldi:explicitMember></segment>
      </context>
      <context id="b">
        <period><startDate>2026-01-01</startDate><endDate>2026-03-31</endDate></period>
        <segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">brka:EquivalentClassBMember</xbrldi:explicitMember></segment>
      </context>
      <us-gaap:EarningsPerShareBasic contextRef="a" unitRef="usdPerShare">7027</us-gaap:EarningsPerShareBasic>
      <us-gaap:EarningsPerShareBasic contextRef="b" unitRef="usdPerShare">4.68</us-gaap:EarningsPerShareBasic>
    </xbrl>
    `,
    'brka:EquivalentClassBMember',
  ),
  [{ date: '2026-03-31', quarter: '2026 Q1', eps: 4.68 }],
)

assert.deepEqual(
  buildQuarterlyEpsRows(
    [
      { date: '2025-03-31', quarter: '2025 Q1', eps: 2.13 },
      { date: '2025-06-30', quarter: '2025 Q2', eps: 5.73 },
      { date: '2025-09-30', quarter: '2025 Q3', eps: 14.28 },
      { date: '2026-03-31', quarter: '2026 Q1', eps: 4.68 },
    ],
    [{ date: '2025-12-31', quarter: '2025 Q4', eps: 31.04 }],
  ),
  [
    { date: '2025-03-31', quarter: '2025 Q1', eps: 2.13 },
    { date: '2025-06-30', quarter: '2025 Q2', eps: 5.73 },
    { date: '2025-09-30', quarter: '2025 Q3', eps: 14.28 },
    { date: '2025-12-31', quarter: '2025 Q4', eps: 8.9 },
    { date: '2026-03-31', quarter: '2026 Q1', eps: 4.68 },
  ],
)

assert.equal(
  isQuarterDataStale(
    [{ date: '2024-12-31' }],
    new Date('2026-05-09T00:00:00Z'),
  ),
  false,
)
assert.equal(
  isQuarterDataStale(
    [{ date: '2013-12-31' }],
    new Date('2026-05-09T00:00:00Z'),
  ),
  true,
)

const quarterlyRows = pickEastmoneyEpsRows(
  [
    {
      REPORT_DATE: '2024-03-31 00:00:00',
      EPSJB: 1,
      TOTAL_PARENT_EQUITY: 100,
      TOTAL_LIABILITIES: 40,
      MONETARYFUNDS: 25,
    },
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
assert.equal(quarterlyRows[0].shareholderEquity, 100)
assert.equal(quarterlyRows[0].liabilities, 40)
assert.equal(quarterlyRows[0].cash, 25)

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
assert.equal(points[0].shareholderEquity, 100)
assert.equal(points[0].liabilities, 40)
assert.equal(points[0].cash, 25)

assert.deepEqual(
  latestDailyPrice([
    { date: '2025-03-31', close: 50 },
    { date: '2026-05-06', close: 61.234 },
    { date: '2026-05-02', close: 59 },
  ]),
  { date: '2026-05-06', price: 61.23 },
)

assert.deepEqual(
  normalizeYahooDividendEvents({
    '1711929600': { date: 1711929600, amount: 0.5 },
    ignored: { date: 1719878400, amount: 0 },
    '1719878400': { date: 1719878400, amount: 0.1256 },
  }),
  [
    { date: '2024-04-01', amount: 0.5 },
    { date: '2024-07-02', amount: 0.1256 },
  ],
)
