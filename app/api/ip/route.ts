// 已下线：唯一消费者 vmess 页面已 404（AdSense 重审前下架），稳定返回 404。
// 恢复 vmess 时从 git 历史找回原实现。
export const POST = () => new Response(null, { status: 404 })
