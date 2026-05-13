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

export type DividendEvent = {
  date: string
  amount: number
}

const US_SHARE_CLASS_DOT_SYMBOLS = new Set(['BRK.A', 'BRK.B'])
const US_EPS_SCALE_BY_SYMBOL: Record<string, number> = {
  'BRK-B': 1500,
}
const SEC_EPS_TAGS = [
  'EarningsPerShareDiluted',
  'EarningsPerShareBasicAndDiluted',
  'EarningsPerShareBasic',
]
const SEC_ANNUAL_REPORT_FORMS = new Set(['10-K', '20-F', '40-F'])

type SecEpsFact = {
  form?: string
  start?: string
  end?: string
  val?: number
  frame?: string
  filed?: string
}

export function normalizeUsSymbol(input: string) {
  const symbol = input.trim().toUpperCase().replace(/\.US$/, '')
  return US_SHARE_CLASS_DOT_SYMBOLS.has(symbol)
    ? symbol.replace('.', '-')
    : symbol
}

export function adjustUsEpsForShareClass<T extends EpsRow>(
  symbol: string,
  quarters: T[],
): T[] {
  const scale = US_EPS_SCALE_BY_SYMBOL[normalizeUsSymbol(symbol)]
  if (!scale) return quarters

  return quarters.map((quarter) => ({
    ...quarter,
    eps: Number((quarter.eps / scale).toFixed(4)),
    ...(quarter.ttmEps === undefined
      ? {}
      : { ttmEps: Number((quarter.ttmEps / scale).toFixed(4)) }),
  }))
}

export function isQuarterDataStale(
  quarters: Pick<EpsRow, 'date'>[],
  asOf = new Date(),
  maxAgeDays = 550,
) {
  const latestDate = quarters.at(-1)?.date
  if (!latestDate) return true

  const latestMs = new Date(`${latestDate}T00:00:00Z`).getTime()
  const asOfMs = asOf.getTime()
  if (!Number.isFinite(latestMs) || !Number.isFinite(asOfMs)) return true

  return asOfMs - latestMs > maxAgeDays * 86_400_000
}

function pickSecAnnualEpsRowsFromFacts(facts: SecEpsFact[]): EpsRow[] {
  const byEndDate = new Map<
    string,
    { date: string; quarter: string; eps: number; ttmEps: number; rank: number }
  >()

  facts.forEach((fact) => {
    if (!fact.end || typeof fact.val !== 'number') return
    if (!SEC_ANNUAL_REPORT_FORMS.has(fact.form || '')) return

    const hasAnnualFrame = /^CY\d{4}$/.test(fact.frame || '')
    const durationDays = fact.start ? daysBetweenDates(fact.start, fact.end) : 0
    const isAnnualDuration = durationDays >= 350 && durationDays <= 380

    if (!hasAnnualFrame && !isAnnualDuration) return

    const year = fact.end.slice(0, 4)
    const rank =
      (hasAnnualFrame ? 4 : 0) +
      (fact.form === '20-F' || fact.form === '40-F' ? 2 : 1) +
      (fact.filed ? new Date(fact.filed).getTime() / 10_000_000_000_000 : 0)
    const existing = byEndDate.get(fact.end)

    if (!existing || rank >= existing.rank) {
      const eps = Number(fact.val.toFixed(4))
      byEndDate.set(fact.end, {
        date: fact.end,
        quarter: `${year} FY`,
        eps,
        ttmEps: eps,
        rank,
      })
    }
  })

  return Array.from(byEndDate.values())
    .sort((a, b) => a.date.localeCompare(b.date))
    .map(({ rank, ...row }) => row)
    .slice(-48)
}

export function pickSecAnnualEpsRows(secFacts: any): EpsRow[] {
  const gaap = secFacts?.facts?.['us-gaap']

  for (const tag of SEC_EPS_TAGS) {
    const facts = gaap?.[tag]?.units?.['USD/shares']
    if (!Array.isArray(facts)) continue

    const rows = pickSecAnnualEpsRowsFromFacts(facts)
    if (rows.length > 0) return rows
  }

  return []
}

