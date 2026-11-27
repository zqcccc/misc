/**
 * 跨境 ETF 溢价监控：纯计算/分类/解析函数的确定性测试。
 * 运行：ts-node --project ./tsconfig-debug.json tests/etf-premium.test.ts
 * 夹具按 2026-11-24 实测的上游真实响应结构构造（见各断言旁的字段说明）。
 */
import * as assert from 'node:assert/strict'
import {
  buildPremiumRows,
  buildPremiumSeries,
  classifyMechanism,
  describeNavLag,
  filterRows,
  formatAmountCny,
  formatPrice,
  formatQuoteTime,
  formatSignedPercent,
  indexGroupLabel,
  indexGroupOf,
  isEtfCode,
  markGroupLowest,
  mechanismLabel,
  navLagDays,
  parseCnjyHtml,
  parseEastmoneyKlines,
  parseEastmoneyUlist,
  parseLsjzPayload,
  parseTencentKline,
  parseTencentQuoteText,
  premiumPct,
  quoteDateOf,
  type QuoteRow,
  type UniverseRow,
} from '../lib/etf-premium'

// ---------------------------------------------------------------- 溢价符号与缺失

assert.ok(Math.abs(premiumPct(2.528, 2.295)! - 10.1525) < 1e-4, '溢价为正：真实 513500 行情（2026-11-24）')
assert.ok(Math.abs(premiumPct(1.306, 1.3074)! + 0.1071) < 1e-4, '折价为负：真实 513660 行情')
assert.ok(premiumPct(2.528, 2.295)! > 0, '高 IOPV 偏离时符号必须为正')
assert.ok(premiumPct(2.295, 2.528)! < 0, '参数顺序颠倒时符号必须为负（折价）')
assert.equal(premiumPct(2.528, 0), null, 'IOPV 为 0 时不能输出 0 或无穷大')
assert.equal(premiumPct(2.528, null), null, 'IOPV 缺失 → null，不用 0 冒充')
assert.equal(premiumPct(null, 2.295), null, '价格缺失 → null')
assert.equal(premiumPct(Number.NaN, 2.295), null, 'NaN → null')
assert.equal(formatSignedPercent(null), '—', '缺失溢价展示为 —')
assert.equal(formatSignedPercent(10.149), '+10.15%', '正值带加号')
assert.equal(formatSignedPercent(-0.107), '-0.11%', '负值符号')
assert.equal(formatSignedPercent(0), '0.00%', '零不显示符号')

// ---------------------------------------------------------------- 机制与代码分类

assert.equal(isEtfCode('513500'), true, '沪 ETF 前缀 51')
assert.equal(isEtfCode('159941'), true, '深 ETF 前缀 159')
assert.equal(isEtfCode('561990'), true, '沪 ETF 前缀 56')
assert.equal(isEtfCode('501018'), false, 'LOF 501 排除')
assert.equal(isEtfCode('160323'), false, 'LOF 16x 排除')
assert.equal(isEtfCode('510300'), true, '境内 ETF 也匹配代码前缀（由类型规则排除跨境）')

assert.equal(classifyMechanism('标普500ETF博时', '指数型-海外股票'), 'qdii', '类型含海外 → QDII')
assert.equal(classifyMechanism('恒生ETF华夏', '指数型-海外股票'), 'qdii', '159920 是 QDII')
assert.equal(classifyMechanism('恒生ETF华夏', '指数型-股票'), 'connect', '同名 513660 是港股通，靠类型区分')
assert.equal(classifyMechanism('港股通科技ETF博时', '指数型-股票'), 'connect', '港股通名称 + 境内指数类型 → 港股通')
assert.equal(classifyMechanism('港股汽车ETF天弘', '指数型-股票'), 'connect', '港股名称也属港股通')
assert.equal(
  classifyMechanism('景顺长城标普中国A股', '指数型-股票'),
  null,
  '名称含境外指数字样但底层是 A 股 → 不纳入',
)
assert.equal(classifyMechanism('沪港深精选ETF', '指数型-股票'), null, '沪港深混合产品不纳入')
assert.equal(classifyMechanism('国债ETF国泰', '指数型-固收'), null, '固收 ETF 不纳入')
assert.equal(classifyMechanism('中证A500ETF', '指数型-股票'), null, '境内宽基不纳入')
assert.equal(mechanismLabel('qdii'), 'QDII')
assert.equal(mechanismLabel('connect'), '港股通')

