import { NextResponse } from 'next/server'

// 旧版 Chat 的 GPT 代理 API 已下线：向外部服务转发请求与密钥的旧执行路径已删除，
// 统一返回 404。历史实现见仓库历史。
export function POST() {
  return NextResponse.json({ message: 'Not Found' }, { status: 404 })
}
