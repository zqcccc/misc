import { CompanyValuationCard } from './types'

export const currencyFormatter = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return value.toFixed(digits)
}

export function pct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

export function qualityColor(value: CompanyValuationCard['profitQuality'] | undefined) {
  if (value === '需调整') return 'text-rose-500 dark:text-rose-400'
  if (value === '正常') return 'text-emerald-600 dark:text-emerald-400'
  return 'text-amber-700 dark:text-amber-400'
}
