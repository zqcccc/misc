// 已下线：无仓库内消费者的旧 share 读写接口，稳定返回 404。
// share 数据表与 Prisma schema 保持不动，恢复时从 git 历史找回原实现。
const offline = () => new Response(null, { status: 404 })

export const GET = offline