// ---------------------------------------------------------------- 保守分组

assert.equal(indexGroupOf('513500'), 'sp500', '已核对代码进组')
assert.equal(indexGroupOf('159920'), 'hsi')
assert.equal(indexGroupOf('513660'), 'hsi', '同跟踪恒生指数，分组与机制无关')
assert.equal(indexGroupOf('999999'), null, '名单外代码必须 null，不猜')
assert.equal(indexGroupLabel('sp500'), '标普500')
assert.equal(indexGroupLabel('nope'), null, '未知组 key → null')

// ---------------------------------------------------------------- 组内低溢价选择

type MinimalRow = {
  indexKey: string | null
  premiumPct: number | null
  code: string
  isLowestPremiumInGroup?: boolean
}
function rowOf(code: string, indexKey: string | null, premiumPct: number | null): MinimalRow {
  return { code, indexKey, premiumPct }
}

const groupRows = [
  rowOf('513500', 'sp500', 10.15),
  rowOf('159612', 'sp500', 8.02),
  rowOf('159655', 'sp500', 9.11),
  rowOf('513170', 'hsCentralSoe', 5.0), // 单成员组：不应标记
  rowOf('513990', null, 1.0), // 未分组：不应标记
  rowOf('159941', 'ndx100', null), // 无溢价：组内只剩一只，不标记
]
markGroupLowest(groupRows)
assert.deepEqual(
  groupRows.map((row) => row.isLowestPremiumInGroup ?? false),
  [false, true, false, false, false, false],
  '同组至少两只可算溢价时，溢价最低者标记为组内低溢价',
)

const tieRows = [
  rowOf('159655', 'sp500', 3.3),
  rowOf('513500', 'sp500', 3.3),
]
markGroupLowest(tieRows)
assert.deepEqual(
  tieRows.filter((row) => row.isLowestPremiumInGroup).map((row) => row.code),
  ['159655'],
  '并列时按代码升序取第一只，保证确定性',
)

// ---------------------------------------------------------------- buildPremiumRows：合并行情、缺失原因

const funds = [
  { code: '513500', name: '标普500ETF博时', type: '指数型-海外股票', mechanism: 'qdii' as const },
  { code: '513660', name: '恒生ETF华夏', type: '指数型-股票', mechanism: 'connect' as const },
  { code: '513998', name: '示例港股通ETF', type: '指数型-股票', mechanism: 'connect' as const },
]
const quoteEntries: Array<[string, QuoteRow]> = [
  [
    '513500',
    {
      code: '513500',
      name: '标普500ETF博时',
      price: 2.528,
      prevClose: 2.455,
      changePct: 2.97,
      iopv: 2.295,
      amountCny: 283378174,
      quoteTimeText: '2026-11-24 16:14:51',
      navLatest: 2.2973,
    },
  ],
  [
    '513660',
    {
      code: '513660',
      name: '恒生ETF华夏',
      price: 1.306,
      prevClose: 1.318,
      changePct: -0.91,
      iopv: 1.3074,
      amountCny: null,
      quoteTimeText: '2026-11-24 16:14:59',
      navLatest: 1.3275,
    },
  ],
]
const quotes = new Map(quoteEntries)

const built = buildPremiumRows(funds, quotes)
assert.equal(built.length, 3)
const spRow = built.find((row) => row.code === '513500')!
assert.equal(spRow.indexLabel, '标普500')
assert.equal(spRow.mechanismLabel, 'QDII')
assert.equal(formatSignedPercent(spRow.premiumPct), '+10.15%')
const hsRow = built.find((row) => row.code === '513660')!
assert.equal(hsRow.indexLabel, '恒生指数')
assert.equal(hsRow.amountCny, null, '成交额缺失保留 null')
const unknownRow = built.find((row) => row.code === '513998')!
assert.equal(unknownRow.indexKey, null, '名单外代码在展示层也是未分组')
assert.equal(unknownRow.price, null)
assert.ok(unknownRow.missing.includes('场内价缺失'), '缺失要有可读原因')
assert.ok(unknownRow.missing.includes('IOPV缺失'))
assert.equal(formatSignedPercent(unknownRow.premiumPct), '—', '无法计算时展示 —')

