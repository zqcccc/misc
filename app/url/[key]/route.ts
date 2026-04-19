import { getRedis } from '@/app/api/shorter/redis'

const REDIRECT_STATUS = 302

export const GET = async (
  _req: Request,
  { params }: { params: Promise<{ key: string }> },
) => {
  const { key } = await params
  const redis = await getRedis()
  const target =
    (await redis.get(key.trim())) || process.env.DEFAULT_REDIRECT_URL
  if (!target) {
    return new Response('url not found', { status: 404 })
  }
  return Response.redirect(target, REDIRECT_STATUS)
}
