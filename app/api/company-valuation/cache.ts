import { getRedis } from '../shorter/redis'

export type CompanyValuationRedis = {
  keys(pattern: string): Promise<string[]>
  del(keys: string | string[]): Promise<number>
}

export function buildCompanyValuationAllKey() {
  return 'company-valuation:v2:all'
}

export function buildCompanyValuationCachePattern() {
  return 'company-valuation:v2:*'
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
