export type Market = 'us' | 'cn' | 'hk'

export type NormalizedMarketSymbol =
  | {
      market: 'us'
      symbol: string
    }
  | {
      market: 'cn' | 'hk'
      symbol: string
      eastmoneyCode: string
      priceSecid: string
      currency: 'CNY' | 'HKD'
    }

export type EpsRow = {
  date: string
  quarter: string
  eps: number
  ttmEps?: number
  name?: string
  currency?: string
  shareholderEquity?: number | null
  liabilities?: number | null
  cash?: number | null
}

export type DailyPrice = {
  date: string
  close: number
}

export type QuarterPoint = {
  date: string
  quarter: string
  eps: number
  ttmEps: number | null
  price: number | null
  ttmPe: number | null
  shareholderEquity: number | null
  liabilities: number | null
  cash: number | null
}

export type LatestDailyPrice = {
  date: string
  price: number
}

export function normalizeMarketSymbol(input: string): NormalizedMarketSymbol {
  const raw = input.trim().toUpperCase()
  const compact = raw.replace(/\s+/g, '')

  const hkMatch =
    compact.match(/^(\d{1,5})\.HK$/) ||
    compact.match(/^HK[:.]?(\d{1,5})$/) ||
    compact.match(/^(\d{1,5})$/)
  if (hkMatch) {
    const symbol = hkMatch[1].padStart(5, '0')
    return {
      market: 'hk',
      symbol,
      eastmoneyCode: symbol,
      priceSecid: `116.${symbol}`,
      currency: 'HKD',
    }
  }

  const cnMatch =
    compact.match(/^(\d{6})\.(SH|SZ)$/) ||
    compact.match(/^(SH|SZ)(\d{6})$/) ||
    compact.match(/^(\d{6})$/)

  if (cnMatch) {
    const symbol = cnMatch[1]?.length === 6 ? cnMatch[1] : cnMatch[2]
    const explicitExchange =
      cnMatch[2]?.length === 2
        ? cnMatch[2]
        : cnMatch[1]?.length === 2
          ? cnMatch[1]
          : undefined
    const exchange = explicitExchange || (symbol.startsWith('6') ? 'SH' : 'SZ')
    const marketCode = exchange === 'SH' ? '1' : '0'

    return {
      market: 'cn',
      symbol,
      eastmoneyCode: `${symbol}.${exchange}`,
      priceSecid: `${marketCode}.${symbol}`,
      currency: 'CNY',
    }
  }

  return {
    market: 'us',
    symbol: compact.replace(/\.US$/, ''),
  }
}

function toDateString(value: unknown) {
  if (typeof value !== 'string') return null
  const date = value.slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null
}

function quarterLabel(date: string) {
  const value = new Date(`${date}T00:00:00Z`)
  const quarter = Math.floor(value.getUTCMonth() / 3) + 1
  return `${value.getUTCFullYear()} Q${quarter}`
}

export function toNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function pickEastmoneyEpsRows(
  rows: Array<Record<string, unknown>>,
  epsField: string,
  ttmField?: string,
) {
  return rows
    .map((row): EpsRow | null => {
      const date =
        toDateString(row.REPORT_DATE) ||
        toDateString(row.STD_REPORT_DATE) ||
        toDateString(row.END_DATE)
      const eps = toNumber(row[epsField])
      if (!date || eps === null) return null

      const ttmValue = ttmField ? toNumber(row[ttmField]) : null
      const shareholderEquity = toNumber(
        row.TOTAL_PARENT_EQUITY ?? row.PARENT_EQUITY ?? row.TOTAL_EQUITY,
      )
      const liabilities = toNumber(row.TOTAL_LIABILITIES ?? row.TOTAL_LIAB)
      const cash = toNumber(
        row.MONETARYFUNDS ??
          row.CASH_CASH_EQUIVALENTS ??
          row.CASH_AND_CASH_EQUIVALENTS,
      )
      return {
        date,
        quarter: quarterLabel(date),
        eps: Number(eps.toFixed(4)),
        ...(ttmValue === null
          ? {}
          : { ttmEps: Number(ttmValue.toFixed(4)) }),
        ...(typeof row.SECURITY_NAME_ABBR === 'string'
          ? { name: row.SECURITY_NAME_ABBR }
          : {}),
        ...(typeof row.CURRENCY === 'string' ? { currency: row.CURRENCY } : {}),
        shareholderEquity,
        liabilities,
        cash,
      } satisfies EpsRow
    })
    .filter((row): row is EpsRow => Boolean(row))
    .sort((a, b) => a.date.localeCompare(b.date))
}

export function priceAtOrBefore(prices: DailyPrice[], date: string) {
  let selected: number | null = null
  for (const price of prices) {
    if (price.date > date) break
    selected = price.close
  }
  return selected === null ? null : Number(selected.toFixed(2))
}

export function latestDailyPrice(prices: DailyPrice[]): LatestDailyPrice | null {
  const latest = prices.reduce<DailyPrice | null>((selected, price) => {
    if (!selected || price.date > selected.date) return price
    return selected
  }, null)

  if (!latest) return null

  return {
    date: latest.date,
    price: Number(latest.close.toFixed(2)),
  }
}

export function buildQuarterPoints(
  quarters: EpsRow[],
  prices: DailyPrice[],
): QuarterPoint[] {
  return quarters.map((quarter, index) => {
    const ttmEps =
      quarter.ttmEps !== undefined
        ? quarter.ttmEps
        : index >= 3
          ? Number(
              quarters
                .slice(index - 3, index + 1)
                .reduce((total, item) => total + item.eps, 0)
                .toFixed(4),
            )
          : null
    const price = priceAtOrBefore(prices, quarter.date)
    const ttmPe =
      price !== null && ttmEps !== null && ttmEps > 0
        ? Number((price / ttmEps).toFixed(2))
        : null

    return {
      date: quarter.date,
      quarter: quarter.quarter,
      eps: quarter.eps,
      ttmEps,
      price,
      ttmPe,
      shareholderEquity: quarter.shareholderEquity ?? null,
      liabilities: quarter.liabilities ?? null,
      cash: quarter.cash ?? null,
    }
  })
}

export function parseEastmoneyKlines(klines: string[] | undefined): DailyPrice[] {
  if (!klines) return []
  return klines
    .map((line) => {
      const [date, , close] = line.split(',')
      const closeValue = Number(close)
      if (!date || !Number.isFinite(closeValue)) return null
      return {
        date,
        close: closeValue,
      }
    })
    .filter((row): row is DailyPrice => Boolean(row))
    .sort((a, b) => a.date.localeCompare(b.date))
}
