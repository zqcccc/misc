import * as assert from 'node:assert/strict'
import { buildChartSource, type ChartBasePoint } from '../app/pe/chart-data'

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
