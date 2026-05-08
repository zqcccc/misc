import * as assert from 'node:assert/strict'
import {
  PROFIT_LINE_CACHE_TTL_SECONDS,
  buildProfitLineCacheKey,
  readProfitLineCache,
  writeProfitLineCache,
} from '../app/api/profit-line/cache'

class FakeRedis {
  values = new Map<string, string>()
  expires = new Map<string, number>()

  async get(key: string) {
    return this.values.get(key) || null
  }

  async set(key: string, value: string) {
    this.values.set(key, value)
  }

  async expire(key: string, ttl: number) {
    this.expires.set(key, ttl)
  }
}

async function run() {
  assert.equal(buildProfitLineCacheKey(' 00700.hk '), 'profit-line:v2:00700.HK')

  const redis = new FakeRedis()
  const cacheKey = buildProfitLineCacheKey('AAPL')
  const payload = {
    symbol: 'AAPL',
    points: [{ date: '2025-12-31', eps: 1.2 }],
  }

  assert.equal(await readProfitLineCache(redis, cacheKey), null)

  await writeProfitLineCache(redis, cacheKey, payload)

  assert.deepEqual(await readProfitLineCache(redis, cacheKey), payload)
  assert.equal(redis.expires.get(cacheKey), PROFIT_LINE_CACHE_TTL_SECONDS)

  redis.values.set(cacheKey, '{bad json')
  assert.equal(await readProfitLineCache(redis, cacheKey), null)
}

run()
