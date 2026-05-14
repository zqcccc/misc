export const PROFIT_LINE_CACHE_TTL_SECONDS = 60 * 60 * 24

export type ProfitLineRedis = {
  get(key: string): Promise<string | null>
  set(key: string, value: string): Promise<unknown>
  expire(key: string, seconds: number): Promise<unknown>
}

export function buildProfitLineCacheKey(symbol: string) {
  return `profit-line:v9:${symbol.trim().toUpperCase()}`
}

export async function readProfitLineCache<T>(
  redis: ProfitLineRedis,
  key: string,
): Promise<T | null> {
  const cached = await redis.get(key)
  if (!cached) return null

  try {
    return JSON.parse(cached) as T
  } catch {
    return null
  }
}

export async function writeProfitLineCache(
  redis: ProfitLineRedis,
  key: string,
  payload: unknown,
  ttlSeconds = PROFIT_LINE_CACHE_TTL_SECONDS,
) {
  await redis.set(key, JSON.stringify(payload))
  await redis.expire(key, ttlSeconds)
}
