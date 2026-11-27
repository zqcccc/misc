import * as assert from 'node:assert/strict'
import { GET } from '../app/api/profit-line/route'
import {
  HkCurrencyError,
  convertCnyEpsToHkd,
  fetchCnyToHkdRate,
  fetchHkCompanyProfile,
  prepareHkEps,
  resolveHkEpsCurrency,
} from '../app/api/profit-line/hk-currency'
import type { EpsRow } from '../app/api/profit-line/market-data'

type UpstreamSpec = {
  status?: number
  statusText?: string
  body?: unknown
  raw?: string
}

type FetchCall = { url: string; init?: RequestInit }

function stubResponse(spec: UpstreamSpec): Response {
  const status = spec.status ?? 200
  const payload =
    spec.raw !== undefined
      ? spec.raw
      : JSON.stringify(spec.body === undefined ? {} : spec.body)
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: spec.statusText ?? '',
    json: async () => JSON.parse(payload),
  } as unknown as Response
}

// 确定性上游桩：按 URL 正则返回固定响应，未覆盖的请求直接抛错，
// 保证测试不访问真实上游，且任何计划外的上游调用都会让测试失败。
function makeFetchStub(
  routes: Array<{ match: RegExp; spec: UpstreamSpec | Error }>,
) {
  const calls: FetchCall[] = []
  const stub: typeof fetch = async (input, init) => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.href
          : input.url
    calls.push({ url, init })
    for (const route of routes) {
      if (!route.match.test(url)) continue
      if (route.spec instanceof Error) throw route.spec
      return stubResponse(route.spec)
    }
    throw new Error(`测试桩未覆盖的上游请求: ${url}`)
  }
  return { calls, stub }
}

const PROFILE_H_SHARE = {
  zqzl: { zqlx: 'H股', mgmz: '1.00 CNY' },
  gszl: { zcd: '中国' },
}

const FX_BODY = {
  chart: { result: [{ meta: { regularMarketPrice: 1.25 } }] },
}

const TS_2026_03_27 = Math.floor(
  new Date('2026-03-27T00:00:00Z').getTime() / 1000,
)
const TS_2026_03_30 = Math.floor(
  new Date('2026-03-30T00:00:00Z').getTime() / 1000,
)

const HK_CHART_BODY = {
  chart: {
    result: [
      {
        meta: { regularMarketPrice: 305.25 },
        timestamp: [TS_2026_03_27, TS_2026_03_30],
        indicators: { quote: [{ close: [300.5, 305.25] }] },
        events: {},
      },
    ],
  },
}

const HK_QUARTER_ROWS = [
  { STD_REPORT_DATE: '2025-03-31 00:00:00', BASIC_EPS: 1.1, EPS_TTM: 4.4, SECURITY_NAME_ABBR: '测试股' },
  { STD_REPORT_DATE: '2025-06-30 00:00:00', BASIC_EPS: 1.2, EPS_TTM: 4.5, SECURITY_NAME_ABBR: '测试股' },
  { STD_REPORT_DATE: '2025-09-30 00:00:00', BASIC_EPS: 1.3, EPS_TTM: 4.6, SECURITY_NAME_ABBR: '测试股' },
  { STD_REPORT_DATE: '2025-12-31 00:00:00', BASIC_EPS: 1.4, EPS_TTM: 4.7, SECURITY_NAME_ABBR: '测试股' },
  { STD_REPORT_DATE: '2026-03-31 00:00:00', BASIC_EPS: 1.5, EPS_TTM: 4.8, SECURITY_NAME_ABBR: '测试股' },
]

const EPS_ROWS: EpsRow[] = [
  {
    date: '2025-12-31',
    quarter: '2025 Q4',
    eps: 1.2,
    ttmEps: 4.8,
    shareholderEquity: 1000,
    liabilities: 400,
    cash: 250,
  },
  {
    date: '2026-03-31',
    quarter: '2026 Q1',
    eps: 1.5,
    shareholderEquity: 1100,
    liabilities: 420,
    cash: 260,
  },
]

