/**
 * 跨境 ETF 溢价监控：纯计算与分类函数。
 *
 * 本文件只包含确定性逻辑（分类、分组、溢价计算、上游响应解析、排序过滤），
 * 不做任何网络请求。网络 I/O 在 app/api/etf-premium/upstream.ts。
 *
 * 机制识别口径（2026-11-24 用东方财富三处真实输出核对过）：
 * - 天天基金「场内交易基金」页 cnjy_dwjz.html 的「类型」列：指数型-海外股票 = QDII。
 * - 东方财富基金档案 FundMNBaseInfo 的 FTYPE 与 FULLNAME：逐只核对了全部候选
 *   （temp/etf_fund_info.json，193 只，0 失败）。同为"恒生ETF华夏"，
 *   159920 是 QDII（恒生），513660 是港股通（沪港通恒生）——名称关键词不能代替类型。
 * - 代码前缀 51/56/58/159 为场内 ETF；501/502/16x 为 LOF，不纳入。
 */

export type EtfMechanism = 'qdii' | 'connect'

export type EtfPremiumRow = {
  code: string
  name: string
  mechanism: EtfMechanism
  mechanismLabel: string
  indexKey: string | null
  indexLabel: string | null
  price: number | null
  prevClose: number | null
  changePct: number | null
  iopv: number | null
  premiumPct: number | null
  amountCny: number | null
  quoteTimeText: string | null
  quoteDate: string | null
  isStaleQuote?: boolean
  isLowestPremiumInGroup: boolean
  missing: string[]
}

export type UniverseRow = {
  code: string
  name: string
  type: string
}

export type ClassifiedFund = {
  code: string
  name: string
  type: string
  mechanism: EtfMechanism
}

export type QuoteRow = {
  code: string
  name: string | null
  price: number | null
  prevClose: number | null
  changePct: number | null
  iopv: number | null
  amountCny: number | null
  quoteTimeText: string | null
  navLatest: number | null
}

export type HistoryPoint = {
  date: string
  close: number
  nav: number
  premiumPct: number
}

export type SortKey =
  | 'premium_desc'
  | 'premium_asc'
  | 'premium_abs_desc'
  | 'amount_desc'
  | 'code_asc'

export type FilterState = {
  query: string
  groupKey: string | 'all'
  minAbsPremium: number | null
  sort: SortKey
}

/** 场内 ETF 代码前缀（SH 51/56/58，SZ 159）。LOF（501/502/16x）不在此列。 */
export function isEtfCode(code: string): boolean {
  return /^(51|56|58)\d{4}$|^159\d{3}$/.test(code)
}

/** 名称含这些关键词、且类型为境内指数股基的，按港股通处理。 */
const HK_NAME_PATTERN = /(恒生|港股|H股|香港)/

/** 这些名称虽然含境外指数字样，但底层是 A 股或跨市场混合产品，不纳入跨境。 */
const NON_CROSS_BORDER_NAME_PATTERN = /(A股|沪港深)/

export function mechanismLabel(mechanism: EtfMechanism): string {
  return mechanism === 'qdii' ? 'QDII' : '港股通'
}

/**
 * 机制分类，完全依据上游「类型」列与名称：
 * 1. 类型含「海外」或「QDII」→ QDII（东方财富的类型列，已逐只核对 FULLNAME）。
 * 2. 其余名称含港股关键词且类型为指数股基 → 港股通（非 QDII 的港股 ETF 只能经港股通投资）。
 * 3. 其余 → null，不纳入监控。
 */
export function classifyMechanism(name: string, type: string): EtfMechanism | null {
  if (type.includes('海外') || type.includes('QDII')) return 'qdii'
  if (
    !NON_CROSS_BORDER_NAME_PATTERN.test(name) &&
    HK_NAME_PATTERN.test(name) &&
    type.includes('指数型') &&
    type.includes('股票')
  ) {
    return 'connect'
  }
  return null
}

/** 从 cnjy 行筛出跨境 ETF。返回被排除的数量便于页面对账。 */
export function pickCrossBorderFunds(rows: UniverseRow[]): {
  funds: ClassifiedFund[]
  etfCount: number
  excludedNonEtf: number
  excludedOther: number
} {
  const funds: ClassifiedFund[] = []
  let etfCount = 0
  let excludedNonEtf = 0
  let excludedOther = 0
  for (const row of rows) {
    if (!isEtfCode(row.code)) {
      excludedNonEtf += 1
      continue
    }
    etfCount += 1
    const mechanism = classifyMechanism(row.name, row.type)
    if (!mechanism) {
      excludedOther += 1
      continue
    }
    funds.push({ code: row.code, name: row.name, type: row.type, mechanism })
  }
  return { funds, etfCount, excludedNonEtf, excludedOther }
}

