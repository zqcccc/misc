import * as assert from 'node:assert/strict'
import {
  buildChartSource,
  buildDividendChartSource,
  type ChartBasePoint,
} from '../app/pe/chart-data'

const points: ChartBasePoint[] = [
  {
    date: '2025-09-30',
    quarter: '2025 Q3',
    eps: 1,
    ttmEps: 10,
    price: 200,
    ttmPe: 20,
    profitLine: 150,
    deviation: 33.3333,
    alert: false,
    shareholderEquity: 1000,
    liabilities: 400,
    cash: 200,
  },
  {
    date: '2025-12-31',
    quarter: '2025 Q4',
    eps: 1,
    ttmEps: 20,
    price: 600,
    ttmPe: 30,
    profitLine: 300,
    deviation: 100,
    alert: false,
    shareholderEquity: 1200,
    liabilities: 500,
    cash: 250,
  },
]

const source = buildChartSource(
  points,
  { date: '2026-05-07', price: 477.4 },
  15,
  30,
)

assert.equal(source.length, 3)
assert.deepEqual(source.at(-1), {
  date: '2026-05-07',
  quarter: '最新价 2026-05-07',
  eps: 1,
  ttmEps: 20,
  price: 477.4,
  ttmPe: 23.87,
  profitLine: 300,
  referenceLine: 600,
  deviation: 59.133333333333326,
  alert: false,
  shareholderEquity: null,
  liabilities: null,
  cash: null,
  isLatestPrice: true,
  displayLabel: '2026-05-07',
  epsSourceQuarter: '2025 Q4',
})

const sameDateSource = buildChartSource(
  points,
  { date: '2025-12-31', price: 610 },
  15,
  30,
)

assert.equal(sameDateSource.length, 2)

assert.deepEqual(
  buildDividendChartSource([
    { date: '2024-04-01', amount: 0.5 },
    { date: '2024-07-02', amount: 0.1256 },
    { date: '2025-03-20', amount: 0.33 },
  ]),
  [
    { year: '2024', amount: 0.63, count: 2 },
    { year: '2025', amount: 0.33, count: 1 },
  ],
)
