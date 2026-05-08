export type ChartBasePoint = {
  date: string
  quarter: string
  eps: number
  ttmEps: number | null
  price: number | null
  ttmPe: number | null
  profitLine: number | null
  deviation: number | null
  alert: boolean
  shareholderEquity?: number | null
  liabilities?: number | null
  cash?: number | null
}

export type LatestPricePoint = {
  date: string
  price: number
} | null | undefined

export type ChartPoint = ChartBasePoint & {
  referenceLine: number | null
  isLatestPrice: boolean
  displayLabel: string
  epsSourceQuarter?: string
}

function linePrice(ttmEps: number | null, multiple: number) {
  return ttmEps === null ? null : Number((ttmEps * multiple).toFixed(2))
}

export function buildChartSource(
  points: ChartBasePoint[],
  latestPrice: LatestPricePoint,
  profitMultiple: number,
  referenceMultiple: number,
): ChartPoint[] {
  const source = points.map((point) => ({
    ...point,
    referenceLine: linePrice(point.ttmEps, referenceMultiple),
    isLatestPrice: false,
    displayLabel: point.quarter,
  }))

  const latestQuarterPoint = [...source]
    .reverse()
    .find((point) => point.price !== null && point.ttmEps !== null)

  if (!latestPrice || !latestQuarterPoint || latestPrice.date <= latestQuarterPoint.date) {
    return source
  }

  const profitLine = linePrice(latestQuarterPoint.ttmEps, profitMultiple)
  const referenceLine = linePrice(latestQuarterPoint.ttmEps, referenceMultiple)
  const ttmPe =
    latestQuarterPoint.ttmEps !== null && latestQuarterPoint.ttmEps > 0
      ? Number((latestPrice.price / latestQuarterPoint.ttmEps).toFixed(2))
      : null
  const deviation =
    profitLine !== null && profitLine !== 0
      ? ((latestPrice.price - profitLine) / profitLine) * 100
      : null

  return [
    ...source,
    {
      ...latestQuarterPoint,
      date: latestPrice.date,
      quarter: `最新价 ${latestPrice.date}`,
      price: latestPrice.price,
      ttmPe,
      profitLine,
      referenceLine,
      deviation,
      alert: profitLine !== null && latestPrice.price < profitLine,
      shareholderEquity: null,
      liabilities: null,
      cash: null,
      isLatestPrice: true,
      displayLabel: latestPrice.date,
      epsSourceQuarter: latestQuarterPoint.quarter,
    },
  ]
}
