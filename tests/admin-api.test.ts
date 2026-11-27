import * as assert from 'node:assert/strict'
import { guardAdminRequest, readJsonBody } from '../lib/admin-api'

const ADMIN_TOKEN = ['admin', 'test', 'token-42'].join('-')
const REQUEST_URL = 'http://localhost/api/test'
// 每次进程内运行生成唯一路由 ID，避免与历史限流桶共享状态
const RATE_ROUTE_ID = `admin-api-test:rate:${Date.now()}`
const MAX_BODY_BYTES = 1024 * 1024

function makeRequest(
  init: {
    method?: string
    headers?: Record<string, string>
    body?: string
  } = {},
): Request {
  return new Request(REQUEST_URL, {
    method: init.method ?? 'POST',
    headers: init.headers,
    body: init.body,
  })
}

function authorizedRequest(headers: Record<string, string> = {}): Request {
  return makeRequest({
    headers: { authorization: `Bearer ${ADMIN_TOKEN}`, ...headers },
  })
}

async function withAdminToken(execute: () => Promise<void>) {
  const originalToken = process.env.ADMIN_API_TOKEN
  process.env.ADMIN_API_TOKEN = ADMIN_TOKEN
  try {
    await execute()
  } finally {
    if (originalToken !== undefined) {
      process.env.ADMIN_API_TOKEN = originalToken
    } else {
      delete process.env.ADMIN_API_TOKEN
    }
  }
}

async function run() {
  // ---- 未配置 ADMIN_API_TOKEN：fail-closed 503，且响应不回显 token ----
  const originalToken = process.env.ADMIN_API_TOKEN
  delete process.env.ADMIN_API_TOKEN
  try {
    const notConfigured = guardAdminRequest(makeRequest(), 'admin-api-test')
    assert.equal(notConfigured?.status, 503)
    if (notConfigured) {
      assert.equal((await notConfigured.text()).includes(ADMIN_TOKEN), false)
    }
  } finally {
    if (originalToken !== undefined) {
      process.env.ADMIN_API_TOKEN = originalToken
    }
  }

  await withAdminToken(async () => {
    // ---- 错误 token：401；缺少 Authorization 头同样 401；响应不回显 token ----
    const wrongToken = guardAdminRequest(
      makeRequest({ headers: { authorization: 'Bearer wrong-token' } }),
      'admin-api-test',
    )
    assert.equal(wrongToken?.status, 401)
    if (wrongToken) {
      assert.equal((await wrongToken.text()).includes(ADMIN_TOKEN), false)
    }
    const noHeader = guardAdminRequest(makeRequest(), 'admin-api-test')
    assert.equal(noHeader?.status, 401)

    // ---- 正确 token：放行 ----
    assert.equal(
      guardAdminRequest(authorizedRequest(), 'admin-api-test'),
      null,
    )

    // ---- Content-Length 超限：413 ----
    const oversize = guardAdminRequest(
      authorizedRequest({ 'content-length': String(2 * MAX_BODY_BYTES) }),
      'admin-api-test',
      { maxContentLengthBytes: MAX_BODY_BYTES },
    )
    assert.equal(oversize?.status, 413)

    // ---- 实际 body 超限：伪造过小的 Content-Length 不能绕过字节上限 ----
    const forged = makeRequest({
      headers: { 'content-length': '10' },
      body: 'x'.repeat(MAX_BODY_BYTES + 1),
    })
    const forgedResult = await readJsonBody(forged, MAX_BODY_BYTES)
    assert.equal(forgedResult.ok, false)
    if (!forgedResult.ok) {
      assert.equal(forgedResult.response.status, 413)
    }

    // 正常大小的合法 JSON 不受上限影响
    const normalResult = await readJsonBody<{ url: string }>(
      makeRequest({
        headers: { 'content-length': '22' },
        body: '{"url":"https://a.com"}',
      }),
      MAX_BODY_BYTES,
    )
    assert.equal(normalResult.ok, true)
    if (normalResult.ok) {
      assert.deepEqual(normalResult.data, { url: 'https://a.com' })
    }

    // ---- 速率限制：同 IP 超出窗口限额后 429，并返回 Retry-After ----
    const rateOptions = { rateLimitPerWindow: 2 }
    const ipA = '203.0.113.10'
    const first = guardAdminRequest(
      authorizedRequest({ 'x-forwarded-for': ipA }),
      RATE_ROUTE_ID,
      rateOptions,
    )
    const second = guardAdminRequest(
      authorizedRequest({ 'x-forwarded-for': ipA }),
      RATE_ROUTE_ID,
      rateOptions,
    )
    assert.equal(first, null)
    assert.equal(second, null)
    const third = guardAdminRequest(
      authorizedRequest({ 'x-forwarded-for': ipA }),
      RATE_ROUTE_ID,
      rateOptions,
    )
    assert.equal(third?.status, 429)
    if (third) {
      const retryAfter = Number(third.headers.get('retry-after'))
      assert.equal(Number.isInteger(retryAfter) && retryAfter >= 1, true)
    }

    // ---- 不同 IP 互相隔离，不共用配额 ----
    const otherIp = guardAdminRequest(
      authorizedRequest({ 'x-forwarded-for': '203.0.113.11' }),
      RATE_ROUTE_ID,
      rateOptions,
    )
    assert.equal(otherIp, null)
  })
}

run().then(
  () => console.log('admin-api tests passed'),
  (error) => {
    console.error(error)
    process.exit(1)
  },
)