// ---------------------------------------------------------------- 腾讯批量行情解析（字段序号来自真实响应）

/**
 * 按实测的腾讯字段序号构造记录：0 市场占位 / 1 名称 / 2 代码 / 3 最新价 / 4 昨收 /
 * 30 时间戳 / 31 涨跌额 / 32 涨跌幅 / 33 最高 / 57 成交额（万元）/
 * 78 IOPV / 79,80 辅助列 / 81 最新单位净值 / 82 币种。
 */
function tencentRecord(values: Record<number, string>): string {
  const fields = new Array<string>(88).fill('')
  for (const [index, value] of Object.entries(values)) {
    fields[Number(index)] = value
  }
  return `v_${values[2]}="${fields.join('~')}";`
}

const tencentFixture = [
  tencentRecord({
    1: '标普500ETF博时',
    2: '513500',
    3: '2.528',
    4: '2.455',
    30: '20261124161451',
    31: '0.073',
    32: '2.97',
    33: '2.543',
    57: '28337.8174',
    78: '2.2950',
    79: '5.77',
    80: '-0.04',
    81: '2.2973',
    82: 'CNY',
  }),
  tencentRecord({
    1: '纳指ETF广发',
    2: '159941',
    3: '1.560',
    4: '1.517',
    30: '20261124161418',
    31: '0.043',
    32: '2.83',
    33: '1.564',
    57: '11580.7897',
    78: '1.3368',
    79: '16.70',
    80: '-0.08',
    81: '0.0000',
    82: 'CNY',
  }),
  tencentRecord({ 1: '空数据', 2: '000000' }),
].join('')

const tencentRows = parseTencentQuoteText(tencentFixture)
assert.equal(tencentRows.length, 2, '缺字段的残缺记录要被跳过而不是产出垃圾行')
const parsed513500 = tencentRows[0]
assert.equal(parsed513500.code, '513500')
assert.equal(parsed513500.price, 2.528, '字段 3 是最新价')
assert.equal(parsed513500.prevClose, 2.455, '字段 4 是昨收')
assert.equal(parsed513500.changePct, 2.97, '字段 32 是涨跌幅')
assert.equal(parsed513500.amountCny, 283378174, '字段 57 是万元成交额 ×1e4')
assert.equal(parsed513500.iopv, 2.295, '字段 78 是 IOPV，与东财 f441 一致')
assert.equal(parsed513500.navLatest, 2.2973, '字段 81 是最新单位净值，与 lsjz DWJZ 一致')
assert.equal(formatQuoteTime(parsed513500.quoteTimeText), '2026-11-24 16:14:51', '字段 30 是行情时间戳')
assert.equal(quoteDateOf(parsed513500.quoteTimeText), '2026-11-24')
const parsed159941 = tencentRows[1]
assert.equal(parsed159941.iopv, 1.3368)
assert.equal(parsed159941.navLatest, null, '净值字段为 0 时视为缺失，不能当真实净值')

// ---------------------------------------------------------------- 东财 ulist 解析

const emUlistPayload = {
  rc: 0,
  data: {
    total: 2,
    diff: [
      { f2: 2.528, f3: 2.97, f6: 283378174, f12: '513500', f13: 1, f14: '标普500ETF博时', f124: 1795507911, f297: 20261124, f441: 2.295 },
      { f2: '-', f3: '-', f6: '-', f12: '513999', f13: 1, f14: '无效行ETF', f124: '-', f297: '-', f441: '-' },
    ],
  },
}
const emRows = parseEastmoneyUlist(emUlistPayload)
assert.equal(emRows.length, 2, '无效值解析为 null 而不是丢弃整行')
assert.equal(emRows[0].price, 2.528)
assert.equal(emRows[0].iopv, 2.295)
assert.equal(emRows[0].amountCny, 283378174)
assert.equal(formatQuoteTime(emRows[0].quoteTimeText), '2026-11-24 16:11:51', '东财 unix 秒按交易所时区展示')
assert.equal(emRows[1].price, null, '“-”占位解析为 null')
assert.equal(emRows[1].iopv, null)
assert.equal(parseEastmoneyUlist({ data: {} }).length, 0, '结构异常返回空数组，由上层报错')

