// 已下线：原接口把客户端 Cookie（EudicWebSession）转发到上游，存在凭据泄露风险，稳定返回 404。
// 恢复时从 git 历史找回原实现。
const offline = () => new Response(null, { status: 404 })

export const GET = offline
export const POST = offline
