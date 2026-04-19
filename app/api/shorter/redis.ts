import { createClient, type RedisClientType } from 'redis'

const globalForRedis = globalThis as unknown as {
  redisClient: RedisClientType | undefined
}

export async function getRedis(): Promise<RedisClientType> {
  if (!globalForRedis.redisClient) {
    const client: RedisClientType = createClient({ url: process.env.REDIS_URL })
    client.on('error', (err) => console.error('[redis] error:', err))
    await client.connect()
    globalForRedis.redisClient = client
    return client
  }
  if (!globalForRedis.redisClient.isOpen) {
    await globalForRedis.redisClient.connect()
  }
  return globalForRedis.redisClient
}
