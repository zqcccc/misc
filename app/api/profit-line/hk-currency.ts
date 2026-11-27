import type { EpsRow } from './market-data'

export type HkCompanyProfile = {
  zqzl?: {
    zqlx?: string
    mgmz?: string
  }
  gszl?: {
    zcd?: string
  }
}

export type HkEpsCurrency = 'CNY' | 'HKD' | 'unknown'

export class HkCurrencyError extends Error {}

// 东方财富未提供统一的 EPS 币种字段；这批港股财报确认按 HKD 列示，无需折算。
// 其余港股的币种必须由公司资料接口确认，确认不了就显式失败，不允许默认值。
export const HKD_EPS_STOCKS: Record<string, true> = {
  '00001': true,
  '01038': true,
  '01113': true,
  '01929': true,
  '01997': true,
}

export function resolveHkEpsCurrency(
  symbol: string,
  profile: HkCompanyProfile | null | undefined,
): HkEpsCurrency {
  if (HKD_EPS_STOCKS[symbol]) return 'HKD'

  const zqlx = profile?.zqzl?.zqlx
  if (!zqlx) return 'unknown'

  if (zqlx === 'H股' || zqlx === '红筹股') return 'CNY'

  if (zqlx === '非H股') {
    const zcd = profile?.gszl?.zcd || ''
    if (zcd.includes('中国') && !zcd.includes('Cayman')) return 'HKD'
    if (zcd.includes('United Kingdom') || zcd.includes('英国')) return 'HKD'
    // 其余注册地（开曼群岛等）的非 H 股（腾讯、小米、阿里等）财报按 CNY 列示
    return 'CNY'
  }

  return 'unknown'
}

const EASTMONEY_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

export async function fetchHkCompanyProfile(
  symbol: string,
  fetchImpl: typeof fetch = fetch,
): Promise<HkCompanyProfile> {
  const url = `https://emweb.securities.eastmoney.com/PC_HKF10/CompanyProfile/PageAjax?code=${symbol}`

  let data: unknown
  try {
    const response = await fetchImpl(url, {
      headers: {
        Accept: 'application/json',
        Referer: 'https://emweb.securities.eastmoney.com/',
        'User-Agent': EASTMONEY_UA,
      },
      cache: 'no-store',
      signal: AbortSignal.timeout(10_000),
    })
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`)
    }
    data = await response.json()
  } catch (error) {
    throw new HkCurrencyError(
      `港股公司资料请求失败，无法确认 EPS 币种（${
        error instanceof Error ? error.message : String(error)
      }）`,
    )
  }

  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    throw new HkCurrencyError('港股公司资料结构异常，无法确认 EPS 币种')
  }

  return data as HkCompanyProfile
}

// 从 Yahoo chart 响应中收窄出 CNY/HKD 汇率；结构不符或数值非法时返回 null
function pickCnyHkdRateFromChart(data: unknown): number | null {
  if (!data || typeof data !== 'object' || !('chart' in data)) return null
  const chart = data.chart
  if (!chart || typeof chart !== 'object' || !('result' in chart)) return null
  const results = chart.result
  const result = Array.isArray(results) ? results[0] : null
  if (!result || typeof result !== 'object' || !('meta' in result)) return null
  const meta = result.meta
  if (!meta || typeof meta !== 'object' || !('regularMarketPrice' in meta)) {
    return null
  }
  const rate = meta.regularMarketPrice
  return typeof rate === 'number' && Number.isFinite(rate) && rate > 0
    ? rate
    : null
}

export async function fetchCnyToHkdRate(
  fetchImpl: typeof fetch = fetch,
): Promise<number> {
  const url =
    'https://query2.finance.yahoo.com/v8/finance/chart/CNYHKD=X?range=5d&interval=1d'

  let data: unknown
  try {
    const response = await fetchImpl(url, {
      headers: {
        Accept: 'application/json',
        'User-Agent': EASTMONEY_UA,
      },
      cache: 'no-store',
      signal: AbortSignal.timeout(10_000),
    })
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`)
    }
    data = await response.json()
  } catch (error) {
    throw new HkCurrencyError(
      `CNY/HKD 汇率请求失败，无法折算港股 EPS（${
        error instanceof Error ? error.message : String(error)
      }）`,
    )
  }

  const rate = pickCnyHkdRateFromChart(data)
  if (rate === null) {
    throw new HkCurrencyError('CNY/HKD 汇率数据异常，无法折算港股 EPS')
  }

  return rate
}

export function convertCnyEpsToHkd(quarters: EpsRow[], rate: number): EpsRow[] {
  return quarters.map((quarter) => ({
    ...quarter,
    eps: quarter.eps * rate,
    ttmEps: quarter.ttmEps != null ? quarter.ttmEps * rate : undefined,
  }))
}

export type HkEpsPreparation = {
  epsCurrency?: string
  fxRate?: number
  convertedQuarters: EpsRow[]
}

// 币种或汇率无法确认时抛出 HkCurrencyError，调用方必须以错误响应结束，
// 不得产出貌似正常的估值数据，也不得写入缓存。
export async function prepareHkEps(
  symbol: string,
  quarters: EpsRow[],
  fetchImpl: typeof fetch = fetch,
): Promise<HkEpsPreparation> {
  if (HKD_EPS_STOCKS[symbol]) {
    return { convertedQuarters: quarters }
  }

  const profile = await fetchHkCompanyProfile(symbol, fetchImpl)
  const currency = resolveHkEpsCurrency(symbol, profile)

  if (currency === 'unknown') {
    const zqlx = profile.zqzl?.zqlx
    throw new HkCurrencyError(
      zqlx
        ? `无法确认港股 EPS 币种（证券类型：${zqlx}）`
        : '港股公司资料缺少证券类型字段，无法确认 EPS 币种',
    )
  }

  if (currency === 'HKD') {
    return { convertedQuarters: quarters }
  }

  const rate = await fetchCnyToHkdRate(fetchImpl)
  return {
    epsCurrency: 'CNY',
    fxRate: rate,
    convertedQuarters: convertCnyEpsToHkd(quarters, rate),
  }
}