// 集成测试共用：替换全局 fetch；REDIS_URL 指向无效协议让缓存读写立即失败
//（不可达但格式合法的地址会让 node-redis 无限重连、请求永久挂起）。
// 失败路径的 GET 会在写缓存之前抛错，因此不会向任何 Redis 写入测试数据。
async function withStubbedUpstream(
  routes: Array<{ match: RegExp; spec: UpstreamSpec | Error }>,
  execute: (calls: FetchCall[]) => Promise<void>,
) {
  const { calls, stub } = makeFetchStub(routes)
  const originalFetch = globalThis.fetch
  const originalRedisUrl = process.env.REDIS_URL
  process.env.REDIS_URL = 'invalid://profit-line-test'
  globalThis.fetch = stub
  try {
    await execute(calls)
  } finally {
    globalThis.fetch = originalFetch
    if (originalRedisUrl === undefined) {
      delete process.env.REDIS_URL
    } else {
      process.env.REDIS_URL = originalRedisUrl
    }
  }
}

function hkUpstreamRoutes(
  profileSpec: UpstreamSpec,
  fxSpec: UpstreamSpec,
): Array<{ match: RegExp; spec: UpstreamSpec | Error }> {
  return [
    {
      match: /RPT_HKF10_FN_MAININDICATOR/,
      spec: { body: { result: { data: HK_QUARTER_ROWS } } },
    },
    { match: /RPT_HKF10_FN_BALANCE/, spec: { body: { result: { data: [] } } } },
    { match: /CompanyProfile\/PageAjax/, spec: profileSpec },
    { match: /CNYHKD=X/, spec: fxSpec },
    { match: /finance\/chart\/09999\.HK/, spec: { body: HK_CHART_BODY } },
  ]
}

