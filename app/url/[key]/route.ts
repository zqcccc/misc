import { getRedis, isValidShortId } from '@/app/api/shorter/redis'

const REDIRECT_STATUS = 302

export const GET = async (
  _req: Request,
  { params }: { params: Promise<{ key: string }> },
) => {
  const { key } = await params
  const id = key.trim()
  // 仅允许 5 位字母数字短链 ID，避免读取同一 Redis 实例上的其他业务键
  if (!isValidShortId(id)) {
    return new Response('url not found', { status: 404 })
  }
  const redis = await getRedis()
  const target =
    (await redis.get(id)) || process.env.DEFAULT_REDIRECT_URL || ''
  // 只跟随 http/https 目标，非短链值一律按未找到处理
  if (!/^https?:\/\//i.test(target)) {
    return new Response('url not found', { status: 404 })
  }
  return Response.redirect(target, REDIRECT_STATUS)
}
