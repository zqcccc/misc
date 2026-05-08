import * as assert from 'node:assert/strict'
import {
  buildCompanyValuationAllKey,
  invalidateCompanyValuationCache,
} from '../app/api/company-valuation/cache'

class FakeRedis {
  values = new Map<string, string>()
  deleted: string[] = []

  async get(key: string) {
    return this.values.get(key) || null
  }

  async set(key: string, value: string) {
    this.values.set(key, value)
  }

  async expire() {}

  async keys(pattern: string) {
    const prefix = pattern.replace('*', '')
    return Array.from(this.values.keys()).filter((key) => key.startsWith(prefix))
  }

  async del(keys: string | string[]) {
    const list = Array.isArray(keys) ? keys : [keys]
    for (const key of list) {
      this.deleted.push(key)
      this.values.delete(key)
    }
    return list.length
  }
}

async function run() {
  const redis = new FakeRedis()
  redis.values.set(buildCompanyValuationAllKey(), '{"entries":[]}')
  redis.values.set('company-valuation:v2:page:1:size:30', '{"entries":[]}')
  redis.values.set('profit-line:v6:AAPL', '{}')

  const deleted = await invalidateCompanyValuationCache(redis)

  assert.equal(deleted, 2)
  assert.deepEqual(redis.deleted.sort(), [
    'company-valuation:v2:all',
    'company-valuation:v2:page:1:size:30',
  ])
  assert.equal(redis.values.has('profit-line:v6:AAPL'), true)
}

run()