function parseXmlAttrs(value: string) {
  const attrs: Record<string, string> = {}
  const attrPattern = /([\w:-]+)="([^"]*)"/g
  let match = attrPattern.exec(value)

  while (match) {
    attrs[match[1]] = match[2]
    match = attrPattern.exec(value)
  }

  return attrs
}

function daysBetweenDates(start: string, end: string) {
  return Math.round(
    (new Date(`${end}T00:00:00Z`).getTime() -
      new Date(`${start}T00:00:00Z`).getTime()) /
      86_400_000,
  )
}

export function pickSecFilingEpsRows(
  xml: string,
  classMember: string,
  periodType: 'quarterly' | 'annual' = 'quarterly',
): EpsRow[] {
  const contexts = new Map<string, string>()
  const contextPattern = /<context id="([^"]+)">([\s\S]*?)<\/context>/g
  let contextMatch = contextPattern.exec(xml)

  while (contextMatch) {
    contexts.set(contextMatch[1], contextMatch[2])
    contextMatch = contextPattern.exec(xml)
  }

  const byDate = new Map<string, EpsRow>()
  const epsPattern =
    /<us-gaap:EarningsPerShareBasic\b([^>]*)>([^<]*)<\/us-gaap:EarningsPerShareBasic>/g
  let epsMatch = epsPattern.exec(xml)

  while (epsMatch) {
    const attrs = parseXmlAttrs(epsMatch[1])
    const context = contexts.get(attrs.contextRef)

    if (context?.includes(classMember)) {
      const start = context.match(/<startDate>([^<]+)<\/startDate>/)?.[1]
      const end = context.match(/<endDate>([^<]+)<\/endDate>/)?.[1]
      const eps = toNumber(epsMatch[2])

      if (start && end && eps !== null) {
        const durationDays = daysBetweenDates(start, end)
        const matchesPeriod =
          periodType === 'quarterly'
            ? durationDays >= 70 && durationDays <= 110
            : durationDays >= 350 && durationDays <= 380

        if (matchesPeriod) {
          byDate.set(end, {
            date: end,
            quarter: quarterLabel(end),
            eps: Number(eps.toFixed(4)),
          })
        }
      }
    }

    epsMatch = epsPattern.exec(xml)
  }

  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date))
}

export function buildQuarterlyEpsRows(
  quarterlyRows: EpsRow[],
  annualRows: EpsRow[],
) {
  const byDate = new Map(quarterlyRows.map((row) => [row.date, row]))

  annualRows.forEach((annual) => {
    if (!annual.date.endsWith('-12-31') || byDate.has(annual.date)) return

    const year = annual.date.slice(0, 4)
    const firstThreeQuarters = [`${year}-03-31`, `${year}-06-30`, `${year}-09-30`]
      .map((date) => byDate.get(date)?.eps)

    if (firstThreeQuarters.some((eps) => eps === undefined)) return

    const firstThreeQuartersTotal = firstThreeQuarters.reduce<number>(
      (total, eps) => total + (eps ?? 0),
      0,
    )
    const q4Eps = Number((annual.eps - firstThreeQuartersTotal).toFixed(4))
    byDate.set(annual.date, {
      date: annual.date,
      quarter: quarterLabel(annual.date),
      eps: q4Eps,
    })
  })

  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date))
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
    symbol: normalizeUsSymbol(compact),
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

export function normalizeYahooDividendEvents(
  events: Record<string, unknown> | undefined,
): DividendEvent[] {
  return Object.values(events || {})
    .map((event): DividendEvent | null => {
      if (!event || typeof event !== 'object') return null
      const row = event as { date?: unknown; amount?: unknown }
      if (typeof row.date !== 'number') return null
      const amount = toNumber(row.amount)
      if (amount === null || amount <= 0) return null

      return {
        date: new Date(row.date * 1000).toISOString().slice(0, 10),
        amount: Number(amount.toFixed(4)),
      }
    })
    .filter((event): event is DividendEvent => Boolean(event))
    .sort((a, b) => a.date.localeCompare(b.date))
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
