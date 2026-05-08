import { ProfitPoint, PeriodType, PeriodStats } from './types'

export function getPreparedPoints(data: { points: ProfitPoint[] } | null, profitMultiple: number) {
  if (!data) return []
  return data.points.map((point) => {
    const profitLine =
      point.ttmEps === null ? null : Number((point.ttmEps * profitMultiple).toFixed(2))
    const deviation =
      point.price !== null && profitLine !== null && profitLine !== 0
        ? ((point.price - profitLine) / profitLine) * 100
        : null

    return {
      ...point,
      profitLine,
      deviation,
      alert: point.price !== null && profitLine !== null && point.price < profitLine,
    }
  })
}

export function calculatePePercentile(
  points: ProfitPoint[],
  currentPe: number | null,
  period: PeriodType = 'all',
): number | null {
  if (currentPe === null || points.length === 0) return null

  const now = new Date()
  const cutoffDate = period === 'all'
    ? new Date(0)
    : new Date(now.getFullYear() - period, now.getMonth(), now.getDate())

  const validPes = points
    .filter((p) => {
      if (p.ttmPe === null || Number.isNaN(p.ttmPe)) return false
      const pointDate = new Date(p.date)
      return pointDate >= cutoffDate
    })
    .map((p) => p.ttmPe as number)

  if (validPes.length === 0) return null

  const countLessOrEqual = validPes.filter((pe) => pe <= currentPe).length
  return Number(((countLessOrEqual / validPes.length) * 100).toFixed(1))
}

export function calculatePeriodStats(points: ProfitPoint[], period: PeriodType): PeriodStats {
  const now = new Date()
  const cutoffDate = period === 'all'
    ? new Date(0)
    : new Date(now.getFullYear() - period, now.getMonth(), now.getDate())

  const filteredPoints = points.filter((p) => {
    if (p.ttmPe === null || Number.isNaN(p.ttmPe)) return false
    const pointDate = new Date(p.date)
    return pointDate >= cutoffDate
  })

  const validPes = filteredPoints.map((p) => p.ttmPe as number)

  if (validPes.length === 0) {
    return {
      period,
      label: period === 'all' ? '全部' : `过去${period}年`,
      avgPe: null,
      minPe: null,
      maxPe: null,
      count: 0,
    }
  }

  const avgPe = validPes.reduce((sum, pe) => sum + pe, 0) / validPes.length
  const minPe = Math.min(...validPes)
  const maxPe = Math.max(...validPes)

  return {
    period,
    label: period === 'all' ? '全部' : `过去${period}年`,
    avgPe: Number(avgPe.toFixed(2)),
    minPe: Number(minPe.toFixed(2)),
    maxPe: Number(maxPe.toFixed(2)),
    count: validPes.length,
  }
}
