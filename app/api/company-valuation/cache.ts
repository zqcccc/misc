import { getRedis } from '../shorter/redis'

export const COMPANY_VALUATION_CACHE_TTL_SECONDS = 60 * 60 * 24

export type CompanyValuationRedis = {
  get(key: string): Promise<string | null>
  set(key: string, value: string): Promise<unknown>
  expire(key: string, seconds: number): Promise<unknown>
}

export function buildCompanyValuationCacheKey(page: number, pageSize: number) {
  return `company-valuation:v1:page:${page}:size:${pageSize}`
}

export function buildCompanyValuationTotalKey() {
  return 'company-valuation:v1:total'
}

export async function readCompanyValuationCache<T>(
  redis: CompanyValuationRedis,
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

export async function writeCompanyValuationCache(
  redis: CompanyValuationRedis,
  key: string,
  payload: unknown,
  ttlSeconds = COMPANY_VALUATION_CACHE_TTL_SECONDS,
) {
  await redis.set(key, JSON.stringify(payload))
  await redis.expire(key, ttlSeconds)
}

export async function getCompanyValuationRedis(): Promise<CompanyValuationRedis> {
  return getRedis()
}
