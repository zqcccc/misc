import { NextResponse } from 'next/server'
import { getRedis } from '../shorter/redis'
import {
  buildProfitLineCacheKey,
  readProfitLineCache,
  writeProfitLineCache,
} from './cache'
import {
  adjustUsEpsForShareClass,
  buildQuarterPoints,
  buildQuarterlyEpsRows,
  isQuarterDataStale,
  latestDailyPrice,
  normalizeMarketSymbol,
  normalizeUsSymbol,
  normalizeYahooDividendEvents,
  pickSecAnnualEpsRows,
  pickSecFilingEpsRows,
  pickEastmoneyEpsRows,
  toNumber,
  type DividendEvent,
  type EpsRow,
  type NormalizedMarketSymbol,
} from './market-data'

type CompanyTicker = {
  cik_str: number
  ticker: string
  title: string
}

type SecFact = {
  form?: string
  start?: string
  end?: string
  val?: number
  frame?: string
  filed?: string
}

type SecRecentFilings = {
  form: string[]
  filingDate: string[]
  accessionNumber: string[]
  primaryDocument: string[]
}

type SplitEvent = {
  date: string
  numerator: number
  denominator: number
}

type ProfitLinePayload = {
  symbol: string
  name: string
  market: 'us' | 'cn' | 'hk'
  currency: string
  points: ReturnType<typeof buildQuarterPoints>
  latestPrice: ReturnType<typeof latestDailyPrice>
  dividends: DividendEvent[]
  sources: {
    eps: string
    price: string
    dividends?: string
  }
  ttmMethod: 'quarterly-rollup' | 'source-eps-ttm'
  splitAdjusted?: boolean
  epsCurrency?: string
  fxRate?: number
  balanceCurrency?: string
}

type RegionalMarketSymbol = Extract<
  NormalizedMarketSymbol,
  { market: 'cn' | 'hk' }
>

const SEC_HEADERS = {
  'User-Agent':
    process.env.SEC_USER_AGENT || 'misc-profit-line-tool contact@onlylike.work',
  Accept: 'application/json,text/plain,*/*',
}

const EPS_TAGS = [
  'EarningsPerShareDiluted',
  'EarningsPerShareBasicAndDiluted',
  'EarningsPerShareBasic',
]
const SEC_INSTANT_FACT_FORM_RANK: Record<string, number> = {
  '10-Q': 4,
  '6-K': 3,
  '10-K': 2,
  '20-F': 1,
}

const BERKSHIRE_CLASS_MEMBER_BY_TICKER: Record<string, string> = {
  'BRK-A': 'brka:EquivalentClassAMember',
  'BRK-B': 'brka:EquivalentClassBMember',
}

const CNY_TO_HKD_FALLBACK_RATE = 1.08

function jsonError(message: string, status = 400) {
  return NextResponse.json({ message }, { status })
}

function jsonPayload(payload: ProfitLinePayload, cacheStatus: 'HIT' | 'MISS') {
  return NextResponse.json(payload, {
    headers: {
      'Cache-Control': 's-maxage=21600, stale-while-revalidate=86400',
      'x-profit-line-cache': cacheStatus,
    },
  })
}

