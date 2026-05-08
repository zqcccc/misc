import { getRedis } from '../shorter/redis'

export const COMPANY_VALUATION_CACHE_TTL_SECONDS = 60 * 60 * 24

export type CompanyValuationRedis = {
  get(key: string): Promise<string | null>
  set(key: string, value: string): Promise<unknown>
  expire(key: string, seconds: number): Promise<unknown>
  keys(pattern: string): Promise<string[]>
  del(keys: string | string[]): Promise<number>
}

export function buildCompanyValuationCacheKey(page: number, pageSize: number, search?: string, quality?: string) {
  const searchPart = search ? `:search:${search.toLowerCase().trim()}` : ''
  const qualityPart = quality && quality !== '全部' ? `:quality:${quality}` : ''
  return `company-valuation:v2:page:${page}:size:${pageSize}${searchPart}${qualityPart}`
}

export function buildCompanyValuationTotalKey(search?: string, quality?: string) {
  const searchPart = search ? `:search:${search.toLowerCase().trim()}` : ''
  const qualityPart = quality && quality !== '全部' ? `:quality:${quality}` : ''
  return `company-valuation:v2:total${searchPart}${qualityPart}`
}

export function buildCompanyValuationAllKey() {
  return 'company-valuation:v2:all'
}

export function buildCompanyValuationCachePattern() {
  return 'company-valuation:v2:*'
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
  return await getRedis() as unknown as CompanyValuationRedis
}

export async function invalidateCompanyValuationCache(
  redis?: CompanyValuationRedis,
) {
  const client = redis || await getCompanyValuationRedis()
  const keys = await client.keys(buildCompanyValuationCachePattern())
  if (keys.length === 0) return 0
  return client.del(keys)
}
