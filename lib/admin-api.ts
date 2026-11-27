import { createHash, timingSafeEqual } from 'node:crypto'
import { NextResponse } from 'next/server'

// 服务端管理接口防护：Bearer Token 校验（常量时间比较）+ 有界内存速率限制 + 请求体上限。
// 所有拒绝响应均为稳定 JSON，不泄露 token 与内部错误细节。

const TOKEN_ENV_KEY = 'ADMIN_API_TOKEN'
const RATE_WINDOW_MS_DEFAULT = 60_000
// 有界：每进程最多保留这么多「路由+IP」桶，超出时先清过期再逐出最旧窗口
const RATE_BUCKETS_MAX_ENTRIES = 10_000

interface RateBucket {
  count: number
  windowStart: number
}

const globalForAdminApi = globalThis as unknown as {
  __adminApiRateBuckets?: Map<string, RateBucket>
}

const rateBuckets: Map<string, RateBucket> =
  (globalForAdminApi.__adminApiRateBuckets ??= new Map())

export interface AdminGuardOptions {
  /** 请求体 Content-Length 上限（字节），超出返回 413 */
  maxContentLengthBytes?: number
  /** 每个速率窗口内允许的最大请求次数（按路由+IP），不传则不限流 */
  rateLimitPerWindow?: number
  /** 速率窗口毫秒数，默认 60 秒 */
  rateLimitWindowMs?: number
}

function errorResponse(status: number, error: string): NextResponse {
  return NextResponse.json({ success: false, error }, { status })
}

export function getClientIp(request: Request): string {
  const forwarded = request.headers.get('x-forwarded-for')
  if (forwarded) {
    return forwarded.split(',')[0].trim()
  }
  return request.headers.get('x-real-ip')?.trim() || 'unknown'
}

function evictRateBuckets(now: number, windowMs: number): void {
  for (const [key, bucket] of Array.from(rateBuckets)) {
    if (now - bucket.windowStart >= windowMs) {
      rateBuckets.delete(key)
    }
    if (rateBuckets.size < RATE_BUCKETS_MAX_ENTRIES) return
  }
  // 仍满时逐出窗口起点最早的桶，保证内存有界
  let oldestKey: string | null = null
  let oldestStart = Number.POSITIVE_INFINITY
  for (const [key, bucket] of Array.from(rateBuckets)) {
    if (bucket.windowStart < oldestStart) {
      oldestStart = bucket.windowStart
      oldestKey = key
    }
  }
  if (oldestKey !== null) {
    rateBuckets.delete(oldestKey)
  }
}

function hitRateLimit(
  routeId: string,
  ip: string,
  limit: number,
  windowMs: number,
): { allowed: boolean; retryAfterSeconds: number } {
  const now = Date.now()
  const key = `${routeId}:${ip}`
  const bucket = rateBuckets.get(key)

  if (!bucket || now - bucket.windowStart >= windowMs) {
    if (!bucket && rateBuckets.size >= RATE_BUCKETS_MAX_ENTRIES) {
      evictRateBuckets(now, windowMs)
    }
    rateBuckets.set(key, { count: 1, windowStart: now })
    return { allowed: true, retryAfterSeconds: 0 }
  }

  bucket.count += 1
  if (bucket.count > limit) {
    const retryAfterSeconds = Math.ceil(
      (bucket.windowStart + windowMs - now) / 1000,
    )
    return {
      allowed: false,
      retryAfterSeconds: Math.max(1, retryAfterSeconds),
    }
  }
  return { allowed: true, retryAfterSeconds: 0 }
}

type TokenVerdict = 'ok' | 'unauthorized' | 'not-configured'

function verifyAdminToken(request: Request): TokenVerdict {
  const expected = process.env[TOKEN_ENV_KEY]
  if (!expected) {
    // fail-closed：未配置凭证时一律拒绝
    return 'not-configured'
  }

  const header = request.headers.get('authorization') ?? ''
  const match = /^Bearer\s+(\S+)$/i.exec(header.trim())
  if (!match) {
    return 'unauthorized'
  }

  // 先做 sha256 再比较：长度归一（timingSafeEqual 要求等长输入），并抵抗时序侧信道
  const providedHash = createHash('sha256').update(match[1]).digest()
  const expectedHash = createHash('sha256').update(expected).digest()
  return timingSafeEqual(Uint8Array.from(providedHash), Uint8Array.from(expectedHash))
    ? 'ok'
    : 'unauthorized'
}

/**
 * 管理接口统一守卫。返回 NextResponse 表示请求应被拒绝（直接返回该响应），
 * 返回 null 表示校验通过，可继续执行业务逻辑。
 */
export function guardAdminRequest(
  request: Request,
  routeId: string,
  options: AdminGuardOptions = {},
): NextResponse | null {
  const {
    maxContentLengthBytes,
    rateLimitPerWindow,
    rateLimitWindowMs = RATE_WINDOW_MS_DEFAULT,
  } = options

  if (maxContentLengthBytes !== undefined) {
    const contentLength = Number(request.headers.get('content-length') ?? 0)
    if (contentLength > maxContentLengthBytes) {
      return errorResponse(413, '请求体过大')
    }
  }

  if (rateLimitPerWindow !== undefined) {
    const verdict = hitRateLimit(
      routeId,
      getClientIp(request),
      rateLimitPerWindow,
      rateLimitWindowMs,
    )
    if (!verdict.allowed) {
      const response = errorResponse(429, '请求过于频繁，请稍后重试')
      response.headers.set('Retry-After', String(verdict.retryAfterSeconds))
      return response
    }
  }

  const tokenVerdict = verifyAdminToken(request)
  if (tokenVerdict === 'not-configured') {
    return errorResponse(503, '服务未启用：管理员凭证未配置')
  }
  if (tokenVerdict === 'unauthorized') {
    const response = errorResponse(401, '无效凭证')
    response.headers.set('WWW-Authenticate', 'Bearer')
    return response
  }
  return null
}

/**
 * 读取 JSON 请求体并强制字节数上限（不依赖客户端提供的 Content-Length）。
 */
export async function readJsonBody<T>(
  request: Request,
  maxBytes: number,
): Promise<{ ok: true; data: T } | { ok: false; response: NextResponse }> {
  const text = await request.text()
  if (Buffer.byteLength(text, 'utf8') > maxBytes) {
    return { ok: false, response: errorResponse(413, '请求体过大') }
  }
  try {
    return { ok: true, data: JSON.parse(text) as T }
  } catch {
    return { ok: false, response: errorResponse(400, '请求体不是合法 JSON') }
  }
}
