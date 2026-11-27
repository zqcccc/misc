// 已下线：无仓库内消费者的 Next.js 示例接口，稳定返回 404。
// 恢复时从 git 历史找回原实现。
export const GET = () => new Response(null, { status: 404 })