/**
 * 指数分组：仅收录经 FundMNBaseInfo FULLNAME 逐只核对过的代码。
 * 核对方法：完整基金名中「交易型开放式」之前的跟踪指数表述完全一致才并入同组；
 * 口径存疑的组合（如"恒指港股通"与恒生指数）保持独立组，不猜测合并。
 * 名单外或未收录的代码一律返回 null（未分组），禁止按名称猜分组。
 */
export const ETF_INDEX_GROUPS: Record<string, { label: string; market: string }> = {
  sp500: { label: '标普500', market: '美股' },
  ndx100: { label: '纳斯达克100', market: '美股' },
  djia: { label: '道琼斯工业平均', market: '美股' },
  msciUs50: { label: 'MSCI美国50', market: '美股' },
  ndxBiotech: { label: '纳斯达克生物科技', market: '美股' },
  ndxTech: { label: '纳斯达克科技市值加权', market: '美股' },
  spBiotech: { label: '标普生物科技精选行业', market: '美股' },
  spOilGas: { label: '标普石油天然气勘探及生产精选行业', market: '美股' },
  spConsume: { label: '标普消费精选', market: '美股' },
  spNewChina: { label: '标普中国新经济行业', market: '全球' },
  dax: { label: '德国DAX', market: '欧洲' },
  cac40: { label: '法国CAC40', market: '欧洲' },
  nikkei225: { label: '日经225', market: '日本' },
  topix: { label: '东证指数TOPIX', market: '日本' },
  cnkrSemi: { label: '中证韩交所中韩半导体', market: '全球' },
  seaTech: { label: '新交所泛东南亚科技', market: '全球' },
  ftseApac: { label: '富时亚太精选', market: '全球' },
  saudi: { label: '沙特阿拉伯', market: '全球' },
  brazil: { label: '巴西伊博维斯帕', market: '全球' },
  web50: { label: '中证海外中国互联网50', market: '全球' },
  web30: { label: '中证海外中国互联网30', market: '全球' },
  webGlobal: { label: '中证全球中国互联网', market: '全球' },
  eduGlobal: { label: '中证全球中国教育主题', market: '全球' },
  hsi: { label: '恒生指数', market: '港股' },
  hsiConnect: { label: '恒指港股通', market: '港股' },
  hscei: { label: '恒生中国企业', market: '港股' },
  hsTech: { label: '恒生科技', market: '港股' },
  hsInternet: { label: '恒生互联网科技业', market: '港股' },
  hsHealth: { label: '恒生医疗保健', market: '港股' },
  hsBiotech: { label: '恒生生物科技', market: '港股' },
  hsConsume: { label: '恒生消费', market: '港股' },
  hsCentralSoe: { label: '恒生中国央企', market: '港股' },
  hsHkConnect50: { label: '恒生港股通50', market: '港股' },
  hsHkConnectDiv: { label: '恒生港股通红利', market: '港股' },
  hsHkConnectDivLowVol: { label: '恒生港股通红利低波动', market: '港股' },
  hsHkConnectCentralDiv: { label: '恒生港股通中国央企红利', market: '港股' },
  hsHkConnectTech: { label: '恒生港股通中国科技', market: '港股' },
  hsHkConnectTechTheme: { label: '恒生港股通科技主题', market: '港股' },
  hsHkConnectAuto: { label: '恒生港股通汽车主题', market: '港股' },
  hsHkConnectInno: { label: '恒生港股通创新药', market: '港股' },
  hsHkConnectInnoMed: { label: '恒生港股通创新药及医疗保健', market: '港股' },
  hsHkConnectInnerDiv: { label: '恒生港股通中国内地企业红利', market: '港股' },
  hsHkConnectNewEco: { label: '恒生港股通新经济', market: '港股' },
  hkTechCsi: { label: '中证港股通科技', market: '港股' },
  hkTechCni: { label: '国证港股通科技', market: '港股' },
  hkInternetCsi: { label: '中证港股通互联网', market: '港股' },
  hkInternetCni: { label: '国证港股通互联网', market: '港股' },
  hkDivCsi: { label: '中证港股通高股息投资', market: '港股' },
  hkDivLowVolCni: { label: '国证港股通红利低波动率', market: '港股' },
  hkLowVolSp: { label: '标普港股通低波红利', market: '港股' },
  hkCentralDivCsi: { label: '中证港股通央企红利', market: '港股' },
  hkConsumeCsi: { label: '中证港股通消费主题', market: '港股' },
  hkConsumeCni: { label: '国证港股通消费主题', market: '港股' },
  hkMedCsi: { label: '中证港股通医药卫生综合', market: '港股' },
  hkMedThemeCsi: { label: '中证港股通医疗主题', market: '港股' },
  hkInnoCni: { label: '国证港股通创新药', market: '港股' },
  hkInnoCsi: { label: '中证港股通创新药', market: '港股' },
  hk50Csi: { label: '中证港股通50', market: '港股' },
  hkItCsi: { label: '中证港股通信息技术综合', market: '港股' },
  hkFinanceInnerCsi: { label: '中证港股通内地金融', market: '港股' },
  hkFinanceServices: { label: '中证港股通金融服务', market: '港股' },
  hkNonBankCsi: { label: '中证港股通非银行金融主题', market: '港股' },
  hkSecuritiesCsi: { label: '中证香港证券投资主题', market: '港股' },
  hkSoeCsi: { label: '中证香港内地国有企业', market: '港股' },
  hkTechHongKongCsi: { label: '中证香港科技', market: '港股' },
  hk100Csi: { label: '中证港股通中国100', market: '港股' },
  hk100Ces: { label: 'CES港股通精选100', market: '港股' },
  shHkConnect: { label: '上证港股通', market: '港股' },
}

