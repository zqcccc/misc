/**
 * 跨境 ETF 溢价监控：上游网络请求与进程内缓存。
 *
 * 数据源（全部为公开接口，逐一带 UA/Referer/超时/结构校验验证过，2026-11-24）：
 * - 全量场内基金名单与「类型」列：fund.eastmoney.com/cnjy_dwjz.html（GBK HTML）。
 *   类型「指数型-海外股票」即 QDII，是机制分类的唯一上游依据。
 * - 批量行情（价格/IOPV/成交额/时间）：优先东方财富 push2 ulist.np/get；
 *   该主机在本网络曾被限流，失败时改用腾讯 qt.gtimg.cn 批量行情，
 *   IOPV/净值字段已与东财 f441、lsjz DWJZ 交叉核对一致。失败即报错，不伪造数据。
 * - 历史日线：优先东方财富 push2his kline（fqt=0 不复权），失败时腾讯 ifzq 日线（不复权）。
 * - 历史单位净值与申购状态：api.fund.eastmoney.com/f10/lsjz（pageSize 上限 20，需 Referer）。
 * - 基金档案（全名/类型/申赎状态）：fundmobapi FundMNBaseInfo。
 */
import {
  buildPremiumRows,
  buildPremiumSeries,
  classifyMechanism,
  describeNavLag,
  isEtfCode,
  navLagDays,
  parseCnjyHtml,
  parseEastmoneyKlines,
  parseEastmoneyUlist,
  parseLsjzPayload,
  parseTencentKline,
  parseTencentQuoteText,
  pickCrossBorderFunds,
  type ClassifiedFund,
  type EtfPremiumRow,
  type HistoryPoint,
  type QuoteRow,
} from '@/lib/etf-premium'

const REQUEST_TIMEOUT_MS = 12_000
const SNAPSHOT_TTL_MS = 60_000
const DETAIL_TTL_MS = 10 * 60_000
const TENCENT_BATCH_SIZE = 50
const LSJZ_PAGE_SIZE = 20
const LSJZ_MAX_PAGES = 40

const BROWSER_HEADERS = {
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  Accept: '*/*',
}

export class UpstreamError extends Error {
  stage: string

  constructor(stage: string, message: string) {
    super(message)
    this.name = 'UpstreamError'
    this.stage = stage
  }
}

async function fetchWithTimeout(url: string, referer?: string): Promise<Response> {
  let response: Response
  try {
    response = await fetch(url, {
      headers: { ...BROWSER_HEADERS, ...(referer ? { Referer: referer } : {}) },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      cache: 'no-store',
    })
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    throw new UpstreamError('network', `上游请求失败：${reason}`)
  }
  if (!response.ok) {
    throw new UpstreamError('http', `上游返回 HTTP ${response.status}：${new URL(url).host}`)
  }
  return response
}

async function fetchJson(url: string, referer?: string): Promise<unknown> {
  const response = await fetchWithTimeout(url, referer)
  try {
    return await response.json()
  } catch (error) {
    throw new UpstreamError('parse', `上游响应不是合法 JSON：${new URL(url).host}`)
  }
}

async function fetchGbkText(url: string, referer?: string): Promise<string> {
  const response = await fetchWithTimeout(url, referer)
  const buffer = await response.arrayBuffer()
  try {
    return new TextDecoder('gbk').decode(buffer)
  } catch {
    throw new UpstreamError('decode', `GBK 解码失败：${new URL(url).host}`)
  }
}

/** cnjy 表头日期 → 名单基准日；行结构已在 parseCnjyHtml 校验。 */
export async function fetchUniverse(): Promise<{
  navDate: string | null
  funds: ClassifiedFund[]
  etfCount: number
  excludedNonEtf: number
  excludedOther: number
}> {
  const html = await fetchGbkText('https://fund.eastmoney.com/cnjy_dwjz.html')
  const { navDate, rows } = parseCnjyHtml(html)
  if (rows.length === 0) {
    throw new UpstreamError('parse', '场内基金名单解析为空，上游页面结构可能已变化')
  }
  const picked = pickCrossBorderFunds(rows)
  if (picked.funds.length === 0) {
    throw new UpstreamError('parse', '名单中没有任何跨境 ETF，分类规则或上游数据异常')
  }
  return { navDate, ...picked }
}

