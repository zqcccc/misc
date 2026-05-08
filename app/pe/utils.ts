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

function normalizeSearchValue(value: string) {
  return value.trim().toUpperCase()
}

function stripMarketSuffix(value: string) {
  return value.replace(/\.(SH|SZ|HK)$/i, '')
}

export function resolveCompanySearchSymbol(
  query: string,
  entries: Pick<CompanyValuationCard, 'symbol' | 'title' | 'tags'>[],
) {
  const cleanQuery = normalizeSearchValue(query)
  if (!cleanQuery) return ''

  const queryBase = stripMarketSuffix(cleanQuery).replace(/^0+/, '')
  const matchingEntry = entries.find((entry) => {
    const symbol = normalizeSearchValue(entry.symbol)
    const symbolBase = stripMarketSuffix(symbol).replace(/^0+/, '')
    const title = entry.title.trim().toUpperCase()
    const tags = entry.tags.map(normalizeSearchValue)

    return (
      symbol === cleanQuery ||
      symbolBase === queryBase ||
      title === cleanQuery ||
      tags.includes(cleanQuery)
    )
  })

  return matchingEntry?.symbol || cleanQuery
}