export const ETF_CODE_INDEX: Record<string, string> = {
  // 美股宽基与行业（QDII）
  '513500': 'sp500',
  '159612': 'sp500',
  '159655': 'sp500',
  '513650': 'sp500',
  '513100': 'ndx100',
  '159941': 'ndx100',
  '513300': 'ndx100',
  '159632': 'ndx100',
  '513110': 'ndx100',
  '513390': 'ndx100',
  '159659': 'ndx100',
  '159660': 'ndx100',
  '159513': 'ndx100',
  '159501': 'ndx100',
  '159696': 'ndx100',
  '513870': 'ndx100',
  '513400': 'djia',
  '513850': 'msciUs50',
  '159577': 'msciUs50',
  '513290': 'ndxBiotech',
  '159509': 'ndxTech',
  '159502': 'spBiotech',
  '159518': 'spOilGas',
  '513350': 'spOilGas',
  '159529': 'spConsume',
  '159822': 'spNewChina',
  // 欧洲（QDII）
  '513030': 'dax',
  '159561': 'dax',
  '513080': 'cac40',
  // 日本（QDII）
  '513000': 'nikkei225',
  '513520': 'nikkei225',
  '159866': 'nikkei225',
  '513880': 'nikkei225',
  '513800': 'topix',
  // 亚太与新兴市场（QDII）
  '513310': 'cnkrSemi',
  '513730': 'seaTech',
  '159687': 'ftseApac',
  '159329': 'saudi',
  '159100': 'brazil',
  // 中概（QDII）
  '513050': 'web50',
  '159605': 'web30',
  '159607': 'web30',
  '513220': 'webGlobal',
  '513360': 'eduGlobal',
  // 恒生系列
  '513600': 'hsi',
  '513210': 'hsi',
  '159920': 'hsi',
  '513660': 'hsi',
  '159271': 'hsi',
  '159318': 'hsiConnect',
  '159312': 'hsiConnect',
  '159365': 'hsiConnect',
  '510900': 'hscei',
  '159850': 'hscei',
  '159954': 'hscei',
  '159960': 'hscei',
  '513260': 'hsTech',
  '513010': 'hsTech',
  '159742': 'hsTech',
  '513180': 'hsTech',
  '513580': 'hsTech',
  '159741': 'hsTech',
  '513130': 'hsTech',
  '159740': 'hsTech',
  '513380': 'hsTech',
  '159202': 'hsInternet',
  '159688': 'hsInternet',
  '513330': 'hsInternet',
  '159303': 'hsHealth',
  '159557': 'hsHealth',
  '513060': 'hsHealth',
  '159615': 'hsBiotech',
  '513280': 'hsBiotech',
  '513930': 'hsBiotech',
  '159169': 'hsBiotech',
  '159130': 'hsBiotech',
  '159105': 'hsBiotech',
  '159132': 'hsBiotech',
  '159102': 'hsBiotech',
  '159699': 'hsConsume',
  '513970': 'hsConsume',
  '513170': 'hsCentralSoe',
  // 恒生港股通系列
  '159109': 'hsHkConnect50',
  '513690': 'hsHkConnectDiv',
  '513950': 'hsHkConnectDivLowVol',
  '159545': 'hsHkConnectDivLowVol',
  '513920': 'hsHkConnectCentralDiv',
  '159143': 'hsHkConnectCentralDiv',
  '513160': 'hsHkConnectTech',
  '159010': 'hsHkConnectTechTheme',
  '159015': 'hsHkConnectTechTheme',
  '159135': 'hsHkConnectTechTheme',
  '159152': 'hsHkConnectTechTheme',
  '159262': 'hsHkConnectTechTheme',
  '159120': 'hsHkConnectTechTheme',
  '159239': 'hsHkConnectAuto',
  '159186': 'hsHkConnectAuto',
  '159028': 'hsHkConnectAuto',
  '159121': 'hsHkConnectAuto',
  '159316': 'hsHkConnectInno',
  '159506': 'hsHkConnectInnoMed',
  '159726': 'hsHkConnectInnerDiv',
  '513320': 'hsHkConnectNewEco',
  // 港股通指数系列（非 QDII）
  '513150': 'hkTechCsi',
  '159269': 'hkTechCsi',
  '513860': 'hkTechCsi',
  '513020': 'hkTechCsi',
  '159751': 'hkTechCsi',
  '159191': 'hkTechCni',
  '159251': 'hkTechCni',
  '159101': 'hkTechCni',
  '159125': 'hkTechCni',
  '159128': 'hkTechCni',
  '159636': 'hkTechCni',
  '159040': 'hkInternetCsi',
  '513040': 'hkInternetCsi',
  '159179': 'hkInternetCsi',
  '159792': 'hkInternetCsi',
  '513770': 'hkInternetCsi',
  '159568': 'hkInternetCsi',
  '513720': 'hkInternetCsi',
  '159089': 'hkInternetCni',
  '159170': 'hkInternetCni',
  '159280': 'hkInternetCni',
  '159302': 'hkDivCsi',
  '159331': 'hkDivCsi',
  '513820': 'hkDivCsi',
  '159127': 'hkDivCsi',
  '159277': 'hkDivCsi',
  '513830': 'hkDivCsi',
  '513530': 'hkDivCsi',
  '159569': 'hkDivLowVolCni',
  '159117': 'hkLowVolSp',
  '159118': 'hkLowVolSp',
  '159220': 'hkLowVolSp',
  '513630': 'hkLowVolSp',
  '513910': 'hkCentralDivCsi',
  '159333': 'hkCentralDivCsi',
  '159266': 'hkCentralDivCsi',
  '159281': 'hkCentralDivCsi',
  '513070': 'hkConsumeCsi',
  '513230': 'hkConsumeCsi',
  '513590': 'hkConsumeCsi',
  '159735': 'hkConsumeCsi',
  '159265': 'hkConsumeCni',
  '159268': 'hkConsumeCni',
  '159285': 'hkConsumeCni',
  '159245': 'hkConsumeCni',
  '159776': 'hkMedCsi',
  '513200': 'hkMedCsi',
  '159718': 'hkMedCsi',
  '513700': 'hkMedCsi',
  '159137': 'hkMedCsi',
  '159366': 'hkMedThemeCsi',
  '513620': 'hkMedThemeCsi',
  '159167': 'hkMedThemeCsi',
  '159570': 'hkInnoCni',
  '159217': 'hkInnoCni',
  '159286': 'hkInnoCni',
  '159297': 'hkInnoCni',
  '159567': 'hkInnoCni',
  '513780': 'hkInnoCsi',
  '159711': 'hk50Csi',
  '159712': 'hk50Csi',
  '513550': 'hk50Csi',
  '159126': 'hk50Csi',
  '159198': 'hkItCsi',
  '159196': 'hkItCsi',
  '159047': 'hkItCsi',
  '159185': 'hkItCsi',
  '513240': 'hkItCsi',
  '159131': 'hkItCsi',
  '513190': 'hkFinanceInnerCsi',
  '159091': 'hkFinanceInnerCsi',
  '513140': 'hkFinanceServices',
  '513750': 'hkNonBankCsi',
  '513090': 'hkSecuritiesCsi',
  '159519': 'hkSoeCsi',
  '513810': 'hkSoeCsi',
  '159747': 'hkTechHongKongCsi',
  '159750': 'hkTechHongKongCsi',
  '159788': 'hk100Csi',
  '513900': 'hk100Ces',
  '513990': 'shHkConnect',
}