function etfSecid(code: string): string {
  return `${code.startsWith('5') ? '1' : '0'}.${code}`
}

async function fetchEastmoneyQuotes(codes: string[]): Promise<Map<string, QuoteRow>> {
  const secids = codes.map(etfSecid).join(',')
  const url =
    'https://push2.eastmoney.com/api/qt/ulist.np/get?ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2' +
    `&secids=${secids}&fields=f2,f3,f6,f12,f13,f14,f124,f297,f441`
  const payload = await fetchJson(url, 'https://quote.eastmoney.com/')
  const rows = parseEastmoneyUlist(payload)
  if (rows.length === 0) {
    throw new UpstreamError('parse', '东财批量行情没有返回任何行')
  }
  return new Map(rows.map((row) => [row.code, row]))
}

async function fetchTencentQuotes(codes: string[]): Promise<Map<string, QuoteRow>> {
  const quotes = new Map<string, QuoteRow>()
  for (let i = 0; i < codes.length; i += TENCENT_BATCH_SIZE) {
    const batch = codes.slice(i, i + TENCENT_BATCH_SIZE)
    const symbols = batch.map((code) => `${code.startsWith('5') ? 'sh' : 'sz'}${code}`)
    const text = await fetchGbkText(`https://qt.gtimg.cn/q=${symbols.join(',')}`, 'https://gu.qq.com/')
    for (const row of parseTencentQuoteText(text)) {
      quotes.set(row.code, row)
    }
  }
  if (quotes.size === 0) {
    throw new UpstreamError('parse', '腾讯批量行情没有返回任何行')
  }
  return quotes
}

export type QuoteSource = 'eastmoney' | 'tencent'

export type SnapshotPayload = {
  generatedAt: string
  quoteSource: QuoteSource
  quoteSourceNote: string | null
  universeNavDate: string | null
  etfCount: number
  excludedNonEtf: number
  excludedOther: number
  rows: EtfPremiumRow[]
}

let snapshotCache: { at: number; payload: SnapshotPayload } | null = null

/** 只读已缓存的快照，不触发上游请求。供详情路由取已核对名称/机制，避免为提示信息拉全量。 */
export function peekSnapshot(): SnapshotPayload | null {
  return snapshotCache?.payload ?? null
}

export async function getSnapshot(refresh = false): Promise<SnapshotPayload> {
  const now = Date.now()
  if (!refresh && snapshotCache && now - snapshotCache.at < SNAPSHOT_TTL_MS) {
    return snapshotCache.payload
  }
  const universe = await fetchUniverse()
  const codes = universe.funds.map((fund) => fund.code)

  let quoteSource: QuoteSource = 'eastmoney'
  let quoteSourceNote: string | null = null
  let quotes = new Map<string, QuoteRow>()
  try {
    quotes = await fetchEastmoneyQuotes(codes)
  } catch (eastmoneyError) {
    const eastmoneyReason = eastmoneyError instanceof Error ? eastmoneyError.message : String(eastmoneyError)
    quoteSource = 'tencent'
    quoteSourceNote = `东方财富行情接口不可用（${eastmoneyReason}），已改用腾讯公开行情，字段口径一致。`
    quotes = await fetchTencentQuotes(codes)
  }

  const rows = buildPremiumRows(universe.funds, quotes)
  const payload: SnapshotPayload = {
    generatedAt: new Date(now).toISOString(),
    quoteSource,
    quoteSourceNote,
    universeNavDate: universe.navDate,
    etfCount: universe.etfCount,
    excludedNonEtf: universe.excludedNonEtf,
    excludedOther: universe.excludedOther,
    rows,
  }
  snapshotCache = { at: now, payload }
  return payload
}

