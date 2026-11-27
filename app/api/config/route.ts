// 已下线：无仓库内消费者的旧配置读写接口，稳定返回 404。
// 恢复时从 git 历史找回原实现。
const offline = () => new Response(null, { status: 404 })

export const GET = offline
export const POST = offline