/** 保守取组：名单外一律 null。 */
export function indexGroupOf(code: string): string | null {
  return ETF_CODE_INDEX[code] ?? null
}

export function indexGroupLabel(key: string): string | null {
  return ETF_INDEX_GROUPS[key]?.label ?? null
}

/** 溢价率（%）：(场内价 - IOPV) / IOPV × 100。任一缺失或非正返回 null，绝不用 0 冒充。 */
export function premiumPct(price: number | null, iopv: number | null): number | null {
  if (price == null || iopv == null) return null
  if (!Number.isFinite(price) || !Number.isFinite(iopv)) return null
  if (price <= 0 || iopv <= 0) return null
  return ((price - iopv) / iopv) * 100
}

function toNumber(value: unknown): number | null {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/**
 * 组内相对低溢价载体：同组（indexKey 相同）内至少 2 只可计算溢价时，
 * 溢价率最低的那只标记为 true；并列时取排序后的第一只，保证确定性。
 */
export function markGroupLowest<
  T extends {
    indexKey: string | null
    premiumPct: number | null
    code: string
    isLowestPremiumInGroup?: boolean
  },
>(rows: T[]): void {
  const groups = new Map<string, T[]>()
  for (const row of rows) {
    if (!row.indexKey || row.premiumPct == null) continue
    const list = groups.get(row.indexKey)
    if (list) list.push(row)
    else groups.set(row.indexKey, [row])
  }
  const groupLists = Array.from(groups.values())
  for (const list of groupLists) {
    if (list.length < 2) continue
    const sorted = [...list].sort((a, b) => a.premiumPct! - b.premiumPct! || a.code.localeCompare(b.code))
    sorted[0].isLowestPremiumInGroup = true
  }
}

/** 为一组合并后的行补齐展示字段（分组、溢价、缺失说明），返回可排序的完整行。 */
export function buildPremiumRows(
  funds: ClassifiedFund[],
  quotes: Map<string, QuoteRow>,
): EtfPremiumRow[] {
  const rows: EtfPremiumRow[] = funds.map((fund) => {
    const quote = quotes.get(fund.code)
    const price = quote?.price ?? null
    const iopv = quote?.iopv ?? null
    const premium = premiumPct(price, iopv)
    const missing: string[] = []
    if (price == null) missing.push('场内价缺失')
    if (iopv == null) missing.push('IOPV缺失')
    if (premium == null && price != null && iopv != null) missing.push('数值无效')
    return {
      code: fund.code,
      name: quote?.name || fund.name,
      mechanism: fund.mechanism,
      mechanismLabel: mechanismLabel(fund.mechanism),
      indexKey: indexGroupOf(fund.code),
      indexLabel: indexGroupOf(fund.code) ? indexGroupLabel(indexGroupOf(fund.code)!) : null,
      price,
      prevClose: quote?.prevClose ?? null,
      changePct: quote?.changePct ?? null,
      iopv,
      premiumPct: premium,
      amountCny: quote?.amountCny ?? null,
      quoteTimeText: formatQuoteTime(quote?.quoteTimeText ?? null),
      quoteDate: quoteDateOf(quote?.quoteTimeText ?? null),
      isLowestPremiumInGroup: false,
      missing,
    }
  })
  markGroupLowest(rows)
  return rows
}

export const UNGROUPED_KEY = 'ungrouped'
export const UNGROUPED_LABEL = '未分组'

export function groupCounts(rows: EtfPremiumRow[]): Array<{
  key: string
  label: string
  market: string
  count: number
}> {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const key = row.indexKey ?? UNGROUPED_KEY
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  const entries = Array.from(counts.entries()).map(([key, count]) => {
    if (key === UNGROUPED_KEY) {
      return { key, label: UNGROUPED_LABEL, market: '', count }
    }
    const meta = ETF_INDEX_GROUPS[key]
    return { key, label: meta?.label ?? key, market: meta?.market ?? '', count }
  })
  entries.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'zh-Hans'))
  return entries
}