class ProfitLineDataError extends Error {
  constructor(
    message: string,
    public status = 400,
  ) {
    super(message)
  }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

async function fetchText(url: string, init?: RequestInit): Promise<string> {
  const response = await fetch(url, init)
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  return response.text()
}

async function fetchEastmoneyJson<T>(
  url: string,
  params: Record<string, string>,
): Promise<T> {
  const requestUrl = `${url}?${new URLSearchParams(params).toString()}`
  return fetchJson<T>(requestUrl, {
    headers: {
      Accept: 'application/json,text/plain,*/*',
      Referer: 'https://emweb.securities.eastmoney.com/',
      'User-Agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    },
    cache: 'no-store',
  })
}

async function resolveCompany(symbol: string) {
  const tickers = await fetchJson<Record<string, CompanyTicker>>(
    'https://www.sec.gov/files/company_tickers.json',
    {
      headers: SEC_HEADERS,
      cache: 'no-store',
    },
  )
  const normalized = normalizeUsSymbol(symbol)
  const company = Object.values(tickers).find(
    (item) => item.ticker.toUpperCase() === normalized,
  )

  if (!company) return null

  return {
    cik: company.cik_str.toString().padStart(10, '0'),
    ticker: company.ticker.toUpperCase(),
    name: company.title,
  }
}

function daysBetween(start?: string, end?: string) {
  if (!start || !end) return Number.POSITIVE_INFINITY
  const startMs = new Date(start).getTime()
  const endMs = new Date(end).getTime()
  return Math.round((endMs - startMs) / 86_400_000)
}

function quarterLabel(date: string, frame?: string) {
  const match = frame?.match(/^CY(\d{4})Q([1-4])$/)
  if (match) return `${match[1]} Q${match[2]}`
  const value = new Date(`${date}T00:00:00Z`)
  const quarter = Math.floor(value.getUTCMonth() / 3) + 1
  return `${value.getUTCFullYear()} Q${quarter}`
}

function pickQuarterlyEpsFromFacts(facts: SecFact[]): Array<{
  date: string
  quarter: string
  eps: number
  filed: string
}> {
  const byEndDate = new Map<
    string,
    { date: string; quarter: string; eps: number; filed: string; rank: number }
  >()

  facts.forEach((fact) => {
    if (!fact.end || typeof fact.val !== 'number') return
    if (!['10-Q', '10-K'].includes(fact.form || '')) return

    const hasQuarterFrame = /^CY\d{4}Q[1-4]$/.test(fact.frame || '')
    const durationDays = daysBetween(fact.start, fact.end)
    const isQuarterDuration = durationDays >= 70 && durationDays <= 110

    if (!hasQuarterFrame && !isQuarterDuration) return

    const rank =
      (hasQuarterFrame ? 4 : 0) +
      (fact.form === '10-Q' ? 2 : 0) +
      (fact.filed ? new Date(fact.filed).getTime() / 10_000_000_000_000 : 0)
    const existing = byEndDate.get(fact.end)

    if (!existing || rank >= existing.rank) {
      byEndDate.set(fact.end, {
        date: fact.end,
        quarter: quarterLabel(fact.end, fact.frame),
        eps: Number(fact.val.toFixed(4)),
        filed: fact.filed || '',
        rank,
      })
    }
  })

  return Array.from(byEndDate.values())
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-48)
}

function pickQuarterlyEps(secFacts: any): Array<{
  date: string
  quarter: string
  eps: number
  filed: string
}> {
  const gaap = secFacts?.facts?.['us-gaap']

  for (const tag of EPS_TAGS) {
    const facts = gaap?.[tag]?.units?.['USD/shares']
    if (!Array.isArray(facts)) continue

    const rows = pickQuarterlyEpsFromFacts(facts)
    if (rows.length > 0) return rows
  }

  return []
}

function pickSecInstantFacts(secFacts: any, tags: string[]) {
  const gaap = secFacts?.facts?.['us-gaap']
  const matchedTags = tags.filter((name) =>
    Array.isArray(gaap?.[name]?.units?.USD),
  )
  const byEndDate = new Map<string, { value: number; rank: number }>()

  matchedTags.forEach((tag, tagPriority) => {
    const facts = gaap[tag].units.USD as SecFact[]
    facts.forEach((fact) => {
      if (!fact.end || typeof fact.val !== 'number') return
      const formRank = SEC_INSTANT_FACT_FORM_RANK[fact.form || '']
      if (!formRank) return

      const rank =
        formRank +
        (fact.frame ? 0.5 : 0) +
        (fact.filed ? new Date(fact.filed).getTime() / 10_000_000_000_000 : 0) +
        (matchedTags.length - tagPriority) * 100
      const existing = byEndDate.get(fact.end)
      if (!existing || rank >= existing.rank) {
        byEndDate.set(fact.end, {
          value: Number(fact.val.toFixed(2)),
          rank,
        })
      }
    })
  })

  return new Map(
    Array.from(byEndDate.entries()).map(([date, item]) => [date, item.value]),
  )
}

function mergeUsBalanceMetrics<T extends { date: string }>(
  quarters: T[],
  secFacts: any,
) {
  const equityByDate = pickSecInstantFacts(secFacts, [
    'StockholdersEquity',
    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
  ])
  const liabilitiesByDate = pickSecInstantFacts(secFacts, ['Liabilities'])
  const cashByDate = pickSecInstantFacts(secFacts, [
    'CashAndCashEquivalentsAtCarryingValue',
    'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
    'CashAndDueFromBanks',
  ])

  return quarters.map((quarter) => ({
    ...quarter,
    shareholderEquity: equityByDate.get(quarter.date) ?? null,
    liabilities: liabilitiesByDate.get(quarter.date) ?? null,
    cash: cashByDate.get(quarter.date) ?? null,
  }))
}

function toUnixSeconds(date: string, dayOffset = 0) {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + dayOffset)
  return Math.floor(value.getTime() / 1000)
}

