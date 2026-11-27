export const PROFIT_LINE_CACHE_TTL_SECONDS = 60 * 60 * 24

export type ProfitLineRedis = {
  get(key: string): Promise<unknown>
  set(key: string, value: string): Promise<unknown>
  expire(key: string, seconds: number): Promise<unknown>
}

export function buildProfitLineCacheKey(symbol: string) {
  // v10: 港股 EPS 币种/汇率失败改为显式报错；作废旧版本里按 1.08 兜底汇率或默认 CNY 折算出的缓存
  return `profit-line:v10:${symbol.trim().toUpperCase()}`
}

export async function readProfitLineCache<T>(
  redis: ProfitLineRedis,
  key: string,
): Promise<T | null> {
  const cached = await redis.get(key)
  if (typeof cached !== 'string' || cached.length === 0) return null

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