/** 名称/代码包含查询词（不区分大小写）。 */
export function matchesQuery(row: Pick<EtfPremiumRow, 'code' | 'name'>, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return row.code.includes(q) || row.name.toLowerCase().includes(q)
}

export function filterRows(rows: EtfPremiumRow[], filter: FilterState): EtfPremiumRow[] {
  let result = rows.filter((row) => {
    if (!matchesQuery(row, filter.query)) return false
    if (filter.groupKey !== 'all' && (row.indexKey ?? UNGROUPED_KEY) !== filter.groupKey) return false
    if (filter.minAbsPremium != null) {
      if (row.premiumPct == null) return false
      if (Math.abs(row.premiumPct) < filter.minAbsPremium) return false
    }
    return true
  })
  const premium = (row: EtfPremiumRow) => row.premiumPct
  const tieBreak = (a: EtfPremiumRow, b: EtfPremiumRow) => a.code.localeCompare(b.code)
  switch (filter.sort) {
    case 'premium_desc':
      result = result.sort(
        (a, b) => (premium(b) ?? -Infinity) - (premium(a) ?? -Infinity) || tieBreak(a, b),
      )
      break
    case 'premium_asc':
      result = result.sort(
        (a, b) => (premium(a) ?? Infinity) - (premium(b) ?? Infinity) || tieBreak(a, b),
      )
      break
    case 'premium_abs_desc':
      result = result.sort(
        (a, b) => Math.abs(premium(b) ?? -1) - Math.abs(premium(a) ?? -1) || tieBreak(a, b),
      )
      break
    case 'amount_desc':
      result = result.sort((a, b) => (b.amountCny ?? -1) - (a.amountCny ?? -1) || tieBreak(a, b))
      break
    case 'code_asc':
      result = result.sort(tieBreak)
      break
  }
  return result
}