// ---------------------------------------------------------------- cnjy 名单解析

const cnjyFixture = `
<table>
<tr><td>关注</td><td>比较</td><td>序号</td><td>基金代码</td><td>基金简称</td><td>类型</td><td>2026-11-23</td><td>2026-11-20</td></tr>
<tr><td></td><td></td><td>1</td><td>513500</td><td>标普500ETF博时行情吧档案</td><td>指数型-海外股票</td><td>2.2973</td><td>4.5946</td><td>2.2973</td><td>4.5946</td><td>0.11</td><td>+10.15%</td><td>2.528</td></tr>
<tr><td></td><td></td><td>2</td><td>513660</td><td>恒生ETF华夏行情吧档案</td><td>指数型-股票</td><td>1.3275</td><td>1.3300</td><td>1.3275</td><td>1.3300</td><td>-0.01</td><td>-0.91%</td><td>1.306</td></tr>
<tr><td></td><td></td><td>3</td><td>501018</td><td>南方原油LOF行情吧档案</td><td>指数型-海外股票</td><td>0.8</td><td>0.8</td><td>0.8</td><td>0.8</td><td>0</td><td>0%</td><td>0.9</td></tr>
</table>
`
const cnjyParsed = parseCnjyHtml(cnjyFixture)
assert.equal(cnjyParsed.navDate, '2026-11-23', '表头第一个日期作为名单基准日')
assert.equal(cnjyParsed.rows.length, 3, 'LOF 行也先解析出来，由分类规则排除')
assert.equal(cnjyParsed.rows[0].name, '标普500ETF博时', '行情吧档案后缀要剥掉')
const cnjyPicked = classifyMechanism(cnjyParsed.rows[0].name, cnjyParsed.rows[0].type)
assert.equal(cnjyPicked, 'qdii')
assert.equal(isEtfCode(cnjyParsed.rows[2].code), false, '501018 LOF 被代码规则排除')

// ---------------------------------------------------------------- lsjz 净值解析

const lsjzPayload = {
  TotalCount: 3,
  ErrCode: 0,
  Data: {
    LSJZList: [
      { FSRQ: '2026-11-24', DWJZ: '2.5280', SGZT: '暂停申购', SHZT: '场内卖出' },
      { FSRQ: '2026-11-23', DWJZ: '2.2973', SGZT: '暂停申购', SHZT: '场内卖出' },
      { FSRQ: '2026-11-22', DWJZ: '', SGZT: '暂停申购', SHZT: '场内卖出' },
    ],
  },
}
const lsjzParsed = parseLsjzPayload(lsjzPayload)
assert.deepEqual(
  lsjzParsed.navs.map((item) => item.date),
  ['2026-11-22', '2026-11-23', '2026-11-24'].slice(1),
  '空净值行剔除，剩余按日期升序',
)
assert.equal(lsjzParsed.navs[lsjzParsed.navs.length - 1].nav, 2.528)
assert.equal(lsjzParsed.purchaseStatus, '暂停申购', '最新披露的申购状态取自第一条')
assert.throws(() => parseLsjzPayload({ ErrCode: -999, Data: null }), /-999/, '上游错误码必须抛出而不是当成空数据')

// ---------------------------------------------------------------- 日线与溢价序列重建

const emKlines = [
  '2026-11-20,2.480,2.474,2.500,2.460,1095563,297502743.000',
  '2026-11-23,2.460,2.455,2.470,2.450,998000,250000000.000',
  '2026-11-24,2.510,2.528,2.543,2.518,1121066,283378174.000',
]
const emCloses = parseEastmoneyKlines(emKlines)
assert.equal(emCloses.length, 3)
assert.equal(emCloses[0].close, 2.474, '字段 2 是收盘价（不复权）')

const tencentKlinePayload = {
  data: {
    sh513500: {
      day: [
        ['2026-11-20', '2.480', '2.474', '2.500', '2.460', '1095563.000'],
        ['2026-11-23', '2.460', '2.455', '2.470', '2.450', '998000.000'],
        ['2026-11-24', '2.510', '2.528', '2.543', '2.518', '1121066.000'],
      ],
    },
  },
}
const tencentCloses = parseTencentKline(tencentKlinePayload, 'sh513500')
assert.equal(tencentCloses.length, 3)
assert.equal(tencentCloses[2].close, 2.528, '腾讯日线字段 2 也是收盘价')
assert.equal(parseTencentKline(tencentKlinePayload, 'sz159941').length, 0, '错误 symbol 返回空')

