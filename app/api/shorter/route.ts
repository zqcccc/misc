import { randomBytes } from 'node:crypto'
import { getRedis, isValidShortId, type ShortLinkRedis } from './redis'
import { guardAdminRequest, readJsonBody } from '@/lib/admin-api'

const ID_LENGTH = 5
const ID_ALPHABET = 'abcdefghijklmnopqrstuvwxyz0123456789'
const ID_GENERATION_ATTEMPTS = 5
const MAX_URL_LENGTH = 2048
const MAX_BODY_BYTES = 64 * 1024
const RATE_LIMIT_PER_WINDOW = 10
const STATUS_BAD_REQUEST = 400
const STATUS_CONFLICT = 409
const STATUS_UNAVAILABLE = 503

const generateId = () => {
  const bytes = randomBytes(ID_LENGTH)
  let id = ''
  for (let i = 0; i < ID_LENGTH; i += 1) {
    id += ID_ALPHABET[bytes[i] % ID_ALPHABET.length]
  }
  return id
}

const isValidTargetUrl = (url: string) => {
  if (!url || url.length > MAX_URL_LENGTH) return false
  try {
    const { protocol } = new URL(url)
    return protocol === 'http:' || protocol === 'https:'
  } catch {
    return false
  }
}

// SET NX：键已存在（存量短链或其他业务键）时不覆盖，返回是否写入成功
const setNewKey = async (
  redis: ShortLinkRedis,
  key: string,
  value: string,
  duration: number | null | undefined,
): Promise<boolean> => {
  const result =
    duration && duration > 0
      ? await redis.set(key, value, {
          condition: 'NX',
          expiration: { type: 'EX', value: duration },
        })
      : await redis.set(key, value, { condition: 'NX' })
  return result !== null
}

// 反向键 url -> id 仅在确实归属本短链时更新，已被其他数据占用的键一律不覆盖
const syncReverseKey = async (
  redis: ShortLinkRedis,
  url: string,
  id: string,
  duration: number | null | undefined,
) => {
  const existing = await redis.get(url)
  if (existing === id) {
    if (duration && duration > 0) {
      await redis.expire(url, duration)
    } else {
      await redis.persist(url)
    }
    return
  }
  if (existing !== null) return
  await setNewKey(redis, url, id, duration)
}

export const GET = async (req: Request) => {
  const { searchParams } = new URL(req.url)
  const key = searchParams.get('key')
  const trimmedKey = key?.trim() ?? ''
  if (!isValidShortId(trimmedKey)) {
    return new Response('', { status: STATUS_BAD_REQUEST })
  }
  const redis = await getRedis()
  const url = (await redis.get(trimmedKey)) || ''
  if (searchParams.get('format') === 'json') {
    const ttl = await redis.ttl(trimmedKey)
    return Response.json({ url, ttl })
  }
  return new Response(url)
}

export const POST = async (request: Request) => {
  const denied = guardAdminRequest(request, 'shorter:POST', {
    rateLimitPerWindow: RATE_LIMIT_PER_WINDOW,
  })
  if (denied) return denied

  const bodyResult = await readJsonBody<{
    url?: string
    duration?: number | null
  }>(request, MAX_BODY_BYTES)
  if (!bodyResult.ok) return bodyResult.response
  const url = bodyResult.data.url ?? ''
  const duration = bodyResult.data.duration

  if (!isValidTargetUrl(url)) {
    return Response.json(
      { error: 'url 必须是合法的 http/https 地址' },
      { status: STATUS_BAD_REQUEST },
    )
  }

  const redis = await getRedis()

  // 同一 URL 已有短链时直接复用（反向键 url -> id），保持既有去重行为
  const existingId = await redis.get(url)
  if (existingId && isValidShortId(existingId)) {
    return new Response(existingId)
  }

  // 创建走 SET NX + 有限碰撞重试：生成的 ID 绝不覆盖已有键
  let id: string | null = null
  for (let attempt = 0; attempt < ID_GENERATION_ATTEMPTS; attempt += 1) {
    const candidate = generateId()
    if (await setNewKey(redis, candidate, url, duration)) {
      id = candidate
      break
    }
  }
  if (!id) {
    return Response.json(
      { error: '短链 ID 分配失败，请稍后重试' },
      { status: STATUS_UNAVAILABLE },
    )
  }

  await syncReverseKey(redis, url, id, duration)
  return new Response(id)
}

export const PATCH = async (request: Request) => {
  const denied = guardAdminRequest(request, 'shorter:PATCH', {
    rateLimitPerWindow: RATE_LIMIT_PER_WINDOW,
  })
  if (denied) return denied

  const bodyResult = await readJsonBody<{
    id?: string
    url?: string
    duration?: number | null
  }>(request, MAX_BODY_BYTES)
  if (!bodyResult.ok) return bodyResult.response
  const { id = '', url = '', duration } = bodyResult.data

  if (!isValidShortId(id)) {
    return Response.json(
      { error: 'id 必须是 5 位字母数字短链 ID' },
      { status: STATUS_BAD_REQUEST },
    )
  }
  if (!isValidTargetUrl(url)) {
    return Response.json(
      { error: 'url 必须是合法的 http/https 地址' },
      { status: STATUS_BAD_REQUEST },
    )
  }

  const redis = await getRedis()
  const oldUrl = await redis.get(id)

  if (oldUrl !== null && !isValidTargetUrl(oldUrl)) {
    // 目标键存在但不是短链（可能是其他业务键），拒绝覆盖
    return Response.json(
      { error: '目标 ID 不是短链，拒绝修改' },
      { status: STATUS_CONFLICT },
    )
  }

  if (oldUrl === null) {
    // 新 ID 同样走 NX，避免撞上其他业务键
    const created = await setNewKey(redis, id, url, duration)
    if (!created) {
      return Response.json(
        { error: '目标 ID 已被占用' },
        { status: STATUS_CONFLICT },
      )
    }
  } else {
    if (oldUrl !== url) {
      // 仅当反向键确实指向本短链时才清理，避免误删其他业务键
      const reverseValue = await redis.get(oldUrl)
      if (reverseValue === id) {
        await redis.del(oldUrl)
      }
    }
    if (duration && duration > 0) {
      await redis.set(id, url, { expiration: { type: 'EX', value: duration } })
    } else {
      // 不带 EX 的 SET 会清除 TTL，等效 persist
      await redis.set(id, url)
    }
  }

  await syncReverseKey(redis, url, id, duration)
  return new Response(id)
}