export type DetailPayload = {
  code: string
  name: string | null
  mechanism: 'qdii' | 'connect' | null
  fund: {
    fullName: string | null
    ftype: string | null
    purchaseStatus: string | null
    redeemStatus: string | null
    navLatest: number | null
    shortName?: string | null
  }
  history: {
    priceSource: 'eastmoney' | 'tencent'
    series: HistoryPoint[]
    firstDate: string | null
    lastDate: string | null
    navLastDate: string | null
    navLagDays: number | null
    navLagNote: string | null
  }
  notes: string[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

/** FundMNBaseInfo 档案：全名/类型/申赎状态。字段缺失按 null 处理，不猜。 */
async function fetchFundProfile(
  code: string,
): Promise<DetailPayload['fund'] & { shortName: string | null }> {
  const url =
    `https://fundmobapi.eastmoney.com/FundMNewApi/FundMNBaseInfo?FCODE=${code}` +
    '&deviceid=c9cu-etf-premium&plat=Iphone&product=EFund&version=6.2.8'
  const payload = await fetchJson(url)
  const datas = asRecord(asRecord(payload)?.Datas)
  const navLatest = Number(datas?.DWJZ)
  return {
    fullName: typeof datas?.FULLNAME === 'string' ? datas.FULLNAME : null,
    ftype: typeof datas?.FTYPE === 'string' ? datas.FTYPE : null,
    purchaseStatus: typeof datas?.SGZT === 'string' ? datas.SGZT : null,
    redeemStatus: typeof datas?.SHZT === 'string' ? datas.SHZT : null,
    navLatest: Number.isFinite(navLatest) && navLatest > 0 ? navLatest : null,
    shortName: typeof datas?.SHORTNAME === 'string' ? datas.SHORTNAME : null,
  }
}

async function fetchPriceHistory(
  code: string,
  startDate: string,
  endDate: string,
): Promise<{ closes: Array<{ date: string; close: number }>; source: 'eastmoney' | 'tencent' }> {
  const symbol = `${code.startsWith('5') ? 'sh' : 'sz'}${code}`
  try {
    const url =
      'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
      '?fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57' +
      '&ut=7eea3edcaed734bea9cbfc24409ed989&klt=101&fqt=0' +
      `&secid=${etfSecid(code)}&beg=${startDate.replaceAll('-', '')}&end=${endDate.replaceAll('-', '')}`
    const payload = await fetchJson(url)
    const data = asRecord(asRecord(payload)?.data)
    const closes = parseEastmoneyKlines(data?.klines)
    if (closes.length > 0) return { closes, source: 'eastmoney' }
    throw new UpstreamError('parse', '东财日线为空')
  } catch (eastmoneyError) {
    const url =
      `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${symbol},day,${startDate},${endDate},640,`
    const payload = await fetchJson(url)
    const closes = parseTencentKline(payload, symbol)
    if (closes.length === 0) {
      const reason = eastmoneyError instanceof Error ? eastmoneyError.message : String(eastmoneyError)
      throw new UpstreamError('history-price', `日线数据不可用（东财：${reason}；腾讯：返回为空）`)
    }
    return { closes, source: 'tencent' }
  }
}

async function fetchNavHistory(code: string, startDate: string): Promise<{
  navs: Array<{ date: string; nav: number }>
  purchaseStatus: string | null
  redeemStatus: string | null
}> {
  const referer = `https://fundf10.eastmoney.com/jjjz_${code}.html`
  const navs: Array<{ date: string; nav: number }> = []
  let purchaseStatus: string | null = null
  let redeemStatus: string | null = null
  let pageIndex = 1
  while (pageIndex <= LSJZ_MAX_PAGES) {
    const url =
      `https://api.fund.eastmoney.com/f10/lsjz?fundCode=${code}&pageIndex=${pageIndex}` +
      `&pageSize=${LSJZ_PAGE_SIZE}&startDate=${startDate}&endDate=2050-01-01&_=${Date.now()}`
    const parsed = parseLsjzPayload(await fetchJson(url, referer))
    navs.push(...parsed.navs)
    purchaseStatus = purchaseStatus ?? parsed.purchaseStatus
    redeemStatus = redeemStatus ?? parsed.redeemStatus
    const oldest = parsed.navs.length > 0 ? parsed.navs[0].date : null
    if (oldest && oldest <= startDate) break
    if (parsed.navs.length === 0 || navs.length >= parsed.totalCount) break
    pageIndex += 1
  }
  if (navs.length === 0) {
    throw new UpstreamError('history-nav', '净值接口没有返回任何单位净值')
  }
  navs.sort((a, b) => a.date.localeCompare(b.date))
  return { navs, purchaseStatus, redeemStatus }
}

const detailCache = new Map<string, { at: number; payload: DetailPayload }>()

export async function getDetail(
  code: string,
  days: number,
  hint?: { name?: string | null; mechanism?: 'qdii' | 'connect' | null },
): Promise<DetailPayload> {
  if (!isEtfCode(code)) {
    throw new UpstreamError('input', `代码 ${code} 不是场内 ETF`)
  }
  const cacheKey = `${code}:${days}`
  const cached = detailCache.get(cacheKey)
  if (cached && Date.now() - cached.at < DETAIL_TTL_MS) {
    return cached.payload
  }

  const today = new Date()
  const start = new Date(today.getTime() - days * 86400000)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  const startDate = iso(start)
  const endDate = iso(today)

  const [profileResult, priceResult] = await Promise.allSettled([
    fetchFundProfile(code),
    fetchPriceHistory(code, startDate, endDate),
  ])
  if (priceResult.status === 'rejected') {
    throw priceResult.reason instanceof Error ? priceResult.reason : new UpstreamError('history-price', '日线数据不可用')
  }
  const profile = profileResult.status === 'fulfilled' ? profileResult.value : null
  const navResult = await fetchNavHistory(code, startDate)

  const series = buildPremiumSeries(priceResult.value.closes, navResult.navs)
  if (series.length === 0) {
    throw new UpstreamError('history-join', '行情与净值没有可对齐的日期，无法重建溢价序列')
  }
  const navLastDate = navResult.navs[navResult.navs.length - 1].date
  const lagDays = navLagDays(navLastDate, endDate)
  const mechanism = hint?.mechanism ?? classifyMechanism(profile?.shortName ?? '', profile?.ftype ?? '') ?? null
  const notes: string[] = [
    '溢价率 = (当日收盘价 − 当日单位净值) / 当日单位净值，两列都是披露口径，不是盘中可成交价。',
    '单位净值在交易结束后才最终确定，QDII 通常 T+1 至 T+2 披露；本序列只能说明历史溢价幅度，不代表盘中可实时套利。',
    navResult.purchaseStatus
      ? `基金最新申购状态：${navResult.purchaseStatus}${navResult.redeemStatus ? `，赎回状态：${navResult.redeemStatus}` : ''}。申购受限时二级市场溢价可能长期存在。`
      : '未能取得申购/赎回状态。',
  ]
  const payload: DetailPayload = {
    code,
    name: hint?.name ?? profile?.shortName ?? null,
    mechanism,
    fund: {
      fullName: profile?.fullName ?? null,
      ftype: profile?.ftype ?? null,
      purchaseStatus: navResult.purchaseStatus,
      redeemStatus: navResult.redeemStatus,
      navLatest: navResult.navs[navResult.navs.length - 1].nav,
      shortName: profile?.shortName ?? null,
    },
    history: {
      priceSource: priceResult.value.source,
      series,
      firstDate: series[0].date,
      lastDate: series[series.length - 1].date,
      navLastDate,
      navLagDays: lagDays,
      navLagNote: lagDays == null ? null : describeNavLag(lagDays, mechanism ?? 'connect'),
    },
    notes,
  }
  detailCache.set(cacheKey, { at: Date.now(), payload })
  return payload
}