async function fetchMarketData(symbol: string, firstDate: string) {
  const yahooSymbol = /\.(SS|SZ|HK)$/.test(symbol)
    ? symbol
    : symbol.replace(/\./g, '-')
  const period1 = toUnixSeconds(firstDate, -14)
  const period2 = Math.floor(Date.now() / 1000) + 86_400
  const url = `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(
    yahooSymbol,
  )}?period1=${period1}&period2=${period2}&interval=1d&events=history%7Csplits%7Cdividends`

  const data = await fetchJson<any>(url, {
    headers: {
      Accept: 'application/json',
      'User-Agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    },
    cache: 'no-store',
  })
  const result = data?.chart?.result?.[0]
  const timestamps: number[] = result?.timestamp || []
  const closes: Array<number | null> = result?.indicators?.quote?.[0]?.close || []
  const splitEvents = Object.values(result?.events?.splits || {}) as Array<{
    date: number
    numerator: number
    denominator: number
  }>

  return {
    prices: timestamps
      .map((timestamp, index) => ({
        date: new Date(timestamp * 1000).toISOString().slice(0, 10),
        close: closes[index],
      }))
      .filter((item) => typeof item.close === 'number') as Array<{
      date: string
      close: number
    }>,
    splits: splitEvents
      .map((split) => ({
        date: new Date(split.date * 1000).toISOString().slice(0, 10),
        numerator: split.numerator,
        denominator: split.denominator,
      }))
      .filter((split) => split.numerator > 0 && split.denominator > 0),
    dividends: normalizeYahooDividendEvents(result?.events?.dividends),
  }
}

function secArchiveFilingUrl(cik: string, accessionNumber: string, document: string) {
  const cikNumber = String(Number(cik))
  const accessionPath = accessionNumber.replace(/-/g, '')
  const xmlDocument = document.replace(/\.htm$/i, '_htm.xml')
  return `https://www.sec.gov/Archives/edgar/data/${cikNumber}/${accessionPath}/${xmlDocument}`
}

async function fetchBerkshireQuarterlyEps(
  company: Awaited<ReturnType<typeof resolveCompany>>,
) {
  if (!company) return []

  const classMember = BERKSHIRE_CLASS_MEMBER_BY_TICKER[company.ticker]
  if (!classMember) return []

  const submissions = await fetchJson<{ filings?: { recent?: SecRecentFilings } }>(
    `https://data.sec.gov/submissions/CIK${company.cik}.json`,
    {
      headers: SEC_HEADERS,
      cache: 'no-store',
    },
  )
  const recent = submissions.filings?.recent
  if (!recent) return []

  const quarterlyRows: EpsRow[] = []
  const annualRows: EpsRow[] = []
  for (let index = 0; index < recent.form.length; index += 1) {
    const form = recent.form[index]
    if (!['10-Q', '10-K'].includes(form)) continue

    const url = secArchiveFilingUrl(
      company.cik,
      recent.accessionNumber[index],
      recent.primaryDocument[index],
    )
    const xml = await fetchText(url, {
      headers: {
        ...SEC_HEADERS,
        Accept: 'application/xml,text/xml,text/plain,*/*',
      },
      cache: 'no-store',
    })
    quarterlyRows.push(...pickSecFilingEpsRows(xml, classMember, 'quarterly'))
    if (form === '10-K') {
      annualRows.push(...pickSecFilingEpsRows(xml, classMember, 'annual'))
    }

    if (buildQuarterlyEpsRows(quarterlyRows, annualRows).length >= 8) break
  }

  return buildQuarterlyEpsRows(quarterlyRows, annualRows).slice(-48)
}

function splitAdjustmentForDate(splits: SplitEvent[], date: string) {
  return splits.reduce((factor, split) => {
    if (split.date <= date) return factor
    return factor * (split.numerator / split.denominator)
  }, 1)
}

async function buildUsPayload(symbol: string): Promise<ProfitLinePayload> {
  const company = await resolveCompany(symbol)
  if (!company) {
    throw new ProfitLineDataError('当前数据源无法识别该美股代码', 404)
  }

  const secFacts = await fetchJson<any>(
    `https://data.sec.gov/api/xbrl/companyfacts/CIK${company.cik}.json`,
    {
      headers: SEC_HEADERS,
      cache: 'no-store',
    },
  )
  const filingQuarters = await fetchBerkshireQuarterlyEps(company)
  const companyFactQuarters = pickQuarterlyEps(secFacts)
  const annualRows = pickSecAnnualEpsRows(secFacts)
  const quarters =
    filingQuarters.length > 0
      ? filingQuarters
      : companyFactQuarters.length > 0
        ? companyFactQuarters
        : annualRows

  if (quarters.length < 4) {
    throw new ProfitLineDataError('可用 EPS 数据少于 4 个，无法绘制利润线', 404)
  }
  if (isQuarterDataStale(quarters)) {
    throw new ProfitLineDataError('SEC EPS 数据已过期，无法可靠计算利润线', 404)
  }

  const marketData = await fetchMarketData(company.ticker, quarters[0].date)
  const shareClassAdjustedQuarters =
    filingQuarters.length > 0
      ? quarters
      : adjustUsEpsForShareClass(company.ticker, quarters)
  const adjustedQuarters = shareClassAdjustedQuarters.map((quarter) => {
    const splitAdjustment = splitAdjustmentForDate(marketData.splits, quarter.date)
    const ttmEps = 'ttmEps' in quarter ? quarter.ttmEps : undefined

    return {
      ...quarter,
      eps: Number((quarter.eps / splitAdjustment).toFixed(4)),
      ...(ttmEps === undefined
        ? {}
        : { ttmEps: Number((ttmEps / splitAdjustment).toFixed(4)) }),
    }
  })
  const quartersWithBalance = mergeUsBalanceMetrics(adjustedQuarters, secFacts)
  const points = buildQuarterPoints(quartersWithBalance, marketData.prices)

  return {
    symbol: company.ticker,
    name: company.name,
    market: 'us',
    currency: 'USD',
    points,
    latestPrice: latestDailyPrice(marketData.prices),
    dividends: marketData.dividends,
    sources: {
      eps:
        filingQuarters.length > 0
          ? 'SEC filing XBRL class-specific EPS'
          : companyFactQuarters.length > 0
            ? 'SEC companyfacts quarterly EPS'
            : 'SEC companyfacts annual EPS',
      price: 'Yahoo Finance chart',
      dividends: 'Yahoo Finance chart',
    },
    ttmMethod: 'quarterly-rollup',
    splitAdjusted: marketData.splits.length > 0,
    balanceCurrency: 'USD',
  }
}

type BalanceMetric = {
  date: string
  shareholderEquity: number | null
  liabilities: number | null
  cash: number | null
  balanceCurrency?: string
}

function normalizeCurrencyCode(value: unknown) {
  if (typeof value !== 'string') return undefined
  if (/^[A-Z]{3}$/.test(value)) return value
  if (value.includes('人民币')) return 'CNY'
  if (value.includes('港')) return 'HKD'
  if (value.includes('美元')) return 'USD'
  return undefined
}

function mergeBalanceMetrics(quarters: EpsRow[], metrics: BalanceMetric[]) {
  const byDate = new Map(metrics.map((metric) => [metric.date, metric]))
  return quarters.map((quarter) => {
    const metric = byDate.get(quarter.date)
    return {
      ...quarter,
      shareholderEquity:
        quarter.shareholderEquity ?? metric?.shareholderEquity ?? null,
      liabilities: quarter.liabilities ?? metric?.liabilities ?? null,
      cash: quarter.cash ?? metric?.cash ?? null,
    }
  })
}

async function fetchCnBalanceMetrics(
  marketSymbol: RegionalMarketSymbol,
): Promise<{ metrics: BalanceMetric[]; balanceCurrency?: string }> {
  const data = await fetchEastmoneyJson<any>(
    'https://datacenter.eastmoney.com/securities/api/data/v1/get',
    {
      reportName: 'RPT_F10_FINANCE_GBALANCE',
      columns: 'ALL',
      quoteColumns: '',
      filter: `(SECUCODE="${marketSymbol.eastmoneyCode}")`,
      pageNumber: '1',
      pageSize: '200',
      sortTypes: '-1',
      sortColumns: 'REPORT_DATE',
      source: 'HSF10',
      client: 'PC',
    },
  )
  const rawRows = data?.result?.data || []
  const balanceCurrency = normalizeCurrencyCode(rawRows[0]?.CURRENCY)

  return {
    metrics: rawRows
      .map((row: Record<string, unknown>) => {
        const date = typeof row.REPORT_DATE === 'string'
          ? row.REPORT_DATE.slice(0, 10)
          : null
        if (!date) return null
        return {
          date,
          shareholderEquity: toNumber(
            row.TOTAL_PARENT_EQUITY ?? row.TOTAL_EQUITY,
          ),
          liabilities: toNumber(row.TOTAL_LIABILITIES),
          cash: toNumber(row.MONETARYFUNDS),
          balanceCurrency,
        }
      })
      .filter((row: BalanceMetric | null): row is BalanceMetric => Boolean(row)),
    balanceCurrency,
  }
}

async function fetchHkBalanceMetrics(
  marketSymbol: RegionalMarketSymbol,
): Promise<{ metrics: BalanceMetric[]; balanceCurrency?: string }> {
  const data = await fetchEastmoneyJson<any>(
    'https://datacenter.eastmoney.com/securities/api/data/v1/get',
    {
      reportName: 'RPT_HKF10_FN_BALANCE',
      columns: 'ALL',
      quoteColumns: '',
      filter: `(SECUCODE="${marketSymbol.eastmoneyCode}.HK")`,
      pageNumber: '1',
      pageSize: '3000',
      sortTypes: '-1',
      sortColumns: 'STD_REPORT_DATE',
      source: 'F10',
      client: 'PC',
    },
  )
  const rawRows = data?.result?.data || []
  const balanceCurrency =
    normalizeCurrencyCode(rawRows[0]?.CURRENCY_CODE) ||
    normalizeCurrencyCode(rawRows[0]?.CURRENCY)
  const byDate = new Map<string, BalanceMetric>()

  rawRows.forEach((row: Record<string, unknown>) => {
    const date =
      typeof row.STD_REPORT_DATE === 'string'
        ? row.STD_REPORT_DATE.slice(0, 10)
        : null
    if (!date) return

    const metric = byDate.get(date) || {
      date,
      shareholderEquity: null,
      liabilities: null,
      cash: null,
      balanceCurrency,
    }
    if (row.STD_ITEM_CODE === '004030999') {
      metric.shareholderEquity = toNumber(row.AMOUNT)
    }
    if (row.STD_ITEM_CODE === '004025999') {
      metric.liabilities = toNumber(row.AMOUNT)
    }
    if (row.STD_ITEM_CODE === '004002010') {
      metric.cash = toNumber(row.AMOUNT)
    }
    byDate.set(date, metric)
  })

  return {
    metrics: Array.from(byDate.values()),
    balanceCurrency,
  }
}

async function fetchEastmoneyQuarters(
  marketSymbol: RegionalMarketSymbol,
): Promise<{
  name: string
  quarters: EpsRow[]
  ttmMethod: 'quarterly-rollup' | 'source-eps-ttm'
  epsSource: string
  balanceCurrency?: string
}> {
  if (marketSymbol.market === 'cn') {
    const data = await fetchEastmoneyJson<any>(
      'https://datacenter.eastmoney.com/securities/api/data/v1/get',
      {
        reportName: 'RPT_F10_QTR_MAINFINADATA',
        columns: 'ALL',
        quoteColumns: '',
        filter: `(SECUCODE="${marketSymbol.eastmoneyCode}")`,
        pageNumber: '1',
        pageSize: '200',
        sortTypes: '-1',
        sortColumns: 'REPORT_DATE',
        source: 'HSF10',
        client: 'PC',
      },
    )
    const rawRows = data?.result?.data || []
    const balanceData = await fetchCnBalanceMetrics(marketSymbol)
    const quarters = mergeBalanceMetrics(
      pickEastmoneyEpsRows(rawRows, 'EPSJB').slice(-48),
      balanceData.metrics,
    )

    return {
      name: rawRows[0]?.SECURITY_NAME_ABBR || marketSymbol.symbol,
      quarters,
      ttmMethod: 'quarterly-rollup',
      epsSource: 'Eastmoney A-share quarterly financial indicators',
      balanceCurrency: balanceData.balanceCurrency,
    }
  }

  const data = await fetchEastmoneyJson<any>(
    'https://datacenter.eastmoney.com/securities/api/data/v1/get',
    {
      reportName: 'RPT_HKF10_FN_MAININDICATOR',
      columns: 'HKF10_FN_MAININDICATOR',
      quoteColumns: '',
      filter: `(SECUCODE="${marketSymbol.eastmoneyCode}.HK")`,
      pageNumber: '1',
      pageSize: '200',
      sortTypes: '-1',
      sortColumns: 'STD_REPORT_DATE',
      source: 'F10',
      client: 'PC',
      v: '01975982096513973',
    },
  )
  const rawRows = data?.result?.data || []
  const balanceData = await fetchHkBalanceMetrics(marketSymbol)
  const quarters = mergeBalanceMetrics(
    pickEastmoneyEpsRows(rawRows, 'BASIC_EPS', 'EPS_TTM').slice(-48),
    balanceData.metrics,
  )

  return {
    name: rawRows[0]?.SECURITY_NAME_ABBR || marketSymbol.symbol,
    quarters,
    ttmMethod: 'source-eps-ttm',
    epsSource: 'Eastmoney HK financial indicators',
    balanceCurrency: balanceData.balanceCurrency,
  }
}

function toRegionalYahooSymbol(
  marketSymbol: RegionalMarketSymbol,
) {
  if (marketSymbol.market === 'hk') {
    return `${Number(marketSymbol.symbol).toString().padStart(4, '0')}.HK`
  }

  return marketSymbol.eastmoneyCode.endsWith('.SH')
    ? `${marketSymbol.symbol}.SS`
    : `${marketSymbol.symbol}.SZ`
}

async function fetchCnyToHkdRate(): Promise<number> {
  const url =
    'https://query2.finance.yahoo.com/v8/finance/chart/CNYHKD=X?range=5d&interval=1d'

  try {
    const data = await fetchJson<any>(url, {
      headers: {
        Accept: 'application/json',
        'User-Agent':
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      },
      cache: 'no-store',
    })
    const rate = data?.chart?.result?.[0]?.meta?.regularMarketPrice
    if (typeof rate === 'number' && Number.isFinite(rate) && rate > 0) {
      return rate
    }

    throw new Error('无法获取 CNY/HKD 汇率')
  } catch (error) {
    console.warn('[profit-line] CNY/HKD rate fallback used:', error)
    return CNY_TO_HKD_FALLBACK_RATE
  }
}

type HkCompanyProfile = {
  zqzl?: {
    zqlx?: string
    mgmz?: string
  }
  gszl?: {
    zcd?: string
  }
}

async function fetchHkCompanyProfile(symbol: string): Promise<HkCompanyProfile> {
  const url = `http://f10.eastmoney.com/PC_HKF10/CompanyProfile/PageAjax?code=${symbol}`
  try {
    const data = await fetchJson<HkCompanyProfile>(url, {
      headers: {
        Accept: 'application/json',
        Referer: 'http://f10.eastmoney.com/',
        'User-Agent':
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      },
      cache: 'no-store',
    })
    return data
  } catch {
    return {}
  }
}

const HKD_EPS_STOCKS = new Set([
  '00001',
  '01038',
  '01113',
  '01929',
  '01997',
])

function isEpsInCny(symbol: string, profile: HkCompanyProfile): boolean {
  if (HKD_EPS_STOCKS.has(symbol)) {
    return false
  }

  const zqlx = profile.zqzl?.zqlx
  const zcd = profile.gszl?.zcd || ''

  if (zqlx === 'H股' || zqlx === '红筹股') {
    return true
  }

  if (zqlx === '非H股' && zcd.includes('中国') && !zcd.includes('Cayman')) {
    return false
  }

  if (
    zqlx === '非H股' &&
    (zcd.includes('United Kingdom') || zcd.includes('英国'))
  ) {
    return false
  }

  return true
}

async function buildEastmoneyPayload(
  marketSymbol: RegionalMarketSymbol,
): Promise<ProfitLinePayload> {
  const financialData = await fetchEastmoneyQuarters(marketSymbol)
  const quarters = financialData.quarters

  if (quarters.length < 4) {
    throw new ProfitLineDataError('可用 EPS 数据少于 4 个，无法绘制利润线', 404)
  }

  let epsCurrency: string | undefined
  let fxRate: number | undefined
  let convertedQuarters = quarters

  if (marketSymbol.market === 'hk') {
    const profile = await fetchHkCompanyProfile(marketSymbol.symbol)
    if (isEpsInCny(marketSymbol.symbol, profile)) {
      const rate = await fetchCnyToHkdRate()
      epsCurrency = 'CNY'
      fxRate = rate
      convertedQuarters = quarters.map((q) => ({
        ...q,
        eps: q.eps * rate,
        ttmEps: q.ttmEps != null ? q.ttmEps * rate : undefined,
      }))
    }
  }

  const yahooSymbol = toRegionalYahooSymbol(marketSymbol)
  const marketData = await fetchMarketData(yahooSymbol, quarters[0].date)
  const points = buildQuarterPoints(convertedQuarters, marketData.prices)

  return {
    symbol:
      marketSymbol.market === 'hk'
        ? `${marketSymbol.symbol}.HK`
        : marketSymbol.eastmoneyCode,
    name: financialData.name,
    market: marketSymbol.market,
    currency: marketSymbol.currency,
    points,
    latestPrice: latestDailyPrice(marketData.prices),
    dividends: marketData.dividends,
    sources: {
      eps: financialData.epsSource,
      price: 'Yahoo Finance chart',
      dividends: 'Yahoo Finance chart',
    },
    ttmMethod: financialData.ttmMethod,
    ...(epsCurrency ? { epsCurrency, fxRate } : {}),
    ...(financialData.balanceCurrency
      ? { balanceCurrency: financialData.balanceCurrency }
      : {}),
  }
}

function canonicalCacheSymbol(marketSymbol: NormalizedMarketSymbol) {
  if (marketSymbol.market === 'us') return marketSymbol.symbol
  if (marketSymbol.market === 'hk') return `${marketSymbol.symbol}.HK`
  return marketSymbol.eastmoneyCode
}

async function readRedisCache(key: string) {
  try {
    const redis = await getRedis()
    return await readProfitLineCache<ProfitLinePayload>(redis, key)
  } catch (error) {
    console.warn('[profit-line] redis read skipped:', error)
    return null
  }
}

async function writeRedisCache(key: string, payload: ProfitLinePayload) {
  try {
    const redis = await getRedis()
    await writeProfitLineCache(redis, key, payload)
  } catch (error) {
    console.warn('[profit-line] redis write skipped:', error)
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const inputSymbol = searchParams.get('symbol') || ''
  const symbol = inputSymbol.trim()

  if (!symbol) return jsonError('请输入股票代码')

  try {
    const marketSymbol = normalizeMarketSymbol(symbol)
    const cacheKey = buildProfitLineCacheKey(canonicalCacheSymbol(marketSymbol))
    const cached = await readRedisCache(cacheKey)

    if (cached && Array.isArray(cached.dividends)) {
      return jsonPayload(cached, 'HIT')
    }

    const payload =
      marketSymbol.market === 'us'
        ? await buildUsPayload(marketSymbol.symbol)
        : await buildEastmoneyPayload(marketSymbol)

    await writeRedisCache(cacheKey, payload)

    return jsonPayload(payload, 'MISS')
  } catch (error) {
    if (error instanceof ProfitLineDataError) {
      return jsonError(error.message, error.status)
    }

    console.error(error)
    return jsonError('数据获取失败，请稍后重试', 502)
  }
}
