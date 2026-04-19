import { getRedis } from './redis'

const ID_LENGTH = 5
const BASE36_RADIX = 36
const ID_OFFSET = 2
const STATUS_BAD_REQUEST = 400

const generateId = () =>
  Math.random()
    .toString(BASE36_RADIX)
    .slice(ID_OFFSET, ID_OFFSET + ID_LENGTH)

const setWithTtl = async (
  redis: Awaited<ReturnType<typeof getRedis>>,
  key: string,
  value: string,
  ttl?: number | null,
) => {
  await redis.set(key, value)
  if (ttl) {
    await redis.expire(key, ttl)
  } else {
    await redis.persist(key)
  }
}

export const GET = async (req: Request) => {
  const { searchParams } = new URL(req.url)
  const key = searchParams.get('key')
  if (!key) {
    return new Response('', { status: STATUS_BAD_REQUEST })
  }
  const redis = await getRedis()
  const url = (await redis.get(key.trim())) || ''
  return new Response(url)
}

export const POST = async (request: Request) => {
  const { url, duration } = (await request.json()) as {
    url: string
    duration?: number | null
  }
  const redis = await getRedis()
  const existing = await redis.get(url)
  if (existing) {
    return new Response(existing)
  }
  const id = generateId()
  await setWithTtl(redis, id, url, duration)
  await setWithTtl(redis, url, id, duration)
  return new Response(id)
}

export const PATCH = async (request: Request) => {
  const { id, url, duration } = (await request.json()) as {
    id: string
    url: string
    duration?: number | null
  }
  const redis = await getRedis()
  const oldUrl = await redis.get(id)
  if (oldUrl) {
    await redis.del(oldUrl)
  }
  await setWithTtl(redis, id, url, duration)
  await setWithTtl(redis, url, id, duration)
  return new Response(id)
}