export function formatSignedPercent(value: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}%`
}

export function formatPrice(value: number | null, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return value.toFixed(digits)
}

export function formatAmountCny(value: number | null): string {
  if (value == null || !Number.isFinite(value) || value <= 0) return '—'
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (value >= 1e4) return `${(value / 1e4).toFixed(1)}万`
  return value.toFixed(0)
}

/** 行情时间统一按交易所时区（Asia/Shanghai）展示，避免服务器时区影响口径。 */
const SHANGHAI_TIME_FORMATTER = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

function shanghaiDateTime(ms: number): string {
  return SHANGHAI_TIME_FORMATTER.format(new Date(ms)).replace('T', ' ')
}

/** 行情时间展示：腾讯 20261124161451 → 2026-11-24 16:14:51；东财 unix 秒 → 同格式。 */
export function formatQuoteTime(raw: string | null): string | null {
  if (!raw) return null
  const compact = raw.replace(/\D/g, '')
  if (compact.length >= 14) {
    return `${compact.slice(0, 4)}-${compact.slice(4, 6)}-${compact.slice(6, 8)} ${compact.slice(8, 10)}:${compact.slice(10, 12)}:${compact.slice(12, 14)}`
  }
  if (/^\d{10}$/.test(compact)) {
    return shanghaiDateTime(Number(compact) * 1000)
  }
  if (/^\d{13}$/.test(compact)) {
    return shanghaiDateTime(Number(compact))
  }
  return raw
}

/** 行情时间对应的交易日（YYYY-MM-DD），用于标记过期行情。 */
export function quoteDateOf(raw: string | null): string | null {
  const text = formatQuoteTime(raw)
  if (!text) return null
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(0, 10) : null
}

/** 东方财富 cnjy_dwjz.html（GBK 解码后的文本）→ 表格行与净值基准日。 */
export function parseCnjyHtml(html: string): { navDate: string | null; rows: UniverseRow[] } {
  const rows: UniverseRow[] = []
  let navDate: string | null = null
  const trMatches = Array.from(html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g))
  for (const trMatch of trMatches) {
    const cells = Array.from(trMatch[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)).map((cell) =>
      cell[1]
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ')
        .trim(),
    )
    if (!navDate) {
      for (const cell of cells) {
        const m = cell.match(/^(\d{4})-(\d{2})-(\d{2})$/)
        if (m) {
          navDate = `${m[1]}-${m[2]}-${m[3]}`
          break
        }
      }
    }
    if (cells.length >= 6 && /^\d{6}$/.test(cells[3] ?? '')) {
      const name = (cells[4] ?? '').replace(/行情吧档案$/, '').trim()
      if (name) rows.push({ code: cells[3], name, type: cells[5] ?? '' })
    }
  }
  return { navDate, rows }
}

/**
 * 腾讯批量行情（qt.gtimg.cn，GBK 解码后的文本）。
 * 字段：1 名称 / 2 代码 / 3 最新价 / 4 昨收 / 30 时间戳 / 32 涨跌幅% /
 * 57 成交额（万元）/ 78 IOPV实时估值 / 81 最新单位净值。
 * 已与东方财富 f441/IOPV、lsjz/DWJZ 交叉核对一致（2026-11-24，513500）。
 */
export function parseTencentQuoteText(text: string): QuoteRow[] {
  const rows: QuoteRow[] = []
  for (const record of text.split(';')) {
    const start = record.indexOf('="')
    if (start < 0) continue
    const fields = record.slice(start + 2).split('~')
    const code = fields[2]
    if (code == null || !isEtfCode(code)) continue
    const amountWan = toNumber(fields[57])
    const nav = toNumber(fields[81])
    const iopvRaw = toNumber(fields[78])
    rows.push({
      code,
      name: fields[1] ? fields[1].trim() : null,
      price: toNumber(fields[3]),
      prevClose: toNumber(fields[4]),
      changePct: toNumber(fields[32]),
      iopv: iopvRaw != null && iopvRaw > 0 ? iopvRaw : null,
      amountCny: amountWan != null && amountWan > 0 ? amountWan * 1e4 : null,
      quoteTimeText: fields[30] ?? null,
      navLatest: nav != null && nav > 0 ? nav : null,
    })
  }
  return rows
}

/** 未知来源 JSON 的窄化读取：仅当它是普通对象时返回，供上游响应解析使用。 */
function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

/** 东方财富 push2 ulist.np/get 批量行情。f2 最新价 / f3 涨跌幅 / f6 成交额 / f441 IOPV / f124 时间戳。 */
export function parseEastmoneyUlist(payload: unknown): QuoteRow[] {
  const root = asRecord(payload)
  const data = root ? asRecord(root.data) : null
  const diff = data?.diff
  if (!Array.isArray(diff)) return []
  const rows: QuoteRow[] = []
  for (const rawItem of diff) {
    const item = asRecord(rawItem)
    if (!item) continue
    const code = typeof item.f12 === 'string' ? item.f12 : String(item.f12 ?? '')
    if (!/^\d{6}$/.test(code)) continue
    const iopvRaw = toNumber(item.f441)
    const timestamp = toNumber(item.f124)
    rows.push({
      code,
      name: typeof item.f14 === 'string' ? item.f14 : null,
      price: toNumber(item.f2),
      prevClose: null,
      changePct: toNumber(item.f3),
      iopv: iopvRaw != null && iopvRaw > 0 ? iopvRaw : null,
      amountCny: toNumber(item.f6),
      quoteTimeText: timestamp != null ? String(timestamp) : null,
      navLatest: null,
    })
  }
  return rows
}

/** 天天基金 lsjz 历史净值。DWJZ 为单位净值；返回按日期升序排列。 */
export function parseLsjzPayload(payload: unknown): {
  navs: Array<{ date: string; nav: number }>
  totalCount: number
  purchaseStatus: string | null
  redeemStatus: string | null
} {
  const body = asRecord(payload)
  const errCode = body?.ErrCode
  if (errCode != null && errCode !== 0) {
    throw new Error(`lsjz 返回错误码 ${errCode}`)
  }
  const dataRecord = asRecord(body?.Data)
  const list = dataRecord?.LSJZList
  if (!Array.isArray(list)) {
    throw new Error('lsjz 响应缺少 LSJZList')
  }
  const navs: Array<{ date: string; nav: number }> = []
  let purchaseStatus: string | null = null
  let redeemStatus: string | null = null
  for (const item of list) {
    const date = item.FSRQ ?? ''
    const nav = toNumber(item.DWJZ)
    if (/^\d{4}-\d{2}-\d{2}$/.test(date) && nav != null && nav > 0) {
      navs.push({ date, nav })
    }
    // LSJZList 按日期倒序，第一条即最新披露口径
    if (!purchaseStatus && item.SGZT) purchaseStatus = item.SGZT
    if (!redeemStatus && item.SHZT) redeemStatus = item.SHZT
  }
  navs.sort((a, b) => a.date.localeCompare(b.date))
  const totalCount = typeof body?.TotalCount === 'number' ? body.TotalCount : navs.length
  return { navs, totalCount, purchaseStatus, redeemStatus }
}

/** 东方财富 push2his 日线（fields2 含 f51 日期、f53 收盘，fqt=0 不复权）。 */
export function parseEastmoneyKlines(klines: unknown): Array<{ date: string; close: number }> {
  if (!Array.isArray(klines)) return []
  const out: Array<{ date: string; close: number }> = []
  for (const raw of klines) {
    if (typeof raw !== 'string') continue
    const parts = raw.split(',')
    const date = parts[0] ?? ''
    const close = toNumber(parts[2])
    if (/^\d{4}-\d{2}-\d{2}$/.test(date) && close != null && close > 0) {
      out.push({ date, close })
    }
  }
  return out
}

/** 腾讯 ifzq 日线（不复权）：data[<symbol>].day = [date, open, close, high, low, volume]。 */
export function parseTencentKline(payload: unknown, symbol: string): Array<{ date: string; close: number }> {
  const root = asRecord(payload)
  const data = root ? asRecord(root.data) : null
  const symbolEntry = data ? asRecord(data[symbol]) : null
  const rows = symbolEntry?.day
  if (!Array.isArray(rows)) return []
  const out: Array<{ date: string; close: number }> = []
  for (const row of rows) {
    const date = typeof row?.[0] === 'string' ? row[0] : ''
    const close = toNumber(Array.isArray(row) ? row[2] : undefined)
    if (/^\d{4}-\d{2}-\d{2}$/.test(date) && close != null && close > 0) {
      out.push({ date, close })
    }
  }
  return out
}

/**
 * 价格与单位净值按日期对齐重建溢价序列。
 * 两边都是"当日"口径：收盘价来自行情 K 线（不复权），单位净值来自基金公司当日披露值。
 * 交易日有价无净值（如净值未披露/停牌日）会被跳过，不做插值、不重述。
 */
export function buildPremiumSeries(
  closes: Array<{ date: string; close: number }>,
  navs: Array<{ date: string; nav: number }>,
): HistoryPoint[] {
  const navByDate = new Map(navs.map((item) => [item.date, item.nav]))
  const points: HistoryPoint[] = []
  for (const { date, close } of closes) {
    const nav = navByDate.get(date)
    if (nav == null || nav <= 0 || close <= 0) continue
    const premium = ((close - nav) / nav) * 100
    if (!Number.isFinite(premium)) continue
    points.push({ date, close, nav, premiumPct: premium })
  }
  points.sort((a, b) => a.date.localeCompare(b.date))
  return points
}

/** 净值披露滞后（日历日）：最新净值日期距今多少天。 */
export function navLagDays(navLastDate: string | null, todayIso: string): number | null {
  if (!navLastDate || !/^\d{4}-\d{2}-\d{2}$/.test(todayIso)) return null
  const navTime = Date.parse(`${navLastDate}T00:00:00Z`)
  const nowTime = Date.parse(`${todayIso}T00:00:00Z`)
  if (!Number.isFinite(navTime) || !Number.isFinite(nowTime)) return null
  return Math.max(0, Math.round((nowTime - navTime) / 86400000))
}

/** 净值滞后天数 → 可解释文字。 */
export function describeNavLag(lagDays: number | null, mechanism: EtfMechanism): string | null {
  if (lagDays == null) return null
  if (lagDays === 0) return '最新单位净值披露于今日（盘后更新前为上一交易日口径）。'
  if (lagDays === 1) {
    return mechanism === 'qdii'
      ? '最新单位净值披露于 1 天前，QDII 净值通常 T+1 至 T+2 才公布，属正常披露节奏。'
      : '最新单位净值披露于 1 天前。'
  }
  return `最新单位净值披露于 ${lagDays} 天前${
    mechanism === 'qdii' ? '，QDII 净值通常 T+1 至 T+2 公布；更久未更新需注意节假日差异' : ''
  }。`
}