const navSeries = [
  { date: '2026-11-20', nav: 2.1938 },
  { date: '2026-11-23', nav: 2.2973 },
  // 11-24 净值尚未披露（QDII T+1/T+2），故意缺席
]
const series = buildPremiumSeries(tencentCloses, navSeries)
assert.deepEqual(
  series.map((point) => point.date),
  ['2026-11-20', '2026-11-23'],
  '有价无净值的交易日跳过，不插值',
)
assert.ok(Math.abs(series[0].premiumPct - ((2.474 - 2.1938) / 2.1938) * 100) < 1e-9, '溢价用当日收盘与当日净值')
assert.equal(series[0].close, 2.474)
assert.equal(series[0].nav, 2.1938)

// ---------------------------------------------------------------- 净值滞后

assert.equal(navLagDays('2026-11-23', '2026-11-24'), 1)
assert.equal(navLagDays('2026-11-24', '2026-11-24'), 0)
assert.equal(navLagDays(null, '2026-11-24'), null)
assert.ok(describeNavLag(1, 'qdii')!.includes('T+1'), '滞后说明要写清 QDII 披露节奏')
assert.ok(describeNavLag(3, 'connect')!.includes('3 天前'))

// ---------------------------------------------------------------- 过滤与排序

const filterBase = built
const queried = filterRows(filterBase, { query: '标普', groupKey: 'all', minAbsPremium: null, sort: 'code_asc' })
assert.deepEqual(queried.map((row) => row.code), ['513500'], '名称搜索命中')
assert.deepEqual(
  filterRows(filterBase, { query: '513660', groupKey: 'all', minAbsPremium: null, sort: 'code_asc' }).map((row) => row.code),
  ['513660'],
  '代码搜索命中',
)
assert.deepEqual(
  filterRows(filterBase, { query: '', groupKey: 'all', minAbsPremium: 5, sort: 'code_asc' }).map((row) => row.code),
  ['513500'],
  '阈值筛选把无法计算溢价的行排除掉（|—| 不算 ≥5%）',
)
assert.deepEqual(
  filterRows(filterBase, { query: '', groupKey: 'sp500', minAbsPremium: null, sort: 'code_asc' }).map((row) => row.code),
  ['513500'],
  '指数分组筛选',
)
const sortDesc = filterRows(filterBase, { query: '', groupKey: 'all', minAbsPremium: null, sort: 'premium_desc' })
assert.deepEqual(sortDesc.map((row) => row.code), ['513500', '513660', '513998'], '溢价降序，缺失排最后')
const sortAsc = filterRows(filterBase, { query: '', groupKey: 'all', minAbsPremium: null, sort: 'premium_asc' })
assert.deepEqual(sortAsc.map((row) => row.code), ['513660', '513500', '513998'], '溢价升序，缺失排最后')
const sortAmount = filterRows(filterBase, { query: '', groupKey: 'all', minAbsPremium: null, sort: 'amount_desc' })
assert.deepEqual(sortAmount.map((row) => row.code), ['513500', '513660', '513998'], '成交额降序，null 排最后')

// ---------------------------------------------------------------- 展示格式

assert.equal(formatPrice(null), '—')
assert.equal(formatPrice(2.528), '2.528')
assert.equal(formatAmountCny(283378174), '2.83亿')
assert.equal(formatAmountCny(95324394), '9532.4万')
assert.equal(formatAmountCny(null), '—')
assert.equal(formatQuoteTime('1795507911'), '2026-11-24 16:11:51', 'unix 秒转交易所时区')
assert.equal(formatQuoteTime('20261124161451'), '2026-11-24 16:14:51', '腾讯紧凑时间戳')
assert.equal(formatQuoteTime('abc'), 'abc', '无法识别时原样返回，不猜')
assert.equal(formatQuoteTime(null), null)

console.log('tests/etf-premium.test.ts 全部通过')
