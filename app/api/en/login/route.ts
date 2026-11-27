// 已下线：原接口向上游签发 Eudic 登录会话 Cookie，存在凭据泄露风险，稳定返回 404。
// 恢复时从 git 历史找回原实现。
export const POST = () => new Response(null, { status: 404 })