async function run() {
  // ---- resolveHkEpsCurrency：币种判定 ----
  assert.equal(resolveHkEpsCurrency('01929', null), 'HKD')
  assert.equal(resolveHkEpsCurrency('01929', { zqzl: { zqlx: 'H股' } }), 'HKD')
  assert.equal(resolveHkEpsCurrency('00700', { zqzl: { zqlx: 'H股' } }), 'CNY')
  assert.equal(resolveHkEpsCurrency('00941', { zqzl: { zqlx: '红筹股' } }), 'CNY')
  assert.equal(
    resolveHkEpsCurrency('00388', { zqzl: { zqlx: '非H股' }, gszl: { zcd: '中国' } }),
    'HKD',
  )
  assert.equal(
    resolveHkEpsCurrency('00005', {
      zqzl: { zqlx: '非H股' },
      gszl: { zcd: 'United Kingdom 英国' },
    }),
    'HKD',
  )
  assert.equal(
    resolveHkEpsCurrency('00005', { zqzl: { zqlx: '非H股' }, gszl: { zcd: '英国' } }),
    'HKD',
  )
  assert.equal(
    resolveHkEpsCurrency('01810', {
      zqzl: { zqlx: '非H股' },
      gszl: { zcd: 'Cayman Islands 开曼群岛（英属）' },
    }),
    'CNY',
  )
  assert.equal(
    resolveHkEpsCurrency('01024', {
      zqzl: { zqlx: '非H股' },
      gszl: { zcd: 'Bermuda 百慕大' },
    }),
    'CNY',
  )
  assert.equal(resolveHkEpsCurrency('00700', {}), 'unknown')
  assert.equal(resolveHkEpsCurrency('00700', null), 'unknown')
  assert.equal(resolveHkEpsCurrency('00700', { zqzl: { zqlx: '未知类型' } }), 'unknown')

  // ---- fetchHkCompanyProfile：HTTPS 上游 + 响应结构校验 ----
  {
    const { calls, stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: PROFILE_H_SHARE } },
    ])
    const profile = await fetchHkCompanyProfile('00700', stub)
    assert.deepEqual(profile, PROFILE_H_SHARE)
    assert.equal(
      calls[0].url,
      'https://emweb.securities.eastmoney.com/PC_HKF10/CompanyProfile/PageAjax?code=00700',
    )
    assert.deepEqual(calls[0].init?.headers, {
      Accept: 'application/json',
      Referer: 'https://emweb.securities.eastmoney.com/',
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    })
  }
  {
    const { stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { status: 403, statusText: 'Forbidden' } },
    ])
    await assert.rejects(
      fetchHkCompanyProfile('00700', stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /资料请求失败/)
        assert.match(error.message, /403/)
        return true
      },
    )
  }
  {
    const { stub } = makeFetchStub([
      {
        match: /CompanyProfile\/PageAjax/,
        spec: { raw: '<!DOCTYPE html><html>403</html>' },
      },
    ])
    await assert.rejects(
      fetchHkCompanyProfile('00700', stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /资料请求失败/)
        return true
      },
    )
  }
  {
    const { stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: ['不是对象'] } },
    ])
    await assert.rejects(
      fetchHkCompanyProfile('00700', stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /资料结构异常/)
        return true
      },
    )
  }
  {
    const { stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: null } },
    ])
    await assert.rejects(
      fetchHkCompanyProfile('00700', stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /资料结构异常/)
        return true
      },
    )
  }

  // ---- fetchCnyToHkdRate：成功取数 + 失败必须抛错（绝不允许 1.08 兜底）----
  {
    const { calls, stub } = makeFetchStub([
      { match: /CNYHKD=X/, spec: { body: FX_BODY } },
    ])
    assert.equal(await fetchCnyToHkdRate(stub), 1.25)
    assert.equal(
      calls[0].url,
      'https://query2.finance.yahoo.com/v8/finance/chart/CNYHKD=X?range=5d&interval=1d',
    )
  }
  {
    const { stub } = makeFetchStub([
      {
        match: /CNYHKD=X/,
        spec: { status: 500, statusText: 'Internal Server Error' },
      },
    ])
    await assert.rejects(
      fetchCnyToHkdRate(stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /汇率请求失败/)
        assert.match(error.message, /500/)
        return true
      },
    )
  }
  for (const badBody of [
    { chart: { result: [{ meta: {} }] } },
    { chart: { result: [{ meta: { regularMarketPrice: '1.25' } }] } },
    { chart: { result: [{ meta: { regularMarketPrice: 0 } }] } },
    { chart: { result: [{ meta: { regularMarketPrice: -1.25 } }] } },
    { chart: { result: [] } },
    {},
  ]) {
    const { stub } = makeFetchStub([{ match: /CNYHKD=X/, spec: { body: badBody } }])
    await assert.rejects(
      fetchCnyToHkdRate(stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /汇率数据异常/)
        return true
      },
    )
  }

  // ---- convertCnyEpsToHkd：正常换算（与旧实现逐字段一致）----
  {
    const converted = convertCnyEpsToHkd(EPS_ROWS, 1.25)
    assert.equal(converted.length, 2)
    assert.ok(Math.abs(converted[0].eps - 1.5) < 1e-9)
    assert.ok(Math.abs(converted[0].ttmEps! - 6) < 1e-9)
    assert.equal(converted[0].date, '2025-12-31')
    assert.equal(converted[0].shareholderEquity, 1000)
    assert.equal(converted[0].liabilities, 400)
    assert.equal(converted[0].cash, 250)
    assert.equal(converted[0].quarter, '2025 Q4')
    assert.ok(Math.abs(converted[1].eps - 1.875) < 1e-9)
    assert.equal(converted[1].ttmEps, undefined)
    assert.equal(converted[1].shareholderEquity, 1100)
  }

  // ---- prepareHkEps：编排层 ----
  {
    // 白名单港股：完全不需要上游请求，数据原样返回
    const { calls, stub } = makeFetchStub([])
    const prepared = await prepareHkEps('01929', EPS_ROWS, stub)
    assert.deepEqual(prepared, { convertedQuarters: EPS_ROWS })
    assert.equal(calls.length, 0)
  }
  {
    // CNY 港股：资料 + 汇率都成功，按汇率折算
    const { calls, stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: PROFILE_H_SHARE } },
      { match: /CNYHKD=X/, spec: { body: FX_BODY } },
    ])
    const prepared = await prepareHkEps('02318', EPS_ROWS, stub)
    assert.equal(prepared.epsCurrency, 'CNY')
    assert.equal(prepared.fxRate, 1.25)
    assert.equal(prepared.convertedQuarters.length, 2)
    assert.ok(Math.abs(prepared.convertedQuarters[0].eps - 1.5) < 1e-9)
    assert.ok(Math.abs(prepared.convertedQuarters[0].ttmEps! - 6) < 1e-9)
    assert.ok(Math.abs(prepared.convertedQuarters[1].eps - 1.875) < 1e-9)
    assert.equal(prepared.convertedQuarters[1].ttmEps, undefined)
    assert.equal(calls.length, 2)
  }
  {
    // HKD 港股：资料确认无需折算，不请求汇率接口
    const { calls, stub } = makeFetchStub([
      {
        match: /CompanyProfile\/PageAjax/,
        spec: { body: { zqzl: { zqlx: '非H股' }, gszl: { zcd: '中国' } } },
      },
      { match: /CNYHKD=X/, spec: { body: FX_BODY } },
    ])
    const prepared = await prepareHkEps('00388', EPS_ROWS, stub)
    assert.deepEqual(prepared, { convertedQuarters: EPS_ROWS })
    assert.ok(!calls.some((call) => call.url.includes('CNYHKD=X')))
  }
  {
    // 资料请求失败：显式抛错，绝不按 CNY 兜底，也不请求汇率
    const { calls, stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: new Error('network down') },
      { match: /CNYHKD=X/, spec: { body: FX_BODY } },
    ])
    await assert.rejects(
      prepareHkEps('00700', EPS_ROWS, stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /资料请求失败/)
        return true
      },
    )
    assert.ok(!calls.some((call) => call.url.includes('CNYHKD=X')))
  }
  {
    // 资料缺证券类型字段：显式抛错
    const { stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: {} } },
    ])
    await assert.rejects(
      prepareHkEps('00700', EPS_ROWS, stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /缺少证券类型字段/)
        return true
      },
    )
  }
  {
    // 证券类型无法识别：显式抛错并带上类型值
    const { calls, stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: { zqzl: { zqlx: 'GEM' } } } },
      { match: /CNYHKD=X/, spec: { body: FX_BODY } },
    ])
    await assert.rejects(
      prepareHkEps('00700', EPS_ROWS, stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /无法确认港股 EPS 币种（证券类型：GEM）/)
        return true
      },
    )
    assert.ok(!calls.some((call) => call.url.includes('CNYHKD=X')))
  }
  {
    // 汇率请求失败：显式抛错，不产出折算数据
    const { stub } = makeFetchStub([
      { match: /CompanyProfile\/PageAjax/, spec: { body: PROFILE_H_SHARE } },
      {
        match: /CNYHKD=X/,
        spec: { status: 500, statusText: 'Internal Server Error' },
      },
    ])
    await assert.rejects(
      prepareHkEps('02318', EPS_ROWS, stub),
      (error: unknown) => {
        assert.ok(error instanceof HkCurrencyError)
        assert.match(error.message, /汇率请求失败/)
        return true
      },
    )
  }

  // ---- GET 集成：失败路径不返回貌似正常的估值，也不写缓存 ----
  await withStubbedUpstream(
    hkUpstreamRoutes(
      { status: 403, statusText: 'Forbidden' },
      { body: FX_BODY },
    ),
    async (calls) => {
      const response = await GET(
        new Request('http://localhost:3011/api/profit-line?symbol=09999'),
      )
      assert.equal(response.status, 502)
      const body = await response.json()
      assert.match(body.message, /无法确认 EPS 币种/)
      assert.equal(body.points, undefined)
      assert.ok(!calls.some((call) => call.url.includes('CNYHKD=X')))
    },
  )
  await withStubbedUpstream(
    hkUpstreamRoutes(
      { body: PROFILE_H_SHARE },
      { status: 500, statusText: 'Internal Server Error' },
    ),
    async (calls) => {
      const response = await GET(
        new Request('http://localhost:3011/api/profit-line?symbol=09999'),
      )
      assert.equal(response.status, 502)
      const body = await response.json()
      assert.match(body.message, /汇率请求失败/)
      assert.equal(body.points, undefined)
      assert.ok(!calls.some((call) => call.url.includes('finance/chart/09999')))
    },
  )
  await withStubbedUpstream(
    hkUpstreamRoutes({ body: { zqzl: { zqlx: 'GEM' } } }, { body: FX_BODY }),
    async () => {
      const response = await GET(
        new Request('http://localhost:3011/api/profit-line?symbol=09999'),
      )
      assert.equal(response.status, 502)
      const body = await response.json()
      assert.match(body.message, /无法确认港股 EPS 币种（证券类型：GEM）/)
      assert.equal(body.points, undefined)
    },
  )
}

run().then(
  () => {
    console.log('profit-line-hk tests passed')
    process.exit(0)
  },
  (error) => {
    console.error(error)
    process.exit(1)
  },
)
