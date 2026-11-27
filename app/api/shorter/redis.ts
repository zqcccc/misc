import { createClient, type RedisClientType } from 'redis'

// 短链 ID 的唯一格式定义（与存量数据一致：5 位小写字母数字）。
// 短链读写路由共用本守卫，杜绝非法 ID 碰到同一 Redis 实例上的其他业务键。
const SHORT_ID_PATTERN = /^[0-9a-z]{5}$/

export const isValidShortId = (id: string) => SHORT_ID_PATTERN.test(id)

export type ShortLinkRedis = RedisClientType

const globalForRedis = globalThis as unknown as {
  redisClient: RedisClientType | undefined
  redisConnection: Promise<RedisClientType> | undefined
  redisConnecting: boolean | undefined
}

export async function getRedis(): Promise<RedisClientType> {
  if (globalForRedis.redisClient?.isOpen) return globalForRedis.redisClient
  if (globalForRedis.redisClient && !globalForRedis.redisConnecting) {
    globalForRedis.redisClient = undefined
    globalForRedis.redisConnection = undefined
  }
  if (!globalForRedis.redisConnection) {
    const client: RedisClientType = createClient({
      url: process.env.REDIS_URL,
      socket: { connectTimeout: 3000, reconnectStrategy: false },
    })
    client.on('error', (err) => console.error('[redis] error:', err))
    globalForRedis.redisClient = client
    globalForRedis.redisConnecting = true
    globalForRedis.redisConnection = client.connect()
      .then(() => {
        globalForRedis.redisConnecting = false
        return client
      })
      .catch(async (error) => {
        globalForRedis.redisClient = undefined
        globalForRedis.redisConnection = undefined
        globalForRedis.redisConnecting = false
        if (client.isOpen) await client.disconnect()
        throw error
      })
  }
  return globalForRedis.redisConnection
}
